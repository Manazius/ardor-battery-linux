#!/usr/bin/env python3
"""Linux battery probe for 3554:f52d/f52e. Default operation is passive diagnostics."""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import select
import stat
import struct
import sys
import time

VID, PID = 0x3554, 0xF52D
WIRED_PID = 0xF52E
SUPPORTED_PIDS = (PID, WIRED_PID)
SYSFS = Path('/sys/class/hidraw')
REQUEST = bytes.fromhex('08 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 49')


class ProbeError(Exception):
    """Expected discovery, protocol or transport failure."""


@dataclass
class Descriptor:
    applications: list[tuple[int, int]]
    bits: dict[tuple[str, int], int]

    @property
    def battery_endpoint(self) -> bool:
        return ((0xFF02, 2) in self.applications
                and self.bits.get(('input', 8)) == 128
                and self.bits.get(('output', 8)) == 128)


def parse_descriptor(data: bytes) -> Descriptor:
    """Parse HID short items, global push/pop and application collections.

    Lengths exclude Report ID. Local usages reset after every main item.
    Unknown items do not establish protocol support.
    """
    globals_ = {0: 0, 7: 0, 8: 0, 9: 0}
    stack = []
    usages = []
    applications = []
    bits = defaultdict(int)
    offset = 0
    depth = 0
    while offset < len(data):
        prefix = data[offset]
        offset += 1
        if prefix == 0xFE:
            raise ProbeError('Unsupported long HID item')
        size = (0, 1, 2, 4)[prefix & 3]
        if offset + size > len(data):
            raise ProbeError('Truncated HID descriptor')
        value = int.from_bytes(data[offset:offset + size], 'little')
        offset += size
        kind, tag = (prefix >> 2) & 3, prefix >> 4
        if kind == 1:
            if tag == 10:
                stack.append(globals_.copy())
            elif tag == 11:
                if not stack:
                    raise ProbeError('HID Pop without Push')
                globals_ = stack.pop()
            else:
                globals_[tag] = value
        elif kind == 2 and tag == 0:
            usages.append((value >> 16, value & 0xFFFF) if size == 4
                          else (globals_[0], value))
        elif kind == 0:
            if tag == 10:
                if value == 1 and depth == 0 and usages:
                    applications.append(usages[0])
                depth += 1
            elif tag == 12:
                depth -= 1
                if depth < 0:
                    raise ProbeError('Unbalanced HID Collection')
            elif tag in (8, 9, 11):
                report_kind = {8: 'input', 9: 'output', 11: 'feature'}[tag]
                bits[report_kind, globals_[8]] += globals_[7] * globals_[9]
            usages.clear()
    if depth or stack:
        raise ProbeError('Unclosed HID Collection/Push')
    return Descriptor(applications, dict(bits))


@dataclass
class Endpoint:
    path: str
    interface: int
    descriptor: bytes
    product_id: int = PID

    @property
    def layout(self) -> Descriptor:
        return parse_descriptor(self.descriptor)


def discover() -> list[Endpoint]:
    endpoints = []
    for entry in sorted(SYSFS.glob('hidraw*')):
        try:
            device = (entry / 'device').resolve(strict=True)
            attrs = dict(line.split('=', 1) for line in
                         (device / 'uevent').read_text().splitlines() if '=' in line)
            bus, vendor, product = (int(v, 16) for v in attrs['HID_ID'].split(':'))
            if bus != 3 or vendor != VID or product not in SUPPORTED_PIDS:
                continue
            interface = next(parent for parent in device.parents
                             if (parent / 'bInterfaceNumber').exists())
            endpoints.append(Endpoint('/dev/' + entry.name,
                                      int((interface / 'bInterfaceNumber').read_text(), 16),
                                      (device / 'report_descriptor').read_bytes(), product))
        except FileNotFoundError:
            continue  # Unplugged during discovery.
        except (KeyError, ValueError, StopIteration, OSError) as exc:
            raise ProbeError(f'Could not inspect {entry}: {exc}') from exc
    return endpoints


def choose(endpoints: list[Endpoint], path: str | None = None) -> Endpoint:
    matches = [e for e in endpoints if e.layout.battery_endpoint
               and (path is None or e.path == path)]
    # A connected cable takes precedence over a receiver that may stop replying.
    # Do not silently hide wired access errors by querying the receiver instead.
    if path is None and any(e.product_id == WIRED_PID for e in matches):
        matches = [e for e in matches if e.product_id == WIRED_PID]
    if len(matches) != 1:
        raise ProbeError(f'Expected one compatible interface, found: {len(matches)}. '
                         'Use --diagnose; specify --device for multiple devices.')
    return matches[0]


@dataclass
class BatteryReading:
    percent: int
    cable_state: bool
    raw: str
    device: str
    timestamp: float
    product_id: int | None = None


def decode_response(data: bytes, path: str) -> BatteryReading:
    if len(data) != 17:
        raise ProbeError(f'Response length {len(data)}, expected 17')
    if data == REQUEST:
        raise ProbeError('Request echo: not a battery reading')
    if data[0] not in (8, 9) or data[1] != 4:
        raise ProbeError('Unrelated command/report ID')
    if sum(data) & 0xFF != 0x55:
        raise ProbeError('Invalid checksum')
    if data[6] > 100:
        raise ProbeError(f'Percentage out of range: {data[6]}')
    return BatteryReading(data[6], bool(data[7]), data.hex(' '), path, time.time())


def _exchange(endpoint: Endpoint, timeout: float, connection) -> None:
    """Isolated worker: parent bounds even a blocking kernel USB write."""
    operation = 'open hidraw'
    try:
        fd = os.open(endpoint.path, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            if not stat.S_ISCHR(os.fstat(fd).st_mode):
                raise ProbeError('Path is not a character device')
            # Linux HIDIOCGRAWINFO: confirm identity on the opened handle (hotplug).
            operation = 'HIDIOCGRAWINFO'
            info = bytearray(8)
            fcntl.ioctl(fd, 0x80084803, info, True)
            if struct.unpack('=IHH', info) != (3, VID, endpoint.product_id):
                raise ProbeError('Device identity changed after discovery')
            # Linux HIDIOCGRDESC: confirm descriptor on that same handle.
            operation = 'HIDIOCGRDESCSIZE'
            size_buffer = bytearray(4)
            fcntl.ioctl(fd, 0x80044801, size_buffer, True)
            expected_length = struct.unpack('=I', size_buffer)[0]
            if not 0 < expected_length < 4096:
                raise ProbeError(f'Invalid HID descriptor length: {expected_length}')
            operation = 'HIDIOCGRDESC'
            descriptor = bytearray(4100)
            struct.pack_into('=I', descriptor, 0, expected_length)
            fcntl.ioctl(fd, 0x90044802, descriptor, True)
            length = struct.unpack_from('=I', descriptor)[0]
            if not 0 < length <= 4096 or bytes(descriptor[4:4 + length]) != endpoint.descriptor:
                raise ProbeError('HID descriptor changed after discovery')
            operation = 'write battery request'
            if os.write(fd, REQUEST) != len(REQUEST):
                raise ProbeError('Incomplete write; no retry performed')
            operation = 'read battery response'
            deadline = time.monotonic() + timeout
            rejected = []
            while (remaining := deadline - time.monotonic()) > 0:
                if not select.select([fd], [], [], remaining)[0]:
                    break
                try:
                    data = os.read(fd, 4096)
                except BlockingIOError:
                    continue
                if not data:
                    raise ProbeError('Device disconnected')
                try:
                    reading = decode_response(data, endpoint.path)
                    reading.product_id = endpoint.product_id
                except ProbeError as exc:
                    rejected.append(f'{exc}: {data.hex(" ")}')
                    rejected = rejected[-4:]
                    continue
                connection.send(('ok', asdict(reading)))
                return
            details = '; '.join(rejected) or 'no Input reports'
            raise ProbeError(f'No valid response within {timeout:g} s ({details})')
        finally:
            os.close(fd)
    except (OSError, ProbeError) as exc:
        connection.send(('error', f'{operation}: {exc}'))
    finally:
        connection.close()


def read_battery(endpoint: Endpoint, timeout: float = 0.8) -> BatteryReading:
    """Send exactly one known battery query. Never return cached/fallback data."""
    if endpoint.product_id not in SUPPORTED_PIDS or not endpoint.layout.battery_endpoint:
        raise ProbeError('Descriptor does not identify a battery endpoint')
    context = multiprocessing.get_context('spawn')
    receiver, sender = context.Pipe(duplex=False)
    worker = context.Process(target=_exchange, args=(endpoint, timeout, sender), daemon=True)
    worker.start()
    sender.close()
    try:
        if not receiver.poll(timeout + 2):
            raise ProbeError('USB operation timed out; no retry performed')
        try:
            status, payload = receiver.recv()
        except EOFError as exc:
            raise ProbeError('USB worker exited without a result') from exc
        if status != 'ok':
            raise ProbeError(payload)
        return BatteryReading(**payload)
    finally:
        receiver.close()
        worker.join(0.1)
        if worker.is_alive():
            worker.terminate()
            worker.join(0.2)
        if worker.is_alive():
            worker.kill()
            worker.join(0.2)


def diagnose(endpoints: list[Endpoint]) -> None:
    for endpoint in endpoints:
        layout = endpoint.layout
        print(f'{endpoint.path}: usb={VID:04x}:{endpoint.product_id:04x}, interface={endpoint.interface:02x}, '
              f'node_exists={Path(endpoint.path).exists()}, '
              f'read_write_access={os.access(endpoint.path, os.R_OK | os.W_OK)}, '
              f'battery_endpoint={layout.battery_endpoint}')
        print('  Application usages:', ', '.join(f'{p:04x}:{u:04x}' for p, u in layout.applications))
        print('  Reports:', ', '.join(f'{k} ID={r:02x} data={b} bits' for (k, r), b in layout.bits.items()))
        print('  Descriptor:', endpoint.descriptor.hex(' '))
    try:
        import hid
        print('hidapi version:', hid.version_str())
        for product_id in SUPPORTED_PIDS:
            print(f'hidapi enumeration {VID:04x}:{product_id:04x}:', hid.enumerate(VID, product_id))
    except (ImportError, OSError) as exc:
        print('hidapi diagnostic:', exc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--diagnose', action='store_true', help='Passive sysfs/hidapi enumeration (default)')
    mode.add_argument('--read', action='store_true', help='Send one known battery query')
    parser.add_argument('--device', help='Select /dev/hidrawN; descriptor validation is mandatory')
    parser.add_argument('--timeout', type=float, default=0.8, help='Response timeout in seconds (0.1–10)')
    parser.add_argument('--json', action='store_true', help='Print a successful reading as JSON')
    args = parser.parse_args()
    if not 0.1 <= args.timeout <= 10:
        parser.error('--timeout must be between 0.1 and 10')
    try:
        endpoints = discover()
        if not endpoints:
            raise ProbeError('No 3554:f52d/f52e devices found in sysfs')
        if not args.read:
            diagnose(endpoints)
            return 0
        endpoint = choose(endpoints, args.device)
        reading = read_battery(endpoint, args.timeout)
        print(json.dumps(asdict(reading), ensure_ascii=False) if args.json
              else f'Mouse battery: {reading.percent}% (cable state: {int(reading.cable_state)})')
        return 0
    except (ProbeError, OSError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
