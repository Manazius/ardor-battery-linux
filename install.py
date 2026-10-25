#!/usr/bin/env python3
"""Install per-user launchers for this checkout. Does not install dependencies or udev."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys


def systemd_quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def desktop_quote(value):
    # Desktop Entry string escaping followed by Exec argument escaping.
    argument = '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
    return argument.replace('\\', '\\\\')


def render(root, python):
    service = (root / 'systemd/ardor-battery.service').read_text()
    service = service.replace('@PYTHON@', systemd_quote(python)).replace('@ROOT@', systemd_quote(root))
    service = service.replace('@TRAY@', systemd_quote(root / 'ardor_tray.py'))
    desktop = (root / 'desktop/ardor-battery.desktop').read_text()
    desktop = desktop.replace('@PYTHON@', desktop_quote(python)).replace('@TRAY@', desktop_quote(root / 'ardor_tray.py'))
    launcher = '#!/bin/sh\nexec ' + shlex.quote(str(python)) + ' ' + shlex.quote(str(root / 'ardor_tray.py')) + ' "$@"\n'
    return service, desktop, launcher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable', action='store_true', help='Enable and restart the user service after installation')
    parser.add_argument('--dry-run', action='store_true', help='Print generated service and desktop entry without writing files')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    # Do not resolve the venv interpreter symlink: that would bypass the venv.
    python = Path(sys.executable).absolute()
    service, desktop, launcher = render(root, python)
    if args.dry_run:
        print(service + '\n' + desktop + '\n' + launcher)
        return 0
    if os.geteuid() == 0:
        parser.error('Run as your desktop user, without sudo.')
    if args.enable:
        try:
            import PySide6.QtWidgets  # noqa: F401
        except ImportError:
            parser.error('Install requirements-tray.txt in this interpreter first.')
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
    targets = [(config / 'systemd/user/ardor-battery.service', service),
               (data / 'applications/ardor-battery.desktop', desktop),
               (Path.home() / '.local/bin/ardor-battery', launcher)]
    for path, content in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        if path.name == 'ardor-battery':
            path.chmod(0o755)
        print(f'Installed: {path}')
    if args.enable:
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', '--user', 'enable', 'ardor-battery.service'], check=True)
        subprocess.run(['systemctl', '--user', 'restart', 'ardor-battery.service'], check=True)
    else:
        print('To start at login: systemctl --user daemon-reload && systemctl --user enable --now ardor-battery.service')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'Installation failed: {exc}', file=sys.stderr)
        raise SystemExit(2)
