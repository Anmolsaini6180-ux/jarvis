"""Redact credential values from diagnostic streams. UI drafts remain reviewable."""
import re,threading
_known=[];_lock=threading.Lock()
def register(value):
    if not isinstance(value,str) or len(value)<8:return
    with _lock:
        if value not in _known:_known.append(value)
        if len(_known)>256:del _known[:-256]
def redact(text):
    s=str(text)
    with _lock:
        for secret in _known:s=s.replace(secret,'[REDACTED]')
    s=re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9_.~+/=-]+',r'\1[REDACTED]',s)
    s=re.sub(r'AIza[0-9A-Za-z_-]{20,}','[REDACTED]',s)
    return s
class RedactedStream:
    def __init__(self,stream):self.stream=stream
    def write(self,s):return self.stream.write(redact(s))
    def __getattr__(self,k):return getattr(self.stream,k)
def install():
    import sys
    for key in ('stdout','stderr'):
        stream=getattr(sys,key)
        if stream and not isinstance(stream,RedactedStream):setattr(sys,key,RedactedStream(stream))
