"""Run manually with QT_QPA_PLATFORM=offscreen; never starts a USB query."""
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run():
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon
    import ardor_tray

    seen = []

    def verify():
        tray = seen[0]
        menu = tray.contextMenu()
        assert any(a.text() == 'Refresh now' for a in menu.actions())
        language = next(a.menu() for a in menu.actions() if a.text() == 'Language')
        next(a for a in language.actions() if a.text() == 'Русский').trigger()
        assert any(a.text() == 'Обновить сейчас' for a in menu.actions())
        assert any(a.text() == 'Язык' for a in menu.actions())
        assert 'Ожидание первого ответа' in tray.toolTip()
        assert not tray.icon().isNull()
        assert tray.icon().pixmap(64, 64).toImage().pixelColor(0, 0).alpha() == 0
        QApplication.instance().aboutToQuit.emit()
        return 0

    with tempfile.TemporaryDirectory() as directory, \
            patch.dict(os.environ, {'QT_QPA_PLATFORM': 'offscreen', 'XDG_CONFIG_HOME': directory,
                                    'XDG_RUNTIME_DIR': directory}), \
            patch.object(sys, 'argv', ['ardor_tray.py', '--language', 'en']), \
            patch.object(QSystemTrayIcon, 'isSystemTrayAvailable', return_value=True), \
            patch.object(QSystemTrayIcon, 'show', lambda self: seen.append(self)), \
            patch('PySide6.QtCore.QTimer.singleShot'), \
            patch('PySide6.QtCore.QProcess.start', side_effect=AssertionError('USB query in GUI test')), \
            patch.object(QApplication, 'exec', side_effect=verify):
        assert ardor_tray.main() == 0
    print('GUI smoke passed: startup, English/Russian switch, transparent icon; no USB queries.')


if __name__ == '__main__':
    run()
