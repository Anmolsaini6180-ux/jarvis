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
        buttons=app._win.findChildren(ui.QPushButton)
        for label in ['START LISTENING','STOP LISTENING','TEST MICROPHONE (LOCAL)','TEST VOICE (WINDOWS SAPI)','RETRY PROVIDER']:
            assert any(button.text()==label for button in buttons)
        activations=[]
        app._win.on_start_listening=lambda:activations.append('start')
        next(button for button in buttons if button.text()=='START LISTENING').click()
        assert activations==['start']
        from PyQt6.QtTest import QTest
        from PyQt6.QtCore import Qt
        held=[];app._win.ptt_hold=held.append
        app._win._apply_ptt_shortcut(True)
        QTest.keyPress(app._win._input,Qt.Key.Key_Space,Qt.KeyboardModifier.ControlModifier)
        QTest.keyRelease(app._win._input,Qt.Key.Key_Space,Qt.KeyboardModifier.ControlModifier)
        app._app.processEvents()
        assert True in held and held[-1] is False,held
        app._win._apply_ptt_shortcut(False)
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
