import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from core.book_downloader import BookDownloader


def chapter(number, branches):
    return SimpleNamespace(volume='1', number=str(number), name=f'Chapter {number}',
                           branches=[SimpleNamespace(branch_id=b) for b in branches], index=None,
                           id=int(number))


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.exporter = Mock()
        self.exporter.export.return_value = 'book.epub'
        self.downloader = BookDownloader(Mock(), self.exporter)
        self.downloader.titles.get_title = Mock(return_value=SimpleNamespace(
            id=7, slug_url='7--example', title='Book', authors=('Author',), description='Summary'))
        self.downloader.contents.get_chapter = Mock(return_value=SimpleNamespace(
            data={'id': 888, 'volume': '1', 'number': '2', 'name': 'One', 'content': {'type': 'doc', 'content': [
                {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Hello'}]}]}},
            content={'type': 'doc', 'content': []}))

    def test_prepare_translations_and_reuse(self):
        self.downloader.chapters.get_chapters = Mock(return_value=[
            chapter(2, [10, 20]), chapter(1, [10]),
        ])
        plan = self.downloader.prepare('7')
        self.assertEqual([(t.branch_id, t.chapter_count) for t in plan.translations],
                         [(10, 2), (20, 1)])
        self.downloader.download(plan, 'book.epub', branch_id=20,
                                 limit=1, delay=0, cache_dir=self.temp.name)
        self.downloader.titles.get_title.assert_called_once()
        self.downloader.chapters.get_chapters.assert_called_once()

    def test_ambiguous_branch_fails_before_download(self):
        self.downloader.chapters.get_chapters = Mock(return_value=[chapter(1, [10, 20])])
        with self.assertRaisesRegex(ValueError, 'Multiple translations'):
            self.downloader.download('7', 'book.epub')
        self.downloader.contents.get_chapter.assert_not_called()

    def test_sorted_and_limited(self):
        self.downloader.chapters.get_chapters = Mock(return_value=[chapter(10, [10]), chapter(2, [10])])
        self.assertEqual(self.downloader.download('7', 'book.epub', branch_id=10, limit=1, cache_dir=self.temp.name, delay=0), 'book.epub')
        self.downloader.contents.get_chapter.assert_called_once_with(
            '7--example', volume='1', number='2', branch_id=10)
        self.assertEqual(len(self.exporter.export.call_args.kwargs['chapters']), 1)

    def test_download_does_not_export_after_chapter_failure(self):
        self.downloader.chapters.get_chapters = Mock(return_value=[chapter(1, [10])])
        self.downloader.contents.get_chapter = Mock(side_effect=ValueError('API failure'))
        with self.assertRaisesRegex(ValueError, 'API failure'):
            self.downloader.download('7', 'book.epub', branch_id=10)
        self.exporter.export.assert_not_called()

    def test_statistics_callback(self):
        self.downloader.chapters.get_chapters = Mock(return_value=[chapter(2, [10])])
        received = []
        self.downloader.download(
            '7', 'book.epub', branch_id=10, cache_dir=self.temp.name,
            delay=0, statistics=received.append,
        )
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].chapters, 1)
        self.assertEqual(received[0].images, 0)
        self.assertEqual(received[0].saved_image_percent, 0.0)
        self.assertEqual(received[0].cached_chapters, 0)
        self.assertEqual(received[0].epub_bytes, 0)

    def test_fractional_range_only_downloads_selected_chapters(self):
        items = [chapter(46, [10]), chapter(14, [10]), chapter(13, [20]),
                 chapter(45, [10]), chapter(1, [10])]
        fractional = chapter(13, [10])
        fractional.number = "13.4"
        items.append(fractional)
        self.downloader.chapters.get_chapters = Mock(return_value=items)

        def chapter_response(reference, *, volume, number, branch_id):
            return SimpleNamespace(data={
                "id": 888, "volume": volume, "number": number,
                "name": f"Chapter {number}",
                "content": {"type": "doc", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]}
                ]},
            })

        self.downloader.contents.get_chapter = Mock(side_effect=chapter_response)
        self.downloader.download(
            "7", "book.epub", branch_id=10,
            chapter_from="13.4", chapter_to="45",
            delay=0, cache_dir=self.temp.name,
        )
        sent = [call.kwargs["number"] for call in self.downloader.contents.get_chapter.call_args_list]
        self.assertEqual(sent, ["13.4", "14", "45"])
        self.assertEqual(len(self.exporter.export.call_args.kwargs["chapters"]), 3)

    def test_range_failure_before_content_request(self):
        self.downloader.chapters.get_chapters = Mock(return_value=[chapter(1, [10])])
        with self.assertRaisesRegex(ValueError, "not available"):
            self.downloader.download("7", "book.epub", branch_id=10,
                                     chapter_from="99", cache_dir=self.temp.name)
        self.downloader.contents.get_chapter.assert_not_called()

    def test_no_statistics_on_failure(self):
        self.downloader.chapters.get_chapters = Mock(return_value=[chapter(2, [10])])
        self.downloader.contents.get_chapter = Mock(side_effect=ValueError('failure'))
        received = []
        with self.assertRaises(ValueError):
            self.downloader.download(
                '7', 'book.epub', branch_id=10, cache_dir=self.temp.name,
                delay=0, statistics=received.append,
            )
        self.assertEqual(received, [])


if __name__ == '__main__':
    unittest.main()
