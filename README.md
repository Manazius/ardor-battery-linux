# ARDOR Battery for Linux

[Русский](README.ru.md)

A native Linux battery reader and KDE Plasma 6 tray indicator for the
**ARDOR GAMING Phantom PRO V2**. Tested by its owner on Fedora, Plasma 6 and
Wayland, over both the 2.4 GHz receiver and USB cable.

- Transparent, neutral tray number that follows the desktop palette.
- Automatic refresh every 30 seconds and manual refresh from the menu.
- USB/receiver connection mode, error details and last successful reading time.
- English and Russian UI, with a saved language choice in the tray menu.
- Optional low-battery notifications; disabled by default.
- No root needed after installing the device-specific udev rule.

This is an unofficial project. Other mouse models are not supported or queried.

## Install

Requires Linux, Python 3.10+ and a graphical session with a StatusNotifierItem
tray. Plasma 6 on Wayland is the tested environment. Qt is an extra dependency
for the tray; the command-line battery reader uses only Python's standard library.

### Dependencies

| Layer | Dependency |
| --- | --- |
| CLI | Python 3.10+, Linux hidraw/sysfs and device access; no pip packages |
| Tray | PySide6 Essentials; pip automatically installs matching shiboken6 and the wheel's Qt components |
| Desktop | Qt native libraries/fonts, session D-Bus and a StatusNotifierItem tray host (tested: Plasma 6) |
| Device permissions | udev + logind for the supplied active-session uaccess rule |
| Autostart | systemd user manager and systemctl |
| Diagnostic commands only | usbutils (lsusb), acl (getfacl); hidapi is optional |

Install Python tooling for your distribution (sudo must already be configured):

**Fedora:**

```sh
sudo dnf install python3 python3-pip
```

**Debian / Ubuntu / Kubuntu / Linux Mint and compatible derivatives:**

```sh
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

Optional diagnostic commands: `sudo dnf install usbutils acl` on Fedora,
or `sudo apt install usbutils acl` on Debian/Ubuntu.
These commands do not install a desktop environment. Debian/Ubuntu instructions
have not been validated on hardware; Fedora KDE remains the tested setup.
The tray requires a StatusNotifierItem host; installing packages alone does not
add one to an arbitrary GNOME or other desktop session.

See [the full dependency guide](docs/dependencies.md) for native Wayland/XCB
libraries, tested versions, command providers and Qt plugin troubleshooting.
Pip requirements alone do not describe the whole system.

### Python packages

Download or clone this repository and open its directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Grant the active local desktop session access to **3554:F52D/F52E, interface 01**:

```sh
sudo install -m 0644 udev/70-ardor-battery.rules /etc/udev/rules.d/70-ardor-battery.rules
sudo udevadm control --reload-rules
```

Unplug and reconnect the receiver and mouse cable after installing the rule.
It does not grant access to other HID devices or to every interface of this mouse.

```sh
.venv/bin/python ardor.py --read --json
.venv/bin/python ardor_tray.py
```

Run the tray as your desktop user, without sudo.

## Language

Right-click the icon → **Language → System default / English / Русский**.
Changes apply immediately and are saved. Automatic selection uses Russian for a
Russian locale and English otherwise. Override the saved choice for one run:

```sh
.venv/bin/python ardor_tray.py --language en
.venv/bin/python ardor_tray.py --language ru
```

CLI diagnostics and low-level error details are in English. JSON keys are stable.

## Autostart

Close any manually started tray using **Quit**. From the repository directory:

```sh
.venv/bin/python install.py --enable
```

The installer generates a user service, an application menu entry and
`~/.local/bin/ardor-battery`, using this checkout and its Python interpreter.
It does not copy source code, install dependencies or change udev. Keep the
checkout and its venv in place; rerun the installer after moving them.
Use `install.py --dry-run` to inspect generated files without changing anything.
Do not copy templates from `systemd/` or `desktop/` directly: they contain placeholders.

If you previously installed `~/.config/autostart/ardor-battery.desktop`, remove
that specific entry to avoid two autostart methods. The installer does not remove it.

```sh
systemctl --user status ardor-battery.service --no-pager
systemctl --user restart ardor-battery.service
journalctl --user -u ardor-battery.service -b -n 50 --no-pager
```

The service follows the graphical session and restarts on failure. Choosing
**Quit** exits normally and does not restart it until the next session or an
explicit start. No system service or linger is needed.

To disable autostart:

```sh
systemctl --user disable --now ardor-battery.service
```

## Behavior and limits

The wired endpoint takes precedence when both devices are present. Every read
rediscovers the HID path, checks the descriptor and sends one known battery
query. Requests are bounded and do not overlap in the tray. No DPI, polling-rate,
profile or firmware commands are sent. The program does not reset USB devices
or detach their kernel drivers.

A timeout shows `?`. A previous percentage is shown only as a last successful
reading, with its timestamp; it is not presented as current. A timeout alone
cannot distinguish sleeping, switched-off or unreachable mice.

**The device reports different percentages over USB and wireless** (for example,
40% over USB followed by 30% wireless). Values are displayed without smoothing
or correction; their independent accuracy has not been established. The cable
flag is not treated as proof of active charging.

Notifications must be enabled in the tray menu. Thresholds are 20%, 10% and 5%,
confirmed by two consecutive successful low readings, only over the receiver
with the cable flag clear. Each threshold notifies once until a wireless
reading above 25% rearms it. Errors and cable readings break confirmation.
Delivery depends on Plasma notification settings and Do Not Disturb.

Settings use Qt QSettings under `ardor-community/battery-tray` in the user config.
Use `--interval 60` to change polling to 60 seconds (minimum 10 seconds).

## Troubleshooting

```sh
.venv/bin/python ardor.py --diagnose
lsusb -d 3554:
```

Diagnosis is passive: no battery query is sent. `hidapi` is optional and used
only for supplemental enumeration. Its libusb backend can report zero Usage
values; this tool reads the real descriptor from sysfs instead.

For access problems, inspect the *current* hidraw node from diagnosis:

```sh
udevadm info --query=property --name=/dev/hidraw4 --no-pager
getfacl /dev/hidraw4
loginctl list-sessions --no-pager
```

Look for `ARDOR_BATTERY_RECEIVER=1`, `uaccess`, and an ACL for the active desktop
user. Reloading rules alone does not update an existing device: reconnect it.
If wired USB repeatedly disconnects, test another data cable and port with the
utility closed. A bad cable caused this issue during owner testing.

## Other mouse models

Only Phantom PRO V2 is hardware-verified. To request another model, open an issue
with the exact model, receiver/wired VID/PID, passive `--diagnose` output and a
reliable protocol source or official software link. A model using the same
protocol may be supported with a small device profile, but requires owner tests.
See [CONTRIBUTING.md](CONTRIBUTING.md); unknown devices are never probed blindly.

## Development and contributions

Developed with AI assistance and tested on physical hardware by the project owner.

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Protocol notes: [docs/protocol.md](docs/protocol.md).
Contributions: [CONTRIBUTING.md](CONTRIBUTING.md).
The CLI works without Qt; UI/state tests are separated from hardware access.

## License and credits

MIT. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Protocol research used the Windows project
[ardor-mouse-battery-tray](https://github.com/KhromotozzDevOut/ardor-mouse-battery-tray).
