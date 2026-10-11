"""Real SDK/security checks and explicitly mocked runtime/transport regressions."""
import asyncio
import base64
import hashlib
import hmac
import io
import logging
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from core.credential_input import InvalidCredential, validate_gemini_key, plausible
from core.live_config import compatible_config, compatible_declarations, probe_stages
from core.provider_errors import classify

DUMMY_KEY = 'AIza' + 'DUMMY_ONLY_'*3
MODEL = 'models/gemini-3.1-flash-live-preview'

class CredentialTests(unittest.TestCase):
    def test_negative_inputs_do_not_echo_secret(self):
        for value in [None, 2, '', 'curl -H "x-goog-api-key: '+DUMMY_KEY+'"',
                      '{"key":"'+DUMMY_KEY+'"}', 'Bearer '+DUMMY_KEY,
                      'x-goog-api-key: '+DUMMY_KEY, DUMMY_KEY+'\n', DUMMY_KEY+'\r\nheader',
                      DUMMY_KEY+'\x00', 'AIza'+'a'*300, 'x'*40, DUMMY_KEY+' secret']:
            with self.subTest(value=type(value).__name__), self.assertRaises(InvalidCredential) as caught:
                validate_gemini_key(value)
            self.assertNotIn(DUMMY_KEY, str(caught.exception))
        self.assertEqual(validate_gemini_key(' '+DUMMY_KEY+' '), DUMMY_KEY)
        self.assertTrue(plausible(DUMMY_KEY));self.assertFalse(plausible('curl '+DUMMY_KEY))

    def test_invalid_save_never_touches_vault_or_config(self):
        from memory import config_manager as cm
        with patch('core.credentials.backend') as backend:
            with self.assertRaises(InvalidCredential):cm.save_config({'gemini_api_key':'curl '+DUMMY_KEY})
            backend.assert_not_called()

    def test_stream_and_sdk_logger_redaction(self):
        from core.redaction import install, redact, RedactedStream
        install()
        buf=io.StringIO();stream=RedactedStream(buf)
        stream.write('x-goog-api-key: '+DUMMY_KEY+' ?token=DUMMY_BEARER_123456789')
        self.assertNotIn(DUMMY_KEY, buf.getvalue());self.assertNotIn('DUMMY_BEARER',buf.getvalue())
        handler=logging.StreamHandler(buf);logger=logging.getLogger('google.genai.round2_test')
        logger.addHandler(handler);logger.setLevel(logging.ERROR)
        try:
            try:raise RuntimeError(DUMMY_KEY)
            except RuntimeError:logger.exception('Handshake %s', DUMMY_KEY)
        finally:logger.removeHandler(handler)
        self.assertNotIn(DUMMY_KEY,buf.getvalue())
        self.assertNotIn('DUMMY_QUERY_KEY',redact('/?key=DUMMY_QUERY_KEY'))

class ConfigurationTests(unittest.TestCase):
    def test_31_model_capabilities_actual_sdk(self):
        from google.genai import types
        cfg=compatible_config({'response_modalities':['AUDIO'],
             'proactivity':{'proactive_audio':True},'enable_affective_dialog':True,
             'thinking_config':{'thinking_budget':-1},
             'tools':[{'function_declarations':[{'name':'safe_tool','description':'Test',
                       'behavior':'NON_BLOCKING','parameters':{'type':'OBJECT','properties':{}}}]}]}, MODEL)
        data=cfg.model_dump(mode='json',exclude_none=True)
        self.assertNotIn('proactivity',data);self.assertNotIn('enable_affective_dialog',data)
        self.assertEqual(data['thinking_config']['thinking_level'],'LOW')
        self.assertNotIn('thinking_budget',data['thinking_config'])
        self.assertNotIn('behavior',data['tools'][0]['function_declarations'][0])
        self.assertIsInstance(cfg, types.LiveConnectConfig)

    def test_isolate_only_invalid_declarations(self):
        logs=[]
        decls=compatible_declarations([{'name':'good','parameters':{'type':'OBJECT'}},
                 {'name':'bad','parameters':{'type':'NOT_A_TYPE'}},
                 {'name':'good','parameters':{'type':'OBJECT'}}],MODEL,logs.append)
        self.assertEqual([d['name'] for d in decls],['good']);self.assertEqual(len(logs),2)

    def test_probe_sequence_keeps_effective_config(self):
        cfg=compatible_config({'response_modalities':['AUDIO'],'speech_config':{'voice_config':{'prebuilt_voice_config':{'voice_name':'Puck'}}},
                             'input_audio_transcription':{},'system_instruction':'Test persona',
                             'tools':[{'function_declarations':[{'name':'test'}]}],
                             'session_resumption':{},'context_window_compression':{'sliding_window':{}},
                             'thinking_config':{'thinking_budget':-1}},MODEL)
        stages=list(probe_stages(cfg))
        self.assertEqual(set(stages[0][1].model_dump(exclude_none=True)),{'response_modalities'})
        self.assertEqual(stages[-1][1],cfg)

    def test_unknown_model_does_not_invent_optional_support(self):
        cfg=compatible_config({'response_modalities':['AUDIO'],'proactivity':{'proactive_audio':True},'thinking_config':{'thinking_budget':-1}},'custom-account-model')
        self.assertIsNone(cfg.proactivity);self.assertIsNone(cfg.thinking_config)

    def test_malformed_header_and_policy_classification(self):
        from websockets.exceptions import InvalidHeaderValue
        failure=classify(InvalidHeaderValue('x-goog-api-key','curl '+DUMMY_KEY))
        self.assertEqual(failure.kind,'CREDENTIAL_FORMAT');self.assertFalse(failure.retryable)
        self.assertEqual(classify(InvalidCredential('bad')).kind,'CREDENTIAL_FORMAT')
        payload=RuntimeError();payload.close_code=1007
        self.assertEqual(classify(ExceptionGroup('task',[payload])).kind,'CONFIG')

class HandoffTests(unittest.TestCase):
    def test_input_enumeration_does_not_open_or_capture(self):
        import sys
        from core import audio_devices
        sd=Mock()
        sd.query_devices.return_value=[{'name':'Test microphone','max_input_channels':1,'max_output_channels':0,'hostapi':0}]
        sd.query_hostapis.return_value=[{'name':'Windows DirectSound'}]
        with patch.dict(sys.modules,{'sounddevice':sd}),patch('platform.system',return_value='Windows'),patch.object(audio_devices,'_usable') as opened,patch.object(audio_devices,'_transport_works') as capture:
            result=audio_devices._query()
        self.assertEqual(result['input'],['Test microphone'])
        opened.assert_not_called();capture.assert_not_called()

    def test_callback_is_bounded_copies_and_counts_overflows(self):
        import numpy as np
        from core.audio_handoff import AudioHandoff
        loop=Mock();received=[];handoff=AudioHandoff(loop,lambda frame,context:received.append((frame.tolist(),context)),capacity=3)
        frame=np.array([0],dtype=np.int16)
        for i in range(10):frame[0]=i;handoff.offer(frame,True,overflow=(i==1))
        self.assertEqual(loop.call_soon_threadsafe.call_count,1)
        self.assertEqual(handoff.dropped,7);self.assertEqual(handoff.overflows,1)
        self.assertEqual(received,[])
        handoff.drain();self.assertEqual([x[0] for x in received],[[7],[8],[9]])
        handoff.close();handoff.offer(frame,False);handoff.drain();self.assertEqual(len(received),3)

class ProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_setup_ack_required_mocked_transport(self):
        from tools.live_probe import probe
        client=Mock();client.aio.models.get=AsyncMock()
        setups=[]
        class Context:
            def __init__(self,config):self.config=config
            async def __aenter__(self):
                if self.config.input_audio_transcription is not None:
                    e=RuntimeError();e.close_code=1007;raise e
                return SimpleNamespace(setup_complete=object())
            async def __aexit__(self,*args):return False
        def connect(**kwargs):setups.append(kwargs['config']);return Context(kwargs['config'])
        client.aio.live.connect.side_effect=connect
        cfg=compatible_config({'response_modalities':['AUDIO'],'input_audio_transcription':{},'system_instruction':'Test'},MODEL)
        rows=await probe(client,MODEL,cfg)
        self.assertEqual([row['status'] for row in rows],['PASS','PASS','FAIL','SKIPPED'])
        self.assertIn('CONFIG',rows[2]['detail']);self.assertEqual(len(setups),2)

    async def test_invalid_auth_waits_for_explicit_retry_even_when_config_ready(self):
        from main import JarvisLive
        from google.genai.errors import ClientError
        ui=Mock();ui.muted=False;ui._win._ready=True
        with patch('main.get_push_to_talk_enabled',return_value=False),patch('main.get_wake_word_enabled',return_value=False):app=JarvisLive(ui)
        app._build_config=Mock(return_value={})
        client=Mock();client.aio.aclose=AsyncMock()
        class Context:
            async def __aenter__(self):raise ClientError(401,{'error':{'message':'Test invalid key'}})
            async def __aexit__(self,*args):return False
        client.aio.live.connect.return_value=Context()
        with patch('main.sd',None),patch('main.audio_devices.prefetch'),patch('main._get_api_key',return_value=DUMMY_KEY),patch('main.genai.Client',return_value=client) as create,patch('dashboard.server.DashboardServer',side_effect=ImportError()):
            task=asyncio.create_task(app.run())
            await asyncio.sleep(.3)
            self.assertEqual(create.call_count,1)
            self.assertIsNone(app.session)
            self.assertFalse(app.runtime.provider)
            app.request_shutdown();await asyncio.wait_for(task,2)
        self.assertTrue(all(t.done() for t in app._lifetime))

    async def test_sdk_audio_and_transcript_parts_are_processed_once(self):
        from main import JarvisLive
        from google.genai import types
        ui=Mock();ui.muted=False
        with patch('main.get_push_to_talk_enabled',return_value=False),patch('main.get_wake_word_enabled',return_value=False):app=JarvisLive(ui)
        app._asst_name='Jarvis';app._turn_done_event=asyncio.Event();app.audio_in_queue=asyncio.Queue(maxsize=20)
        responses=[types.LiveServerMessage(server_content=types.LiveServerContent(output_transcription=types.Transcription(text=text))) for text in ['ha','ha',' hello',' world!']]
        responses.append(types.LiveServerMessage(server_content=types.LiveServerContent(turn_complete=True,model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(data=b'\x01\x00',mime_type='audio/pcm;rate=24000')),types.Part(inline_data=types.Blob(data=b'\x02\x00',mime_type='audio/pcm;rate=24000'))]))))
        class Session:
            async def receive(self):
                for response in responses:yield response
                await asyncio.Future()
        app.session=Session()
        task=asyncio.create_task(app._receive_audio());await asyncio.sleep(0)
        task.cancel();await asyncio.gather(task,return_exceptions=True)
        self.assertIn('Jarvis: haha hello world!',app._session_log)
        self.assertEqual(app.audio_in_queue.get_nowait(),b'\x01\x00\x02\x00')
        self.assertTrue(app.audio_in_queue.empty())

class PTTInterruptionTests(unittest.TestCase):
    def test_explicit_ptt_press_interrupts_current_playback(self):
        from main import JarvisLive
        import threading
        app=JarvisLive.__new__(JarvisLive)
        app._ptt_held=False;app._is_speaking=True;app.interrupt=Mock()
        app._capture_enabled=threading.Event();app._awake=True;app.runtime=Mock()
        app._on_ptt(True)
        app.interrupt.assert_called_once()
        self.assertTrue(app._capture_enabled.is_set())
        self.assertTrue(app._ptt_held)

class DashboardProtocolTests(unittest.TestCase):
    def setUp(self):
        from dashboard.server import DashboardServer
        from fastapi.testclient import TestClient
        self.server=DashboardServer();self.client=TestClient(self.server.app);self.client.__enter__()
        key=self.server.new_key();result=self.client.post('/login',json={'pin':key}).json()
        self.token=result['token'];self.headers={'Authorization':'Bearer '+self.token}
    def tearDown(self):self.client.__exit__(None,None,None)

    def ticket(self,scope):
        response=self.client.post('/api/socket-ticket',headers=self.headers,json={'scope':scope})
        self.assertEqual(response.status_code,200);return response.json()['ticket']

    def test_socket_ticket_single_use_scope_and_no_bearer_query(self):
        from starlette.websockets import WebSocketDisconnect
        ticket=self.ticket('events')
        with self.client.websocket_connect('/ws?ticket='+ticket) as ws:
            ws.send_json({'type':'command','text':'test command'})
        for url in ['/ws?ticket='+ticket,'/ws?token='+self.token,'/ws?ticket='+self.ticket('audio')]:
            with self.assertRaises(WebSocketDisconnect):
                with self.client.websocket_connect(url):pass

    def envelope(self,text,seq=1):
        from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
        from cryptography.hazmat.primitives import padding
        from dashboard.server import _derive_key
        pad=padding.PKCS7(128).padder();data=pad.update(text.encode())+pad.finalize()
        iv=b'DUMMY_IV_16BYTES';self.assertEqual(len(iv),16)
        enc=Cipher(algorithms.AES(_derive_key(self.token)),modes.CBC(iv)).encryptor()
        payload=base64.b64encode(iv+enc.update(data)+enc.finalize()).decode()
        key=hashlib.sha256((self.token+'JARVIS-DASHBOARD-MAC-v2').encode()).digest()
        mac=hmac.new(key,(str(seq)+'.'+payload).encode(),hashlib.sha256).hexdigest()
        return f'v2:{seq}:{payload}:{mac}'

    def test_authenticated_envelope_tamper_replay_and_legacy_rejected(self):
        envelope=self.envelope('test command')
        self.assertEqual(self.client.post('/api/command',headers=self.headers,json={'enc':envelope}).status_code,200)
        self.assertEqual(self.server._command_queue.get_nowait(),'test command')
        for changed in [envelope,envelope[:-1]+('0' if envelope[-1]!='0' else '1'),'legacy-unsigned-cbc']:
            self.assertEqual(self.client.post('/api/command',headers=self.headers,json={'enc':changed}).status_code,400)
        self.assertTrue(self.server._command_queue.empty())

    def test_download_bearer_header_and_no_query_authorization(self):
        with tempfile.TemporaryDirectory() as scratch:
            self.server._uploads_dir=Path(scratch);(Path(scratch)/'test.txt').write_text('test')
            with patch('core.path_policy._scopes',[(Path(scratch),True)]):
                self.assertEqual(self.client.get('/uploads/test.txt?token='+self.token).status_code,401)
                response=self.client.get('/uploads/test.txt',headers=self.headers)
                self.assertEqual(response.status_code,200);self.assertEqual(response.text,'test')

    def test_phone_pcm_alignment_and_rate(self):
        from starlette.websockets import WebSocketDisconnect
        with self.client.websocket_connect('/ws/phone-audio?ticket='+self.ticket('audio')) as ws:
            ws.send_bytes(b'\x01\x00'*100)
            ws.send_bytes(b'odd')
            with self.assertRaises(WebSocketDisconnect):ws.receive_bytes()
        frame=self.server._phone_audio_queue.get_nowait()
        self.assertEqual(frame['mime_type'],'audio/pcm;rate=16000')
        self.assertTrue(self.server._phone_audio_queue.empty())

class WakeTests(unittest.TestCase):
    def test_inference_failure_marks_detector_not_running(self):
        import numpy as np
        from core.wake_word import WakeWordDetector
        detector=WakeWordDetector(Mock(),logger=Mock(),notify=Mock())
        detector._model=Mock();detector._model.predict.side_effect=RuntimeError('Test inference failure')
        detector._running=True;detector._ready=True
        for _ in range(3):detector._queue.put_nowait(np.zeros(1280,dtype=np.int16))
        detector._loop()
        self.assertFalse(detector.ready);self.assertFalse(detector._running)
        self.assertEqual(detector.error,'RuntimeError')

    def test_ready_resources_do_not_claim_detector_active(self):
        from main import JarvisLive
        app=JarvisLive.__new__(JarvisLive);app._wake_detector=None;app._wake_enabled=True;app._awake=False
        app.ui=Mock();app.ui.muted=False;app.runtime=Mock()
        with patch('main.wake_is_ready',return_value=True),patch('core.wake_word.is_installed',return_value=True):
            state=app._wake_state()
        self.assertEqual(state['status'],'READY');self.assertFalse(state['running'])

class ProactiveTests(unittest.TestCase):
    def test_opt_in_mute_sleep_speaking_and_quiet_hours(self):
        from main import JarvisLive
        app=JarvisLive.__new__(JarvisLive);app.ui=Mock();app.ui.muted=False
        app.session=object();app._awake=True;app._is_speaking=False
        with patch('memory.config_manager.load_api_keys',return_value={}),patch('main.datetime') as now:
            now.now.return_value.hour=12
            self.assertFalse(app._proactive_allowed('proactive_checkins_enabled'))
        cfg={'proactive_checkins_enabled':True,'quiet_hours':[22,8]}
        with patch('memory.config_manager.load_api_keys',return_value=cfg),patch('main.datetime') as now:
            now.now.return_value.hour=12
            self.assertTrue(app._proactive_allowed('proactive_checkins_enabled'))
            app.ui.muted=True;self.assertFalse(app._proactive_allowed('proactive_checkins_enabled'))
            app.ui.muted=False;app._awake=False;self.assertFalse(app._proactive_allowed('proactive_checkins_enabled'))
            app._awake=True;app._is_speaking=True;self.assertFalse(app._proactive_allowed('proactive_checkins_enabled'))
            app._is_speaking=False;now.now.return_value.hour=23;self.assertFalse(app._proactive_allowed('proactive_checkins_enabled'))

if __name__=='__main__':unittest.main()
