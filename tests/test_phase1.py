import json,sys,tempfile,threading,time,unittest,zipfile,tarfile,io
from pathlib import Path
from unittest.mock import patch
from core import path_policy as pp,safe_files as sf,undo,confirm
from core.execution import run_trusted,run_generated,parse_command,propose_dependencies
from core.archives import extract_bounded
from actions import dev_agent,desktop,code_helper
class FileSafety(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.scopes=patch.object(pp,'_scopes',[(self.root,True)]);self.scopes.start()
  self.recovery=patch.object(sf,'RECOVERY',self.root/'recover');self.recovery.start();undo.clear()
 def tearDown(self):self.recovery.stop();self.scopes.stop();self.tmp.cleanup()
 def test_generated_traversal(self):
  for name in ['../escape','/tmp/escape','C:\\escape','a/../../escape','a\\..\\escape','x:stream','NUL.txt','a.']:
   with self.subTest(name=name),self.assertRaises((ValueError,PermissionError)):pp.project_path(self.root,name)
 def test_symlink(self):
  outside=self.root.parent/'outside';(self.root/'link').symlink_to(outside)
  with self.assertRaises(PermissionError):pp.validate(self.root/'link'/'file')
 def test_selected_file_not_parent(self):
  with patch.object(pp,'_scopes',[]):
   f=self.root/'selected';f.write_text('data');pp.grant(f)
   self.assertEqual(pp.validate(f),f)
   with self.assertRaises(PermissionError):pp.validate(self.root/'other')
 def test_sensitive(self):
  with self.assertRaises(PermissionError):pp.validate(self.root/'.env')
 def test_large_write_and_undo(self):
  p=self.root/'large';p.write_bytes(b'a'*1_100_000);sf.write(p,'replacement');undo.undo_last()
  self.assertEqual(p.read_bytes(),b'a'*1_100_000)
 def test_backup_failure_aborts(self):
  p=self.root/'file';p.write_text('old')
  with patch.object(sf,'snapshot',side_effect=OSError('disk full')),self.assertRaises(OSError):sf.write(p,'new')
  self.assertEqual(p.read_text(),'old')
 def test_move_undo_conflict(self):
  p=self.root/'a';q=self.root/'b';p.write_text('a');sf.move(p,q);q.write_text('new');result=undo.undo_last()
  self.assertIn('Could not undo',result);self.assertEqual(q.read_text(),'new');self.assertFalse(p.exists())
 def test_archive_traversal_and_links(self):
  for name in ['../escape','/escape','C:/escape','a/../../escape']:
   z=self.root/'input.zip'
   with zipfile.ZipFile(z,'w') as f:f.writestr(name,'bad')
   with self.assertRaises((ValueError,PermissionError)):extract_bounded(z,self.root/'output')
   self.assertFalse((self.root/'output').exists())
  t=self.root/'input.tar'
  with tarfile.open(t,'w') as f:
   i=tarfile.TarInfo('link');i.type=tarfile.SYMTYPE;i.linkname='../escape';f.addfile(i)
  with self.assertRaises(ValueError):extract_bounded(t,self.root/'output')
 def test_archive_normal_and_collision(self):
  z=self.root/'input.zip'
  with zipfile.ZipFile(z,'w') as f:f.writestr('a/b.txt','hello')
  extract_bounded(z,self.root/'output');self.assertEqual((self.root/'output/a/b.txt').read_text(),'hello')
  with self.assertRaises(FileExistsError):extract_bounded(z,self.root/'output')
 def test_archive_size_limit(self):
  z=self.root/'input.zip'
  with zipfile.ZipFile(z,'w') as f:f.writestr('data','x'*100)
  with patch('core.archives.MAX_TOTAL',50),self.assertRaises(ValueError):extract_bounded(z,self.root/'output')
 def test_desktop_does_not_exec(self):
  p=self.root/'victim';p.write_text('keep')
  r=desktop._execute_generated_code(f"Path({str(p)!r}).unlink()")
  self.assertIn('rejected',r);self.assertEqual(p.read_text(),'keep')
 def test_desktop_typed_action(self):
  r=desktop._execute_generated_code(json.dumps({'action':'file_controller','parameters':{'action':'create_file','path':str(self.root),'name':'typed','content':'ok'}}))
  self.assertIn('created',r);self.assertEqual((self.root/'typed').read_text(),'ok')
 def test_unavailable_runner_never_host_fallback(self):
  p=self.root/'main.py';p.write_text('raise SystemExit(7)')
  with patch.dict('os.environ',{'JARVIS_RUNNER_IMAGE':''}):r=code_helper._run_file(p,[],1)
  self.assertEqual(r.status,'unavailable');self.assertFalse(r.succeeded)
 def test_dependencies_do_not_install(self):
  with patch('subprocess.Popen') as popen:
   r=propose_dependencies(['requests'],self.root)
   self.assertIn('unavailable',r);popen.assert_not_called()
 def test_dependency_order(self):
  f=[{'path':'main.py','imports':['a']},{'path':'a.py','imports':['b']},{'path':'b.py','imports':[]}]
  self.assertEqual([x['path'] for x in dev_agent._dependency_order(f)],['b.py','a.py','main.py'])
class ExecutionTruth(unittest.TestCase):
 def test_failed_exit(self):
  r=run_trusted([sys.executable,'-c','raise SystemExit(7)']);self.assertEqual(r.exit_code,7);self.assertFalse(r.succeeded)
 def test_timeout(self):
  r=run_trusted([sys.executable,'-c','import time;time.sleep(3)'],timeout=.1);self.assertTrue(r.timed_out);self.assertFalse(r.succeeded)
 def test_cancel(self):
  event=threading.Event();threading.Timer(.1,event.set).start()
  r=run_trusted([sys.executable,'-c','import time;time.sleep(3)'],cancel=event);self.assertTrue(r.cancelled)
 def test_success_not_verified(self):
  r=run_trusted([sys.executable,'-c','print("ok")']);self.assertTrue(r.succeeded);self.assertFalse(r.verified);self.assertIn('ok',r.stdout)
 def test_quoted_command(self):self.assertEqual(parse_command('python "file name.py" "hello world"'),['python','file name.py','hello world'])
 def test_confirmation_not_replaced(self):
  with patch.object(confirm,'_pending',None),patch.object(confirm,'_show_cb',lambda *a:None):
   confirm.request('a','First','detail',lambda:'a');r=confirm.request('b','Second','detail',lambda:'b')
   self.assertIn('BUSY',r);self.assertEqual(confirm.pending_title(),'First')
