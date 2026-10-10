"""Explicit project-relative dependency setup; never called at assistant runtime."""
import argparse
import subprocess
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
GROUPS = {name: HERE / "requirements" / (name + ".txt") for name in
          ("browser", "documents", "dashboard", "media", "windows", "test", "wake")}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extras", nargs="*", choices=sorted(GROUPS), default=[])
    parser.add_argument("--browsers", action="store_true", help="Explicitly download Chromium; requires browser extras")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without changing anything")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error("Python 3.11+ required; Python 3.12 is the version tested in this cloud environment")
    if not args.dry_run and sys.prefix == sys.base_prefix:
        parser.error("Create a virtual environment first. Windows: py -3.12 -m venv .venv; then .venv\\Scripts\\python.exe setup.py")
    if args.browsers and "browser" not in args.extras:
        parser.error("--browsers requires --extras browser")
    files = [HERE / "requirements-core.txt"] + [GROUPS[n] for n in dict.fromkeys(args.extras)]
    commands = [[sys.executable, "-m", "pip", "install", "-r", str(f)] for f in files]
    if args.browsers:
        commands.append([sys.executable, "-m", "playwright", "install", "chromium"])
    for command in commands:
        print(subprocess.list2cmdline(command))
        if not args.dry_run:
            subprocess.run(command, check=True, cwd=HERE)
    print("Dependency plan printed." if args.dry_run else "Requested dependencies installed. Run tools/diagnostics.py --audio before main.py; native hardware/account capabilities remain unverified.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
