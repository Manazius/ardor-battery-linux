"""English/Russian tray text. No Qt dependency."""
import locale
import os

EN = {
    'Ожидание первого ответа': 'Waiting for the first response',
    'Ожидание ответа…': 'Waiting for a response…',
    'Обновить сейчас': 'Refresh now',
    'Подробности…': 'Details…',
    'Уведомлять о низком заряде': 'Low battery notifications',
    'Выход': 'Quit',
    'Нет актуального показания': 'No current reading',
    'Последнее успешное чтение: ': 'Last successful reading: ',
    'Заряд: ': 'Battery: ',
    'Получено: ': 'Received: ',
    'Кабель: ': 'Cable: ',
    'подключён': 'connected',
    'не отмечен устройством': 'not reported by the device',
    'Обновление…': 'Refreshing…',
    'Нет ответа': 'No response',
    'USB-кабель': 'USB cable',
    'Приёмник 2.4 ГГц': '2.4 GHz receiver',
    'Процесс чтения завершился с ошибкой': 'Battery reader failed',
    'Некорректный ответ процесса чтения: ': 'Invalid battery reader response: ',
    'Низкий заряд мыши ARDOR': 'ARDOR mouse battery is low',
    'Мышь сообщает {percent}%. Подключите кабель.': 'Mouse reports {percent}%. Connect the cable.',
    'Не удалось запустить чтение: ': 'Could not start the battery reader: ',
    'Истёк общий таймаут процесса чтения': 'Battery reader timed out',
    'Батарея ARDOR': 'ARDOR Battery',
    'Язык': 'Language',
    'Как в системе': 'System default',
}


def system_language():
    # LANGUAGE may contain a colon-separated preference list; use its first entry.
    value = (os.environ.get('LANGUAGE', '').split(':')[0]
             or os.environ.get('LC_ALL') or os.environ.get('LC_MESSAGES')
             or os.environ.get('LANG') or locale.getlocale()[0] or 'en')
    return 'ru' if value.lower().startswith('ru') else 'en'


def resolve_language(choice):
    return choice if choice in ('en', 'ru') else system_language()


def translate(text, language):
    return text if resolve_language(language) == 'ru' else EN.get(text, text)
