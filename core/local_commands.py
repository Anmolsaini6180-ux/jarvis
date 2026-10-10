"""Small deterministic text-command fallback; no AI replies or fuzzy tool selection."""
import re
from datetime import datetime

def route(text):
    text=re.sub(r'[^\w\s]',' ',text.casefold())
    text=' '.join(text.split())
    text=re.sub(r'^(?:hey )?jarvis\s+','',text)
    if text in {'stop','cancel','cancel tasks','ruk jao','bas'}:return 'stop',{}
    if text in {'what time is it','time kya hai','samay kya hai'}:
        return 'time',datetime.now().strftime('The time is %I:%M %p.')
    for name in ('chrome','notepad'):
        if text in {f'open {name}',f'{name} kholo'}:return 'open_app',{'app_name':name}
    return None
