import ast,asyncio,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from core.tasks import TaskManager,checkpoint,in_executor,cancellation_event,offer_audio
class TaskTests(unittest.IsolatedAsyncioTestCase):
 def call(self,n):return NS(id=str(n),name='fake',args={})
 async def test_fifo_failure_and_bounded_queue(self):
  gate=asyncio.Event();events=[]
  async def execute(call):
   events.append(call.id)
   if call.id=='0':await gate.wait()
   if call.id=='1':raise ValueError('fake failure')
   return call.id
  m=TaskManager(execute,max_pending=2);a=m.submit(self.call(0),0);await asyncio.sleep(.01)
  b=m.submit(self.call(1),0);c=m.submit(self.call(2),0);d=m.submit(self.call(3),0)
  self.assertEqual((await d.future).status,'rejected');gate.set()
  self.assertEqual((await a.future).value,'0');self.assertEqual((await b.future).status,'failed')
  self.assertEqual((await c.future).value,'2');self.assertEqual(events,['0','1','2']);await m.close()
 async def test_cancel_prevents_following_steps_and_resolves_queue(self):
  effects=[];started=asyncio.Event()
  async def execute(call):
   started.set()
   for step in range(50):
    await asyncio.sleep(.01);checkpoint();effects.append(step)
  m=TaskManager(execute);a=m.submit(self.call(0),0);await started.wait();b=m.submit(self.call(1),0)
  m.cancel_all();self.assertEqual((await b.future).status,'cancelled');self.assertEqual((await a.future).status,'cancelled')
  self.assertEqual(effects,[]);await m.close()
 async def test_context_propagates_to_executor(self):
  started=threading.Event();effects=[]
  def sync():
   started.set();event=cancellation_event();self.assertIsNotNone(event);event.wait(1);checkpoint();effects.append('bad')
  async def execute(call):return await in_executor(asyncio.get_running_loop(),None,sync)
  m=TaskManager(execute);a=m.submit(self.call(0),0)
  while not started.is_set():await asyncio.sleep(.01)
  m.cancel_all();self.assertEqual((await a.future).status,'cancelled');self.assertEqual(effects,[]);await m.close()
 async def test_stall_does_not_release_mutation_slot(self):
  gate=asyncio.Event();effects=[]
  async def execute(call):
   effects.append(call.id)
   if call.id=='0':await gate.wait()
   return call.id
  m=TaskManager(execute,timeout=.03);a=m.submit(self.call(0),0);b=m.submit(self.call(1),0)
  await asyncio.sleep(.06);self.assertEqual(a.status,'stalled');self.assertEqual(effects,['0'])
  gate.set();self.assertEqual((await a.future).status,'cancelled');await b.future;await m.close()
 async def test_session_change_cancels_old_calls(self):
  gate=asyncio.Event()
  async def execute(call):await gate.wait();return call.id
  m=TaskManager(execute);a=m.submit(self.call(0),0);await asyncio.sleep(.01);b=m.submit(self.call(1),0)
  m.new_session(1);c=m.submit(self.call(2),0)
  self.assertEqual((await c.future).status,'cancelled');self.assertEqual((await b.future).status,'cancelled')
  gate.set();self.assertEqual((await a.future).status,'cancelled');await m.close()
 async def test_audio_bounded(self):
  q=asyncio.Queue(maxsize=2)
  for i in range(10):offer_audio(q,i)
  self.assertEqual(q.qsize(),2);self.assertEqual(await q.get(),8)
 async def test_real_receive_method_keeps_receiving_during_tool(self):
  # Execute the real method with a fake transport; does not prove Gemini SDK compatibility.
  tree=ast.parse(Path('main.py').read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='JarvisLive')
  methods=[n for n in cls.body if isinstance(n,ast.AsyncFunctionDef) and n.name in {'_receive_audio','_deliver_tool_batch'}]
  namespace={'asyncio':asyncio,'offer_audio':offer_audio,'types':NS(FunctionResponse=lambda **kw:NS(**kw))}
  exec(compile(ast.Module(body=methods,type_ignores=[]),'main.py','exec'),namespace)
  received=asyncio.Event();release=asyncio.Event();tool_started=asyncio.Event();sent=[]
  class Session:
   async def receive(self):
    yield NS(data=None,server_content=None,tool_call=NS(function_calls=[NS(id='abc',name='fake')]))
    await tool_started.wait();received.set();await asyncio.Future()
   async def send_tool_response(self,**kwargs):sent.extend(kwargs['function_responses'])
  async def execute(fc):tool_started.set();await release.wait();return NS(id=fc.id,name=fc.name)
  session=Session();obj=NS(session=session,_session_epoch=0,_deliveries=set(),_delivery_lock=asyncio.Lock(),ui=NS(write_log=lambda *a:None))
  obj._tasks=TaskManager(execute);obj._deliver_tool_batch=lambda *a:namespace['_deliver_tool_batch'](obj,*a)
  obj._flush_pending_vision=lambda:asyncio.sleep(0)
  receive=asyncio.create_task(namespace['_receive_audio'](obj));await asyncio.wait_for(received.wait(),1)
  self.assertEqual(sent,[]);obj.session=Session();obj._session_epoch=1;release.set()
  await asyncio.sleep(.03);self.assertEqual(sent,[]) # old result must not reach replacement session
  receive.cancel();await asyncio.gather(receive,return_exceptions=True);await obj._tasks.close()
