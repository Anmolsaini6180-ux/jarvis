import asyncio,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from fastapi.testclient import TestClient
from dashboard.server import DashboardServer
from core import confirm
from actions import send_message as msg
class DashboardSecurity(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.server=DashboardServer();self.server._uploads_dir=Path(self.tmp.name)
  self.scope=patch('core.path_policy._scopes',[(Path(self.tmp.name),True)]);self.scope.start()
  self.client=TestClient(self.server.app);self.client.__enter__()
 def tearDown(self):self.client.__exit__(None,None,None);self.scope.stop();self.tmp.cleanup()
 def login(self):
  key=self.server.new_key();r=self.client.post('/login',json={'pin':key});self.assertEqual(r.status_code,200)
  tok=r.json()['token'];return tok,{'Authorization':'Bearer '+tok}
 def test_malformed_login_command_and_websocket(self):
  for body in ([],{'device_token':2},{'device_token':'x'*257}):
   self.assertEqual(self.client.post('/api/device-login',json=body).status_code,400)
  tok,h=self.login()
  self.assertEqual(self.client.post('/api/command',headers=h,content=b'{bad').status_code,400)
  self.assertEqual(self.client.post('/api/command',headers=h,json={'enc':12}).status_code,400)
  from starlette.websockets import WebSocketDisconnect
  with self.client.websocket_connect('/ws?token='+tok) as ws:
   ws.send_json([])
   with self.assertRaises(WebSocketDisconnect):
    for _ in range(10):ws.receive_json()
  self.assertTrue(self.server._command_queue.empty())
 def test_unauthorized(self):self.assertEqual(self.client.post('/api/command',json={'text':'x'}).status_code,401)
 def test_revoked_http(self):
  tok,h=self.login();self.assertEqual(self.client.post('/api/revoke-devices',headers=h).status_code,200)
  self.assertEqual(self.client.post('/api/command',headers=h,json={'text':'x'}).status_code,401)
 def test_expired_http(self):
  tok,h=self.login();self.server._token_expiry[tok]=0
  self.assertEqual(self.client.get('/api/files',headers=h).status_code,401)
 def test_invalid_pairing_rate(self):
  codes=[self.client.post('/login',json={'pin':'WRONG'}).status_code for _ in range(11)]
  self.assertEqual(codes[:10],[401]*10);self.assertEqual(codes[-1],429)
 def test_logout(self):
  tok,h=self.login();self.assertEqual(self.client.post('/api/logout',headers=h).status_code,200)
  self.assertNotIn(tok,self.server._tokens)
 def test_command_queue_and_size(self):
  tok,h=self.login()
  self.assertEqual(self.client.post('/api/command',headers=h,json={'text':'x'*4097}).status_code,413)
  for i in range(32):self.assertEqual(self.client.post('/api/command',headers=h,json={'text':'x'}).status_code,200)
  self.assertEqual(self.client.post('/api/command',headers=h,json={'text':'x'}).status_code,429)
 def test_preparse_body_limit(self):
  tok,h=self.login();self.assertEqual(self.client.post('/api/command',headers=h,content=b'x'*66000).status_code,413)
 def test_upload_limit(self):
  tok,h=self.login()
  with patch('dashboard.server.MAX_UPLOAD_MB',0):
   r=self.client.post('/api/upload',headers=h,files={'file':('a.txt',b'data')})
  self.assertEqual(r.status_code,413);self.assertFalse(list(Path(self.tmp.name).iterdir()))
 def test_websocket_expiry_and_revocation(self):
  tok,h=self.login()
  with self.client.websocket_connect('/ws?token='+tok) as ws:
   self.server._token_expiry[tok]=0
   # No command is accepted after expiry, even if socket has not yet timed out.
   ws.send_json({'type':'command','text':'fake'})
   from starlette.websockets import WebSocketDisconnect
   with self.assertRaises(WebSocketDisconnect):
    while True:ws.receive_json()
  self.assertTrue(self.server._command_queue.empty())
  tok,h=self.login()
  with self.client.websocket_connect('/ws?token='+tok) as ws:
   self.client.post('/api/revoke-devices',headers=h)
   with self.assertRaises(WebSocketDisconnect):
    while True:ws.receive_json()
 def test_tls_fail_closed(self):
  self.server._active=True
  with patch('dashboard.server._ensure_certs',return_value=False),patch('dashboard.server.uvicorn.Server') as start:
   asyncio.run(self.server.serve());start.assert_not_called();self.assertFalse(self.server._active)
class MessagingSafety(unittest.TestCase):
 def test_missing_driver_usable_draft(self):
  with patch.object(msg,'_ADAPTERS',{}):r=msg.send_message({'receiver':'Fake recipient','message_text':'Test only','platform':'whatsapp'})
  self.assertIn('SEND_UNAVAILABLE',r);self.assertIn('Test only',r)
 def test_verified_recipient_confirm_and_state(self):
  adapter=Mock();adapter.resolve.return_value=msg.Recipient('fake:1','Fake recipient',True)
  adapter.verify.return_value=True;adapter.send.return_value=msg.SendState('accepted','fake receipt')
  with patch.object(msg,'_ADAPTERS',{'fake':adapter}),patch.object(confirm,'_pending',None),patch.object(confirm,'_show_cb',lambda *a:None):
   result=msg.send_message({'receiver':'Fake recipient','message_text':'test','platform':'fake'})
   adapter.send.assert_not_called();self.assertIn('PENDING',result)
   pending=confirm._pending;self.assertIn('fake:1',pending.detail)
   self.assertIn('ACCEPTED',pending.run());adapter.send.assert_called_once()
 def test_identity_changed_prevents_send(self):
  adapter=Mock();adapter.resolve.return_value=msg.Recipient('fake:1','Fake',True);adapter.verify.return_value=False
  with patch.object(msg,'_ADAPTERS',{'fake':adapter}),patch.object(confirm,'_pending',None),patch.object(confirm,'_show_cb',lambda *a:None):
   msg.send_message({'receiver':'Fake','message_text':'test','platform':'fake'})
   self.assertIn('nothing sent',confirm._pending.run());adapter.send.assert_not_called()

class BroadcastBounds(unittest.IsolatedAsyncioTestCase):
 async def test_inactive_history_and_slow_client_bounds(self):
  from unittest.mock import AsyncMock
  server=DashboardServer()
  await server.broadcast({'type':'log','text':'private inactive text'})
  self.assertEqual(server._history,[])
  server.new_key();server._issue('fake-token')
  gate=asyncio.Event()
  async def slow(message):await gate.wait()
  ws=Mock();ws.send_json=AsyncMock(side_effect=slow);ws.close=AsyncMock()
  server._clients.add(ws);server._ws_tokens[ws]='fake-token'
  workers=[asyncio.create_task(server.broadcast({'type':'log','text':'x'*10000})) for _ in range(40)]
  await asyncio.sleep(.02)
  self.assertEqual(server._broadcast_inflight,16);self.assertEqual(len(server._history),16)
  self.assertTrue(all(len(m['text'])<4200 for m in server._history))
  gate.set();await asyncio.gather(*workers)
  self.assertEqual(server._broadcast_inflight,0)
