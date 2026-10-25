# Dependencies

[Русский](dependencies.ru.md)

`requirements.txt` includes `requirements-tray.txt`. These describe Python
packages, not an entire Linux desktop. Installing a wheel does not install
its system-library dependencies through the distribution package manager.

## What each part needs

| Component | Required | Not required |
| --- | --- | --- |
| CLI battery read | Python 3.10+, Linux `hidraw` support, mounted sysfs, access to the matching hidraw node | Qt, hidapi, libusb Python bindings, UPower |
| Tray | CLI requirements, PySide6 Essentials, working Qt platform plugin/native libraries, fonts, session D-Bus and a StatusNotifierItem host | PySide6 Addons, PyQt6, GTK/AppIndicator bindings, dbus-python, PyGObject |
| Access without root using the supplied rule | udev and systemd-logind with an active local desktop session | Global HID permissions or a custom privileged daemon |
| Supplied autostart service | systemd user manager, `systemctl`, graphical session environment imported by the desktop | A system service or linger |
| `install.py --enable` | Qt importable in the selected Python, `systemctl` and writable user config/data directories | Root |
| Installing the udev rule as documented | `install` from coreutils, `udevadm`, administrative access via sudo | Running the application as root |
| Extra diagnostic commands | `usbutils` for `lsusb`; `acl` for `getfacl`; systemd for `loginctl`/`journalctl` | These commands are not called during battery reads |
| Optional hidapi enumeration in `--diagnose` | Python package `hidapi` and libraries required by its chosen backend | hidapi is not needed for actual battery reads |
| Unit tests | Python standard library | pytest or hardware |
| `tests/gui_smoke.py` | PySide6 Essentials and its native libraries; Qt offscreen plugin | A live desktop, mouse or USB queries |

KDE Plasma 6 supplies the tray host and graphical session infrastructure in the
tested Fedora setup. Notifications use the desktop notification service via Qt;
there is no separate Python D-Bus dependency. Do Not Disturb can suppress them.
The Python 3.10 floor is a code requirement, not a claim that every Python/Qt
combination has been tested. pip must find a wheel compatible with the selected
Python version, architecture and glibc. This checkout has been tested with
Python 3.15 and PySide6 Essentials/shiboken6 6.12.0 on Fedora x86_64.

## Fedora installation layers

On an existing Fedora KDE installation, many system packages are already present.
Install missing Python tooling before creating the venv:

```sh
sudo dnf install python3 python3-pip
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

There is no separate `python3-venv` package required for these Fedora instructions.
Optional diagnostic tools:

```sh
sudo dnf install usbutils acl
```

sudo must already be installed and configured for the administrative commands.
It is not a runtime dependency of the tray. udev/systemd and a configured desktop
are assumed to be present. On Fedora, `systemd-udev` provides `udevadm`, `systemd`
provides `systemctl`/`loginctl`/`journalctl`, and `coreutils` provides `install`.
Do not run pip or the tray through sudo.

## Debian / Ubuntu / Kubuntu / Linux Mint

These are package-based installation instructions, not a claim of hardware
verification on every derivative. Use a release with Python 3.10+ and compatible
PySide6 wheels. Linux Mint and other derivatives follow the package naming of
their Debian/Ubuntu base. A configured desktop with a StatusNotifierItem host,
udev, logind and session D-Bus is still required. The supplied autostart requires
systemd; non-systemd derivatives need a different session startup mechanism.

Python tooling (unlike Fedora, include `python3-venv`):

```sh
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

Optional diagnostic tools:

```sh
sudo apt install usbutils acl
```

The following runtime libraries cover the Qt font/graphics, Wayland and XCB
paths used here; most are already present on a full desktop. apt installs their
transitive dependencies. These are runtime packages, not development headers:

```sh
sudo apt install libdbus-1-3 libfontconfig1 libfreetype6 fonts-dejavu-core \
  libgl1 libegl1 libxkbcommon0 libwayland-client0 libwayland-cursor0 \
  libx11-6 libx11-xcb1 libxext6 libxcb1 libxkbcommon-x11-0 \
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-render-util0 libxcb-randr0 libxcb-shape0 libxcb-xfixes0 \
  libxcb-sync1 libxcb-render0 libxcb-shm0 libxcb-xkb1
```

GLib runtime naming differs by release; install the appropriate variant:

| Base release | GLib runtime package |
| --- | --- |
| Debian 12 / Ubuntu 22.04 | `sudo apt install libglib2.0-0` |
| Debian 13 / Ubuntu 24.04 and newer | `sudo apt install libglib2.0-0t64` |

On these distributions `udev` provides `udevadm`, `systemd` provides the service
and journal commands, and `coreutils` provides `install`. They are normally part
of a configured desktop installation; `dbus-user-session` provides the systemd
user-session D-Bus integration. For an intentionally minimal installation, ensure
those components are configured; the library commands above do not create a full
graphical session. GNOME needs an appropriate StatusNotifierItem/AppIndicator
host for the tray; its presence is not guaranteed by these package commands.

Then create the venv and install Python requirements from the checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Use the same sudo-based udev installation and user-service instructions in the
README. Do not use system-wide pip or `--break-system-packages`.

Package references: [Debian python3-venv](https://packages.debian.org/trixie/python3-venv),
[Ubuntu python3-venv](https://packages.ubuntu.com/search?keywords=python3-venv&searchon=names&suite=all&section=all),
[Ubuntu XCB packages](https://packages.ubuntu.com/search?arch=any&keywords=libxcb&suite=noble),
[Debian EGL](https://packages.debian.org/trixie/libegl1).

## Qt native libraries

Official PySide6 Essentials Linux wheels contain Qt libraries and plugins, and
require `shiboken6` at a matching version (pip resolves this automatically).
A separate system Qt/PySide installation is not needed when these wheels work.
System graphics, fonts, D-Bus and window-system libraries are still required.

For the installed wheel, `ldd` resolves the core/gui/widgets bindings and both
Wayland and XCB plugins without missing libraries. Relevant Fedora providers
include:

- Common: `glibc`, `libgcc`, `libstdc++`, `glib2`, `dbus-libs`, `fontconfig`,
  `freetype`, `libxkbcommon`, `libglvnd`, `libglvnd-egl`, `libglvnd-glx`.
- Wayland: `libwayland-client`, `libwayland-cursor`.
- X11/XCB, including XWayland fallback: `libX11`, `libX11-xcb`, `libXext`,
  `libXau`, `libxcb`, `libxkbcommon-x11`, `xcb-util`, `xcb-util-cursor`,
  `xcb-util-image`, `xcb-util-keysyms`, `xcb-util-renderutil`, `xcb-util-wm`.
- Additional linked-library providers in this setup: `bzip2-libs`, `graphite2`,
  `harfbuzz`, `libbrotli`, `libffi`, `libpng`, `libxml2`, `libzstd`, `pcre2`,
  `systemd-libs`, `zlib-ng-compat`.

This is an inventory for the tested wheel/environment, not a fixed minimal
package list for every Qt version. dnf resolves native transitive dependencies;
plugin requirements can change. A working Fedora KDE desktop usually has these.
The project does not need compilers, Qt development headers, `hidapi-devel` or
`libusb-devel` when using compatible binary wheels. Building packages from source
is a different installation route and is not covered here.

## Verify and diagnose

```sh
.venv/bin/python -m pip check
.venv/bin/python -c 'from PySide6 import QtCore, QtGui, QtWidgets; print(QtCore.qVersion())'
QT_QPA_PLATFORM=offscreen .venv/bin/python tests/gui_smoke.py
```

A successful import or offscreen test does not prove that the Wayland/XCB plugin
works in a real desktop. If the tray fails with a Qt plugin error, run it in the
normal desktop terminal with plugin diagnostics enabled:

```sh
QT_DEBUG_PLUGINS=1 .venv/bin/python ardor_tray.py
```

Inspect the reported missing shared library; on Fedora, look up its provider
with `dnf provides '*/the-missing-library.so.N'` before installing a package.
Do not point `QT_PLUGIN_PATH` at an unrelated system Qt installation.

References: [Qt for Python installation](https://doc.qt.io/qtforpython-6/gettingstarted.html),
[Qt Linux platform dependencies](https://doc.qt.io/qt-6/linux-requirements.html).
