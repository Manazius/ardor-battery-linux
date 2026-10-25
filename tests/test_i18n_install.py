import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from i18n import EN, resolve_language, translate
from install import render, systemd_quote


class LanguageTests(unittest.TestCase):
    def test_auto_and_explicit(self):
        with patch.dict(os.environ, {'LANG': 'ru_RU.UTF-8'}, clear=True):
            self.assertEqual(resolve_language('auto'), 'ru')
            self.assertEqual(translate('Выход', 'auto'), 'Выход')
            self.assertEqual(translate('Выход', 'en'), 'Quit')
        with patch.dict(os.environ, {'LANG': 'de_DE.UTF-8'}, clear=True):
            self.assertEqual(resolve_language('auto'), 'en')
            self.assertEqual(translate('Выход', 'ru'), 'Выход')

    def test_catalog_and_format(self):
        for source, target in EN.items():
            self.assertTrue(source and target)
        self.assertEqual(translate('Мышь сообщает {percent}%. Подключите кабель.', 'en').format(percent=10),
                         'Mouse reports 10%. Connect the cable.')


class InstallerTests(unittest.TestCase):
    def test_render_templates_preserves_venv_and_quotes_paths(self):
        import shutil
        with tempfile.TemporaryDirectory(prefix='ardor space % ') as directory:
            root = Path(directory)
            project = Path(__file__).resolve().parents[1]
            for subdirectory in ('systemd', 'desktop'):
                shutil.copytree(project / subdirectory, root / subdirectory)
            python = root / '.venv/bin/python'
            service, desktop, launcher = render(root, python)
            self.assertIn(systemd_quote(python), service)
            self.assertNotIn('@PYTHON@', service + desktop)
            self.assertNotIn('@ROOT@', service)
            self.assertNotIn('@TRAY@', service + desktop)
            self.assertIn('%%', service)
            self.assertIn('"$@"', launcher)
            self.assertIn('.venv/bin/python', launcher)
