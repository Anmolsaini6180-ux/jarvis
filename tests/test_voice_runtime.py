"""Voice control regressions. Fake SDK/audio tests are explicitly mocked."""
import asyncio
import socket
import threading
import unittest
from unittest.mock import Mock
from core.runtime_state import RuntimeState,State
from core.provider_errors import classify,retry_delay

class StateTests(unittest.TestCase):
    def test_startup_and_failure_priority(self):
        publish=Mock();r=RuntimeState(publish)
        self.assertFalse(r.transition('SPEAKING'))
        self.assertTrue(r.transition('INITIALIZING'))
        r.transition('LISTENING');self.assertEqual(r.state,State.PROVIDER_UNAVAILABLE)
        r.provider=True;r.mic=False;r.transition('LISTENING')
        self.assertEqual(r.state,State.MIC_UNAVAILABLE)
        r.mic=True
        for state in ['LISTENING','HEARING SPEECH','PROCESSING','SPEAKING','SLEEPING','LISTENING','STOPPED']:
            self.assertTrue(r.transition(state))
        self.assertFalse(r.transition('LISTENING'))
    def test_thread_safe_publication(self):
        observed=[];r=RuntimeState(observed.append);r.transition('INITIALIZING');r.provider=True
        def interact():
            for _ in range(100):r.transition('LISTENING');r.transition('PROCESSING')
        threads=[threading.Thread(target=interact) for _ in range(8)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(r.state.value,observed[-1])

class ProviderTests(unittest.TestCase):
    def test_real_sdk_objects_mocked_responses(self):
        from google.genai.errors import ClientError
        auth=ClientError(400,{'error':{'code':400,'message':'API key not valid. Please pass a valid API key.','status':'INVALID_ARGUMENT'}})
        failure=classify(ExceptionGroup('task',[auth]))
        self.assertEqual(failure.kind,'AUTH');self.assertFalse(failure.retryable)
        config=ClientError(400,{'error':{'code':400,'message':'Unsupported config','status':'INVALID_ARGUMENT'}})
        self.assertEqual(classify(config).kind,'CONFIG')
        self.assertEqual(classify(ClientError(403,{'error':{'message':'denied'}})).kind,'FORBIDDEN')
        self.assertTrue(classify(ClientError(429,{'error':{'message':'quota'}})).retryable)
    def test_dns_and_payload(self):
        self.assertEqual(classify(socket.gaierror()).kind,'DNS')
        payload=RuntimeError();payload.close_code=1007
        self.assertEqual(classify(payload).kind,'CONFIG')
    def test_backoff_bounds(self):
        delays=[retry_delay(n,lambda:1) for n in range(1,9)]
        self.assertEqual(delays,[3,6,12,24,48,60,60,60])

class PipelineTests(unittest.IsolatedAsyncioTestCase):
    def make_runtime(self):
        from main import JarvisLive
        app=JarvisLive.__new__(JarvisLive)
        app.ui=Mock();app.ui.muted=False
        app.runtime=RuntimeState(app.ui.set_state)
        app.runtime.transition('INITIALIZING');app.runtime.provider=True;app.runtime.mic=True
        app._input_generation=0;app._turn_done_event=asyncio.Event();app._loop=asyncio.get_running_loop();app._deliveries=set()
        app.session=Mock();app.out_queue=asyncio.Queue(maxsize=20)
        app._wake_enabled=True;app._awake=False
        app._capture_enabled=threading.Event();app._ptt_held=False;app._last_user_speech=0
        return app
    async def test_ptt_release_finalizes_after_pcm_mocked(self):
        from unittest.mock import AsyncMock
        app=self.make_runtime()
        app.session.send_realtime_input=AsyncMock()
        await app.out_queue.put({'data':b'\x01\x00'*1024,'mime_type':'audio/pcm;rate=16000'})
        app._on_ptt(True);self.assertTrue(app._awake)
        app._on_ptt(False)
        await asyncio.sleep(0);await asyncio.sleep(0)
        self.assertEqual(app.runtime.state,State.PROCESSING)
        task=asyncio.create_task(app._send_realtime())
        await asyncio.sleep(0)
        calls=app.session.send_realtime_input.call_args_list
        self.assertIn('audio',calls[0].kwargs)
        self.assertEqual(calls[1].kwargs,{'audio_stream_end':True})
        task.cancel()
        await asyncio.gather(task,return_exceptions=True)
    async def test_manual_activation_independent_of_wake(self):
        app=self.make_runtime();app._wake_enabled=False
        app.start_listening();self.assertTrue(app._manual_listening)
        self.assertEqual(app.runtime.state,State.LISTENING)
        app.stop_listening();self.assertFalse(app._awake)
        await asyncio.sleep(0);await asyncio.sleep(0)
    async def test_optional_failure_isolated(self):
        app=self.make_runtime()
        async def broken():raise RuntimeError('optional failure')
        await app._optional(broken)
        self.assertIsNotNone(app.session)
        app.ui.write_log.assert_called()
    async def test_stop_aborts_output_and_cancels_queue_mocked(self):
        app=self.make_runtime()
        app._speech_generation=0;app._tasks=Mock();app._output_stream=Mock();app.audio_in_queue=asyncio.Queue()
        app._visemes=Mock();app._turn_done_event=asyncio.Event()
        app._speaking_lock=threading.Lock();app._out_latency=.2
        app._deliveries=set();app._is_speaking=True
        await app.audio_in_queue.put(b'audio');await app.out_queue.put({'data':b'old'})
        app.interrupt()
        app._output_stream.abort.assert_called_once()
        self.assertTrue(app.audio_in_queue.empty());self.assertTrue(app.out_queue.empty())
        self.assertFalse(app._is_speaking)
        from google.genai import types
        response=await app._execute_tool(types.FunctionCall(name='stop_response',args={},id='stop-test'))
        self.assertIn('remains running',response.response['result'])
        self.assertFalse(getattr(app,'_shutdown_requested',False))

class RunLoopTests(unittest.IsolatedAsyncioTestCase):
    async def run_failure(self,error):
        from unittest.mock import patch,AsyncMock
        import main
        from main import JarvisLive
        ui=Mock();ui.muted=False;ui._win._ready=False
        with patch('main.get_push_to_talk_enabled',return_value=False),patch('main.get_wake_word_enabled',return_value=False):
            app=JarvisLive(ui)
        app._build_config=Mock(return_value={})
        def log(message):
            if 'Automatic retries stopped' in message:app.request_shutdown()
        ui.write_log.side_effect=log
        class Context:
            async def __aenter__(self):raise error
            async def __aexit__(self,*unused):pass
        client=Mock();client.aio.live.connect=Mock(return_value=Context());client.aio.aclose=AsyncMock()
        with patch('main.sd',None),patch('main.audio_devices.prefetch'),patch('main._get_api_key',return_value='AIza'+'DUMMY_'*5),patch('main.genai.Client',return_value=client) as create,patch('core.provider_errors.retry_delay',return_value=.001),patch('dashboard.server.DashboardServer',side_effect=ImportError('not installed')):
            await asyncio.wait_for(app.run(),timeout=3)
        self.assertEqual(app.runtime.state,State.STOPPED)
        self.assertTrue(all(task.done() for task in app._lifetime))
        return create.call_count
    async def test_invalid_auth_no_retry_and_cleanup_mocked(self):
        from google.genai.errors import ClientError
        count=await self.run_failure(ClientError(400,{'error':{'message':'API key not valid','code':400}}))
        self.assertEqual(count,1)
    async def test_network_retry_cap_and_cleanup_mocked(self):
        count=await self.run_failure(TimeoutError())
        self.assertEqual(count,6)

class LocalCommandTests(unittest.TestCase):
    def test_exact_commands_and_no_untrusted_shell_dispatch(self):
        from core.local_commands import route
        self.assertEqual(route('Jarvis, open Notepad.'),('open_app',{'app_name':'notepad'}))
        self.assertEqual(route('Chrome kholo'),('open_app',{'app_name':'chrome'}))
        self.assertEqual(route('what time is it?')[0],'time')
        self.assertIsNone(route('open notepad & calc'))
        self.assertIsNone(route('delete all my files'))
        self.assertEqual(route('Jarvis, stop.'),('stop',{}))

class AudioWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_microphone_failure_does_not_cancel_provider_mocked(self):
        from main import JarvisLive
        from unittest.mock import patch,AsyncMock
        app=JarvisLive.__new__(JarvisLive)
        app._shutdown_requested=False;app.ui=Mock();app.session=object()
        original=app.session;app.runtime=RuntimeState(app.ui.set_state)
        app.runtime.transition('INITIALIZING');app.runtime.provider=True
        calls=[]
        async def mic():
            calls.append(1)
            if len(calls)==2:app._shutdown_requested=True
            raise RuntimeError('device lost')
        with patch('main.asyncio.sleep',new=AsyncMock()):await app._audio_worker(mic,'Microphone')
        self.assertEqual(len(calls),2);self.assertIs(app.session,original)
        self.assertEqual(app.runtime.state,State.MIC_UNAVAILABLE)

    async def test_callback_frames_reach_live_queue_mocked(self):
        import main
        import numpy as np
        from unittest.mock import patch
        ui=Mock();ui.muted=False
        with patch('main.get_push_to_talk_enabled',return_value=False),patch('main.get_wake_word_enabled',return_value=False):app=main.JarvisLive(ui)
        app._capture_enabled.set();app._awake=True;app._shutdown_requested=False
        app.runtime.provider=True;app.session=Mock();app.out_queue=asyncio.Queue(maxsize=20)
        fake_sd=Mock();fake_sd.query_devices.return_value={'name':'Mock microphone'}
        callbacks=[]
        class Input:
            device=None
            def __init__(self,**kw):callbacks.append(kw)
            def __enter__(self):
                callbacks[0]['callback'](np.full((1024,1),1000,dtype=np.int16),1024,None,None)
                asyncio.get_running_loop().call_soon(setattr,app,'_shutdown_requested',True)
                return self
            def __exit__(self,*unused):pass
        fake_sd.InputStream=Input
        with patch('main.sd',fake_sd),patch('main.audio_devices.resolve',return_value=None),patch('main.audio_devices.stream_settings',return_value=None):
            await app._listen_audio()
            await asyncio.sleep(0)
        self.assertEqual(app._mic_frames,1024)
        self.assertTrue(app.runtime.mic)
        frame=app.out_queue.get_nowait()
        self.assertEqual(len(frame['data']),2048)
        self.assertEqual(frame['mime_type'],'audio/pcm;rate=16000')
        self.assertEqual(callbacks[0]['channels'],1)
        self.assertEqual(callbacks[0]['samplerate'],16000)

class WakeSetupTests(unittest.TestCase):
    def test_atomic_verified_resources_and_preserved_user_data_mocked(self):
        import tempfile,types,sys
        from pathlib import Path
        from unittest.mock import patch,MagicMock
        import core.wake_word as wake
        package=types.ModuleType('openwakeword')
        package.FEATURE_MODELS={name:{'download_url':'https://example.test/'+name+'.tflite'} for name in ['melspectrogram','embedding_model']}
        package.MODELS={'hey_jarvis':{'download_url':'https://example.test/hey_jarvis_v0.1.tflite'}}
        response=MagicMock();response.__enter__.return_value=response
        response.iter_content.return_value=[b'verified-test-data'*100]
        runtime=types.ModuleType('onnxruntime');runtime.InferenceSession=Mock()
        with tempfile.TemporaryDirectory() as temporary:
            target=Path(temporary)/'models';target.mkdir()
            sentinel=target/'user-owned.txt';sentinel.write_text('keep')
            with patch.dict(sys.modules,{'openwakeword':package,'onnxruntime':runtime}),patch.object(wake,'model_directory',return_value=target),patch.object(wake,'is_installed',return_value=True),patch('requests.get',return_value=response) as download:
                ok,message=wake.install_and_download()
                self.assertTrue(ok,message)
                self.assertEqual(download.call_count,3)
                self.assertEqual(runtime.InferenceSession.call_count,3)
                self.assertEqual(sentinel.read_text(),'keep')
                self.assertTrue(wake.is_ready())
                ok,_=wake.install_and_download()
                self.assertTrue(ok);self.assertEqual(download.call_count,3)
    def test_single_flight_and_no_runtime_pip(self):
        from unittest.mock import patch
        import core.wake_word as wake
        wake._setup_lock.acquire()
        try:
            ok,message=wake.install_and_download()
            self.assertFalse(ok);self.assertIn('progress',message)
        finally:wake._setup_lock.release()
        with patch.object(wake,'is_installed',return_value=False),patch('subprocess.run') as process:
            ok,message=wake.install_and_download()
            self.assertFalse(ok);process.assert_not_called()
            self.assertIn('setup.py --extras wake',message)

class SDKTransportTests(unittest.TestCase):
    def test_live_sdk_close_codes_and_structured_auth(self):
        from google.genai.errors import APIError
        self.assertEqual(classify(APIError(1007,'invalid payload')).kind,'CONFIG')
        self.assertEqual(classify(APIError(1007,'API key not valid. Please pass a valid API key.')).kind,'AUTH')
        self.assertEqual(classify(APIError(1011,'internal failure')).kind,'NETWORK')
        self.assertFalse(classify(APIError(1008,'policy restriction')).retryable)
        self.assertEqual(classify(APIError(400,{'error':{'message':'rejected','details':[{'reason':'API_KEY_INVALID'}]}})).kind,'AUTH')
    def test_httpx_network_and_tls_causes(self):
        import httpx,ssl
        self.assertTrue(classify(httpx.ConnectError('connection failed')).retryable)
        self.assertEqual(classify(httpx.ReadTimeout('timeout')).kind,'TIMEOUT')
        transport=httpx.ConnectError('tls failed');transport.__cause__=ssl.SSLError('certificate')
        self.assertEqual(classify(transport).kind,'TLS')

class HandshakeTests(unittest.IsolatedAsyncioTestCase):
    async def test_deadline_applies_only_to_handshake(self):
        from core.provider_errors import connect_with_timeout
        client=Mock();closed=[]
        class Manager:
            async def __aenter__(self):return Mock(setup_complete=object())
            async def __aexit__(self,*args):closed.append(args)
        client.aio.live.connect.return_value=Manager()
        async with connect_with_timeout(client,'model',{},seconds=.01):
            await asyncio.sleep(.02)
        self.assertEqual(len(closed),1)
    async def test_missing_setup_ack_does_not_report_connected(self):
        from core.provider_errors import connect_with_timeout,LiveSetupRejected
        client=Mock();closed=[]
        class Manager:
            async def __aenter__(self):return Mock(setup_complete=None)
            async def __aexit__(self,*args):closed.append(args)
        client.aio.live.connect.return_value=Manager()
        with self.assertRaises(LiveSetupRejected):
            async with connect_with_timeout(client,'model',{}):self.fail('must not yield')
        self.assertEqual(len(closed),1)
    async def test_hung_handshake_times_out(self):
        from core.provider_errors import connect_with_timeout
        client=Mock()
        class Manager:
            async def __aenter__(self):await asyncio.Event().wait()
            async def __aexit__(self,*unused):pass
        client.aio.live.connect.return_value=Manager()
        with self.assertRaises(TimeoutError):
            async with connect_with_timeout(client,'model',{},seconds=.01):self.fail('must not yield')
