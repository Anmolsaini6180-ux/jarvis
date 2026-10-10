"""Native OS credential protection. No insecure keyring/plaintext fallback."""
import ctypes,hashlib,json,os,re
from pathlib import Path
from core.safe_files import atomic_bytes
class CredentialUnavailable(RuntimeError):pass

class DPAPIStore:
    """Current-user Windows DPAPI; ciphertext files are not portable across users."""
    def __init__(self,directory):self.directory=Path(directory)
    def _crypt(self,data,decrypt=False):
        from ctypes import wintypes
        class BLOB(ctypes.Structure):_fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
        buf=(ctypes.c_ubyte*len(data)).from_buffer_copy(data);src=BLOB(len(data),buf);out=BLOB()
        crypt=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        name='CryptUnprotectData' if decrypt else 'CryptProtectData';fn=getattr(crypt,name)
        fn.argtypes=[ctypes.POINTER(BLOB),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(BLOB)];fn.restype=wintypes.BOOL
        kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
        if not fn(ctypes.byref(src),None,None,None,None,1,ctypes.byref(out)):
            raise CredentialUnavailable('Windows DPAPI protection failed')
        try:return ctypes.string_at(out.pbData,out.cbData)
        finally:kernel.LocalFree(out.pbData)
    def _path(self,name):return self.directory/(hashlib.sha256(name.encode()).hexdigest()+'.dpapi')
    def set(self,name,value):
        from core.redaction import register
        register(value)
        raw=value.encode();encrypted=self._crypt(raw)
        if self._crypt(encrypted,True)!=raw:raise CredentialUnavailable('DPAPI verification failed')
        atomic_bytes(self._path(name),encrypted)
    def get(self,name):
        try:return self._crypt(self._path(name).read_bytes(),True).decode()
        except FileNotFoundError:raise CredentialUnavailable('Protected credential is missing') from None

class KeyringStore:
    def __init__(self):
        try:
            import keyring
            backend=keyring.get_keyring()
            module=type(backend).__module__
            if not module.startswith(('keyring.backends.macOS','keyring.backends.SecretService','keyring.backends.kwallet')):
                raise CredentialUnavailable('A native OS keyring backend is required; insecure/fallback backends refused')
            self.keyring=keyring
        except ImportError:raise CredentialUnavailable('Install keyring and configure the native OS credential backend') from None
    def set(self,name,value):
        try:
            self.keyring.set_password('MarkLV',name,value)
            if self.keyring.get_password('MarkLV',name)!=value:raise CredentialUnavailable('Credential write verification failed')
        except Exception:raise CredentialUnavailable('OS keyring unavailable/locked') from None
    def get(self,name):
        try:value=self.keyring.get_password('MarkLV',name)
        except Exception:raise CredentialUnavailable('OS keyring unavailable/locked') from None
        if value is None:raise CredentialUnavailable('OS credential missing')
        from core.redaction import register
        register(value)
        return value

def backend(directory):return DPAPIStore(directory) if os.name=='nt' else KeyringStore()

def secret_field(name,ancestry=()):
    return 'plugin_config' in ancestry or bool(re.search(r'(api.?key|access.?key|secret|password|(?:^|_)token$)',name,re.I))

def protect(data,vault,prefix='config'):
    def walk(obj,parts):
        if isinstance(obj,dict):
            if set(obj)=={'$credential'}:return obj
            return {k:({'$credential':save('/'.join(parts+[k]),v)} if isinstance(v,str) and v and secret_field(k,parts) else walk(v,parts+[k])) for k,v in obj.items()}
        if isinstance(obj,list):return [walk(v,parts+[str(i)]) for i,v in enumerate(obj)]
        return obj
    def save(name,value):
        import uuid
        from core.redaction import register
        register(value)
        name=name+'/'+uuid.uuid4().hex
        vault.set(name,value);return name
    return walk(data,[prefix])

def resolve(data,vault):
    if isinstance(data,dict):
        if set(data)=={'$credential'}:
            value=vault.get(data['$credential'])
            from core.redaction import register
            register(value)
            return value
        return {k:resolve(v,vault) for k,v in data.items()}
    if isinstance(data,list):return [resolve(v,vault) for v in data]
    return data

def has_plaintext(data,parts=()):
    if isinstance(data,dict):
        return any((isinstance(v,str) and bool(v) and secret_field(k,parts)) or has_plaintext(v,parts+(k,)) for k,v in data.items() if k!='$credential')
    if isinstance(data,list):return any(has_plaintext(v,parts) for v in data)
    return False
