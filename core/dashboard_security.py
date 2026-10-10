"""Request limits enforced before FastAPI multipart parsing; bounded rate state."""
import time
from collections import deque
class RateLimit:
    def __init__(self,limit=10,window=60):self.limit=limit;self.window=window;self.clients={}
    def allow(self,key):
        now=time.monotonic()
        for k in list(self.clients):
            if not self.clients[k] or self.clients[k][-1]<now-self.window:del self.clients[k]
        if key not in self.clients and len(self.clients)>=1024:return False
        q=self.clients.setdefault(key,deque())
        while q and q[0]<now-self.window:q.popleft()
        if len(q)>=self.limit:return False
        q.append(now);return True

class RequestLimits:
    def __init__(self,app,max_upload=25*1024*1024):self.app=app;self.max_upload=max_upload
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        limit=self.max_upload+65536 if scope.get('path')=='/api/upload' else 65536
        chunks=[];size=0
        while True:
            msg=await receive()
            if msg['type']=='http.disconnect':return
            size+=len(msg.get('body',b''))
            if size>limit:
                await send({'type':'http.response.start','status':413,'headers':[(b'content-type',b'application/json')]})
                return await send({'type':'http.response.body','body':b'{"error":"Request too large"}'})
            chunks.append(msg)
            if not msg.get('more_body',False):break
        async def replay():
            if chunks:return chunks.pop(0)
            return await receive()
        await self.app(scope,replay,send)
