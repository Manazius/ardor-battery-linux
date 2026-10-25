# Зависимости

[English и подробный список нативных библиотек](dependencies.md)

`requirements.txt` подключает `requirements-tray.txt`. Эти файлы описывают
Python-пакеты, но не устанавливают системные библиотеки через пакетный менеджер дистрибутива.

| Часть проекта | Что требуется |
| --- | --- |
| Чтение батареи в терминале | Python 3.10+, Linux hidraw, sysfs и права доступа к нужному узлу |
| Трей | PySide6 Essentials, нативные библиотеки Qt-плагина, шрифты, сеансовый D-Bus и системный лоток StatusNotifierItem |
| Доступ без root через наше правило | udev и systemd-logind, активный локальный графический сеанс |
| Наш сервис автозапуска | Пользовательский systemd, systemctl и окружение графического сеанса |
| Установка правила udev | coreutils/install, udevadm и административный доступ через sudo |
| Дополнительная диагностика | usbutils для lsusb, acl для getfacl, systemd для loginctl/journalctl |
| Необязательное перечисление hidapi | Python-пакет hidapi и зависимости его backend; для чтения батареи он не используется |
| Обычные тесты | Стандартная библиотека Python |
| Проверка GUI без экрана | PySide6 Essentials и его нативные библиотеки, Qt offscreen plugin |

PySide6 Essentials автоматически устанавливает **shiboken6 той же версии**.
Официальный Linux wheel содержит Qt-библиотеки и плагины; отдельно устанавливать
Qt через системный пакетный менеджер при таком способе не нужно. Но wheel зависит от системных библиотек
графики, шрифтов, D-Bus, Wayland/XCB. Pip не устанавливает их через системный пакетный менеджер.

PySide6 Addons, PyQt6, dbus-python, PyGObject, UPower и Python libusb не нужны.
Hidapi не является обязательной зависимостью. Уведомления идут через Qt и службу
уведомлений рабочего стола; отдельный Python D-Bus пакет не используется.

## Fedora KDE

В существующей KDE-системе большая часть системных компонентов уже установлена.
Если не хватает Python/pip:

```sh
sudo dnf install python3 python3-pip
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Для этих инструкций Fedora отдельный пакет python3-venv не требуется.
Дополнительные команды диагностики:

```sh
sudo dnf install usbutils acl
```

Sudo должен быть установлен и настроен заранее. Он нужен только для
административных команд установки; сам трей и pip от root не запускаются.
В Fedora `systemd-udev` предоставляет udevadm, `systemd` —
systemctl/loginctl/journalctl, `coreutils` — install.

## Debian / Ubuntu / Kubuntu / Linux Mint

Названия пакетов приведены для Debian/Ubuntu и производных; аппаратное
тестирование на всех этих дистрибутивах не проводилось. Нужны Python 3.10+,
совместимый wheel PySide6 и настроенный графический сеанс с лотком
StatusNotifierItem, udev/logind и сеансовым D-Bus. Наш автозапуск требует
systemd; для производных без systemd нужен другой механизм запуска.

В отличие от Fedora, устанавливается отдельный пакет python3-venv:

```sh
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

Необязательная диагностика:

```sh
sudo apt install usbutils acl
```

Нативные библиотеки Qt, шрифтов, Wayland и XCB. На полноценном рабочем столе
большинство уже установлено; транзитивные зависимости разрешает apt.
Это runtime-пакеты, devel-пакеты и компилятор не нужны:

```sh
sudo apt install libdbus-1-3 libfontconfig1 libfreetype6 fonts-dejavu-core \
  libgl1 libegl1 libxkbcommon0 libwayland-client0 libwayland-cursor0 \
  libx11-6 libx11-xcb1 libxext6 libxcb1 libxkbcommon-x11-0 \
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-render-util0 libxcb-randr0 libxcb-shape0 libxcb-xfixes0 \
  libxcb-sync1 libxcb-render0 libxcb-shm0 libxcb-xkb1
```

Пакет GLib зависит от базового релиза:

| Базовая система | GLib |
| --- | --- |
| Debian 12 / Ubuntu 22.04 | `sudo apt install libglib2.0-0` |
| Debian 13 / Ubuntu 24.04 и новее | `sudo apt install libglib2.0-0t64` |

Здесь пакет `udev` предоставляет udevadm, `systemd` — команды сервиса и журнала,
`coreutils` — install. На обычном рабочем столе они уже присутствуют.
`dbus-user-session` обеспечивает интеграцию D-Bus с пользовательским systemd.
В минимальной системе эти компоненты нужно настроить отдельно: установка
библиотек выше не создаёт полноценный графический сеанс. Для GNOME нужен
совместимый хост StatusNotifierItem/AppIndicator; он не гарантируется этими командами.

Далее из каталога проекта:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Установка udev и пользовательского сервиса такая же, как в README.
Не используйте системный pip и --break-system-packages.
[Ссылки на пакеты Debian/Ubuntu](dependencies.md#debian--ubuntu--kubuntu--linux-mint).

## Нативные библиотеки и проверенная среда

Проверена установленная сборка Python 3.15 + PySide6 Essentials/shiboken6 6.12.0,
Fedora x86_64. Ограничение Python 3.10+ относится к коду: не все комбинации
Python/Qt проверены. Pip должен найти wheel для версии Python, архитектуры и glibc.
Для установки из совместимых wheels компиляторы и devel-пакеты не нужны.
Сборка зависимостей из исходников здесь не рассматривается.

Через ldd проверены QtCore/QtGui/QtWidgets и плагины Wayland/XCB: отсутствующих
библиотек в текущей системе нет. Среди зависимостей — glibc, libstdc++, GL/EGL,
fontconfig/freetype, dbus-libs, libxkbcommon, Wayland и XCB-библиотеки.
[Список Fedora-пакетов проверенной сборки](dependencies.md#qt-native-libraries)
включает и транзитивные зависимости. Он не объявляется универсальным минимумом
для любых версий Qt: обычно эти библиотеки уже есть в полноценной Fedora KDE.

## Проверка

```sh
.venv/bin/python -m pip check
.venv/bin/python -c 'from PySide6 import QtCore, QtGui, QtWidgets; print(QtCore.qVersion())'
QT_QPA_PLATFORM=offscreen .venv/bin/python tests/gui_smoke.py
```

Успешный импорт или offscreen-тест не гарантирует работу Wayland/XCB в сеансе.
При ошибке платформенного плагина выполните в обычном терминале рабочего стола:

```sh
QT_DEBUG_PLUGINS=1 .venv/bin/python ardor_tray.py
```

Для отсутствующей библиотеки пакет можно найти через
`dnf provides '*/имя-библиотеки.so.N'`. Не смешивайте плагины wheel и другой
системной сборки Qt через QT_PLUGIN_PATH.
