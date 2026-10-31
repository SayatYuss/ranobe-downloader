"""HTTP API tests using a fake library backend; no external services."""
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

try:
    from fastapi.testclient import TestClient
    from interfaces.http.api import create_app
except ImportError:
    TestClient = None


@unittest.skipUnless(TestClient is not None, "Install pip install -e '.[http]'")
class HttpApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        class FakeDownloader:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def get_book(self, reference):
                return SimpleNamespace(
                    id=7, title="Book", slug_url="7--book",
                    authors=("Writer",), chapter_count=1,
                    translations=(SimpleNamespace(branch_id=1, chapter_count=1,
                                                 name="English"),),
                )

            def download(self, reference, *, format, output, progress, **kwargs):
                progress(1, 1, "Done")
                output.write_text("content", encoding="utf-8")
                return output

        self.app = create_app(
            downloader_factory=FakeDownloader,
            output_dir=self.tmp.name,
            max_workers=1,
            max_jobs=2,
        )
        self.client = TestClient(self.app)

    def test_book_info_and_job_lifecycle(self):
        info = self.client.get("/api/books", params={"reference": "7--book"})
        self.assertEqual(info.status_code, 200)
        self.assertEqual(info.json()["translations"][0]["branch_id"], 1)

        response = self.client.post("/api/downloads", json={
            "reference": "7--book", "format": "txt",
        })
        self.assertEqual(response.status_code, 202)
        job_id = response.json()["id"]
        for _ in range(100):
            state = self.client.get(f"/api/downloads/{job_id}").json()
            if state["state"] in ("completed", "failed"):
                break
            time.sleep(0.01)
        self.assertEqual(state["state"], "completed")
        self.assertEqual(state["current"], 1)
        file_response = self.client.get(f"/api/downloads/{job_id}/file")
        self.assertEqual(file_response.status_code, 200)
        self.assertEqual(file_response.content, b"content")

    def test_reject_invalid_format_and_excess_jobs(self):
        self.assertEqual(self.client.post("/api/downloads", json={
            "reference": "7--book", "format": "pdf",
        }).status_code, 422)
        for _ in range(2):
            self.assertEqual(self.client.post("/api/downloads", json={
                "reference": "7--book", "format": "epub",
            }).status_code, 202)
        self.assertEqual(self.client.post("/api/downloads", json={
            "reference": "7--book", "format": "epub",
        }).status_code, 429)

    def test_unknown_and_incomplete_files(self):
        self.assertEqual(self.client.get("/api/downloads/unknown").status_code, 404)
        self.assertEqual(self.client.get("/api/downloads/unknown/file").status_code, 404)


if __name__ == "__main__":
    unittest.main()
