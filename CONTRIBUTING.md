# Contributing

Bug reports and small focused pull requests are welcome. English and Russian
reports are both fine. This project currently supports only Phantom PRO V2.

For a bug report, include the distro, Python/Qt/Plasma versions, connection mode,
steps to reproduce, and relevant errors. For device detection, include `lsusb`
and `python ardor.py --diagnose` output from the project's venv. Remove serial
numbers, usernames and unrelated device details before posting logs.

For another mouse, first provide its exact model, wired/receiver VID/PID,
report descriptors and a reliable protocol source. Do not brute-force commands,
reset devices, flash firmware or detach drivers to probe for battery support.
A matching descriptor alone is not proof of a matching protocol. Label untested
support honestly; owner hardware verification is required.

Before submitting:

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q ardor.py ardor_tray.py tray_state.py i18n.py install.py
```

Keep transport and tray logic separate. New UI text must have English and
Russian versions. Do not change raw battery percentages to hide device quirks.
