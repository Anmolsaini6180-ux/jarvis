"""Offscreen HUD smoke test with disposable settings; no devices/accounts touched."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from memory import config_manager as cm,memory_manager as mm
from PyQt6.QtWidgets import QPlainTextEdit
with tempfile.TemporaryDirectory(prefix='jarvis-ui-smoke-') as scratch:
    root=Path(scratch)
    with patch.object(cm,'CONFIG_DIR',root/'config'),patch.object(cm,'CONFIG_FILE',root/'config/settings.json'),patch.object(mm,'MEMORY_PATH',root/'memory.json'):
        import ui
        ui.HAVE_VIDEO=False  # no multimedia/audio hardware claim
        from core import confirm
        app=ui.JarvisUI(str(Path(__file__).resolve().parents[1]/'core/face_model.obj'))
        app.set_task_status('Task smoke-id · probe · cancelled')
        app._app.processEvents()
        assert 'cancelled' in app._win._task_status.text()
        assert 'STOP / CANCEL' in app._win._interrupt_btn.text()
        assert app._win.findChildren(ui.QPushButton)
        stops=[];app._win.on_interrupt=lambda:stops.append('stop')
        app._win._interrupt_btn.click();app._app.processEvents()
        assert stops==['stop']
        escape=[sc for sc in app._win.findChildren(ui.QShortcut) if sc.key().matches(ui.QKeySequence('Escape'))==ui.QKeySequence.SequenceMatch.ExactMatch][0]
        escape.activated.emit();app._app.processEvents()
        assert len(stops)==2
        detail='Recipient: fake@example.test\n\n<untrusted plain text>\n'+'हैलो / hello '*350
        app.show_confirm('Review fake draft',detail)
        app._app.processEvents()
        review=app._win._confirm_overlay.findChild(QPlainTextEdit)
        assert review.isReadOnly() and review.toPlainText()==detail
        assert '<untrusted plain text>' in review.toPlainText()
        app.hide_confirm();app._app.processEvents()
        app._win.close();app._app.quit()
        print('PASS: HUD/avatar construction, task status, STOP control and full Unicode/plain-text confirmation. Video/audio excluded; no cloud account connection.')
