# Установка из исходников

[Все руководства](README.md)

Эта инструкция нужна для CLI, Python API, HTTP API, Telegram и запуска PySide6 из исходников. Если достаточно готового окна приложения, используйте [сборку из Releases](desktop.md).

## Требования

- Git и Python **3.10 или новее**.
- Доступ к RanobeLib.
- Node.js **22** и npm — только для Web UI (эта версия используется в CI).

## Получение проекта

```bash
git clone https://github.com/SayatYuss/ranobe-downloader.git
cd ranobe-downloader
```

Основная ветка — `main`; разработка ведётся в `develop`. Для воспроизводимого запуска конкретного выпуска можно переключиться на его тег, например `git switch --detach v0.4.0`.

## Виртуальное окружение

Linux/macOS, bash или zsh:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Для fish вместо последней команды: `source .venv/bin/activate.fish`.

Windows, PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Если активация PowerShell запрещена политикой системы, используйте `.\.venv\Scripts\python.exe` напрямую вместо `python`. Для запуска CLI без активации: `.\.venv\Scripts\ranobe.exe --help`.

Следующие команды выполняются **из корня репозитория**. При активном окружении `python` и установленные команды относятся к этому окружению.

## Установка нужного интерфейса

| Интерфейс | Команда |
| --- | --- |
| CLI и Python API | `python -m pip install -e .` |
| PySide6 | `python -m pip install -e '.[desktop,images]'` |
| HTTP API / сервер Web UI | `python -m pip install -e '.[http]'` |
| Telegram | `python -m pip install -e '.[telegram]'` |
| Все интерфейсы для разработки | `python -m pip install -e '.[desktop,http,telegram,images]'` |

Опция `-e` связывает установленный пакет с исходниками. Дополнение `images` устанавливает Pillow для оптимизации изображений; для обычного экспорта исходных изображений оно не обязательно.

Проверка базовой установки:

```bash
ranobe --version
ranobe --help
```

Далее выберите [руководство интерфейса](README.md). Для Web UI зависимости npm устанавливаются отдельно. Для сохранения токена CLI/Desktop нужен работающий системный keyring — [подробнее](authentication.md).
