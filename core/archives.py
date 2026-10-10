"""Bounded ZIP/TAR extraction into a new directory; no links/devices/collisions."""
import os, shutil, stat, tarfile, tempfile, zipfile
from pathlib import Path
from core import path_policy
MAX_FILES=2000
MAX_TOTAL=256*1024*1024
MAX_MEMBER=64*1024*1024

def extract_bounded(source,destination):
    source=path_policy.validate(source);dest=path_policy.validate(destination)
    if dest.exists():raise FileExistsError('Extraction destination exists; no files overwritten')
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.jarvis-extract-',dir=dest.parent) as tmp:
        root=Path(tmp);seen=set();total=0
        def target(name,size):
            nonlocal total
            p=path_policy.project_path(root,name);key=str(p.relative_to(root)).casefold()
            if key in seen:raise ValueError('Duplicate archive destination')
            seen.add(key);total+=size
            if len(seen)>MAX_FILES or size>MAX_MEMBER or total>MAX_TOTAL:raise ValueError('Archive exceeds extraction limits')
            return p
        def copy(stream,p,size):
            p.parent.mkdir(parents=True,exist_ok=True);count=0
            with p.open('xb') as out:
                while True:
                    b=stream.read(65536)
                    if not b:break
                    count+=len(b)
                    if count>size or count>MAX_MEMBER:raise ValueError('Decompression limit exceeded')
                    out.write(b)
        if zipfile.is_zipfile(source):
            with zipfile.ZipFile(source) as z:
                for i in z.infolist():
                    if stat.S_ISLNK(i.external_attr>>16) or i.flag_bits & 1:raise ValueError('Links/encrypted members forbidden')
                    if i.file_size>max(i.compress_size,1)*200:raise ValueError('Suspicious compression ratio')
                    p=target(i.filename.rstrip('/'),i.file_size)
                    if i.is_dir():p.mkdir(parents=True,exist_ok=True)
                    else:
                        with z.open(i) as f:copy(f,p,i.file_size)
        else:
            with tarfile.open(source,'r:*') as t:
                for i in t:
                    if not (i.isfile() or i.isdir()):raise ValueError('Archive links/devices/special members forbidden')
                    p=target(i.name.rstrip('/'),i.size)
                    if i.isdir():p.mkdir(parents=True,exist_ok=True)
                    else:
                        with t.extractfile(i) as f:copy(f,p,i.size)
        # no partial extraction is published on validation failure
        if dest.exists():raise FileExistsError('Extraction collision')
        os.rename(root,dest)
    return dest
