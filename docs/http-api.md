# HTTP API (experimental)

Install the optional dependencies:

```bash
python -m pip install -e '.[http]'
python -m uvicorn interfaces.http.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation.

- `GET /api/health` — process health.
- `GET /api/books?reference=...` — title, chapters and translation branches.
- `POST /api/downloads` — start a download with JSON body `{"reference":"123--title","format":"epub","branch_id":null,"limit":null,"resume":false}`.
- `GET /api/downloads/{id}` — state: `queued`, `running`, `completed` or `failed`, and chapter progress.
- `GET /api/downloads/{id}/file` — download the generated file once completed.

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/downloads \
  -H 'Content-Type: application/json' \
  -d '{"reference":"271947--chuanyue-zhi-xian-yu-qie-shi-de-richang","format":"txt"}'
```

The default deployment is **local only**. **Do not expose this unauthenticated API to the internet.** It has no identity, multi-user authorization, per-user quotas, cancellation or durable task storage. Protect remote deployments with an authenticated reverse proxy and rate limits before allowing external traffic. Jobs and progress are held in memory and disappear on restart; finished files remain on disk. The default executor has two workers, and the server accepts at most 50 jobs during its lifetime. For now, it is a local MVP for UI, bot, and other adapters.
