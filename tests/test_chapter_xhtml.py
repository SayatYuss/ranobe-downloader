import unittest
from xml.etree import ElementTree
from core.chapter_xhtml import chapter_to_xhtml


class XhtmlTests(unittest.TestCase):
    def test_content_escaped_and_formatted(self):
        doc = {'type': 'doc', 'content': [
            {'type': 'paragraph', 'content': [
                {'type': 'text', 'text': 'A & B'},
                {'type': 'text', 'text': ' bold', 'marks': [{'type': 'bold'}]},
            ]},
        ]}
        out = chapter_to_xhtml('Title <1>', doc)
        ElementTree.fromstring(out)
        self.assertIn('A &amp; B', out)
        self.assertIn('<strong> bold</strong>', out)
        self.assertIn('Title &lt;1&gt;', out)

    def test_unknown_nodes_fail(self):
        with self.assertRaises(ValueError):
            chapter_to_xhtml('Title', {'type': 'image', 'attrs': {'src': 'https://example.org'}})

    def test_html_is_not_silently_converted(self):
        with self.assertRaises(ValueError):
            chapter_to_xhtml('Title', '<p>HTML</p>')


if __name__ == '__main__':
    unittest.main()
