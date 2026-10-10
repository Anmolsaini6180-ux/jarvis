"""Compatibility diagnostic API. Runtime never mutates the assistant environment."""
import importlib.util

def _available(module):
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False

def _pip(package, log=None):
    if log:
        log("Runtime installation refused. Review requirements and run setup.py inside the assistant virtual environment.")
    return False

def install_for_config(config, log=None):
    missing = [name for name in ("PyQt6", "numpy", "sounddevice", "google.genai") if not _available(name)]
    if log:
        log("Missing imports: " + ", ".join(missing) if missing else "Core modules found; hardware and accounts are not verified.")
        if config.get("stt_engine") or config.get("tts_engine"):
            log("Local engine settings do not implement an offline conversation pipeline. No packages installed automatically.")
    return missing
