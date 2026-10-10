"""Thread-safe runtime state and capability priority, independent of Qt."""
from enum import StrEnum
from threading import RLock

class State(StrEnum):
    STARTING='STARTING'
    INITIALIZING='INITIALIZING'
    SLEEPING='SLEEPING'
    LISTENING='LISTENING'
    HEARING_SPEECH='HEARING SPEECH'
    PROCESSING='PROCESSING'
    SPEAKING='SPEAKING'
    RECONNECTING='RECONNECTING'
    ERROR='ERROR'
    STOPPED='STOPPED'
    MIC_UNAVAILABLE='MIC_UNAVAILABLE'
    PROVIDER_UNAVAILABLE='PROVIDER_UNAVAILABLE'

_ACTIVE={State.SLEEPING,State.LISTENING,State.HEARING_SPEECH,State.PROCESSING,State.SPEAKING}
_FAILURE={State.ERROR,State.MIC_UNAVAILABLE,State.PROVIDER_UNAVAILABLE,State.RECONNECTING}
ALLOWED={s: (_ACTIVE|_FAILURE|{State.STOPPED}) for s in _ACTIVE|_FAILURE}
ALLOWED[State.STARTING]={State.INITIALIZING,State.STOPPED}
ALLOWED[State.INITIALIZING]=_ACTIVE|_FAILURE|{State.STOPPED}
ALLOWED[State.STOPPED]=set()

class RuntimeState:
    def __init__(self, publish, log=lambda message: None):
        self._lock=RLock()
        self.state=State.STARTING
        self.publish=publish
        self.log=log
        self.provider=False
        self.mic=False
    @property
    def provider(self):
        with self._lock:return self._provider
    @provider.setter
    def provider(self,value):
        with self._lock:self._provider=bool(value)
    @property
    def mic(self):
        with self._lock:return self._mic
    @mic.setter
    def mic(self,value):
        with self._lock:self._mic=value
    def transition(self, value):
        value=State.PROCESSING if value=='THINKING' else State(value)
        with self._lock:
            if value==self.state:return True
            if value not in ALLOWED[self.state]:
                self.log(f'SYS: Rejected state transition {self.state} -> {value}')
                return False
            if value in _ACTIVE-{State.SPEAKING,State.SLEEPING} and not self.provider:value=State.PROVIDER_UNAVAILABLE
            if value in {State.LISTENING,State.HEARING_SPEECH} and self.mic is False:
                value=State.MIC_UNAVAILABLE
            self.state=value
            # Qt publication emits a signal; observers never touch widgets here.
            self.publish(value.value)
            return True
