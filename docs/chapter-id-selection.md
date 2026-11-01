# Chapter selection by ID

The core now accepts stable chapter IDs as inclusive boundaries **after filtering by translation and sorting in reading order**. Chapter IDs need not increase with chapter order.

Python API example:

```python
from ranobe_downloader import Downloader

with Downloader() as downloader:
    book = downloader.get_book("271947--example")
    for chapter in book.list_chapters(branch_id=123):
        print(chapter["id"], chapter["volume"], chapter["number"], chapter["name"])
    downloader.download(
        book, branch_id=123, chapter_start_id=1001, chapter_end_id=1005,
        format="epub", resume=True,
    )
```

CLI:

```bash
ranobe download "271947--example" --branch 123 --list-chapters
ranobe download "271947--example" --branch 123 --start-id 1001 --end-id 1005
```

Web API: `GET /api/books/chapters` now includes `id`; `POST /api/downloads` accepts `chapter_start_id` and `chapter_end_id`.

Telegram: the chapter-picker buttons use the IDs internally, while showing volume and chapter numbers.

Do not combine ID selection with legacy `chapter_from` / `chapter_to` number selection. Boundaries must exist in the chosen translation; a reversed pair fails before downloading chapters. Both ID boundaries are optional. `limit` applies to the resulting span.

The existing `chapter_from` and `chapter_to` number parameters remain for backward compatibility.
