import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.compatibility_audit import _sample_evenly, audit_title


class AuditTests(unittest.TestCase):
    def test_even_sample(self):
        self.assertEqual(_sample_evenly(list(range(10)), 3), [0, 4, 9])
        self.assertEqual(_sample_evenly(list(range(3)), 10), [0, 1, 2])

    def test_structured_content_and_unknown_node(self):
        title = SimpleNamespace(id=7, slug_url="7--book", title="Book",
                                authors=(), description="", cover_url=None)
        chapter = SimpleNamespace(id=1, volume="1", number="1", index=1,
                                  name="First", branches=[SimpleNamespace(branch_id=11)])
        with patch("core.compatibility_audit.TitleProvider") as tp, patch(
            "core.compatibility_audit.ChapterProvider") as cp, patch(
            "core.compatibility_audit.ChapterContentProvider") as dp:
            tp.return_value.get_title.return_value = title
            cp.return_value.get_chapters.return_value = [chapter]
            dp.return_value.get_chapter.return_value = SimpleNamespace(
                title="First", content={"type": "doc", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]}]})
            good = audit_title(Mock(), "7")
            self.assertEqual(good["status"], "COMPATIBLE")
            self.assertEqual(good["passed"], 1)
            dp.return_value.get_chapter.return_value = SimpleNamespace(
                title="First", content={"type": "doc", "content": [{"type": "image"}]})
            bad = audit_title(Mock(), "7")
            self.assertEqual(bad["status"], "INCOMPATIBLE")
            self.assertEqual(bad["node_types"]["image"], 1)
            metadata = audit_title(Mock(), "7", metadata_only=True)
            self.assertEqual(metadata["status"], "NOT_TESTED")
            self.assertEqual(dp.return_value.get_chapter.call_count, 2)
