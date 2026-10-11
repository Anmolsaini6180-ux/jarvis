"""Actual bundled JavaScript encryption to Python decryption; no browser/network."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.redaction import install
install()

def main():
    node=shutil.which('node')
    if not node:
        print('SKIPPED: Node unavailable; dashboard cryptography interop not executed.')
        return 0
    root=Path(__file__).resolve().parents[1]
    html=(root/'dashboard/static/app.html').read_text()
    match=re.search(r'function _encrypt\(plaintext\)\s*\{(.*?)\n    \}',html,re.S)
    if not match:raise RuntimeError('Dashboard encryption function missing')
    token='DUMMY_TEST_TOKEN_NOT_A_REAL_SESSION_0123456789'
    script='const CryptoJS=require('+json.dumps(str(root/'dashboard/static/crypto-js.min.js'))+');\n'
    script+='const _authToken='+json.dumps(token)+"; const _aesKey=CryptoJS.SHA256(_authToken+'JARVIS-DASHBOARD-v1'); let _commandSequence=Date.now()*1000;\n"
    script+='function _encrypt(plaintext) {'+match.group(1)+'\n}\nconsole.log(JSON.stringify(_encrypt("Hello हिंदी test")));'
    result=subprocess.run([node,'-e',script],capture_output=True,text=True,check=True,timeout=10)
    envelope=json.loads(result.stdout)
    from dashboard.server import DashboardServer
    server=DashboardServer()
    server._issue(token)
    assert server._decrypt(token,envelope)=='Hello हिंदी test'
    assert server._decrypt(token,envelope) is None
    second=json.loads(subprocess.run([node,'-e',script.replace('Hello हिंदी test','Another test')],capture_output=True,text=True,check=True,timeout=10).stdout)
    changed=second[:-1]+('0' if second[-1]!='0' else '1')
    assert server._decrypt(token,changed) is None
    print('PASS: actual bundled CryptoJS envelope decrypted by Python; Unicode, MAC tampering and replay verified. No physical browser/TLS validation.')
    return 0

if __name__=='__main__':raise SystemExit(main())
