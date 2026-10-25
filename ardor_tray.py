#!/usr/bin/env python3
"""ARDOR battery tray for KDE Plasma 6. Run as the desktop user."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

from tray_state import Alerts, Sample
from i18n import translate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interval', type=int, default=30, help='Polling interval in seconds (minimum 10)')
    parser.add_argument('--timeout', type=float, default=0.8, help='USB response timeout, 0.1–10 seconds')
    parser.add_argument('--language', choices=('auto', 'en', 'ru'), help='Override saved UI language for this run')
    args = parser.parse_args()
    if args.interval < 10 or not 0.1 <= args.timeout <= 10:
        parser.error('--interval >= 10; --timeout between 0.1 and 10')
    try:
        from PySide6.QtCore import QProcess, QSettings, Qt, QTimer
        from PySide6.QtGui import QActionGroup, QFont, QIcon, QPainter, QPalette, QPixmap
        from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon
    except ImportError:
        print(f'Install Qt with:\n{sys.executable} -m pip install -r '
              f'{Path(__file__).with_name("requirements-tray.txt")}', file=sys.stderr)
        return 2

    # flock is released by the kernel on exit; a stale file cannot block restart.
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', tempfile.gettempdir()))
    lock_fd = os.open(runtime / f'ardor-battery-tray-{os.getuid()}.lock',
                      os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        print('ARDOR tray is already running.', file=sys.stderr)
        return 1

    app = QApplication([sys.argv[0]])
    app.setApplicationName('ARDOR Battery')
    app.setDesktopFileName('ardor-battery')
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print('System tray unavailable. Run inside your KDE Plasma session.', file=sys.stderr)
        os.close(lock_fd)
        return 2

    class Tray:
        def __init__(self):
            self.sample = None
            self.error = None
            self.waiting = True
            self.busy = False
            self.closing = False
            self.details = None
            self.alerts = Alerts()
            self.settings = QSettings('ardor-community', 'battery-tray')
            self.language = args.language or self.settings.value('language', 'auto')
            self.tray = QSystemTrayIcon(app)
            self.menu = QMenu()
            self.status = self.menu.addAction('Ожидание ответа…')
            self.status.setEnabled(False)
            self.refresh_action = self.menu.addAction('Обновить сейчас')
            self.refresh_action.triggered.connect(self.refresh)
            self.details_action = self.menu.addAction('Подробности…')
            self.details_action.triggered.connect(self.show_details)
            self.menu.addSeparator()
            self.notifications = self.menu.addAction('Уведомлять о низком заряде')
            self.notifications.setCheckable(True)
            self.notifications.setChecked(self.settings.value('notifications', False, type=bool))
            self.notifications.toggled.connect(self.set_notifications)
            self.menu.addSeparator()
            self.language_menu = self.menu.addMenu('Language')
            self.language_group = QActionGroup(self.menu)
            self.language_actions = {}
            for code, label in [('auto', 'System default'), ('en', 'English'), ('ru', 'Русский')]:
                action = self.language_menu.addAction(label)
                action.setCheckable(True)
                action.setChecked(code == self.language)
                self.language_group.addAction(action)
                action.triggered.connect(lambda checked=False, code=code: self.set_language(code))
                self.language_actions[code] = action
            self.quit_action = self.menu.addAction('Выход')
            self.quit_action.triggered.connect(app.quit)
            self.tray.setContextMenu(self.menu)
            self.tray.activated.connect(self.activated)
            self.process = QProcess(app)
            self.process.finished.connect(self.finished)
            self.process.errorOccurred.connect(self.process_error)
            self.watchdog = QTimer(app)
            self.watchdog.setSingleShot(True)
            self.watchdog.timeout.connect(self.expired)
            self.timer = QTimer(app)
            self.timer.setInterval(args.interval * 1000)
            self.timer.timeout.connect(self.refresh)
            self.timer.start()
            app.paletteChanged.connect(lambda *_: self.render())
            self.render()
            self.tray.show()
            QTimer.singleShot(0, self.refresh)

        def icon(self):
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            valid = self.sample is not None and self.error is None and not self.waiting
            group = QPalette.ColorGroup.Active if valid else QPalette.ColorGroup.Disabled
            painter.setPen(app.palette().color(group, QPalette.ColorRole.WindowText))
            font = QFont('sans-serif')
            font.setBold(True)
            font.setPixelSize(35 if valid and self.sample.percent == 100 else 43)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter,
                             str(self.sample.percent) if valid else '?')
            painter.end()
            return QIcon(pixmap)

        def text(self):
            lines = ['ARDOR GAMING Phantom PRO V2']
            if self.waiting:
                lines.append(self.t('Ожидание первого ответа'))
            if self.error:
                lines.append(self.t('Нет актуального показания'))
                lines.append(self.error)
            if self.sample:
                prefix = self.t('Последнее успешное чтение: ' if self.error else 'Заряд: ')
                lines.append(f'{prefix}{self.sample.percent}% — {self.t(self.sample.mode)}')
                lines.append(self.t('Получено: ') + time.strftime('%H:%M:%S', time.localtime(self.sample.timestamp)))
                lines.append(self.t('Кабель: ') + self.t('подключён' if self.sample.cable else 'не отмечен устройством'))
            if self.busy:
                lines.append(self.t('Обновление…'))
            return '\n'.join(lines)

        def render(self):
            self.tray.setIcon(self.icon())
            self.tray.setToolTip(self.text())
            self.refresh_action.setText(self.t('Обновить сейчас'))
            self.details_action.setText(self.t('Подробности…'))
            self.notifications.setText(self.t('Уведомлять о низком заряде'))
            self.quit_action.setText(self.t('Выход'))
            self.language_menu.setTitle(self.t('Язык'))
            self.language_actions['auto'].setText(self.t('Как в системе'))
            status = (self.t('Ожидание ответа…') if self.waiting else
                      self.t('Нет ответа') if self.error else
                      f'{self.sample.percent}% · {self.t(self.sample.mode)}')
            self.status.setText(status)
            self.refresh_action.setEnabled(not self.busy)
            if self.details is not None:
                self.details.setWindowTitle(self.t('Батарея ARDOR'))
                self.details.setText(self.text())

        def refresh(self):
            if self.busy or self.closing:
                return
            self.busy = True
            self.render()
            self.process.start(sys.executable, [str(Path(__file__).with_name('ardor.py')),
                                                '--read', '--json', '--timeout', str(args.timeout)])
            self.watchdog.start(int((args.timeout + 5) * 1000))

        def fail(self, message):
            self.waiting = False
            self.error = message
            self.alerts.reset_confirmation()
            self.render()
            print(message, file=sys.stderr, flush=True)

        def finished(self, exit_code, exit_status):
            self.watchdog.stop()
            if self.closing:
                return
            self.busy = False
            stdout = bytes(self.process.readAllStandardOutput()).decode('utf-8', errors='replace')
            stderr = bytes(self.process.readAllStandardError()).decode('utf-8', errors='replace').strip()
            if exit_code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
                self.fail(stderr or self.t('Процесс чтения завершился с ошибкой'))
                return
            try:
                self.sample = Sample.from_json(json.loads(stdout))
            except (ValueError, TypeError) as exc:
                self.fail(self.t('Некорректный ответ процесса чтения: ') + str(exc))
                return
            self.waiting = False
            self.error = None
            self.render()
            if self.notifications.isChecked():
                level = self.alerts.update(self.sample)
                if level is not None:
                    self.tray.showMessage(self.t('Низкий заряд мыши ARDOR'),
                                          self.t('Мышь сообщает {percent}%. Подключите кабель.').format(percent=self.sample.percent),
                                          QSystemTrayIcon.MessageIcon.Warning, 8000)

        def process_error(self, error):
            if self.closing:
                return
            if error == QProcess.ProcessError.FailedToStart:
                self.watchdog.stop()
                self.busy = False
                self.fail(self.t('Не удалось запустить чтение: ') + self.process.errorString())

        def expired(self):
            self.fail(self.t('Истёк общий таймаут процесса чтения'))
            self.process.kill()  # finished handles cleanup; no overlapping request.

        def activated(self, reason):
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                self.show_details()

        def show_details(self):
            if self.details is None:
                self.details = QMessageBox()
                self.details.setWindowTitle(self.t('Батарея ARDOR'))
                self.details.setIcon(QMessageBox.Icon.Information)
                self.details.setStandardButtons(QMessageBox.StandardButton.Ok)
            self.details.setText(self.text())
            self.details.show()
            self.details.raise_()
            self.details.activateWindow()

        def t(self, text):
            return translate(text, self.language)

        def set_language(self, language):
            self.language = language
            self.settings.setValue('language', language)
            self.render()

        def set_notifications(self, enabled):
            self.settings.setValue('notifications', enabled)
            self.alerts = Alerts()

        def close(self):
            self.closing = True
            self.timer.stop()
            self.watchdog.stop()
            if self.process.state() != QProcess.ProcessState.NotRunning:
                # Normal CLI exchange is bounded; allow it to close its HID worker.
                if not self.process.waitForFinished(3500):
                    self.process.kill()
                    self.process.waitForFinished(500)
            self.tray.hide()
            if self.details:
                self.details.close()

    controller = Tray()
    app.aboutToQuit.connect(controller.close)
    # Give the interpreter opportunities to handle terminal SIGINT/SIGTERM.
    signal_timer = QTimer(app)
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(250)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    try:
        return app.exec()
    finally:
        os.close(lock_fd)


if __name__ == '__main__':
    raise SystemExit(main())
