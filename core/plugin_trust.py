"""Review gate BEFORE imports; hash the entire Python plugin bundle including helpers.
Trust is a user decision, not a sandbox. Changes require renewed review.
"""
import hashlib
from pathlib import Path
from core import storage
BASE=Path(__file__).resolve().parent.parent
TRUST_FILE=BASE/'config/plugin_trust.json'

def bundle_digest(directory):
    h=hashlib.sha256()
    root=Path(directory).resolve()
    for p in sorted(root.rglob('*.py')):
        if p.is_symlink() or not p.resolve().is_relative_to(root):raise ValueError('Plugin links refused')
        h.update(str(p.relative_to(root)).encode());h.update(p.read_bytes())
    return h.hexdigest()

def trusted(path):
    p=Path(path)
    return storage.read(TRUST_FILE,{}).get(p.name)==bundle_digest(p.parent)

def approve(path):
    p=Path(path).resolve()
    if not p.is_file() or p.suffix!='.py':raise ValueError('Select an existing plugin Python file')
    digest=bundle_digest(p.parent)
    storage.update(TRUST_FILE,lambda data:data.__setitem__(p.name,digest))
    return 'Plugin bundle trusted. Restart after reviewing all helpers; it runs with your account permissions.'

def request_review(filename):
    from core import confirm
    p=BASE/'plugins'/Path(filename).name
    digest=bundle_digest(p.parent)
    def reviewed():
        if bundle_digest(p.parent)!=digest:return 'Plugin bundle changed; review again. Nothing imported.'
        return approve(p)
    return confirm.request('plugin-trust','Trust plugin Python code',
        f'{p}\nBundle SHA256: {digest}\nReview this file and ALL plugin helpers before confirming. Importing executes code with your account permissions. This is NOT a sandbox. Restart is required.',reviewed)
