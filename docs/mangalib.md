# MangaLib

MangaLib доступен через CLI и Python API. Общие загрузчик, кеш, оптимизация изображений и EPUB/TXT/HTML-экспорт используются повторно.

## CLI

```bash
ranobe download "https://mangalib.me/ru/manga/102416--yomi-no-tsugai" --limit 3
```

Для приватных или ограниченных материалов используйте собственный Bearer-токен, сохранённый командой авторизации CLI. Загрузчик не обходит ограничения доступа.

## Python API

```python
from ranobe_downloader import Downloader

with Downloader(provider="mangalib", token=None) as downloader:
    book = downloader.get_book(
        "https://mangalib.me/ru/manga/102416--yomi-no-tsugai"
    )
    print(book.title, book.chapter_count)
    output = downloader.download(
        book, format="epub", output="yomi-no-tsugai.epub", limit=3
    )
    print(output)
```

Для MangaLib параметр `provider="mangalib"` обязателен. Токен необязателен для публичных произведений.

## Особенности API

- Метаданные: `GET /manga/{slug_url}`.
- Индекс глав: `GET /manga/{slug_url}/chapters`.
- Глава: `GET /manga/{slug_url}/chapter?volume=...&number=...`.
- Страницы приходят массивом `pages`; провайдер преобразует его в общий формат изображений.
- Изображения загружаются с CDN `img3.cdnlibs.org`; обложки — с `cover.imglib.info`.
- Для запросов используются `Site-Id: 1`, `Origin` и `Referer` MangaLib.

Схема API неофициальная и может измениться. Сохранённые Postman-примеры используются как контрактные фикстуры; сетевые интеграционные тесты не выполняются без реальных ответов API.
