"""Integration regressions; fake model/browser transports never call paid accounts."""
import asyncio
import importlib.util
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch
from core import path_policy as pp, safe_files as sf, plugin_trust, plugin_loader, undo
from core.documents import analyze_chunks
from core.action_loader import ActionRegistry, ActionRecord, discover_actions
from core.validation import validate_arguments
from core.tasks import TaskManager
from actions import file_processor as fp, browser_control as bc, computer_settings as cs, open_app as oa

class Integrations(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.patches=[patch.object(pp,'_scopes',[(self.root,True)]),patch.object(pp,'DEFAULT_WORKSPACE',self.root),
                      patch.object(sf,'RECOVERY',self.root/'recovery'),patch.object(plugin_trust,'TRUST_FILE',self.root/'trust.json')]
        for p in self.patches:p.start()
        undo.clear()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        sys.modules.pop('plugins.probe',None)
        self.tmp.cleanup()
    def model(self):return Mock(generate_content=Mock(return_value=NS(text='Grounded only in the supplied excerpt.')))
    def test_chunk_coverage_and_source_references(self):
        model=self.model();result=analyze_chunks('x'*60000,'summarize','source.txt',model)
        self.assertIn('48000/60000',result);self.assertIn('PARTIAL',result)
        self.assertIn('[source.txt: chars 36001-48000]',result);self.assertEqual(model.generate_content.call_count,4)
        self.assertIn('untrusted DATA',model.generate_content.call_args.args[0])
    def test_code_analysis_and_generation_no_undefined_prompt(self):
        p=self.root/'code.py';p.write_text('print("hello")')
        with patch.object(fp,'_gemini_client',return_value=self.model()):
            result=fp._process_code(p,'explain',{})
        self.assertIn('Coverage:',result);self.assertNotIn('failed',result)
        model=Mock(generate_content=Mock(return_value=NS(text='```python\nprint("fixed")\n```')))
        with patch.object(fp,'_gemini_client',return_value=model):
            result=fp._process_code(p,'fix',{'save':True})
        self.assertIn('Saved:',result)
        self.assertEqual(p.read_text(),'print("hello")')
        generated=list((self.root/'Processed').rglob('*.py'));self.assertEqual(len(generated),1)
        self.assertIn('fixed',generated[0].read_text())
    def test_large_code_never_saves_partial_fix(self):
        p=self.root/'big.py';p.write_text('x'*48001)
        with patch.object(fp,'_gemini_client') as cloud:
            result=fp._process_code(p,'fix',{'save':True})
        cloud.assert_not_called();self.assertIn('no partial code patch',result)
    def test_xml_correct_dispatch_and_entity_attack(self):
        p=self.root/'data.xml';p.write_text('<root><child>value</child></root>')
        result=fp.file_processor({'file_path':str(p),'action':'validate'})
        self.assertIn('XML valid',result);self.assertIn('elements: 2',result)
        p.write_text('<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><root>&xxe;</root>')
        result=fp.file_processor({'file_path':str(p),'action':'validate'})
        self.assertIn('EntitiesForbidden',result);self.assertNotIn('root:x:',result)
    def test_output_selected_file_does_not_grant_parent(self):
        outside=self.root/'selected-dir';outside.mkdir();p=outside/'file.txt';p.write_text('hello')
        with patch.object(pp,'_scopes',[(self.root/'Processed',True)]):
            pp.grant(p)
            output=fp._output_path(p,'review','.txt')
            self.assertTrue(output.is_relative_to(self.root/'Processed'))
            with self.assertRaises(PermissionError):pp.validate(outside/'other.txt')
    def test_plugin_trust_prevents_import_then_helper_change_revokes(self):
        folder=self.root/'plugins';folder.mkdir();sentinel=self.root/'import-effect'
        p=folder/'probe.py';p.write_text(f'from pathlib import Path\nPath({str(sentinel)!r}).write_text("imported")\nPLUGIN={{"name":"probe","description":"Test fixture","parameters":{{"type":"OBJECT","properties":{{}}}}}}\ndef run(parameters):return "done"\n')
        helper=folder/'_helper.py';helper.write_text('VALUE=1\n')
        reg=plugin_loader.discover_plugins(folder,set(),logger=lambda x:None)
        self.assertFalse(sentinel.exists());self.assertFalse(reg.has('probe'))
        plugin_trust.approve(p)
        reg=plugin_loader.discover_plugins(folder,set(),logger=lambda x:None)
        self.assertTrue(sentinel.exists());self.assertTrue(reg.has('probe'))
        sentinel.unlink();helper.write_text('VALUE=2\n')
        reg=plugin_loader.discover_plugins(folder,set(),logger=lambda x:None)
        self.assertFalse(sentinel.exists());self.assertFalse(reg.has('probe'))
    def test_argument_validation_before_effects(self):
        fn=Mock(return_value='done')
        schema={'type':'OBJECT','properties':{'count':{'type':'INTEGER'}},'required':['count']}
        reg=ActionRegistry({'probe':ActionRecord('probe',parameters=schema,handler=fn,valid=True)},lambda x:None)
        for args in ({'count':True},{'count':'1'},{'count':1,'unexpected':'value'},{}):
            self.assertIn('failed',reg.run('probe',args));fn.assert_not_called()
        self.assertEqual(reg.run('probe',{'count':1}),'done');fn.assert_called_once()
        validate_arguments({'action':'fill_form','fields':{'#name':'value'}},bc.TOOL['parameters'])
        with self.assertRaises(ValueError):validate_arguments({'action':'fill_form','fields':{'#name':False}},bc.TOOL['parameters'])
    def test_os_setting_undo_preserves_new_setting(self):
        value={'n':40};setter=lambda n:value.update(n=n)
        guarded=cs._guarded_setting_undo(lambda:value['n'],setter,20,40)
        value['n']=50
        with self.assertRaises(RuntimeError):guarded()
        self.assertEqual(value['n'],50)
        value['n']=40;guarded();self.assertEqual(value['n'],20)
    def test_windows_application_name_not_shell_command(self):
        with patch.object(oa.subprocess,'Popen') as process:
            for command in ['notepad & calc','a\nb','powershell:evil','a|b']:
                with self.assertRaises(ValueError):oa._launch_windows(command)
            process.assert_not_called()
        with patch.object(oa.shutil,'which',return_value='/opt/system/notepad.exe'),patch.object(oa.subprocess,'Popen') as process:
            self.assertTrue(oa._launch_windows('notepad'))
            self.assertEqual(process.call_args.args[0],['/opt/system/notepad.exe']);self.assertFalse(process.call_args.kwargs['shell'])
    def test_workspace_executables_not_launched_through_app_tool(self):
        executable=self.root/'generated.exe';executable.write_bytes(b'disposable-not-an-executable')
        with patch.object(oa.shutil,'which',return_value=str(executable)),patch.object(oa.subprocess,'Popen') as process:
            with self.assertRaises(ValueError):oa._launch_windows('generated')
            process.assert_not_called()
        self.assertIn('isolated runner',oa.open_app({'app_name':str(executable)}))

    def test_runtime_installer_never_runs_pip(self):
        from core import installer
        with patch('subprocess.run') as process:
            self.assertFalse(installer._pip('unreviewed-distribution'))
            installer.install_for_config({'stt_engine':'whisper'},lambda x:None)
            process.assert_not_called()
    def test_setup_cwd_independent_and_venv_required(self):
        spec=importlib.util.spec_from_file_location('marklv_setup',Path('setup.py').resolve());setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)
        with patch.object(sys,'prefix','/env'),patch.object(sys,'base_prefix','/base'),patch.object(setup.subprocess,'run') as run:
            setup.main(['--extras','browser'])
            paths=[call.args[0][-1] for call in run.call_args_list]
            self.assertTrue(all(Path(p).is_absolute() and Path(p).is_file() for p in paths))
        with patch.object(sys,'prefix','/base'),patch.object(sys,'base_prefix','/base'),patch.object(setup.subprocess,'run') as run:
            with self.assertRaises(SystemExit):setup.main([])
            run.assert_not_called()
    def test_isolated_runner_command_and_no_host_fallback(self):
        from core import execution
        p=self.root/'project';p.mkdir();(p/'main.py').write_text('raise SystemExit(7)')
        image='reviewed/image@sha256:'+'a'*64
        calls=[]
        def runner(argv,**kwargs):
            calls.append(argv)
            mount=argv[argv.index('--mount')+1]
            stage=Path(mount.split('src=')[1].split(',dst=')[0])
            self.assertEqual((stage/'main.py').read_text(),'raise SystemExit(7)')
            self.assertNotEqual(stage,p)
            return execution.ExecutionResult('failed',7)
        with patch.object(execution,'_image',return_value=(image,'')),patch.object(execution,'run_trusted',side_effect=runner):
            result=execution.run_generated(['python','main.py'],p)
        self.assertFalse(result.succeeded);self.assertEqual(len(calls),1)
        argv=calls[0]
        for flag in ['--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--pull=never','--user=65534:65534']:
            self.assertIn(flag,argv)
        self.assertIn('readonly',argv[argv.index('--mount')+1])
        (p/'.env.local').write_text('fake-secret')
        with patch.object(execution,'run_trusted') as process:
            self.assertEqual(execution.run_generated(['python','main.py'],p).status,'failed')
            process.assert_not_called()
    def test_native_typing_cancellation_stops_following_chunks(self):
        from core.native import cancellable_type
        from core.tasks import _CANCEL,TaskCancelled
        event=threading.Event();calls=[]
        def typed(text,**kwargs):calls.append(text);event.set()
        keyboard=NS(typewrite=typed)
        token=_CANCEL.set(event)
        try:
            with self.assertRaises(TaskCancelled):cancellable_type('private '*20,keyboard=keyboard)
        finally:_CANCEL.reset(token)
        self.assertEqual(len(calls),1);self.assertEqual(len(calls[0]),16)

    def test_write_preparation_preserves_concurrent_editor_change(self):
        p=self.root/'edited.txt';p.write_text('before')
        original=sf.snapshot
        def during_snapshot(path):
            folder=original(path);p.write_text('newer editor change');return folder
        with patch.object(sf,'snapshot',side_effect=during_snapshot),self.assertRaises(sf.UndoConflict):sf.write(p,'assistant change')
        self.assertEqual(p.read_text(),'newer editor change')
    def test_copy_source_change_does_not_publish_partial_or_stale_file(self):
        p=self.root/'source';p.write_text('before');dest=self.root/'destination'
        copy=sf.shutil.copyfileobj
        def during_copy(source,output,**kwargs):
            copy(source,output,**kwargs);p.write_text('newer source edit')
        with patch.object(sf.shutil,'copyfileobj',side_effect=during_copy),self.assertRaises(sf.UndoConflict):sf.copy(p,dest)
        self.assertFalse(dest.exists());self.assertEqual(p.read_text(),'newer source edit')

    def test_screenshot_path_never_falls_back_outside_scope_or_overwrites(self):
        import io
        from PIL import Image
        from actions import computer_control as cc
        with self.assertRaises(PermissionError):cc._safe_screenshot_path(str(self.root.parent/'not-granted.png'))
        self.assertTrue(cc._safe_screenshot_path(None).is_relative_to(self.root))
        p=self.root/'existing.png';p.write_bytes(b'preserve')
        fake=NS(screenshot=lambda:Image.new('RGB',(2,2)))
        with patch.object(cc,'_PYAUTOGUI',True),patch.object(cc,'pyautogui',fake,create=True),self.assertRaises(FileExistsError):
            cc._screenshot(str(p))
        self.assertEqual(p.read_bytes(),b'preserve')
    def test_protected_root_link_and_home_ancestor(self):
        outside=self.root/'target';outside.mkdir();link=self.root/'linked'
        try:link.symlink_to(outside,target_is_directory=True)
        except OSError as e:
            if getattr(e,'winerror',None)==1314:self.skipTest('Windows symlink creation privilege unavailable; root-link check unrun')
            raise
        with self.assertRaises(PermissionError):pp.project_path(link,'file.txt')
        with self.assertRaises(PermissionError):pp.grant(Path.home().parent,directory=True)
    def test_desktop_failed_exit_not_reported_as_wallpaper_success(self):
        from actions import desktop
        from core import execution
        with patch.object(execution,'run_trusted',return_value=execution.ExecutionResult('failed',7,stderr='mock failure')):
            with self.assertRaises(RuntimeError):desktop._checked_process(['gsettings','mock'])

    def test_text_analysis_uses_chunking(self):
        p=self.root/'doc.txt';p.write_text('source '*10000)
        with patch.object(fp,'_gemini_client',return_value=self.model()):
            result=fp._process_text_doc(p,'text','summarize',{'save':False})
        self.assertIn('PARTIAL',result);self.assertIn('doc.txt: chars',result)
    def test_confirm_cancellation_waiting_for_mutation_slot(self):
        from core import confirm
        from core.tasks import _CANCEL
        done=threading.Event();effect=Mock();event=threading.Event()
        with patch.object(confirm,'_pending',None),patch.object(confirm,'_show_cb',lambda *a:None),patch.object(confirm,'_hide_cb',lambda:None),patch.object(confirm,'_log_cb',lambda msg:done.set() if 'failed' in msg or 'cancelled' in msg else None):
            token=_CANCEL.set(event)
            try:confirm.request('test','Review','Full body',effect)
            finally:_CANCEL.reset(token)
            with sf.LOCK:
                confirm.resolve(True)
                confirm.cancel_pending()
            self.assertTrue(done.wait(2));effect.assert_not_called()

    def test_real_sdk_declarations_and_rest_routing(self):
        from google.genai import types
        from core import gemini
        reg=discover_actions(Path('actions'),logger=lambda x:None)
        self.assertGreaterEqual(len(reg.names()),18)
        for declaration in reg.get_tool_declarations():types.FunctionDeclaration(**declaration)
        cloud=Mock();cloud.models.generate_content.return_value=NS(text='ok')
        with patch.object(gemini,'client',return_value=cloud),patch.object(gemini,'_live_call') as audio:
            self.assertEqual(gemini.text('prompt',key='fake-review-only'), 'ok')
            audio.assert_not_called();self.assertEqual(cloud.models.generate_content.call_args.kwargs['model'],gemini._TEXT_MODEL)

class BrowserAndTasks(unittest.IsolatedAsyncioTestCase):
    async def test_browser_value_checks_and_profile_disclosure(self):
        sess=bc._BrowserSession('chrome');element=NS(clear=AsyncMock(),type=AsyncMock(),input_value=AsyncMock(return_value='wrong'))
        element.first=element
        page=NS(locator=Mock(return_value=element),url='https://example.test/page')
        sess._get_page=AsyncMock(return_value=page);sess._page=page;sess._profile_path='disposable-profile';sess._profile_fallback=True
        self.assertIn('mismatch',await sess.type_text('#name','expected'))
        element.input_value.return_value='expected';self.assertIn('verified',await sess.type_text('#name','expected'))
        self.assertIn('SEPARATE AUTOMATION PROFILE',sess.describe_context());self.assertIn('https://example.test/page',sess.describe_context())
        page.wait_for_url=AsyncMock(side_effect=RuntimeError('not reached'))
        self.assertIn('NOT verified',await sess.verify_expected(url='https://different.test'))
    async def test_unsafe_browser_urls(self):
        for url in ['file:///tmp/private','javascript:alert(1)','https://user:password@example.test','data:text/html,test']:
            with self.assertRaises(ValueError):bc._normalize_url(url)
        self.assertEqual(bc._normalize_url('example.test'),'https://example.test')
    async def test_cancel_queue_even_if_history_evicted(self):
        gate=asyncio.Event();started=asyncio.Event()
        async def execute(call):started.set();await gate.wait();return call.name
        manager=TaskManager(execute,max_pending=1)
        first=manager.submit(NS(id='1',name='first'),0);await started.wait()
        queued=manager.submit(NS(id='2',name='second'),0)
        for i in range(110):manager.submit(NS(id=str(i+3),name='reject'),0)
        self.assertNotIn(queued,list(manager.history));manager.cancel_all()
        self.assertEqual((await queued.future).status,'cancelled');self.assertTrue(manager.queue.empty())
        gate.set();await first.future;await manager.close()
