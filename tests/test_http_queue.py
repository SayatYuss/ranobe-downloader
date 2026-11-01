import tempfile
import threading
import time
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from interfaces.http.api import create_app

class QueueTests(unittest.TestCase):
    def test_queue_cancel_and_cleanup(self):
        gate = threading.Event()
        started = threading.Event()
        class Worker:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def download(self, reference, *, output, progress, **kwargs):
                started.set()
                gate.wait(5)
                progress(1, 1, "done")
                Path(output).write_text("ok")
                return output
        with tempfile.TemporaryDirectory() as directory:
            client = TestClient(create_app(downloader_factory=Worker, output_dir=directory,
                                           max_workers=1, max_jobs=5, max_queue=1,
                                           retention_seconds=1))
            def post():
                return client.post("/api/downloads", json={"reference": "book"})
            try:
                first = post()
                self.assertEqual(first.status_code, 202)
                self.assertTrue(started.wait(2))
                second = post()
                self.assertEqual(second.status_code, 202)
                self.assertEqual(post().status_code, 429)
                jid = second.json()["id"]
                self.assertEqual(client.post(f"/api/downloads/{jid}/cancel").json()["state"], "cancelled")
                self.assertEqual(client.delete(f"/api/downloads/{jid}").status_code, 204)
                self.assertEqual(client.get(f"/api/downloads/{jid}").status_code, 404)
                gate.set()
                first_id = first.json()["id"]
                for _ in range(100):
                    state = client.get(f"/api/downloads/{first_id}").json()["state"]
                    if state == "completed": break
                    time.sleep(0.01)
                self.assertEqual(state, "completed")
                self.assertEqual(client.delete(f"/api/downloads/{first_id}").status_code, 204)
            finally:
                gate.set()
