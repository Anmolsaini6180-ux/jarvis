"""Offscreen startup/shutdown without credentials, hardware or provider transport."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QTimer
from memory import config_manager as cm,memory_manager as mm
with tempfile.TemporaryDirectory(prefix='jarvis-runtime-smoke-') as temporary:
    root=Path(temporary)
    with patch.object(cm,'CONFIG_DIR',root/'config'),patch.object(cm,'CONFIG_FILE',root/'config/settings.json'),patch.object(mm,'MEMORY_PATH',root/'memory.json'):
        import main,ui
        ui.HAVE_VIDEO=False
        app=ui.JarvisUI('core/face_model.obj')
        QTimer.singleShot(1500,app._app.quit)
        with patch('main.JarvisUI',return_value=app),patch('main.sd',None),patch('main.audio_devices.prefetch'),patch('dashboard.server.DashboardServer',side_effect=ImportError('excluded from smoke')):
            main.main()
        app._app.processEvents()
        assert app._win.hud.state=='STOPPED',app._win.hud.state
        print('PASS: real entry point initialized and shut down cleanly without a credential. Audio/phone hardware excluded; no provider request made.')
