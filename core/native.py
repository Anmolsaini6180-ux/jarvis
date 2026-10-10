"""Optional desktop imports with an early headless capability check."""
import os
import sys

def desktop_input():
    # PyAutoGUI is X11 based on Linux. Importing without DISPLAY triggers vendor
    # import side effects (MouseInfo subprocesses) before it eventually fails.
    if sys.platform.startswith('linux') and not os.environ.get('DISPLAY'):
        raise ImportError('Desktop input unavailable: no X11 DISPLAY; use a real desktop session')
    import pyautogui
    return pyautogui

def cancellable_type(text,interval=0.03,keyboard=None):
    """Keep native typing interruptible between bounded chunks; target is unverified."""
    from core.tasks import checkpoint,progress
    keyboard=keyboard or desktop_input()
    text=str(text)
    interval=max(0.0,min(float(interval),0.1))
    for start in range(0,len(text),16):
        checkpoint()
        keyboard.typewrite(text[start:start+16],interval=interval)
        progress(f'Text input: {min(start+16,len(text))}/{len(text)} characters dispatched')
