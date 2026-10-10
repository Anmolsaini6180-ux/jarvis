"""Explicit Windows SAPI synthesis to WAV; playback uses the selected app output."""
import platform
import tempfile
from pathlib import Path
import wave

def synthesize(text, voice_name=''):
    if platform.system()!='Windows':raise RuntimeError('Windows SAPI requires Windows and pywin32')
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    path=None
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav',delete=False) as f:path=Path(f.name)
        voice=win32com.client.Dispatch('SAPI.SpVoice')
        if voice_name:
            selected=next((v for v in voice.GetVoices() if v.GetDescription()==voice_name),None)
            if selected is None:raise RuntimeError('Selected SAPI voice is not installed')
            voice.Voice=selected
        output=win32com.client.Dispatch('SAPI.SpFileStream')
        output.Format.Type=22  # SAFT22kHz16BitMono
        output.Open(str(path),3,False)
        try:
            voice.AudioOutputStream=output
            voice.Speak(text)
        finally:output.Close()
        with wave.open(str(path),'rb') as wav:
            if wav.getsampwidth()!=2 or wav.getnchannels()!=1:raise RuntimeError('Unsupported SAPI WAV format')
            pcm=wav.readframes(wav.getnframes())
            if not pcm:raise RuntimeError('SAPI generated empty audio')
            return pcm,wav.getframerate()
    finally:
        if path:path.unlink(missing_ok=True)
        pythoncom.CoUninitialize()
