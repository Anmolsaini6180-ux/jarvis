"""Actual SDK configuration smoke with disposable settings and no API requests."""
import sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from memory import config_manager as cm,memory_manager as mm
with tempfile.TemporaryDirectory(prefix='jarvis-sdk-smoke-') as scratch:
    root=Path(scratch)
    with patch.object(cm,'CONFIG_DIR',root/'config'),patch.object(cm,'CONFIG_FILE',root/'config/settings.json'),patch.object(mm,'MEMORY_PATH',root/'memory.json'):
        import main
        from core.action_loader import discover_actions
        from google.genai import types
        registry=discover_actions(Path(__file__).resolve().parents[1]/'actions',logger=lambda msg:None)
        for declaration in registry.get_tool_declarations():types.FunctionDeclaration(**declaration)
        obj=SimpleNamespace(_action_registry=registry,_plugin_registry=SimpleNamespace(get_tool_declarations=lambda:[]),
                            _resume_handle=None,_enhanced_live=False,_tuned_live=False)
        obj._tuning_config=lambda:main.JarvisLive._tuning_config(obj)
        for enhanced,tuned in [(False,False),(False,True),(True,True)]:
            obj._enhanced_live=enhanced;obj._tuned_live=tuned
            config=main.JarvisLive._build_config(obj)
            assert isinstance(config,types.LiveConnectConfig)
            print(f'PASS: actual LiveConnectConfig; enhanced={enhanced}, tuned={tuned}, tools={len(config.tools[0].function_declarations)}. No API request.')
