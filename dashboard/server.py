from core.dashboard_security import RateLimit, RequestLimits
"""
dashboard/server.py — JARVIS opt-in local HTTPS dashboard

TLS-only remote dashboard on port 8000, inactive until local UI activation.
Security at the application layer: AES-256-CBC with session-key-derived key.
CryptoJS is served from a bundled/cache copy, or explicitly redirected to the CDN; no automatic server download.

Install deps:  pip install fastapi "uvicorn[standard]" cryptography
"""

import asyncio
import base64
import hashlib
import re
import secrets
import socket
import string
import time
from pathlib import Path

_DEPS_OK = False
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
    import uvicorn
    _DEPS_OK = True
except ImportError:
    pass

# python-multipart is required for file uploads — optional dependency
_UPLOAD_OK = False
try:
    from fastapi import UploadFile, File as FastAPIFile
    _UPLOAD_OK = True
except Exception:
    pass

BASE_DIR    = Path(__file__).resolve().parent.parent
STATIC_DIR  = Path(__file__).parent / "static"
PORT        = 8000
MAX_UPLOAD_MB = 25


def _make_uploads_dir() -> Path:
    from core.path_policy import DEFAULT_WORKSPACE
    return DEFAULT_WORKSPACE / 'RemoteUploads'  # no filesystem mutation during import


UPLOADS_DIR = _make_uploads_dir()

def _get_gemini_key():
    from memory.config_manager import get_gemini_key
    return get_gemini_key()

_KEY_CHARS = [c for c in (string.ascii_uppercase + string.digits)
              if c not in ('O', 'I', 'L', '0', '1')]

# ── AES-256-CBC ───────────────────────────────────────────────────────────────
_AES_SALT = b'JARVIS-DASHBOARD-v1'


def _derive_key(session_key: str) -> bytes:
    """SHA-256(sessionKey‖salt) → 32-byte AES-256 key (microseconds, no PBKDF2 needed)."""
    return hashlib.sha256(session_key.encode('utf-8') + _AES_SALT).digest()


def _decrypt_cbc(aes_key: bytes, enc_b64: str) -> str:
    """Decrypt base64(IV[16] ‖ ciphertext) with AES-256-CBC + PKCS7."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as sym_pad
    raw      = base64.b64decode(enc_b64)
    iv, ct   = raw[:16], raw[16:]
    dec      = Cipher(algorithms.AES(aes_key), modes.CBC(iv)).decryptor()
    padded   = dec.update(ct) + dec.finalize()
    unpadder = sym_pad.PKCS7(128).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode('utf-8')


# ── CryptoJS (auto-download once, served locally) ─────────────────────────────
_CRYPTOJS_CDN  = ("https://cdnjs.cloudflare.com/ajax/libs/"
                  "crypto-js/4.2.0/crypto-js.min.js")
_CRYPTOJS_FILE = STATIC_DIR / "crypto-js.min.js"


def _ensure_network_access(port: int) -> None:
    """Compatibility function: never change firewall or network categories."""
    print(f"[Dashboard] Network policy unchanged. Configure port {port} manually only if desired.")


def _ensure_crypto_js() -> None:
    if not _CRYPTOJS_FILE.exists():
        raise RuntimeError('Bundled CryptoJS missing; restore from the source distribution.')


_ensure_crypto_js()


# ── helpers ───────────────────────────────────────────────────────────────────

def _local_ip() -> str:
    """Return the best LAN-facing IPv4 address, no internet required."""
    # Method 1: route trick (fast, works when internet is available)
    for probe in ("8.8.8.8", "1.1.1.1", "192.168.1.1"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect((probe, 80))
            ip = s.getsockname()[0]
            s.close()
            if not ip.startswith("127."):
                return ip
        except Exception:
            pass

    # Method 2: hostname resolution (works offline on most systems)
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if not ip.startswith("127."):
            return ip
    except Exception:
        pass

    # Method 3: enumerate all interfaces (fully offline, no external deps)
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
    except Exception:
        pass

    return "127.0.0.1"


def _ensure_certs() -> bool:
    """
    Make sure config/certs holds a TLS key pair, generating a self-signed one the
    first time the dashboard runs.

    The pair is deliberately NOT shipped in the repository. A private key that
    every user downloads is the same as having no private key at all: anyone can
    present a certificate that matches it. Generating locally gives each install
    its own key, costs about a second, and happens exactly once.

    Returns True when a usable pair exists afterwards; False prevents serving; remote control never falls back to plaintext.
    """
    certs = BASE_DIR / "config" / "certs"
    key_p = certs / "jarvis.key"
    crt_p = certs / "jarvis.crt"
    if key_p.exists() and crt_p.exists():
        return True

    try:
        import datetime
        import ipaddress
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        print("[Dashboard] cryptography not installed — remote service unavailable; TLS is required.")
        print("[Dashboard] For HTTPS run:  pip install cryptography")
        return False

    try:
        certs.mkdir(parents=True, exist_ok=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        who = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "JARVIS Dashboard"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "JARVIS"),
        ])

        # The SAN has to cover every address the phone might use: the LAN IP the
        # QR code encodes, plus localhost when testing on the machine itself.
        alt = [x509.DNSName("localhost"),
               x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]
        try:
            lan = _local_ip()
            if not lan.startswith("127."):
                alt.append(x509.IPAddress(ipaddress.IPv4Address(lan)))
        except Exception:
            pass          # no LAN address resolvable — localhost entries still work

        # Timezone-aware UTC: datetime.utcnow() is deprecated from Python 3.12 on,
        # and the builder normalises aware values to UTC itself.
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(who)
            .issuer_name(who)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName(alt), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256())
        )

        key_p.write_bytes(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        crt_p.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

        try:
            import os as _os
            _os.chmod(key_p, 0o600)   # best effort — largely a no-op on Windows
        except Exception:
            pass

        print(f"[Dashboard] Generated a self-signed certificate for this machine: {certs}")
        return True
    except Exception as e:
        print(f"[Dashboard] Certificate generation failed ({e}) — remote service unavailable; TLS is required.")
        return False


def _read(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


# ── DashboardServer ───────────────────────────────────────────────────────────

class DashboardServer:

    def __init__(self):
        self._ip                          = _local_ip()
        self._tokens: set[str]            = set()
        self._token_keys: dict[str, str]  = {}   # auth_token → session_key
        self._aes_cache:  dict[str, bytes]= {}   # session_key → AES bytes
        self._clients: set[WebSocket]     = set()
        self._history: list[dict]         = []
        self._broadcast_inflight = 0
        self._active = False
        self._token_expiry = {}
        self._ws_tokens = {}
        self._rate = RateLimit()
        self._server = None
        self._command_queue               = asyncio.Queue(maxsize=32)
        self._wake_callback               = None
        self._connect_callback            = None
        self._pending_keys: dict[str, float] = {}
        self._device_sessions: dict[str, dict] = {}  # device_token → {session_key}
        self._phone_audio_queue: asyncio.Queue    = asyncio.Queue(maxsize=20)
        self._uploads_dir                 = UPLOADS_DIR
        self._login_html                  = _read("login.html")
        self._app_html                    = _read("app.html")
        self.app                          = self._build_app()

    # ── one-time key management ───────────────────────────────────────────

    def new_key(self, expiry_secs: int = 600) -> str:
        now = time.time()
        self._pending_keys = {k: v for k, v in self._pending_keys.items() if v > now}
        key = ''.join(secrets.choice(_KEY_CHARS) for _ in range(6))
        if len(self._pending_keys)>=8: self._pending_keys.pop(next(iter(self._pending_keys)))
        self._active = True  # trusted local UI invokes new_key; no remote activation endpoint
        self._pending_keys[key] = now + min(max(expiry_secs,30),600)
        return key

    @staticmethod
    def _ssl_enabled() -> bool:
        certs = BASE_DIR / "config" / "certs"
        return (certs / "jarvis.key").exists() and (certs / "jarvis.crt").exists()

    def get_url(self) -> str:
        proto = "https"
        return f"{proto}://{self._ip}:{PORT}"

    def get_manual_url(self) -> str:
        """Explicit HTTPS endpoint; no plaintext/alias listener."""
        return self.get_url()

    def _aes_key(self, session_key: str) -> bytes:
        if session_key not in self._aes_cache:
            if len(self._aes_cache)>=128:self._aes_cache.pop(next(iter(self._aes_cache)))
            self._aes_cache[session_key] = _derive_key(session_key)
        return self._aes_cache[session_key]

    def _decrypt(self, token: str, enc_b64: str) -> str | None:
        sk = self._token_keys.get(token)
        if not sk:
            return None
        try:
            return _decrypt_cbc(self._aes_key(sk), enc_b64)
        except Exception:
            return None

    # ── callbacks ────────────────────────────────────────────────────────

    def set_wake_callback(self, fn) -> None:
        self._wake_callback = fn

    def set_connect_callback(self, fn) -> None:
        self._connect_callback = fn

    # ── broadcast ────────────────────────────────────────────────────────

    async def broadcast(self, msg: dict) -> None:
        # No private conversation history is collected before local activation.
        # Avoid unbounded waiting send tasks if a phone stops reading.
        if not self._active or self._broadcast_inflight>=16:return
        import json
        msg=dict(msg)
        if isinstance(msg.get('text'),str) and len(msg['text'])>4096:
            msg['text']=msg['text'][:4096]+' [partial]'
        if len(json.dumps(msg,ensure_ascii=False).encode())>16384:return
        self._broadcast_inflight+=1
        try:
            self._history.append(msg)
            if len(self._history)>300:self._history=self._history[-300:]
            for ws in list(self._clients):
                if not self._authorized(self._ws_tokens.get(ws,'')):
                    await self.invalidate(self._ws_tokens.get(ws,''));continue
                try:await asyncio.wait_for(ws.send_json(msg),timeout=2)
                except Exception:
                    self._clients.discard(ws);self._ws_tokens.pop(ws,None)
                    try:await asyncio.wait_for(ws.close(code=1013),timeout=1)
                    except Exception:pass
        finally:self._broadcast_inflight-=1

    # ── FastAPI app ───────────────────────────────────────────────────────

    def _build_app(self) -> "FastAPI":
        app = FastAPI(docs_url=None, redoc_url=None)
        app.add_middleware(RequestLimits,max_upload=MAX_UPLOAD_MB*1024*1024)
        @app.middleware('http')
        async def security_headers(req,call_next):
            if (req.url.path in {'/login','/api/device-login'} and req.method != 'GET') or req.url.path=='/auto-login':
                if not self._rate.allow(req.client.host if req.client else 'unknown'):
                    return JSONResponse({'error':'Too many pairing attempts'},status_code=429)
            try: response=await call_next(req)
            except (ValueError, TypeError):return JSONResponse({'error':'Invalid request'},status_code=400)
            response.headers['Cache-Control']='no-store'
            response.headers['Referrer-Policy']='no-referrer'
            response.headers['X-Content-Type-Options']='nosniff'
            return response

        @app.post('/api/logout')
        async def logout(req: Request):
            token=req.headers.get('authorization','').removeprefix('Bearer ').strip()
            if not self._authorized(token):return JSONResponse({'error':'Unauthorized'},status_code=401)
            await self.invalidate(token)
            return JSONResponse({'ok':True})

        def _auth(req: Request) -> bool:
            tok = req.headers.get("authorization", "").removeprefix("Bearer ").strip()
            return self._authorized(tok)

        # serve CryptoJS from local cache, fallback to CDN redirect
        @app.get("/static/crypto.js")
        async def serve_crypto():
            if _CRYPTOJS_FILE.exists():
                return FileResponse(str(_CRYPTOJS_FILE),
                                    media_type="application/javascript")
            from fastapi.responses import RedirectResponse
            return RedirectResponse(_CRYPTOJS_CDN)

        @app.get("/login", response_class=HTMLResponse)
        async def login_page():
            return HTMLResponse(self._login_html)

        @app.get("/", response_class=HTMLResponse)
        async def index():
            # Auth is handled client-side via sessionStorage bearer token.
            # Server-side header auth can't work here because browser navigations
            # don't send custom headers (location.href doesn't carry Authorization).
            html = (self._app_html
                    .replace("__IP__", self._ip)
                    .replace("__PORT__", str(PORT)))
            return HTMLResponse(html)

        @app.post("/login")
        async def login(req: Request):
            body    = await req.json()
            if not isinstance(body,dict):return JSONResponse({"error":"Object required"},status_code=400)
            entered = str(body.get("pin", "")).strip().upper()
            now     = time.time()
            if self._active and entered in self._pending_keys and self._pending_keys[entered] > now:
                del self._pending_keys[entered]          # one-time use
                tok = secrets.token_urlsafe(32)
                self._issue(tok)
                self._token_keys[tok] = entered
                self._aes_key(entered)                   # pre-derive & cache
                if self._connect_callback:
                    self._connect_callback()
                asyncio.create_task(self.broadcast(
                    {"type": "sys", "text": "Remote connection established."}
                ))
                # Bearer token in response body — no cookies needed (works on any browser/HTTP)
                return JSONResponse({"ok": True, "token": tok})
            return JSONResponse({"ok": False, "error": "Invalid or expired key"},
                                status_code=401)

        @app.get("/auto-login")
        async def auto_login(key: str = ""):
            """QR code target — validates one-time key, creates session, redirects phone."""
            now = time.time()
            if not self._active or not key or key not in self._pending_keys or self._pending_keys[key] <= now:
                return HTMLResponse("""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width">
<style>
  body{background:#07090f;color:#dde3ed;font-family:sans-serif;
       display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center}
  h2{color:#f87171;margin-bottom:12px}p{color:#5e6a7e;font-size:14px}
</style></head>
<body><div><h2>Link Expired</h2>
<p>Press <strong style="color:#dde3ed">Remote Control</strong> in JARVIS to get a new QR code.</p>
</div></body></html>""")

            for device,record in list(self._device_sessions.items()):
                if record['expires']<=time.time(): self._device_sessions.pop(device,None)
            if len(self._device_sessions)>=32:
                return JSONResponse({'error':'Device limit reached'},status_code=429)
            del self._pending_keys[key]
            tok     = secrets.token_urlsafe(32)
            dev_tok = secrets.token_urlsafe(32)
            self._issue(tok)
            self._token_keys[tok] = key
            self._aes_key(key)
            for device,record in list(self._device_sessions.items()):
                if record['expires']<=time.time():self._device_sessions.pop(device,None)
            if len(self._device_sessions)>=32:return JSONResponse({'error':'Device limit reached'},status_code=429)
            self._device_sessions[dev_tok] = {"session_key": key, "expires": time.time()+30*86400}

            if self._connect_callback:
                self._connect_callback()
            asyncio.create_task(self.broadcast(
                {"type": "sys", "text": "Remote connection established via QR code."}
            ))

            return HTMLResponse(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width">
<style>
  body{{background:#07090f;color:#dde3ed;font-family:sans-serif;
       display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center}}
  p{{color:#5e6a7e;font-size:14px}}
</style></head>
<body>
<script>
  sessionStorage.setItem('jarvis_token','{tok}');
  sessionStorage.setItem('jarvis_key','{key}');
  localStorage.setItem('jarvis_device_token','{dev_tok}');
  setTimeout(function(){{location.replace('/')}},400);
</script>
<p>Connecting to JARVIS…</p>
</body></html>""")

        @app.post("/api/device-login")
        async def device_login_ep(req: Request):
            """Return a fresh auth token for a previously paired device token."""
            try:
                body = await req.json()
            except Exception:
                return JSONResponse({"ok": False}, status_code=400)
            if not isinstance(body,dict) or not isinstance(body.get('device_token',''),str):
                return JSONResponse({'ok':False,'error':'String device_token required'},status_code=400)
            dev_tok = (body.get('device_token') or '').strip()
            if len(dev_tok)>256:return JSONResponse({'ok':False},status_code=400)
            if not dev_tok or dev_tok not in self._device_sessions or self._device_sessions[dev_tok]["expires"]<=time.time():
                return JSONResponse({"ok": False}, status_code=401)
            session_key = self._device_sessions[dev_tok]["session_key"]
            tok = secrets.token_urlsafe(32)
            self._issue(tok)
            self._token_keys[tok] = session_key
            self._aes_key(session_key)
            if self._connect_callback:
                self._connect_callback()
            asyncio.create_task(self.broadcast(
                {"type": "sys", "text": "Known device reconnected automatically."}
            ))
            return JSONResponse({"ok": True, "token": tok, "key": session_key})

        @app.post("/api/revoke-devices")
        async def revoke_devices(req: Request):
            """Invalidate all persistent device tokens (admin action)."""
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            count = len(self._device_sessions)
            await self.revoke_all()
            return JSONResponse({"ok": True, "revoked": count})

        @app.post("/api/command")
        async def command(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            try: body = await req.json()
            except (ValueError,TypeError):return JSONResponse({'error':'Invalid JSON'},status_code=400)
            if not isinstance(body,dict):return JSONResponse({"error":"Object required"},status_code=400)
            token = req.headers.get("authorization", "").removeprefix("Bearer ").strip()
            enc = body.get('enc','')
            if not isinstance(enc,str):return JSONResponse({'error':'enc must be a string'},status_code=400)
            if enc:
                text = self._decrypt(token, enc)
                if text is None:
                    return JSONResponse({"error": "Decryption failed"}, status_code=400)
            else:
                if not isinstance(body.get('text',''),str):return JSONResponse({'error':'Text must be a string'},status_code=400)
                text = (body.get("text") or "").strip()
            if text:
                if len(text)>4096:return JSONResponse({'error':'Command too long'},status_code=413)
                try:self._command_queue.put_nowait(text)
                except asyncio.QueueFull:return JSONResponse({'error':'Command queue full'},status_code=429)
                if self._wake_callback:
                    self._wake_callback()
            return JSONResponse({"ok": True})

        @app.post("/api/wake")
        async def wake_ep(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            if self._wake_callback:
                self._wake_callback()
            return JSONResponse({"ok": True})

        # ── Phone mic real-time audio → Gemini Live ──────────────────────────

        @app.websocket("/ws/phone-audio")
        async def phone_audio_ws(websocket: WebSocket, token: str = ""):
            tok = token.strip()
            if not self._authorized(tok):
                await websocket.close(code=4001)
                return
            if len(self._ws_tokens)>=16:
                await websocket.close(code=4008);return
            await websocket.accept()
            self._ws_tokens[websocket]=tok
            asyncio.create_task(self.broadcast(
                {"type": "sys", "text": "Phone microphone live."}
            ))
            try:
                while True:
                    if not self._authorized(tok):break
                    try: data = await asyncio.wait_for(websocket.receive_bytes(),timeout=1)
                    except asyncio.TimeoutError:continue
                    if not self._authorized(tok):break
                    if len(data)>32768:
                        await websocket.close(code=1009);break
                    try:
                        self._phone_audio_queue.put_nowait(
                            {"data": data, "mime_type": "audio/pcm"}
                        )
                    except asyncio.QueueFull:
                        pass  # drop frame rather than block
            except WebSocketDisconnect:
                pass
            finally:
                self._ws_tokens.pop(websocket,None)
                try: await websocket.close(code=4001)
                except Exception: pass
                asyncio.create_task(self.broadcast(
                    {"type": "sys", "text": "Phone microphone stopped."}
                ))

        # ── File sharing ──────────────────────────────────────────────────────

        def _safe_filename(raw: str) -> str:
            name = Path(raw).name                          # strip path components
            name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip(". ")
            return name or "upload"

        if _UPLOAD_OK:
            @app.post("/api/upload")
            async def upload_file(req: Request, file: UploadFile = FastAPIFile(...)):
                if not _auth(req):
                    return JSONResponse({"error": "Unauthorized"}, status_code=401)

                safe = _safe_filename(file.filename or "upload")
                from core import path_policy
                path_policy.validate(self._uploads_dir)
                self._uploads_dir.mkdir(parents=True,exist_ok=True)
                try:path_policy.validate_spelling(safe,relative=True)
                except ValueError:return JSONResponse({'error':'Invalid/reserved filename'},status_code=400)
                dest = path_policy.validate(self._uploads_dir / safe)
                stem, suffix = Path(safe).stem, Path(safe).suffix
                counter = 1
                while dest.exists():
                    dest = self._uploads_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

                size = 0
                max_bytes = MAX_UPLOAD_MB * 1024 * 1024
                try:
                    with open(dest, "xb") as fout:
                        while True:
                            chunk = await file.read(65536)
                            if not chunk:
                                break
                            if not _auth(req):raise PermissionError('Session expired/revoked during upload')
                            size += len(chunk)
                            if size > max_bytes:
                                fout.close()
                                dest.unlink(missing_ok=True)
                                return JSONResponse(
                                    {"error": f"File too large (max {MAX_UPLOAD_MB} MB)"},
                                    status_code=413,
                                )
                            fout.write(chunk)
                except Exception as exc:
                    try:
                        dest.unlink(missing_ok=True)
                    except Exception:
                        pass
                    return JSONResponse({"error": str(exc)}, status_code=500)

                asyncio.create_task(self.broadcast({
                    "type": "file_received",
                    "name": dest.name,
                    "size": size,
                    "saved_to": str(self._uploads_dir),
                }))
                return JSONResponse({"ok": True, "name": dest.name, "size": size})
        else:
            @app.post("/api/upload")
            async def upload_unavailable(req: Request):
                return JSONResponse(
                    {"error": "File uploads require: pip install python-multipart"},
                    status_code=503,
                )

        @app.get("/api/files")
        async def list_files(req: Request):
            if not _auth(req):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            files = []
            try:
                for f in sorted(
                    (p for p in self._uploads_dir.iterdir() if p.is_file()),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                ):
                    files.append({"name": f.name, "size": f.stat().st_size})
            except Exception:
                pass
            return JSONResponse({"files": files})

        @app.get("/uploads/{filename}")
        async def download_file(filename: str, token: str = ""):
            # Auth via query param — browser <a download> can't send custom headers
            tok = token.strip()
            if not self._authorized(tok):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            safe = re.sub(r'[/\\]', '', filename)
            from core.path_policy import validate
            try: path = validate(self._uploads_dir / safe)
            except Exception:return JSONResponse({'error':'Forbidden'},status_code=403)
            if not path.exists() or not path.is_file():
                return JSONResponse({"error": "Not found"}, status_code=404)
            return FileResponse(str(path), filename=safe)

        @app.websocket("/ws")
        async def ws_ep(websocket: WebSocket, token: str = ""):
            tok = token.strip()
            if not self._authorized(tok):
                await websocket.close(code=4001)
                return
            if len(self._ws_tokens)>=16:
                await websocket.close(code=4008);return
            await websocket.accept()
            self._ws_tokens[websocket]=tok
            self._clients.add(websocket)
            for entry in self._history[-50:]:
                try:
                    await websocket.send_json(entry)
                except Exception:
                    break
            try:
                while True:
                    if not self._authorized(tok):break
                    try: raw = await asyncio.wait_for(websocket.receive_text(),timeout=1)
                    except asyncio.TimeoutError:continue
                    if not self._authorized(tok):break
                    if len(raw)>8192:
                        await websocket.close(code=1009);break
                    import json
                    try: data=json.loads(raw)
                    except (ValueError,TypeError,RecursionError):
                        await websocket.close(code=1003);break
                    if not isinstance(data,dict) or not isinstance(data.get('text',''),str) or not isinstance(data.get('enc',''),str):
                        await websocket.close(code=1003);break
                    if data.get("type") == "command":
                        enc = data.get("enc", "")
                        t   = self._decrypt(tok, enc) if enc else (data.get("text") or "").strip()
                        if t:
                            if len(t)>4096:
                                await websocket.send_json({'type':'error','text':'Command too long'});continue
                            try:self._command_queue.put_nowait(t)
                            except asyncio.QueueFull:
                                await websocket.send_json({'type':'error','text':'Command queue full'});continue
                            if self._wake_callback:
                                self._wake_callback()
            except WebSocketDisconnect:
                pass
            finally:
                self._clients.discard(websocket)
                self._ws_tokens.pop(websocket,None)
                try: await websocket.close(code=4001)
                except Exception: pass

        return app

    # ── serve ─────────────────────────────────────────────────────────────

    def _issue(self, token):
        now=time.time()
        for old in list(self._tokens):
            if self._token_expiry.get(old,0)<=now:
                self._tokens.discard(old);self._token_keys.pop(old,None);self._token_expiry.pop(old,None)
        if len(self._tokens)>=64:raise ValueError('Session limit reached')
        self._tokens.add(token);self._token_expiry[token]=now+3600

    def _authorized(self,token):
        return self._active and token in self._tokens and self._token_expiry.get(token,0)>time.time()

    async def invalidate(self,token):
        key=self._token_keys.pop(token,None)
        self._tokens.discard(token);self._token_expiry.pop(token,None)
        for ws,tok in list(self._ws_tokens.items()):
            if tok==token:
                self._clients.discard(ws);self._ws_tokens.pop(ws,None)
                try:await ws.close(code=4001)
                except Exception:pass
        if key:
            for device,record in list(self._device_sessions.items()):
                if record['session_key']==key:self._device_sessions.pop(device,None)
        if not self._tokens:
            while not self._command_queue.empty():self._command_queue.get_nowait()
            while not self._phone_audio_queue.empty():self._phone_audio_queue.get_nowait()

    async def revoke_all(self):
        for token in list(self._tokens):await self.invalidate(token)
        self._device_sessions.clear();self._pending_keys.clear();self._aes_cache.clear();self._history.clear()

    async def disable(self):
        self._active=False;await self.revoke_all()
        if self._server:self._server.should_exit=True

    async def serve(self):
        if not _DEPS_OK:
            print('[Dashboard] Optional dependencies unavailable.');return
        print('[Dashboard] Remote access OFF. Activate from the local Remote Control button.')
        while not self._active:await asyncio.sleep(.2)
        if not _ensure_certs():
            self._active=False;print('[Dashboard] TLS unavailable; remote service was not started.');return
        import ssl
        key=BASE_DIR/'config/certs/jarvis.key';cert=BASE_DIR/'config/certs/jarvis.crt'
        try:
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
        except Exception:
            self._active=False;print('[Dashboard] Invalid TLS key/certificate; service not started.');return
        cfg=uvicorn.Config(self.app,host='0.0.0.0',port=PORT,log_level='warning',access_log=False,
            ssl_keyfile=str(key),ssl_certfile=str(cert),ws_max_size=32768,limit_concurrency=8)
        self._server=uvicorn.Server(cfg)
        print('[Dashboard] Remote access ON with TLS. Firewall/network policy unchanged.')
        async def expiry():
            while self._active:
                for token in set(self._tokens) | set(self._ws_tokens.values()):
                    if not self._authorized(token):await self.invalidate(token)
                await asyncio.sleep(1)
        task=asyncio.create_task(expiry())
        try:await self._server.serve()
        finally:
            task.cancel();await asyncio.gather(task,return_exceptions=True)
            await self.disable()
