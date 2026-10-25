import unittest
from unittest.mock import patch
import ardor


def response(percent=57, report_id=8):
    data = bytearray(17)
    data[0:2] = bytes([report_id, 4])
    data[6] = percent
    data[16] = (0x55 - sum(data[:16])) & 255
    return bytes(data)


class ProtocolTests(unittest.TestCase):
    def test_physical_response_from_owner(self):
        raw = bytes.fromhex('08 04 00 00 00 02 0f 00 0d cb 00 00 00 00 00 00 60')
        reading = ardor.decode_response(raw, '/dev/hidraw4')
        self.assertEqual(reading.percent, 15)
        self.assertFalse(reading.cable_state)
        self.assertEqual(reading.raw, raw.hex(' '))

    def test_physical_wired_response_from_owner(self):
        raw = bytes.fromhex('08 04 00 00 00 02 28 01 0e b2 00 00 00 00 00 00 5e')
        reading = ardor.decode_response(raw, '/dev/hidraw7')
        self.assertEqual(reading.percent, 40)
        self.assertTrue(reading.cable_state)
        self.assertEqual(reading.raw, raw.hex(' '))

    def test_request(self):
        self.assertEqual(len(ardor.REQUEST), 17)
        self.assertEqual(sum(ardor.REQUEST) & 255, 0x55)

    def test_valid_responses(self):
        for report_id in (8, 9):
            for percent in (0, 57, 100):
                with self.subTest(report_id=report_id, percent=percent):
                    data = bytearray(response(percent, report_id))
                    # Differentiate a real zero response from the exact request echo.
                    data[2] = 1
                    data[16] = (0x55 - sum(data[:16])) & 255
                    self.assertEqual(ardor.decode_response(bytes(data), 'test').percent, percent)

    def test_invalid_responses(self):
        corrupt = bytearray(response())
        corrupt[16] ^= 1
        for data in (b'', response()[:8], response() + b'\x00',
                     response(101), response(report_id=3), bytes(corrupt), ardor.REQUEST):
            with self.subTest(data=data):
                with self.assertRaises(ardor.ProbeError):
                    ardor.decode_response(data, 'test')

    def test_descriptor_selection(self):
        # FF02:0002, report 8, 16 bytes input and output.
        descriptor = bytes.fromhex('06 02 ff 09 02 a1 01 85 08 75 08 95 10 81 00 91 00 c0')
        endpoint = ardor.Endpoint('/dev/test', 1, descriptor)
        self.assertTrue(endpoint.layout.battery_endpoint)
        self.assertEqual(ardor.choose([endpoint]), endpoint)
        for candidates in ([], [endpoint, endpoint]):
            with self.assertRaises(ardor.ProbeError):
                ardor.choose(candidates)
        with self.assertRaises(ardor.ProbeError):
            ardor.choose([endpoint], '/dev/wrong')
        self.assertFalse(ardor.parse_descriptor(descriptor.replace(b'\x95\x10', b'\x95\x07')).battery_endpoint)

    def test_wired_priority_and_explicit_receiver(self):
        descriptor = bytes.fromhex('06 02 ff 09 02 a1 01 85 08 75 08 95 10 81 00 91 00 c0')
        receiver = ardor.Endpoint('/dev/receiver', 1, descriptor)
        wired = ardor.Endpoint('/dev/wired', 1, descriptor, ardor.WIRED_PID)
        self.assertEqual(ardor.choose([receiver, wired]), wired)
        self.assertEqual(ardor.choose([wired, receiver], receiver.path), receiver)
        with self.assertRaises(ardor.ProbeError):
            ardor.choose([wired, wired, receiver])

    def test_bad_descriptor(self):
        for data in (b'\x06', b'\xc0', b'\xb4', b'\xa1\x01'):
            with self.assertRaises(ardor.ProbeError):
                ardor.parse_descriptor(data)

    def test_missing_receiver(self):
        with patch('ardor.SYSFS', ardor.Path('/nonexistent-test-sysfs')):
            self.assertEqual(ardor.discover(), [])

class TransportTests(unittest.TestCase):
    def test_descriptor_ioctl_uses_actual_length(self):
        from contextlib import ExitStack
        import struct
        descriptor = bytes.fromhex('06 02 ff 09 02 a1 01 85 08 75 08 95 10 81 00 91 00 c0')
        endpoint = ardor.Endpoint('/dev/test', 1, descriptor)
        connection = unittest.mock.Mock()

        def ioctl(fd, command, buffer, mutate):
            if command == 0x80084803:
                buffer[:] = struct.pack('=IHH', 3, ardor.VID, ardor.PID)
            elif command == 0x80044801:
                buffer[:] = struct.pack('=I', len(descriptor))
            elif command == 0x90044802:
                self.assertEqual(struct.unpack_from('=I', buffer)[0], len(descriptor))
                buffer[4:4 + len(descriptor)] = descriptor
            else:
                self.fail(f'Unexpected ioctl: {command:x}')

        with ExitStack() as stack:
            stack.enter_context(patch('ardor.os.open', return_value=42))
            stack.enter_context(patch('ardor.os.fstat', return_value=unittest.mock.Mock(st_mode=0o020600)))
            stack.enter_context(patch('ardor.os.close'))
            stack.enter_context(patch('ardor.fcntl.ioctl', side_effect=ioctl))
            write = stack.enter_context(patch('ardor.os.write', return_value=17))
            stack.enter_context(patch('ardor.select.select', return_value=([42], [], [])))
            stack.enter_context(patch('ardor.os.read', return_value=response(57)))
            ardor._exchange(endpoint, 0.1, connection)
        write.assert_called_once_with(42, ardor.REQUEST)
        self.assertEqual(connection.send.call_args.args[0][0], 'ok')
        self.assertEqual(connection.send.call_args.args[0][1]['percent'], 57)


if __name__ == '__main__':
    unittest.main()
