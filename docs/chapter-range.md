# Chapter selection (Python API)

The downloader can select a **specific inclusive range of chapter numbers**
after selecting a translation branch. Decimal chapter numbers are compared
exactly (using `Decimal`), not as floating-point indexes.

```python
from ranobe_downloader import Downloader

with Downloader() as downloader:
    book = downloader.get_book("271947--example")
    for chapter in book.list_chapters(branch_id=123):
        print(chapter["volume"], chapter["number"], chapter["name"])

    path = downloader.download(
        book,
        format="epub",
        branch_id=123,
        chapter_from="13.4",
        chapter_to="45",
        resume=True,
    )
```

Both bounds are optional; when both are omitted all chapters are selected.
Bounds are inclusive and must match numbers that actually occur in the selected
translation. Reversed, missing, invalid and ambiguous-across-volumes boundaries
are rejected before any chapter contents are downloaded. `limit`, if supplied,
applies **after** range filtering.

This feature is implemented in the core and Python API; it is **not yet wired**
to the CLI, Web API or Telegram bot.

The index contains chapters across all translations. Use
`book.list_chapters(branch_id=...)` to view the relevant translation.
