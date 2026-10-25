import unittest

from tray_state import Alerts, Sample


def sample(percent=20, wired=False, cable=False):
    return Sample.from_json(dict(percent=percent, product_id=0xF52E if wired else 0xF52D,
                                 cable_state=cable, timestamp=123.5, device='/dev/hidraw4'))


class TrayStateTests(unittest.TestCase):
    def test_mode_uses_pid_not_charging_guess(self):
        self.assertEqual(sample(cable=True).mode, 'Приёмник 2.4 ГГц')
        self.assertEqual(sample(wired=True).mode, 'USB-кабель')

    def test_invalid_cli_output(self):
        good = dict(percent=20, product_id=0xF52D, cable_state=False,
                    timestamp=123, device='/dev/hidraw4')
        for field, bad in [('percent', True), ('percent', 101), ('percent', -1),
                           ('product_id', None), ('product_id', 0x1234),
                           ('timestamp', float('nan')), ('cable_state', 1),
                           ('device', None)]:
            with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                Sample.from_json({**good, field: bad})

    def test_alert_confirmation_and_no_duplicates(self):
        alerts = Alerts()
        self.assertIsNone(alerts.update(sample(15)))
        self.assertEqual(alerts.update(sample(15)), 20)
        self.assertIsNone(alerts.update(sample(15)))
        self.assertIsNone(alerts.update(sample(9)))
        self.assertEqual(alerts.update(sample(9)), 10)
        self.assertIsNone(alerts.update(sample(4)))
        self.assertEqual(alerts.update(sample(4)), 5)
        self.assertIsNone(alerts.update(sample(15)))

    def test_failure_breaks_confirmation(self):
        alerts = Alerts()
        alerts.update(sample(10))
        alerts.update(None)
        self.assertIsNone(alerts.update(sample(10)))
        self.assertEqual(alerts.update(sample(10)), 10)

    def test_cable_never_alerts_or_rearms(self):
        alerts = Alerts()
        alerts.update(sample(15))
        self.assertEqual(alerts.update(sample(15)), 20)
        for reading in [sample(50, wired=True), sample(50, cable=True)]:
            self.assertIsNone(alerts.update(reading))
        self.assertIsNone(alerts.update(sample(15)))
        self.assertIsNone(alerts.update(sample(15)))
        alerts.update(sample(50))
        self.assertIsNone(alerts.update(sample(15)))
        self.assertEqual(alerts.update(sample(15)), 20)


if __name__ == '__main__':
    unittest.main()
