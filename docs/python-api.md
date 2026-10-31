# Python library API

Install the project in editable mode from the repository:

```bash
python -m pip install -e .
```

The package exposes a synchronous, non-interactive Python API independent of the CLI:

```python
from ranobe_downloader import Downloader

with Downloader(token=None) as downloader:
    book = downloader.get_book("271947--chuanyue-zhi-xian-yu-qie-shi-de-richang")
    print(book.title, book.chapter_count)
    for translation in book.translations:
        print(translation.branch_id, translation.name)

    result = downloader.download(
        book, format="epub", output="output/book.epub",
        branch_id=book.translations[0].branch_id if book.translations else None,
        resume=True, progress=lambda current, total, chapter: print(current, total, chapter),
    )
    print(result)
```

Pass `token="..."` for access to content available to your own account. The library never reads keyring or prompts for credentials; you supply them explicitly. A prepared `Book` avoids fetching the index twice. Formats: `epub`, `txt`, `html`. Pass a reference string directly to `download()` if you do not need metadata ahead of time.

For extensions and tests, pass `backend=BookDownloader(...)` to the facade to use separately injected providers. The facade closes only HTTP clients it creates itself; external clients remain caller-owned. A Downloader instance is synchronous and should not be used concurrently. Errors are propagated from core, network transport, and exporters, allowing callers to handle them.
