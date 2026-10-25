# Phantom PRO V2 protocol notes

Verified device IDs: vendor `3554`, receiver `f52d`, wired mouse `f52e`.
Both expose the battery collection on USB interface 01, usage `ff02:0002`.
The interface contains multiple application collections; do not assume its
first usage identifies the battery endpoint. hidraw numbering is dynamic.

Input and Output report ID `08`: 128 data bits, 17 bytes including the ID.
The known battery query is:

```text
08 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 49
```

Checksum: the sum of all 17 bytes modulo 256 is `55` hex.
Responses must be exactly 17 bytes, ID `08` or `09`, command `04`, valid checksum,
and byte 6 between 0 and 100. Byte 7 is exposed as a cable-state flag, not
confirmed charging status. Other bytes are not interpreted.
An exact echo of the request is rejected; a genuine zero response identical
to it would also be rejected. This conservative restriction avoids a false 0%.

Examples captured on the owner's hardware:

```text
# Receiver: 15%, cable flag clear
08 04 00 00 00 02 0f 00 0d cb 00 00 00 00 00 00 60
# Wired: 40%, cable flag set
08 04 00 00 00 02 28 01 0e b2 00 00 00 00 00 00 5e
```

The Linux implementation uses sysfs discovery and hidraw read/write. Before
writing, read-only ioctl calls verify identity and descriptor on the opened fd.
A separate worker bounds waiting for potentially blocking kernel operations.
A terminated worker does not guarantee immediate cancellation of an operation
already running in the kernel. No automatic retry is performed.

Owner checks: both transports read successfully without root; switching the
mouse off without a cable yields no response; switching it on restores reading.
USB can still answer with the lower switch off. Sleep behavior and independent
percentage accuracy remain unverified. Wired/wireless percentages differ.

Reference: [ArdorHid.QueryNordicDirect](https://github.com/KhromotozzDevOut/ardor-mouse-battery-tray/blob/main/ArdorBatteryTray.cs#L1366).
Unknown models must not be queried merely because they use the same brand.
