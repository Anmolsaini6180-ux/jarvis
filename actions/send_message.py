"""Reviewable drafts with an explicit verified-adapter contract. No blind input."""
from dataclasses import dataclass
from typing import Protocol
from core import confirm
from core.execution import current_cancel

@dataclass(frozen=True)
class Recipient:
    identity: str
    display: str
    verified: bool

@dataclass(frozen=True)
class SendState:
    status: str  # attempted | accepted | delivered | read | failed
    evidence: str = ''  # non-sensitive application/server receipt description

class MessagingAdapter(Protocol):
    def resolve(self,query: str) -> Recipient: ...
    def verify(self,recipient: Recipient) -> bool: ...
    def send(self,recipient: Recipient,message: str) -> SendState: ...

_ADAPTERS={}

def register_adapter(platform: str,adapter: MessagingAdapter):
    """Trusted integration registration, never model-supplied/imported code.
    Adapter must resolve unique stable identities and revalidate before sending.
    A UI field emptied is not delivery evidence. No adapters ship in original ZIP.
    """
    if not all(callable(getattr(adapter,k,None)) for k in ('resolve','verify','send')):raise TypeError('Verified adapter contract required')
    _ADAPTERS[platform.lower()]=adapter

def send_message(parameters,response=None,player=None,session_memory=None):
    receiver=parameters.get('receiver','').strip();message=parameters.get('message_text','').strip()
    platform=parameters.get('platform','whatsapp').lower().strip()
    if not receiver or len(receiver)>256 or not message or len(message)>4096:return 'Invalid recipient/message length; nothing sent.'
    draft=f'Platform: {platform}\nRecipient requested: {receiver}\n\n{message}'
    if player and hasattr(player,'show_content'):player.show_content('MESSAGE DRAFT — NOT SENT',draft)
    adapter=_ADAPTERS.get(platform)
    if not adapter:
        return f'[DRAFT_PREPARED / SEND_UNAVAILABLE] No verified {platform} adapter is installed. Copy this draft into the app and verify the recipient manually. Nothing sent.\n{draft}'
    try:
        recipient=adapter.resolve(receiver)
        if not isinstance(recipient,Recipient) or not recipient.verified or not recipient.identity:
            return 'Recipient could not be uniquely verified. Draft prepared; nothing sent.'
    except Exception:return 'Recipient lookup failed. Draft prepared; nothing sent.'
    cancel=current_cancel()
    def reviewed_send():
        if cancel and cancel.is_set():return 'Cancelled before send; nothing sent.'
        if not adapter.verify(recipient):return 'Recipient changed or unavailable; nothing sent.'
        try:state=adapter.send(recipient,message)
        except Exception:return '[SEND_ATTEMPTED / UNVERIFIED] Adapter failed; do not retry automatically (duplicate risk).'
        if not isinstance(state,SendState) or state.status not in {'attempted','accepted','delivered','read','failed'}:
            return '[SEND_ATTEMPTED / UNVERIFIED] Adapter returned no valid state.'
        if state.status in {'accepted','delivered','read'} and not state.evidence:
            return '[SEND_ATTEMPTED / UNVERIFIED] Missing receipt evidence.'
        return f'[MESSAGE_{state.status.upper()}] Delivery/read claimed only when verified by the adapter receipt.'
    return confirm.request('message-send','Review message recipient and content',
        f'Platform: {platform}\nVerified recipient: {recipient.display}\nIdentity: {recipient.identity}\n\n{message}',reviewed_send)

# Compatibility entry points refuse blind drivers.
def _desktop_send(app_name,receiver,message):
    return send_message({'platform':app_name,'receiver':receiver,'message_text':message})
def _send_whatsapp(receiver,message):return _desktop_send('whatsapp',receiver,message)
TOOL={'name':'send_message','description':'Prepare a message draft. Sending requires an installed verified adapter, unique recipient verification and local HUD confirmation. Distinguish attempted, accepted, delivered and read. Do not claim unavailable drivers sent anything.',
 'parameters':{'type':'OBJECT','properties':{'receiver':{'type':'STRING'},'message_text':{'type':'STRING'},'platform':{'type':'STRING'}},'required':['receiver','message_text','platform']},'handler':send_message}
