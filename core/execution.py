"""Generated programs run only in an explicitly configured local Docker image.
The host process runner is reserved for trusted application commands/test fixtures.
See docs/EXECUTION_SECURITY.md. There is deliberately no host-code fallback.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
import os, re, shlex, shutil, signal, subprocess, tempfile, time, uuid, threading
from core import path_policy

@dataclass
class ExecutionResult:
    status: str
    exit_code: int|None=None
    stdout: str=''
    stderr: str=''
    timed_out: bool=False
    cancelled: bool=False
    duration: float=0.0
    verified: bool=False
    def __str__(self):
        import json
        return json.dumps(asdict(self),ensure_ascii=False)
    @property
    def succeeded(self): return self.status=='exited_successfully' and self.exit_code==0

def parse_command(command):
    if isinstance(command,list):
        if not command or not all(isinstance(x,str) and '\x00' not in x for x in command): raise ValueError('Arguments must be strings')
        return command
    if not isinstance(command,str): raise TypeError('Command must be a string or string array')
    # Commands inside the Linux container use POSIX parsing even on Windows.
    parts=shlex.split(command,posix=True)
    if not parts or any(x in {';','&&','||','|','>','<','&'} for x in parts): raise ValueError('Shell operators are not supported')
    return parts

def _terminate(p):
    if os.name=='nt': subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=5)
    else:
        try: os.killpg(p.pid,signal.SIGKILL)
        except ProcessLookupError: pass

def run_trusted(argv,cwd=None,timeout=30,cancel=None):
    start=time.monotonic();p=None
    cancel=cancel or current_cancel()
    try:
        argv=parse_command(argv)
        if cancel and cancel.is_set(): return ExecutionResult('cancelled',cancelled=True)
        p=subprocess.Popen(argv,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            start_new_session=os.name!='nt',creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
        buffers=[bytearray(),bytearray()]
        def drain(pipe,target):
            while True:
                chunk=pipe.read(4096)
                if not chunk: break
                if len(target)<128_000: target.extend(chunk[:128_000-len(target)])
            pipe.close()
        threads=[threading.Thread(target=drain,args=(pipe,b),daemon=True) for pipe,b in zip((p.stdout,p.stderr),buffers)]
        for t in threads:t.start()
        status=None
        while p.poll() is None:
            if cancel and cancel.is_set(): status='cancelled';_terminate(p);break
            if time.monotonic()-start>timeout: status='timed_out';_terminate(p);break
            time.sleep(.03)
        p.wait(timeout=5)
        for t in threads:t.join(timeout=1)
        return ExecutionResult(status or ('exited_successfully' if p.returncode==0 else 'failed'),p.returncode,
            buffers[0].decode('utf-8','replace'),buffers[1].decode('utf-8','replace'),status=='timed_out',status=='cancelled',time.monotonic()-start)
    except Exception as e:
        if p and p.poll() is None:_terminate(p)
        return ExecutionResult('failed',stderr=str(e),duration=time.monotonic()-start)

def current_cancel():
    try:
        from core.tasks import cancellation_event
        return cancellation_event()
    except ImportError: return None

def _image():
    image=os.environ.get('JARVIS_RUNNER_IMAGE','')
    if not re.fullmatch(r'[a-zA-Z0-9./:_-]+@sha256:[0-9a-f]{64}',image):
        return None,'Configure a reviewed Linux runner image pinned by SHA256 in JARVIS_RUNNER_IMAGE.'
    if not shutil.which('docker'): return None,'Docker isolation unavailable. Install Docker Desktop (optional) or keep generation/editing only.'
    check=run_trusted(['docker','image','inspect',image],timeout=10)
    if not check.succeeded: return None,'Runner image is not installed/daemon unavailable. No automatic pull or host execution.'
    return image,''

def _flags(name):
    return ['docker','run','--rm','--pull=never','--name',name,'--network=none','--read-only',
            '--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=64',
            '--memory=512m','--cpus=1','--user=65534:65534','--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
            '--workdir','/project']

def run_generated(command,project_dir,timeout=30,cancel=None):
    try:
        root=path_policy.validate(project_dir);path_policy.validate_tree(root);argv=parse_command(command)
        image,reason=_image()
        if not image:return ExecutionResult('unavailable',stderr=reason)
        name='jarvis-run-'+uuid.uuid4().hex
        # Copy only approved project contents; secrets/links/metadata are rejected.
        with tempfile.TemporaryDirectory(prefix='jarvis-isolated-') as d:
            stage=Path(d)/'project';shutil.copytree(root,stage);stage.chmod(0o755)
            for p in stage.rglob('*'):p.chmod(0o755 if p.is_dir() else 0o644)
            result=run_trusted(_flags(name)+['--mount',f'type=bind,src={stage},dst=/project,readonly',image]+argv,
                               timeout=min(max(int(timeout),1),300),cancel=cancel)
            if result.cancelled or result.timed_out:run_trusted(['docker','rm','-f',name],timeout=10,cancel=threading.Event())
            return result
    except Exception as e:return ExecutionResult('failed',stderr=str(e))

def propose_dependencies(dependencies,project_dir):
    from core.confirm import request
    from core.safe_files import write
    root=path_policy.validate(project_dir)
    if not isinstance(dependencies,list) or not all(isinstance(x,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9_.+-]+',x) for x in dependencies):
        return 'Dependency installation unavailable: supply reviewed distribution names with exact versions (name==version). Import names are never inferred.'
    if not dependencies:return 'No external dependencies requested.'
    # Persist the proposal, never install into the assistant interpreter.
    write(root/'jarvis-dependencies.txt','\n'.join(dependencies)+'\n',overwrite=False)
    return request('dependencies','Review project dependencies','\n'.join(dependencies)+'\nInstallation is not automatic. Use a separate project environment after review. This virtual environment is NOT a sandbox.',
                   lambda:'Dependency proposal reviewed. Create a project .venv and install the reviewed manifest manually; generated execution remains isolated/unverified.')
