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
    s=re.sub(r'(?i)([?&](?:token|key|api_key|device_token)=)[^&\s\"\']+', r'\1[REDACTED]', s)
    s=re.sub(r'(?i)(x-goog-api-key[\"\']?\s*[:=]\s*[\"\']?)[^\s,}\"\']+', r'\1[REDACTED]', s)
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
    import logging, traceback
    factory = logging.getLogRecordFactory()
    if not getattr(factory, '_jarvis_redacted', False):
        def safe_record(*args, **kwargs):
            record = factory(*args, **kwargs)
            record.msg, record.args = redact(record.getMessage()), ()
            if record.exc_info:
                record.exc_text = redact(''.join(traceback.format_exception(*record.exc_info)))
                record.exc_info = None
            return record
        safe_record._jarvis_redacted = True
        logging.setLogRecordFactory(safe_record)
