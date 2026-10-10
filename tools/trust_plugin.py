"""Local user CLI only: review all plugin Python files, then explicitly trust a bundle."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.plugin_trust import approve,bundle_digest
p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--reviewed',action='store_true');a=p.parse_args()
print('Bundle digest:',bundle_digest(Path(a.file).parent))
if not a.reviewed:p.error('Read every plugin/helper first, then pass --reviewed. Plugins execute as your account.')
print(approve(a.file))
