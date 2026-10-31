import unittest
from core.chapter_xhtml import chapter_to_xhtml
from core.download.checkpoint import ChapterCheckpoint
from tempfile import TemporaryDirectory


class ContentFormatsTests(unittest.TestCase):
    def test_html_is_rendered_and_escaped(self):
        html = '<p data-paragraph-index="1">Привет&nbsp;&amp; мир</p><p>Вторая глава</p>'
        xhtml = chapter_to_xhtml('Тест', html)
        self.assertIn('<p>Привет', xhtml)
        self.assertIn('&amp; мир', xhtml)
        self.assertNotIn('data-paragraph-index', xhtml)

    def test_horizontal_rule(self):
        node = {'type': 'doc', 'content': [{'type': 'horizontalRule'}]}
        self.assertIn('<hr />', chapter_to_xhtml('Тест', node))

    def test_html_image_is_not_silently_dropped(self):
        with self.assertRaisesRegex(ValueError, 'attachment support'):
            chapter_to_xhtml('Тест', '<p>A</p><img src="https://other.example/test.png">')

    def test_html_checkpoint(self):
        with TemporaryDirectory() as tmp:
            store = ChapterCheckpoint(tmp, 82409, None)
            data = {'id': 1496632, 'volume': '1', 'number': '2',
                    'content': '<p>Text</p>'}
            store.save(999, data, volume='1', number='2')
            self.assertEqual(store.load(999, volume='1', number='2'), data)
