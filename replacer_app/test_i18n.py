import re
import unittest
from pathlib import Path


WEB = Path(__file__).parent / 'web'


class InternationalizationTests(unittest.TestCase):
    def setUp(self):
        self.html = (WEB / 'index.html').read_text(encoding='utf-8')
        self.app = (WEB / 'app.js').read_text(encoding='utf-8')
        self.i18n = (WEB / 'i18n.js').read_text(encoding='utf-8')

    def translation_keys(self, source):
        return set(re.findall(r'(?:^|[,{]\s*)([A-Za-z][A-Za-z0-9]*):', source, flags=re.MULTILINE))

    def test_english_is_safe_static_default_and_i18n_loads_first(self):
        self.assertIn('<html lang="en">', self.html)
        self.assertIn('<title>RE4 · Character Replacer</title>', self.html)
        self.assertLess(self.html.index('/i18n.js'), self.html.index('/app.js'))

    def test_every_ui_key_exists_in_both_languages(self):
        zh = self.i18n.split("'zh-CN': {", 1)[1].split("\n    },\n    en: {", 1)[0]
        en = self.i18n.split("\n    en: {", 1)[1].split("\n    }\n  };", 1)[0]
        required = set(re.findall(r'data-i18n(?:-[a-z-]+)?="([A-Za-z0-9]+)"', self.html))
        required.update(re.findall(r"\bt\('([A-Za-z0-9]+)'", self.app))
        required.update({'front', 'back', 'side', 'leftHand', 'rightHand'})
        self.assertEqual(set(), required - self.translation_keys(zh))
        self.assertEqual(set(), required - self.translation_keys(en))

    def test_manual_language_switch_is_persistent(self):
        self.assertIn("localStorage.setItem('replacer.language', language)", self.i18n)
        self.assertIn("fetch('/api/language'", self.i18n)
        self.assertIn("$('languageButton').onclick", self.app)
        self.assertIn("url.searchParams.set('lang', language)", self.i18n)


if __name__ == '__main__':
    unittest.main()
