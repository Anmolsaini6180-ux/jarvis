"""Optional existing-Node syntax/escaping check; no DOM, listener or network."""
import json,re,shutil,subprocess,tempfile
from pathlib import Path
node=shutil.which('node')
if not node:raise SystemExit('UNRUN: Node is optional and unavailable; no JavaScript check claimed.')
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='jarvis-js-smoke-') as scratch:
    for name in ['app.html','login.html']:
        source=(root/'dashboard/static'/name).read_text()
        blocks=re.findall(r'<script\b[^>]*>(.*?)</script>',source,re.S|re.I)
        target=Path(scratch)/(name+'.js');target.write_text('\n'.join(blocks),encoding='utf-8')
        subprocess.run([node,'--check',str(target)],check=True,timeout=10)
        assert 'chrome://flags' not in source
    app=(root/'dashboard/static/app.html').read_text()
    match=re.search(r'function esc\(s\)\s*\{(.*?)\n\s*\}',app,re.S)
    encoder='function esc(s) {'+match.group(1)+'}'
    malicious='\"\'><img src=x onerror=alert(1)>&'
    check=encoder+'\nconst output=esc('+json.dumps(malicious)+'); if(output.includes("<")||output.includes("\\\"")||output.includes("\\\'")) process.exit(1);'
    subprocess.run([node,'-e',check],check=True,timeout=10)
print('PASS: both dashboard inline scripts parse; actual HTML encoder escapes tag/attribute payloads; no insecure-origin bypass guide. No real browser/TLS test.')
