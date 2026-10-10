"""Atomic mutations, disk recovery journal and conflict-aware file undo."""
from pathlib import Path
import hashlib, json, os, shutil, tempfile, threading, uuid
from core import path_policy
from core.undo import push_undo
RECOVERY = path_policy.BASE / 'config' / 'recovery'
LOCK = threading.RLock()

class UndoConflict(RuntimeError): pass

def fingerprint(path):
    p=Path(path)
    if not p.exists(): return None
    path_policy.validate_tree(p) if p.is_dir() else path_policy._no_links(p)
    h=hashlib.sha256()
    if p.is_dir():
        for item in sorted(p.rglob('*')):
            h.update(str(item.relative_to(p)).encode());h.update(b'D' if item.is_dir() else b'F')
            if item.is_file(): h.update(bytes.fromhex(fingerprint(item)))
    else:
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    st=p.stat();h.update(str((st.st_mtime_ns,st.st_size)).encode())
    return h.hexdigest()

def atomic_bytes(path, data, overwrite=True):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.jarvis-write-',dir=p.parent)
    try:
        with os.fdopen(fd,'wb') as f: f.write(data);f.flush();os.fsync(f.fileno())
        if overwrite: os.replace(tmp,p)
        else: os.link(tmp,p);os.unlink(tmp)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def snapshot(path):
    p=Path(path); RECOVERY.mkdir(parents=True,exist_ok=True)
    folder=RECOVERY/uuid.uuid4().hex;folder.mkdir()
    before=fingerprint(p)
    if before is not None:
        if p.is_dir(): shutil.copytree(p,folder/'data',copy_function=shutil.copy2)
        else: shutil.copy2(p,folder/'data')
        if fingerprint(p)!=before: raise UndoConflict('File changed while creating recovery snapshot; no mutation made')
    atomic_bytes(folder/'manifest.json',json.dumps({'path':str(p),'before':before,'state':'prepared'}).encode())
    return folder

def _record(folder,path,expected):
    m=json.loads((folder/'manifest.json').read_text());m.update(after=expected,state='applied')
    atomic_bytes(folder/'manifest.json',json.dumps(m).encode())

def restore(path,folder,expected,validator=path_policy.validate):
    with LOCK:
        p=validator(path)
        if fingerprint(p)!=expected: raise UndoConflict('Newer changes preserved; recovery copy remains at '+str(folder))
        data=folder/'data'
        if p.is_dir(): shutil.rmtree(p)
        elif p.exists(): p.unlink()
        if data.is_dir(): shutil.copytree(data,p)
        elif data.exists(): atomic_bytes(p,data.read_bytes(),overwrite=False);shutil.copystat(data,p)
        return 'Previous state restored.'

def write(path,content,overwrite=True,append=False,validator=path_policy.validate):
    with LOCK:
        p=validator(path)
        if p.exists() and not p.is_file(): raise ValueError('Destination is not a regular file')
        if p.exists() and not overwrite: raise FileExistsError('Collision: existing data preserved')
        folder=snapshot(p) # failure prevents any write, including large writes
        data=content.encode('utf-8') if isinstance(content,str) else content
        if append and p.exists(): data=p.read_bytes()+data
        validator(p);atomic_bytes(p,data,overwrite=overwrite)
        expected=fingerprint(p);_record(folder,p,expected)
        push_undo('wrote '+p.name,lambda:restore(p,folder,expected,validator))
        return p

def copy(src,dst,validator=path_policy.validate):
    with LOCK:
        src=validator(src);dst=validator(dst)
        if dst.exists(): raise FileExistsError('Collision: existing destination preserved')
        path_policy.validate_tree(src)
        folder=snapshot(dst);dst.parent.mkdir(parents=True,exist_ok=True)
        if src.is_dir(): shutil.copytree(src,dst)
        else: atomic_bytes(dst,src.read_bytes(),overwrite=False)
        expected=fingerprint(dst);_record(folder,dst,expected)
        push_undo('copied '+src.name,lambda:restore(dst,folder,expected,validator))
        return dst

def move(src,dst,validator=path_policy.validate):
    with LOCK:
        src=validator(src);dst=validator(dst)
        if dst.exists(): raise FileExistsError('Collision: existing destination preserved')
        path_policy.validate_tree(src)
        folder=snapshot(src);dst.parent.mkdir(parents=True,exist_ok=True)
        validator(src);validator(dst);shutil.move(str(src),str(dst));expected=fingerprint(dst)
        _record(folder,dst,expected)
        def undo():
            with LOCK:
                validator(src);validator(dst)
                if src.exists() or fingerprint(dst)!=expected: raise UndoConflict('Newer changes preserved. Snapshot: '+str(folder))
                shutil.move(str(dst),str(src));return 'Moved back.'
        push_undo('moved '+src.name,undo)
        return dst
