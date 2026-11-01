# Ranobe Downloader

Скачивание произведений **RanobeLib** в EPUB 3, TXT и HTML. Проект включает настольное приложение на PySide6, CLI, Python-библиотеку, локальный HTTP API, Telegram-бота и Web UI. Все интерфейсы используют общее ядро скачивания.

> **Alpha / экспериментальный проект.** Скачивайте только материалы, на использование которых у вас есть право. Уважайте правила сервиса и ограничения API. Недоступные платные главы нельзя получить в обход контроля доступа.

## Возможности

| Компонент | Возможности | Инструкция |
| --- | --- | --- |
| Desktop | Нативное окно, очередь, история, кеш, токен и трей | [Desktop](docs/desktop.md) |
| CLI | Скачивание, список глав, выбор переводов и диапазонов, аудит совместимости | [CLI](docs/cli-chapter-range.md) |
| Python Library | Встраивание в собственные программы без консольного ввода | [Python API](docs/python-api.md) |
| HTTP API | Swagger, задания, очередь, прогресс, отмена и очистка | [HTTP API](docs/http-api.md) |
| Telegram | Ссылка в личном чате → кнопки выбора глав/формата → файл | [Telegram](docs/telegram-ui.md) |
| Web UI | Интерфейс на Vue 3: выбор книги/глав, список загрузок | [Web UI](docs/web-ui.md) |

Ядро поддерживает кеш глав и изображений, продолжение скачивания (`--resume`), обработку HTTP 429 и оптимизацию изображений. Главы можно выбирать **по ID** (надёжно при одинаковых номерах в разных томах) либо по номеру в старом API. Форматы: EPUB с оглавлением, TXT без встроенных изображений, HTML со встроенными медиафайлами.

## Быстрый старт: приложение для ПК

В [Releases](https://github.com/SayatYuss/ranobe-downloader/releases) скачайте файл для своей ОС:

| ОС | Файл |
| --- | --- |
| Windows x64 | `RanobeDownloader-Windows-x64.exe` |
| macOS | `RanobeDownloader-macOS.dmg` |
| Linux x86_64 | `RanobeDownloader-Linux-x86_64.AppImage` |

Python и Node.js для готовых сборок не нужны. [Запуск и особенности приложения](docs/desktop.md).

## Требования для запуска из исходников

- Python **3.10+**.
- Node.js и npm — **только для Web UI**.
- Доступ к RanobeLib; для закрытого контента может понадобиться токен своей учётной записи.
- Системный keyring — для сохранения CLI-токена через `ranobe login`.

## Быстрый старт: CLI

```bash
git clone https://github.com/SayatYuss/ranobe-downloader.git
cd ranobe-downloader
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
ranobe --help
```

В fish используй `source .venv/bin/activate.fish`.

```bash
# Посмотреть главы и их ID
ranobe download "https://ranobelib.me/ru/manga/271947--chuanyue-zhi-xian-yu-qie-shi-de-richang" --list-chapters

# Скачать выбранный фрагмент; ID возьми из списка глав
ranobe download "271947--chuanyue-zhi-xian-yu-qie-shi-de-richang" \
  --start-id 1001 --end-id 1010 --format epub --resume

# Альтернативный выбор по номерам глав, если они уникальны в данном переводе
ranobe download "271947--chuanyue-zhi-xian-yu-qie-shi-de-richang" \
  --from 13.4 --to 45 --format txt
```

ID `1001` и `1010` — **примеры**, замените их реальными значениями из `--list-chapters`. Если переводов несколько, укажи `--branch ID` или выбери перевод в интерактивном режиме. По умолчанию создаётся EPUB. Для авторизации: `ranobe login`, проверки `ranobe status`, выхода `ranobe logout`. Никогда не передавай секреты в URL или аргументах командной строки.

### Дополнительные зависимости

```bash
python -m pip install -e '.[images]'    # оптимизация изображений через Pillow
python -m pip install -e '.[http]'      # FastAPI + Uvicorn
python -m pip install -e '.[telegram]'  # Telegram-бот
python -m pip install -e '.[desktop,images]'  # приложение PySide6
```

## Web UI + HTTP API (локально)

В первом терминале, из корня проекта:

```bash
python -m pip install -e '.[http]'
uvicorn interfaces.http.api:app --host 127.0.0.1 --port 8000
```

Во втором:

```bash
cd web
npm install
npm run dev
```

Web UI: **http://127.0.0.1:5173**. Swagger: **http://127.0.0.1:8000/docs**. В режиме разработки Vite автоматически проксирует `/api` к FastAPI.

**Важно:** HTTP API не имеет встроенной аутентификации. Не публикуй его в интернете без авторизации, HTTPS, ограничения частоты запросов и контроля доступа к файлам. Задачи хранятся в памяти; после перезапуска сервера история теряется.

## Telegram-бот

```bash
python -m pip install -e '.[telegram]'
```

Нужно установить переменные `TELEGRAM_BOT_TOKEN` и желательно `TELEGRAM_ALLOWED_USER_IDS`. Затем запустить `ranobe-bot`. Отправь боту HTTPS-ссылку на RanobeLib в личном чате и выбирай действия кнопками. Настройка окружения и ограничения отправки файлов: [docs/telegram-ui.md](docs/telegram-ui.md).

## Python Library

```python
from ranobe_downloader import Downloader

with Downloader() as downloader:
    book = downloader.get_book("271947--chuanyue-zhi-xian-yu-qie-shi-de-richang")
    chapters = book.list_chapters()
    print(book.title, chapters[0]["id"])
    downloader.download(book, chapter_start_id=chapters[0]["id"], format="epub")
```

См. [Python API](docs/python-api.md) для выбора перевода, ошибок и зависимостей.

## Структура репозитория

```text
core/                 движок, план, кеш, выбор глав и обработка контента
providers/libsocial/  провайдер RanobeLib
exporters/            EPUB / TXT / HTML
ranobe_downloader/    публичная Python-библиотека
interfaces/pyside6/   настольное приложение Qt
interfaces/cli/       CLI
interfaces/http/      FastAPI
interfaces/telegram/  Telegram-бот
web/                  Vue 3 + Vite
tests/                модульные и интеграционные тесты с фиктивными данными
docs/                 инструкции по интерфейсам
```

## Проверка и релиз

```bash
python -m pip install -e '.[desktop,http,telegram,images]'
python -m unittest discover -s tests -v
cd web && npm install && npm run build
```

Подготовка выпуска **0.4.0**: [docs/release-0.4.0.md](docs/release-0.4.0.md). История: [CHANGELOG.md](CHANGELOG.md).

## Ограничения

- Поддерживается RanobeLib; другие провайдеры пока не реализованы.
- Платные или недоступные главы пропускаются; получившийся файл может быть неполным.
- TXT не встраивает картинки. HTML со встроенными изображениями может занимать много места.
- Бот ограничивает размер отправляемого файла; большие книги удобнее скачивать через CLI/Web UI.
- Веб-интерфейс не показывает обложку (сейчас API её не отдаёт).
- HTTP-задания и Telegram-сессии не сохраняются между перезапусками.
- Проект развивается, стабильность API до релиза не гарантируется.

## Вклад и лицензия

Предложения и исправления: [CONTRIBUTING.md](CONTRIBUTING.md). По вопросам безопасности: [SECURITY.md](SECURITY.md).

Исходный код проекта предлагается распространять по лицензии **MIT**: см. [LICENSE](LICENSE). Лицензия касается кода репозитория, а **не** книг и другого стороннего контента.
