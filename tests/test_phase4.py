import concurrent.futures,json,multiprocessing,tempfile,unittest,warnings
from pathlib import Path
from unittest.mock import patch
from core import storage,credentials
from core.redaction import redact,register
from memory import memory_manager as mm,config_manager as cm
from actions import background_monitor as bm,reminder as rem

def increment(path,count):
 for _ in range(count):storage.update(path,lambda data:data.__setitem__('n',data.get('n',0)+1))
class Vault:
 def __init__(self):self.values={}
 def set(self,name,value):self.values[name]=value
 def get(self,name):return self.values[name]
class PersistenceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.mp=patch.object(mm,'MEMORY_PATH',self.root/'memory.json');self.mp.start()
  self.cd=patch.object(cm,'CONFIG_DIR',self.root);self.cd.start()
  self.cp=patch.object(cm,'CONFIG_FILE',self.root/'config.json');self.cp.start()
 def tearDown(self):self.cp.stop();self.cd.stop();self.mp.stop();self.tmp.cleanup()
 def test_concurrent_memory_updates(self):
  with concurrent.futures.ThreadPoolExecutor(8) as pool:
   list(pool.map(lambda i:mm.update_memory({'notes':{str(i):{'value':'value'+str(i)}}}),range(80)))
  self.assertEqual(len(mm.load_memory()['notes']),80)
 def test_cross_process_transaction(self):
  p=self.root/'counter.json';storage.write(p,{'n':0})
  processes=[multiprocessing.Process(target=increment,args=(p,20)) for _ in range(3)]
  for x in processes:x.start()
  for x in processes:x.join(10);self.assertEqual(x.exitcode,0)
  self.assertEqual(storage.read(p)['n'],60)
 def test_corrupt_recovery_and_no_silent_reset(self):
  p=self.root/'state.json';storage.write(p,{'old':1});storage.write(p,{'new':2});p.write_text('{broken')
  with warnings.catch_warnings(record=True) as notices:
   self.assertEqual(storage.read(p),{'old':1});self.assertTrue(notices)
  self.assertEqual(len(list(self.root.glob('*.corrupt-*'))),1)
  q=self.root/'bad.json';q.write_text('bad')
  with self.assertRaises(storage.StateCorrupt):storage.update(q,lambda d:d.update(empty=True))
  self.assertEqual(q.read_text(),'bad')
 def test_credential_migration_all_settings_preserved(self):
  vault=Vault();data={'gemini_api_key':'fake-secret-value','assistant_name':'Jarvis','plugin_config':{'fake':{'token':'fake-plugin-secret','host':'example.test'}},'wake_word_enabled':True}
  cm.CONFIG_FILE.write_text(json.dumps(data))
  with patch.object(credentials,'backend',return_value=vault):
   loaded=cm.load_api_keys();self.assertEqual(loaded,data)
   disk=storage.read(cm.CONFIG_FILE);self.assertNotIn('fake-secret-value',json.dumps(disk));self.assertNotIn('fake-plugin-secret',json.dumps(disk))
   self.assertIn('$credential',disk['gemini_api_key']);cm.save_voice('Puck');cm.save_plugin_config('fake',{'token':'new-fake-secret'})
   self.assertEqual(cm.get_gemini_key(),'fake-secret-value');self.assertEqual(cm.get_plugin_setting('fake','token'),'new-fake-secret')
   self.assertTrue(cm.get_wake_word_enabled());self.assertEqual(cm.get_assistant_name(),'Jarvis')
   journal=storage.read(cm.CONFIG_DIR/'credential_migrations.json')
   record=next(iter(journal.values()))
   self.assertEqual(record['status'],'migrated');self.assertEqual(json.loads(vault.get(record['backup'])),data)
 def test_no_secure_backend_preserves_existing_and_refuses_new_keys(self):
  cm.CONFIG_FILE.write_text(json.dumps({'gemini_api_key':'legacy-test-key','other':1}))
  original=cm.CONFIG_FILE.read_bytes()
  with patch.object(credentials,'backend',side_effect=credentials.CredentialUnavailable('locked')),warnings.catch_warnings():
   warnings.simplefilter('ignore');self.assertEqual(cm.get_gemini_key(),'legacy-test-key')
   with self.assertRaises(credentials.CredentialUnavailable):cm.save_api_keys('new-test-key')
  self.assertEqual(cm.CONFIG_FILE.read_bytes(),original)
 def test_secure_backend_write_failure_preserves_config(self):
  cm.CONFIG_FILE.write_text(json.dumps({'setting':1}));v=Vault();v.set=lambda *a: (_ for _ in ()).throw(credentials.CredentialUnavailable('failed'))
  with patch.object(credentials,'backend',return_value=v),self.assertRaises(credentials.CredentialUnavailable):cm.save_api_keys('fake-key')
  self.assertEqual(storage.read(cm.CONFIG_FILE),{'setting':1})
 def test_concurrent_settings(self):
  with patch.object(credentials,'backend',return_value=Vault()),concurrent.futures.ThreadPoolExecutor(8) as pool:
   list(pool.map(lambda i:cm.save_config({str(i):i}),range(40)))
  self.assertEqual(len(cm.load_api_keys()),40)
 def test_unicode_monitors_and_legacy_match(self):
  self.assertNotEqual(bm._slug('हिंदी खबरें'),bm._slug('मौसम'))
  storage.write(mm.MEMORY_PATH,{'monitors':{'':{'topic':'हिंदी खबरें'}}})
  self.assertIn('Already',bm.add_monitor('हिंदी खबरें'));bm.add_monitor('मौसम')
  self.assertEqual(len(bm.list_monitors()),2);bm.remove_monitor('हिंदी खबरें');self.assertEqual(bm.list_monitors(),['मौसम'])
  self.assertFalse(bm._is_blocked('Lincoln history'));self.assertTrue(bm._is_blocked('bitcoin price'))
 def test_concurrent_monitor_updates(self):
  with concurrent.futures.ThreadPoolExecutor(8) as pool:list(pool.map(lambda i:bm.add_monitor('topic '+str(i)),range(20)))
  self.assertEqual(len(bm.list_monitors()),20)
 def test_reminder_unique_same_time_and_scheduler_failure(self):
  scheduled=[]
  def scheduler(dt,name,path,msg):scheduled.append(name);return name
  params={'date':'2099-10-10','time':'12:30','message':'Fake test reminder','timezone':'Asia/Kolkata'}
  with patch.object(rem,'_base_dir',return_value=self.root),patch.object(rem,'_scripts_dir',return_value=self.root),patch.object(rem,'_get_os',return_value='windows'),patch.object(rem,'_schedule_windows',side_effect=scheduler):
   self.assertIn('registered',rem.reminder(params));self.assertIn('registered',rem.reminder(params))
   self.assertEqual(len(set(scheduled)),2)
   # Generated notification scripts are parsed, never run or registered with an actual OS scheduler.
   for p in self.root.glob('*.py'):compile(p.read_text(),str(p),'exec')
   with patch.object(rem,'_schedule_windows',side_effect=RuntimeError('fake denied')):
    self.assertIn('not registered',rem.reminder(params))
  states=storage.read(self.root/'config/reminders.json');self.assertEqual(sorted(r['status'] for r in states.values()),['failed','registered','registered'])
 def test_timezone_and_dst(self):
  self.assertEqual(str(rem._parse_time('2099-01-01','10:00','Asia/Kolkata').utcoffset()),'5:30:00')
  with self.assertRaises(ValueError):rem._parse_time('2026-11-01','01:30','America/New_York')
 def test_redaction(self):
  register('fake-private-api-key');self.assertNotIn('fake-private-api-key',redact('key=fake-private-api-key'))
  self.assertNotIn('secret-token',redact('Bearer secret-token'))
