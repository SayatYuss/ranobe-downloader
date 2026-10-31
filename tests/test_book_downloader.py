import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from core.book_downloader import BookDownloader


def chapter(number, branches):
    return SimpleNamespace(volume='1', number=str(number), name=f'Chapter {number}',
                           branches=[SimpleNamespace(branch_id=b) for b in branches], index=None)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.exporter = Mock()
        self.exporter.export.return_value = 'book.epub'
        self.downloader = BookDownloader(Mock(), self.exporter)
        self.downloader.titles.get_title = Mock(return_value=SimpleNamespace(
            id=7, slug_url='7--example', title='Book', authors=('Author',), description='Summary'))
        self.downloader.contents.get_chapter = Mock(return_value=SimpleNamespace(
            title='One', content={'type': 'doc', 'content': [
                {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Hello'}]}]}))

    def test_ambiguous_branch_fails_before_download(self):
        self.downloader.chapters.get_chapters = Mock(return_value=[chapter(1, [10, 20])])
        with self.assertRaisesRegex(ValueError, 'Multiple translations'):
            self.downloader.download('7', 'book.epub')
        self.downloader.contents.get_chapter.assert_not_called()

    def test_sorted_and_limited(self):
        self.downloader.chapters.get_chapters = Mock(return_value=[chapter(10, [10]), chapter(2, [10])])
        self.assertEqual(self.downloader.download('7', 'book.epub', branch_id=10, limit=1), 'book.epub')
        self.downloader.contents.get_chapter.assert_called_once_with(
            '7--example', volume='1', number='2', branch_id=10)
        self.assertEqual(len(self.exporter.export.call_args.kwargs['chapters']), 1)

    def test_download_does_not_export_after_chapter_failure(self):
        self.downloader.chapters.get_chapters = Mock(return_value=[chapter(1, [10])])
        self.downloader.contents.get_chapter = Mock(side_effect=ValueError('API failure'))
        with self.assertRaisesRegex(ValueError, 'API failure'):
            self.downloader.download('7', 'book.epub', branch_id=10)
        self.exporter.export.assert_not_called()


if __name__ == '__main__':
    unittest.main()
