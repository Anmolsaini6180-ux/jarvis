"""Opt-in voice checks; no microphone uploads and no mocked hardware PASS."""
from pathlib import Path
import argparse
import importlib
import json
import platform
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from core.redaction import install
install()

def diagnose(args):
    rows=[]
    def add(check,status,detail):rows.append(dict(check=check,status=status,detail=detail))
    add('Python version','PASS' if sys.version_info>=(3,11) else 'FAIL',platform.python_version())
    add('OS compatibility','PASS' if platform.system()=='Windows' else 'SKIPPED','Full acceptance requires Windows 10/11; host='+platform.system())
    for module in ['numpy','sounddevice','PyQt6','google.genai']:
        try:importlib.import_module(module);add('Dependency '+module,'PASS','Imported actual installed module')
        except Exception as e:add('Dependency '+module,'FAIL',type(e).__name__)
    try:
        from memory.config_manager import get_gemini_key,get_input_device,get_output_device
        add('Credential presence','PASS' if get_gemini_key() else 'FAIL','Presence only; does not establish authentication')
    except Exception as e:add('Credential presence','FAIL',type(e).__name__)
    sd=None
    try:
        import sounddevice as sd
        devices=sd.query_devices()
        for direction in ['input','output']:
            names=[d['name'] for d in devices if d['max_'+direction+'_channels']>0]
            add(direction+' device enumeration','PASS' if names else 'FAIL',', '.join(names) or 'No devices detected')
    except Exception as e:
        add('input device enumeration','FAIL',type(e).__name__)
        add('output device enumeration','FAIL',type(e).__name__)
    for check in ['Microphone frame capture','Audio format compatibility']:
        add(check,'SKIPPED','Select --mic-test SECONDS for a local capture; no audio retained or uploaded')
    if args.mic_test:
        try:
            import numpy as np
            from core import audio_devices
            dev=audio_devices.resolve(get_input_device(),'input')
            captured=[0,0.0]
            def callback(data,frames,*unused):
                captured[0]+=frames
                captured[1]=max(captured[1],float(np.max(np.abs(data.astype(np.float32)))))
            if sd is None:raise RuntimeError('PortAudio unavailable')
            with sd.InputStream(device=dev,samplerate=16000,channels=1,dtype='int16',blocksize=1024,callback=callback):
                time.sleep(min(30,max(1,args.mic_test)))
            for row in rows:
                if row['check']=='Microphone frame capture':
                    row.update(status='PASS' if captured[0] and captured[1]>0 else 'FAIL',detail=f'Actual frames={captured[0]}, peak={captured[1]}; speech identity needs human verification')
                if row['check']=='Audio format compatibility':row.update(status='PASS' if captured[0] else 'FAIL',detail='Actual 16 kHz mono int16 capture')
        except Exception as e:
            for row in rows:
                if row['check'] in {'Microphone frame capture','Audio format compatibility'}:row.update(status='FAIL',detail=type(e).__name__)
    from core.wake_word import is_installed,is_ready,WakeWordDetector,model_directory
    add('Wake package import','PASS' if is_installed() else 'FAIL','Optional openWakeWord 0.6.0')
    add('Wake model resources','PASS' if is_ready() else 'FAIL',str(model_directory())+'; supported phrase: Hey Jarvis')
    add('Wake engine initialization','SKIPPED','Use --wake-test; no audio recorded by this check')
    if args.wake_test:
        detector=WakeWordDetector(lambda:None)
        ok=detector.start();detector.stop()
        rows[-1].update(status='PASS' if ok else 'FAIL',detail='Actual initialization/cleanup only; wake detection requires speech on Windows')
    add('STT initialization','SKIPPED','STT is Gemini Live; needs configured provider and end-to-end speech test')
    add('TTS synthesis','SKIPPED','Use --tts-test to select local Windows SAPI diagnostic')
    add('Audio playback','SKIPPED','Use --tts-test; audible success needs human confirmation')
    if args.tts_test:
        try:
            from core.local_voice import synthesize
            pcm,rate=synthesize('Jarvis local voice diagnostic. Can you hear me?')
            rows[-2].update(status='PASS',detail=f'Actual SAPI generated {len(pcm)} PCM bytes')
            if sd is None:raise RuntimeError('PortAudio unavailable')
            from core import audio_devices
            dev=audio_devices.resolve(get_output_device(),'output')
            import numpy as np
            x=np.frombuffer(pcm,dtype=np.int16)
            count=round(len(x)*24000/rate)
            pcm=np.interp(np.arange(count)*rate/24000,np.arange(len(x)),x).astype(np.int16).tobytes()
            with sd.RawOutputStream(device=dev,samplerate=24000,channels=1,dtype='int16') as output:
                output.write(pcm)
            rows[-1].update(status='NEEDS_HARDWARE',detail='Actual output write completed. Confirm audibility and selected device')
        except Exception as e:
            failed=rows[-1] if rows[-2]['status']=='PASS' else rows[-2]
            failed.update(status='FAIL',detail=type(e).__name__)
    add('Keyboard registration','SKIPPED','Use --hotkey-test; command dispatch still requires end-to-end acceptance')
    if args.hotkey_test:
        from core.hotkey import PushToTalk
        changes=[];hook=PushToTalk(changes.append);scope=hook.start()
        print('Hold and release Ctrl+Space during the next five seconds.',file=sys.stderr)
        try:time.sleep(5)
        finally:hook.stop()
        rows[-1].update(status='PASS' if True in changes and False in changes else 'FAIL',detail=f'Actual key polling scope={scope}; no command-dispatch claim')
    add('Provider reachability/authentication','SKIPPED','Use --provider; contacts configured Google account without audio')
    if args.provider:
        import asyncio
        from tools.live_probe import run
        rows.extend(asyncio.run(run(network=True)))
    add('Error classification','SKIPPED','Run tests/test_voice_runtime.py; mocked responses are documented separately')
    add('State transitions','SKIPPED','Run automated voice tests and inspect real HUD transitions')
    add('Stop/cancel behavior','SKIPPED','Run mocked regression then physical playback interruption acceptance')
    add('Resource cleanup','SKIPPED','Close/relaunch application on Windows; inspect device availability and worker counts')
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mic-test',type=float,default=0)
    for name in ['wake-test','tts-test','hotkey-test','provider']:p.add_argument('--'+name,action='store_true')
    p.add_argument('--out',default='voice_diagnostics.json')
    args=p.parse_args()
    rows=diagnose(args)
    Path(args.out).write_text(json.dumps(rows,indent=2),encoding='utf-8')
    for row in rows:print(f"{row['status']}: {row['check']} — {row['detail']}")
    return 1 if any(row['status']=='FAIL' for row in rows) else 0
if __name__=='__main__':raise SystemExit(main())
