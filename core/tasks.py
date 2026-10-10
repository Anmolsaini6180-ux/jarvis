"""Bounded FIFO mutation worker; reception and result delivery run separately.

Cancellation is cooperative. An uncooperative third-party call retains the
mutation slot until it actually returns; timeout never pretends it stopped.
"""
import asyncio,contextvars,threading,time,uuid
from dataclasses import dataclass,field
from collections import deque
_CANCEL=contextvars.ContextVar('jarvis_cancel',default=None)
_PROGRESS=contextvars.ContextVar('jarvis_progress',default=None)
class TaskCancelled(RuntimeError):pass

def cancellation_event():return _CANCEL.get()
def checkpoint():
    event=_CANCEL.get()
    if event and event.is_set():raise TaskCancelled('Task cancelled; subsequent step refused')
def progress(detail):
    checkpoint();cb=_PROGRESS.get()
    if cb:cb(str(detail)[:160])
def cancellable_sleep(seconds):
    event=_CANCEL.get()
    if event:
        if event.wait(seconds):checkpoint()
    else:time.sleep(seconds)
def in_executor(loop,executor,fn,*args):
    context=contextvars.copy_context()
    return loop.run_in_executor(executor,context.run,fn,*args)
def offer_audio(queue,item):
    """Keep recent audio; never block reception or raise QueueFull in callback."""
    if queue is None:return
    if queue.full():
        try:queue.get_nowait()
        except asyncio.QueueEmpty:pass
    queue.put_nowait(item)

@dataclass
class TaskResult:
    status:str
    value:object=None
    error:str=''
@dataclass
class TaskRecord:
    id:str
    call_id:str
    name:str
    epoch:int
    status:str='queued'
    detail:str=''
    created:float=field(default_factory=time.monotonic)
    started:float|None=None
    duration:float=0
    cancel:threading.Event=field(default_factory=threading.Event)
    future:object=None

class TaskManager:
    def __init__(self,execute,max_pending=16,timeout=120,on_progress=None):
        self.execute=execute;self.queue=asyncio.Queue(maxsize=max_pending);self.timeout=timeout
        self.history=deque(maxlen=100);self.running=None;self.worker=None;self.epoch=0;self.on_progress=on_progress
    def start(self):
        if not self.worker:self.worker=asyncio.create_task(self._work())
    def _notify(self,rec):
        if self.on_progress:self.on_progress(rec)
    def submit(self,call,epoch):
        self.start();loop=asyncio.get_running_loop();future=loop.create_future()
        rec=TaskRecord(uuid.uuid4().hex[:10],str(call.id),call.name,epoch,future=future)
        self.history.append(rec)
        if epoch!=self.epoch:
            rec.status='cancelled';future.set_result(TaskResult('cancelled',error='Session changed'))
        elif self.queue.full():
            rec.status='rejected';future.set_result(TaskResult('rejected',error='Task queue full; no action performed'))
        else:self.queue.put_nowait((rec,call))
        self._notify(rec);return rec
    def cancel_all(self):
        if self.running:
            self.running.cancel.set();self.running.status='cancelling';self._notify(self.running)
        # Drain queued records directly. Bounded history can evict records after
        # many rejections, but must never remove them from cancellation control.
        while True:
            try:rec,call=self.queue.get_nowait()
            except asyncio.QueueEmpty:break
            rec.cancel.set();rec.status='cancelled';self._notify(rec)
            if not rec.future.done():rec.future.set_result(TaskResult('cancelled',error='Cancelled while queued; no action performed'))
            self.queue.task_done()
    def cancel_calls(self,ids):
        if self.running and self.running.call_id in ids:
            self.running.cancel.set();self.running.status='cancelling';self._notify(self.running)
        retained=[]
        while True:
            try:rec,call=self.queue.get_nowait()
            except asyncio.QueueEmpty:break
            self.queue.task_done()
            if rec.call_id in ids:
                rec.cancel.set();rec.status='cancelled';self._notify(rec)
                if not rec.future.done():rec.future.set_result(TaskResult('cancelled',error='Server cancelled queued call'))
            else:retained.append((rec,call))
        for entry in retained:self.queue.put_nowait(entry)
    def new_session(self,epoch):
        self.cancel_all();self.epoch=epoch
    async def _work(self):
        while True:
            rec,call=await self.queue.get()
            if rec.cancel.is_set() or rec.epoch!=self.epoch:
                if not rec.future.done():rec.future.set_result(TaskResult('cancelled',error='Task cancelled'))
                self.queue.task_done();continue
            self.running=rec;rec.status='running';rec.started=time.monotonic();self._notify(rec)
            token=_CANCEL.set(rec.cancel);ptoken=_PROGRESS.set(lambda detail:self._progress(rec,detail))
            task=asyncio.create_task(self.execute(call))
            try:
                try:value=await asyncio.wait_for(asyncio.shield(task),timeout=self.timeout)
                except asyncio.TimeoutError:
                    rec.cancel.set();rec.status='stalled';rec.detail='Deadline exceeded; waiting for worker to stop safely';self._notify(rec)
                    value=await task # retain serialization; cannot kill a Python thread
                outcome=TaskResult('cancelled' if rec.cancel.is_set() else 'completed',value)
            except TaskCancelled as e:outcome=TaskResult('cancelled',error=str(e))
            except Exception as e:outcome=TaskResult('failed',error=type(e).__name__)
            finally:
                _CANCEL.reset(token);_PROGRESS.reset(ptoken);rec.duration=time.monotonic()-rec.started;self.running=None
            rec.status=outcome.status
            if not rec.future.done():rec.future.set_result(outcome)
            self._notify(rec);self.queue.task_done()
    def _progress(self,rec,detail):
        rec.detail=detail;self._notify(rec)
    async def close(self):
        self.cancel_all()
        if self.worker:
            try:await asyncio.wait_for(self.queue.join(),timeout=5)
            except asyncio.TimeoutError:pass
            self.worker.cancel();await asyncio.gather(self.worker,return_exceptions=True);self.worker=None
