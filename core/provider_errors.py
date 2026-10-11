"""Structured provider failures; no credentials or exception payloads in messages."""
from dataclasses import dataclass
import socket
import ssl
import random

class LiveSetupRejected(Exception):
    """SDK returned a session without a setup-complete acknowledgment."""

class MissingCredential(Exception):
    """Credential not configured; no network request was made."""

@dataclass(frozen=True)
class Failure:
    kind: str
    retryable: bool
    message: str

def classify(exc):
    if isinstance(exc,BaseExceptionGroup):
        errors=[classify(e) for e in exc.exceptions]
        return next((e for e in errors if not e.retryable),errors[0])
    from core.credential_input import InvalidCredential
    if isinstance(exc,InvalidCredential):return Failure('CREDENTIAL_FORMAT',False,'Credential format invalid. Paste a single Gemini API key in Settings; no request was sent.')
    from websockets.exceptions import InvalidHeaderValue, InvalidStatus
    if isinstance(exc,InvalidHeaderValue):return Failure('CREDENTIAL_FORMAT',False,'Invalid provider HTTP header. Check that the credential contains only a single API key.')
    if isinstance(exc,InvalidStatus):
        status=getattr(exc.response,'status_code',0)
        if status in {401,403}:return Failure('AUTH' if status==401 else 'FORBIDDEN',False,'Provider handshake authorization rejected. Check key and account access.')
        if status==429:return Failure('QUOTA',True,'Provider handshake rate limited.')
        if status>=500:return Failure('NETWORK',True,'Provider handshake temporarily unavailable.')
    if isinstance(exc,MissingCredential):return Failure('MISSING_CREDENTIAL',False,'Gemini credential is missing. Configure it locally; audio tests remain available.')
    if isinstance(exc,LiveSetupRejected):return Failure('CONFIG',False,'Live setup was not acknowledged; conversational readiness is unavailable.')
    code=getattr(exc,'code',None)
    response=getattr(exc,'response_json',None) or getattr(exc,'details',None) or {}
    error=response.get('error',{}) if isinstance(response,dict) else {}
    reasons={d.get('reason') for d in error.get('details',[]) if isinstance(d,dict)}
    # Google may report invalid keys as 400. Use structured ErrorInfo first,
    # with the SDK's canonical key message for older responses without details.
    message=getattr(exc,'message','') or (response if isinstance(response,str) else '')
    if code==401 or 'API_KEY_INVALID' in reasons or (code in {400,1007,1008,1011} and 'API key not valid' in message):
        return Failure('AUTH',False,'API credential rejected. Update credentials in Settings.')
    if code==403:return Failure('FORBIDDEN',False,'Provider access denied. Check account eligibility, permissions and billing.')
    if code==404:return Failure('MODEL',False,'Configured Live model is unavailable. Check model access and configuration.')
    if code==429:return Failure('QUOTA',True,'Provider quota or rate limit reached.')
    if code==400:return Failure('CONFIG',False,'Provider rejected the Live configuration.')
    close=getattr(exc,'rcvd',None)
    close_code=getattr(close,'code',getattr(exc,'close_code',code if isinstance(code,int) and code>=1000 else None))
    if close_code==1008:return Failure('FORBIDDEN',False,'Live access rejected by provider policy. Check account and model eligibility.')
    if close_code==1007:return Failure('CONFIG',False,'Live payload rejected (1007); this does not establish an invalid key.')
    import httpx
    if isinstance(exc,httpx.TimeoutException):return Failure('TIMEOUT',True,'Provider connection timed out.')
    if isinstance(exc,httpx.TransportError):
        if exc.__cause__ is not None:
            nested=classify(exc.__cause__)
            if nested.kind in {'DNS','TLS','TIMEOUT'}:return nested
        return Failure('NETWORK',True,'Provider transport failed. Check network configuration.')
    if isinstance(exc,socket.gaierror):return Failure('DNS',True,'DNS lookup failed. Check network and DNS settings.')
    if isinstance(exc,ssl.SSLError):return Failure('TLS',False,'TLS verification failed. Check certificates and system clock.')
    if isinstance(exc,TimeoutError):return Failure('TIMEOUT',True,'Provider connection timed out.')
    if isinstance(exc,ConnectionError) or close_code in {1001,1006,1011,1012,1013} or (isinstance(code,int) and 500<=code<600):
        return Failure('NETWORK',True,'Provider connection interrupted.')
    if isinstance(exc,OSError):return Failure('NETWORK',True,'Connection transport failed. Check network configuration.')
    return Failure('UNKNOWN',False,'Unexpected runtime failure. Inspect diagnostics; retry explicitly.')

def retry_delay(attempt, jitter=random.random):
    return min(60.0,3.0*2**max(0,attempt-1))*(0.8+0.2*jitter())


from contextlib import asynccontextmanager
import asyncio

@asynccontextmanager
async def connect_with_timeout(client, model, config, seconds=20):
    """Limit handshake duration without imposing a timeout on a healthy session."""
    manager=client.aio.live.connect(model=model,config=config)
    async with asyncio.timeout(seconds):
        session=await manager.__aenter__()
    try:
        if getattr(session,'setup_complete',None) is None:
            raise LiveSetupRejected()
        yield session
    except BaseException:
        import sys
        if not await manager.__aexit__(*sys.exc_info()):raise
    else:
        await manager.__aexit__(None,None,None)

