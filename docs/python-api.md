# Python API

[Все руководства](README.md) · [Установка](installation.md)

Библиотека `ranobe_downloader` позволяет получать метаданные и скачивать книги из Python без терминальных меню. Достаточно базовой установки пакета; отдельный HTTP-сервер не нужен.

## Минимальный пример

Замените значение `reference` реальной ссылкой на произведение:

```python
from ranobe_downloader import Downloader

reference = "ССЫЛКА_НА_ПРОИЗВЕДЕНИЕ"
with Downloader(provider="ranobelib") as downloader:
    book = downloader.get_book(reference)
    print(book.title, book.chapter_count)
    for translation in book.translations:
        print(translation.branch_id, translation.name, translation.chapter_count)

    branch = book.translations[0].branch_id if book.translations else None
    result = downloader.download(
        book,
        branch_id=branch,
        format="epub",
        output="output/book.epub",
        limit=10,
        resume=True,
        progress=lambda current, total, chapter: print(current, total, chapter),
    )
    print(result)
```

Пример выбирает первый перевод и первые 10 глав. В приложении с выбором перевода используйте `branch_id`, выбранный пользователем. `result` — путь `Path` к готовому файлу.

## Основные методы

| Метод | Результат |
| --- | --- |
| `get_book(reference)` | Подготовленный `Book`: название, авторы, переводы, индекс глав |
| `book.list_chapters(branch_id)` | Главы перевода: `id`, `volume`, `number`, `name` |
| `download(book_or_reference, ...)` | Скачивание и экспорт, возвращает `Path` |

В `download` можно передать ссылку напрямую. Если метаданные уже получены, передавайте `Book`, чтобы не запрашивать индекс повторно.

## Параметры скачивания

- `format`: `epub`, `txt` или `html`.
- `output`: путь файла; без него используется каталог `output/`.
- `branch_id`: перевод; `limit`: максимум глав.
- `chapter_start_id`/`chapter_end_id`: включительные границы по ID.
- `chapter_from`/`chapter_to`: границы по номерам, если они однозначны.
- `resume=True`, `cache_dir`: повторное использование проверенного кеша.
- `progress(current, total, chapter)`: обработчик прогресса; `status(message)`: сообщения этапов.

[Подробные правила диапазонов](chapter-id-selection.md).

## Токен и жизненный цикл

Для MangaLib укажите `Downloader(provider="mangalib", token=token)`; для RanobeLib используется `provider="ranobelib"` (по умолчанию). Для авторизации передайте `token=token`, получив секрет из защищённой конфигурации вашего приложения. Библиотека сама не читает keyring и не запрашивает ввод. Не прописывайте реальный токен в исходниках.

Контекстный менеджер `with` закрывает созданный библиотекой HTTP-клиент. Внешние клиенты остаются собственностью вызывающего кода. Один экземпляр синхронный и не предназначен для одновременных вызовов из нескольких потоков.

Для тестирования и расширений можно передать собственный `backend=BookDownloader(...)` с внедрёнными провайдерами.

## Ошибки

`AuthenticationError` соответствует HTTP 401/403, `ProviderError` — другим ошибочным HTTP-статусам, `NetworkError` — транспортным ошибкам. Все наследуют `DownloaderError`. Ошибки параметров могут быть `ValueError`/`TypeError`; ошибки файлов и экспорта сохраняют собственные типы.

```python
from ranobe_downloader import Downloader, DownloaderError

try:
    with Downloader() as downloader:
        downloader.download("ССЫЛКА_НА_ПРОИЗВЕДЕНИЕ", format="txt", limit=1)
except DownloaderError as error:
    print(type(error).__name__, str(error))
```

API экспериментальный; перед обновлением версии проверьте [changelog](../CHANGELOG.md).

Для примера MangaLib и особенности его API см. [руководство MangaLib](mangalib.md).
