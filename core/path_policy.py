"""Application file capabilities. UI approval grants only the selected scope.

Not an OS sandbox: a malicious local process can race filesystem operations.
Symlinks and Windows reparse points are rejected, including inside copied trees.
"""
from pathlib import Path, PureWindowsPath
import os, re, threading

BASE = Path(__file__).resolve().parent.parent
DEFAULT_WORKSPACE = Path.home() / 'Documents' / 'JarvisWorkspace'
_PROTECTED_NAMES = {'.git', '.ssh', '.aws', '.azure', '.gnupg', '.env',
                    'api_keys.json', 'settings.json', 'credentials', '.jarvis-deps', '.venv', 'secrets.json'}
_RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$', re.I)
_lock = threading.RLock()
_scopes = [(DEFAULT_WORKSPACE, True)]

def validate_spelling(raw, relative=False):
    s = str(raw)
    if not s or '\x00' in s or any(ord(c)<32 for c in s):
        raise ValueError('Empty or invalid path')
    win = PureWindowsPath(s)
    if s.startswith(('\\\\', '//', '\\?\\', '\\.\\')):
        raise ValueError('UNC/device paths are not supported')
    if relative and (win.drive or win.root or Path(s).is_absolute()):
        raise ValueError('Project paths must be relative')
    parts = s.replace('\\','/').split('/')
    for i, part in enumerate(parts):
        if part == '..': raise ValueError('Traversal is not permitted')
        if part in ('', '.'): continue
        if ':' in part and not (i == 0 and re.fullmatch('[A-Za-z]:',part) and not relative):
            raise ValueError('Alternate data streams/drive-relative paths are forbidden')
        if part.endswith((' ','.')) or _RESERVED.match(part):
            raise ValueError('Ambiguous/reserved Windows filename')
        if any(c in part for c in '<>"|?*'): raise ValueError('Invalid filename')
    if win.drive and not win.root: raise ValueError('Drive-relative path forbidden')
    if os.name != 'nt' and (win.drive or '\\' in s):
        if win.drive: raise ValueError('Foreign absolute path forbidden')
    return s.replace('\\','/')

def _no_links(p):
    for a in [p, *p.parents]:
        if a.is_symlink() or (hasattr(a,'is_junction') and a.is_junction()):
            raise PermissionError('Symlinks/junctions are not permitted')
        if a.exists() and getattr(a.lstat(),'st_file_attributes',0) & 0x400:
            raise PermissionError('Reparse points are not permitted')

def _protected(p):
    if p == BASE or p in {BASE/'main.py',BASE/'ui.py',BASE/'setup.py'} or any(p.is_relative_to(BASE / n) for n in
        ('config','memory','plugins','core','actions','dashboard')):
        return True
    return any(part.lower() in _PROTECTED_NAMES or part.lower().startswith(('.env.', 'credentials.','client_secret')) for part in p.parts)

def grant(path, directory=False):
    """Trusted UI callback only. Never expose as a model parameter handler."""
    p=Path(validate_spelling(path)).expanduser().absolute(); _no_links(p); p=p.resolve()
    if _protected(p) or (directory and (p==Path(p.anchor) or Path.home().resolve().is_relative_to(p))):
        raise PermissionError('Cannot grant a machine/home/assistant sensitive scope')
    with _lock:
        if (p,directory) not in _scopes: _scopes.append((p,directory))
    return p

def validate(path, roots=None):
    from core.tasks import checkpoint
    checkpoint()
    p=Path(validate_spelling(path)).expanduser().absolute();_no_links(p);p=p.resolve()
    if _protected(p): raise PermissionError('Protected assistant/credential metadata')
    with _lock: scopes=list(_scopes) if roots is None else [(Path(r).resolve(),True) for r in roots]
    if not any(p == root or (folder and p.is_relative_to(root)) for root,folder in scopes):
        raise PermissionError('Outside approved workspace. Select a file/folder or approve a scope on the HUD.')
    return p

def project_path(root, relative):
    from core.tasks import checkpoint
    checkpoint()
    root=Path(root).expanduser().absolute();_no_links(root);root=root.resolve();s=validate_spelling(relative,relative=True)
    p=root/s;_no_links(p);p=p.resolve()
    if p == root or not p.is_relative_to(root) or _protected(p):
        raise PermissionError('Invalid/protected project destination')
    return p

def validate_tree(path):
    _no_links(Path(path))
    for base, dirs, files in os.walk(path,followlinks=False):
        for name in dirs+files:
            p=Path(base)/name;_no_links(p)
            if _protected(p): raise PermissionError('Tree contains protected metadata')


def default_workspace():
    """Return/create the currently approved default workspace, never a broad fallback."""
    root=validate(DEFAULT_WORKSPACE)
    root.mkdir(parents=True,exist_ok=True)
    return root
