# Как выбирать перевод и главы

[Все руководства](README.md)

У произведения может быть несколько переводов. Сначала выбирается перевод (`branch_id`), затем из его глав — нужный диапазон.

## ID и номер — разные значения

Номер главы предназначен для читателя: например, том 2, глава 10. Номер может повторяться в другом томе. **ID главы** — идентификатор записи, используемый для точного выбора.

Числовое значение ID не задаёт порядок чтения. Диапазон строится по порядку глав после фильтрации перевода, а не по условию «ID от меньшего к большему».

В Desktop, Web UI и Telegram видны том и номер; соответствующий ID используется внутри интерфейса. В CLI и Python его можно получить из списка глав.

## Правила диапазона

- Обе границы включаются.
- Без начальной границы отсчёт идёт с начала перевода; без конечной — до конца.
- Без обеих границ выбирается весь перевод.
- Границы должны существовать в выбранном переводе; начало должно предшествовать концу или совпадать с ним.
- `limit` ограничивает число глав **после** выбора диапазона.
- ID перевода и ID главы не взаимозаменяемы.

## Python

```python
from ranobe_downloader import Downloader

reference = "ССЫЛКА_НА_ПРОИЗВЕДЕНИЕ"
with Downloader() as downloader:
    book = downloader.get_book(reference)
    branch = book.translations[0].branch_id if book.translations else None
    chapters = book.list_chapters(branch)
    for chapter in chapters:
        print(chapter["id"], chapter["volume"], chapter["number"], chapter["name"])
    if chapters:
        selected = chapters[:10]
        path = downloader.download(
            book, branch_id=branch,
            chapter_start_id=selected[0]["id"],
            chapter_end_id=selected[-1]["id"],
            output="output/first-chapters.epub", resume=True,
        )
        print(path)
```

Здесь для краткости выбран первый перевод. В собственном интерфейсе предложите пользователю выбрать перевод из `book.translations`.

## Выбор по номерам

Параметры `chapter_from`/`chapter_to` библиотеки и `--from`/`--to` CLI поддерживают номера вроде `13.4`. Они сравниваются как точные десятичные значения. Если номер границы отсутствует или повторяется в нескольких томах, выбор отклоняется; используйте ID.

Не смешивайте границы по номерам с `chapter_start_id`/`chapter_end_id` в одном запросе.

[CLI](cli-chapter-range.md) · [Python API](python-api.md) · [HTTP-примеры](http-chapter-range.md)
