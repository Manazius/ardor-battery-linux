"""GUI-independent validation and low-battery notification policy."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Sample:
    percent: int
    wired: bool
    cable: bool
    timestamp: float
    device: str

    @classmethod
    def from_json(cls, value):
        if not isinstance(value, dict):
            raise ValueError('CLI response is not an object')
        percent = value.get('percent')
        cable = value.get('cable_state')
        timestamp = value.get('timestamp')
        device = value.get('device')
        product = value.get('product_id')
        if type(percent) is not int or not 0 <= percent <= 100:
            raise ValueError('Invalid percentage')
        if type(cable) is not bool:
            raise ValueError('Invalid cable state')
        if type(timestamp) not in (int, float) or not math.isfinite(timestamp):
            raise ValueError('Invalid response timestamp')
        if not isinstance(device, str) or not device.startswith('/dev/hidraw'):
            raise ValueError('Invalid device path')
        if type(product) is not int or product not in (0xF52D, 0xF52E):
            raise ValueError('Invalid PID; update ardor.py together with the tray')
        return cls(percent, product == 0xF52E, cable, timestamp, device)

    @property
    def mode(self):
        return 'USB-кабель' if self.wired else 'Приёмник 2.4 ГГц'


class Alerts:
    """Once per threshold per discharge cycle; require two fresh low readings.

    Cable readings and failures break confirmation. Rearm only on a fresh
    wireless reading above 25%, avoiding repeats when switching USB modes.
    """
    def __init__(self):
        self.notified = set()
        self.pending = None

    def reset_confirmation(self):
        self.pending = None

    def update(self, sample):
        if sample is None or sample.wired or sample.cable:
            self.reset_confirmation()
            return None
        if sample.percent > 25:
            self.notified.clear()
        level = next((x for x in (5, 10, 20) if sample.percent <= x), None)
        if level is None or level in self.notified:
            self.reset_confirmation()
            return None
        if self.pending != level:
            self.pending = level
            return None
        self.notified.update(x for x in (5, 10, 20) if x >= level)
        self.reset_confirmation()
        return level
