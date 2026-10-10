"""Locked JSON transactions with atomic replacement and recoverable backups.
All writers must use this API. Locks cover threads and local processes.
"""
import copy,json,os,threading,uuid,warnings
from pathlib import Path
from contextlib import contextmanager
from core.safe_files import atomic_bytes
_locks={};_guard=threading.Lock();_local=threading.local()
class StateCorrupt(RuntimeError):pass

@contextmanager
def transaction(path):
    p=Path(path).resolve();key=str(p)
    with _guard:lock=_locks.setdefault(key,threading.RLock())
    with lock:
        held=getattr(_local,'held',{})
        if key in held:
            yield;return
        p.parent.mkdir(parents=True,exist_ok=True)
        with (p.parent/(p.name+'.lock')).open('a+b') as f:
            if os.name=='nt':
                import msvcrt
                f.seek(0);f.write(b'0');f.flush();f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_LOCK,1)
            else:
                import fcntl
                fcntl.flock(f.fileno(),fcntl.LOCK_EX)
            held[key]=True;_local.held=held
            try:yield
            finally:
                held.pop(key,None)
                if os.name=='nt':
                    f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.flock(f.fileno(),fcntl.LOCK_UN)

def _decode(raw):
    obj=json.loads(raw.decode('utf-8'))
    if not isinstance(obj,dict):raise ValueError('JSON root must be an object')
    return obj

def _read(path,default):
    p=Path(path)
    if not p.exists():return copy.deepcopy(default)
    try:return _decode(p.read_bytes())
    except (ValueError,UnicodeError):
        backup=p.with_name(p.name+'.bak')
        try:data=_decode(backup.read_bytes())
        except (OSError,ValueError,UnicodeError):raise StateCorrupt(f'Invalid state at {p.name}; no valid backup. Original preserved; repair/import a known-good copy.') from None
        corrupt=p.with_name(p.name+'.corrupt-'+uuid.uuid4().hex)
        atomic_bytes(corrupt,p.read_bytes());atomic_bytes(p,backup.read_bytes())
        warnings.warn(f'Recovered {p.name} from last valid backup; damaged copy retained as {corrupt.name}',RuntimeWarning)
        return data

def read(path,default=None):
    with transaction(path):return _read(path,default if default is not None else {})

def _write(path,data,backup=True):
    p=Path(path);raw=json.dumps(data,indent=2,ensure_ascii=False).encode('utf-8')
    _decode(raw)
    if p.exists():
        _read(p,{}) # do not blindly replace corrupt state
        if backup:atomic_bytes(p.with_name(p.name+'.bak'),p.read_bytes())
    atomic_bytes(p,raw)

def write(path,data,backup=True):
    with transaction(path):_write(path,data,backup)
    return copy.deepcopy(data)

def update(path,mutate,default=None):
    with transaction(path):
        obj=_read(path,default if default is not None else {})
        result=mutate(obj)
        _write(path,obj)
        return copy.deepcopy(obj),result
