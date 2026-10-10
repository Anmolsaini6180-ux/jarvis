"""Startup diagnostics; credential reads may apply documented migration/recovery. Never prints credentials or installs packages."""
import argparse,importlib.util,json,platform,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def diagnose(audio=False):
    report={'python':platform.python_version(),'platform':platform.system(),'modules':{},'warnings':[]}
    modules={'desktop_ui':'PyQt6','cloud_sdk':'google.genai','audio':'sounddevice','browser':'playwright','documents_xml':'defusedxml','dashboard':'fastapi','credential_keyring':'keyring'}
    for feature,module in modules.items():
        try:report['modules'][feature]=bool(importlib.util.find_spec(module))
        except ModuleNotFoundError:report['modules'][feature]=False
    from memory.config_manager import get_gemini_key
    try:report['credential_present']=bool(get_gemini_key())
    except Exception as e:report['credential_present']=False;report['warnings'].append('Credential/configuration unavailable: '+type(e).__name__)
    report['offline_conversation']='not implemented; local modules are not routed into Gemini Live'
    report['generated_execution']='requires optional reviewed Docker image; no host fallback'
    if audio:
        try:
            import sounddevice as sd
            devices=sd.query_devices()
            report['audio_usable']=bool(devices)
            report['audio_input_count']=sum(d['max_input_channels']>0 for d in devices)
            report['audio_output_count']=sum(d['max_output_channels']>0 for d in devices)
            if not devices:report['warnings'].append('No audio devices detected')
        except Exception as e:
            report['audio_usable']=False;report['warnings'].append('Audio/device unavailable: '+type(e).__name__)
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--audio',action='store_true');args=p.parse_args()
    print(json.dumps(diagnose(args.audio),indent=2))
