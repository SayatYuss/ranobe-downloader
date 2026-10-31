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

    def test_full_mode_scans_all_chapters(self):
        title = SimpleNamespace(id=7, slug_url="7--book", title="Book",
                                authors=(), description="", cover_url=None)
        chapters = [SimpleNamespace(id=i, volume="1", number=str(i), index=i,
                    name=str(i), branches=[SimpleNamespace(branch_id=11)])
                    for i in range(1, 4)]
        with patch("core.compatibility_audit.TitleProvider") as tp, patch(
            "core.compatibility_audit.ChapterProvider") as cp, patch(
            "core.compatibility_audit.ChapterContentProvider") as dp:
            tp.return_value.get_title.return_value = title
            cp.return_value.get_chapters.return_value = chapters
            dp.return_value.get_chapter.return_value = SimpleNamespace(
                title="Chapter", content={"type": "doc", "content": []})
            result = audit_title(Mock(), "7", sample=1, mode="full")
            self.assertEqual(result["sampled"], 3)
            self.assertEqual(result["status"], "COMPATIBLE")

    def test_ambiguous_branches_remain_inconclusive(self):
        title = SimpleNamespace(id=7, slug_url="7--book", title="Book",
                                authors=(), description="", cover_url=None)
        chapter = SimpleNamespace(id=1, volume="1", number="1", index=1,
                                  name="One", branches=[
                                      SimpleNamespace(branch_id=11),
                                      SimpleNamespace(branch_id=22)])
        with patch("core.compatibility_audit.TitleProvider") as tp, patch(
            "core.compatibility_audit.ChapterProvider") as cp, patch(
            "core.compatibility_audit.ChapterContentProvider") as dp:
            tp.return_value.get_title.return_value = title
            cp.return_value.get_chapters.return_value = [chapter]
            dp.return_value.get_chapter.return_value = SimpleNamespace(
                title="One", content={"type": "doc", "content": []})
            result = audit_title(Mock(), "7", mode="sample")
            self.assertEqual(result["status"], "INCONCLUSIVE")

    def test_rate_limit_is_inconclusive(self):
        import httpx
        title = SimpleNamespace(id=7, slug_url="7--book", title="Book",
                                authors=(), description="", cover_url=None)
        chapter = SimpleNamespace(id=1, volume="1", number="1", index=1,
                                  name="One", branches=[SimpleNamespace(branch_id=11)])
        request = httpx.Request("GET", "https://example.org/chapter")
        response = httpx.Response(429, request=request)
        error = httpx.HTTPStatusError("rate limit", request=request, response=response)
        with patch("core.compatibility_audit.TitleProvider") as tp, patch(
            "core.compatibility_audit.ChapterProvider") as cp, patch(
            "core.compatibility_audit.ChapterContentProvider") as dp:
            tp.return_value.get_title.return_value = title
            cp.return_value.get_chapters.return_value = [chapter]
            dp.return_value.get_chapter.side_effect = error
            result = audit_title(Mock(), "7", retries=1, delay=0)
            self.assertEqual(result["status"], "INCONCLUSIVE")
            self.assertEqual(result["unverified"], 1)
            self.assertEqual(result["failed"], 0)


    def test_progress_and_resume_skip_completed_chapters(self):
        title = SimpleNamespace(id=7, slug_url="7--book", title="Book",
                                authors=(), description="", cover_url=None)
        chapters = [SimpleNamespace(id=i, volume="1", number=str(i), index=i,
                                    name=str(i), branches=[SimpleNamespace(branch_id=11)])
                    for i in range(1, 4)]
        with patch("core.compatibility_audit.TitleProvider") as tp, patch(
            "core.compatibility_audit.ChapterProvider") as cp, patch(
            "core.compatibility_audit.ChapterContentProvider") as dp:
            tp.return_value.get_title.return_value = title
            cp.return_value.get_chapters.return_value = chapters
            dp.return_value.get_chapter.return_value = SimpleNamespace(
                title="One", content={"type": "doc", "content": []})
            snapshots = []
            def record(state, current, total):
                import copy
                snapshots.append(copy.deepcopy(state))
                self.assertEqual(total, 3)
            result = audit_title(Mock(), "7", mode="full", delay=0, progress=record)
            self.assertEqual([s["sampled"] for s in snapshots], [1, 2, 3])
            self.assertEqual(result["passed"], 3)
            dp.return_value.get_chapter.reset_mock()
            resumed = audit_title(Mock(), "7", mode="full", delay=0,
                                  resume_state=snapshots[1])
            self.assertEqual(resumed["passed"], 3)
            dp.return_value.get_chapter.assert_called_once()

    def test_html_image_audit_without_download(self):
        title = SimpleNamespace(id=7, slug_url="7--book", title="Book",
                                authors=(), description="", cover_url=None)
        chapter = SimpleNamespace(id=1, volume="1", number="1", index=1,
                                  name="One", branches=[SimpleNamespace(branch_id=11)])
        with patch("core.compatibility_audit.TitleProvider") as tp, patch(
            "core.compatibility_audit.ChapterProvider") as cp, patch(
            "core.compatibility_audit.ChapterContentProvider") as dp:
            tp.return_value.get_title.return_value = title
            cp.return_value.get_chapters.return_value = [chapter]
            dp.return_value.get_chapter.return_value = SimpleNamespace(
                title="One",
                content='<img src="/uploads/ranobe/book/chapters/1/image.png">',
                data={"id": 1, "attachments": []})
            result = audit_title(Mock(), "7", delay=0)
            self.assertEqual(result["status"], "COMPATIBLE")
            self.assertEqual(result["html_images"], 1)


    def test_retry_unverified_on_resume(self):
        import httpx
        title = SimpleNamespace(id=7, slug_url="7--book", title="Book",
                                authors=(), description="", cover_url=None)
        chapter = SimpleNamespace(id=1, volume="1", number="1", index=1,
                                  name="One", branches=[SimpleNamespace(branch_id=11)])
        request = httpx.Request("GET", "https://example.org/chapter")
        error = httpx.HTTPStatusError("limit", request=request,
                                      response=httpx.Response(429, request=request))
        with patch("core.compatibility_audit.TitleProvider") as tp, patch(
            "core.compatibility_audit.ChapterProvider") as cp, patch(
            "core.compatibility_audit.ChapterContentProvider") as dp:
            tp.return_value.get_title.return_value = title
            cp.return_value.get_chapters.return_value = [chapter]
            dp.return_value.get_chapter.side_effect = error
            first = audit_title(Mock(), "7", delay=0, retries=1)
            self.assertEqual(first["unverified_chapter_ids"], [1])
            dp.return_value.get_chapter.side_effect = None
            dp.return_value.get_chapter.return_value = SimpleNamespace(
                title="One", content={"type": "doc", "content": []})
            second = audit_title(Mock(), "7", delay=0, retries=1, resume_state=first)
            self.assertEqual(second["status"], "COMPATIBLE")
            self.assertEqual((second["passed"], second["unverified"]), (1, 0))

