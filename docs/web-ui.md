# Web UI (Vue 3 + Vite)

The browser interface is an optional, standalone frontend for the existing FastAPI HTTP API. It does not download from RanobeLib directly.

## Development

Start FastAPI in the repository root:

```bash
python -m pip install -e '.[http]'
uvicorn interfaces.http.api:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd web
npm install
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies all `/api` requests to `http://127.0.0.1:8000`, so CORS configuration is unnecessary.

## Workflow

1. Paste a RanobeLib title URL or numeric title reference and request book metadata.
2. Choose a translation when more than one is available.
3. Select all, first 10, last 10, or a custom inclusive range by **chapter ID** (the interface displays volumes and chapter numbers).
4. Choose EPUB, TXT or HTML, then start the download.
5. Follow queue position and progress in Downloads; cancel, remove or download finished results.

## Production

`npm run build` produces static files in `web/dist`. Serve them on the same origin as FastAPI, reverse-proxying `/api/*` to the Python server. The backend currently has no built-in user authentication. **Do not expose it publicly without an authenticated reverse proxy, suitable rate limits and TLS.**

The server keeps jobs in memory and cleans finished outputs after the configured retention period. Reloading the frontend does not delete jobs, but restarting FastAPI loses them.

The book API currently returns no cover image; the interface uses a neutral placeholder rather than making untrusted direct image requests.
