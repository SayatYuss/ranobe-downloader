# Процесс выпуска

[Все руководства](README.md) · [Участие в разработке](../CONTRIBUTING.md)

Инструкция для сопровождающих. Для установки пользователям достаточно [Releases](https://github.com/SayatYuss/ranobe-downloader/releases).

## Подготовка

1. Создайте рабочую ветку от `develop`.
2. Обновите `pyproject.toml`, changelog и документацию. Версия тега без `v` должна совпадать с версией пакета.
3. Откройте PR в `develop` и дождитесь Python, Web UI и PySide6 CI.
4. Проверьте готовые EXE/DMG/AppImage из artifacts на целевых ОС: скачивание, диапазон, очередь, отмену, историю, keyring и трей.
5. Слейте подготовку в `develop`, затем откройте PR `develop` → `main`. Прямой push в защищённые ветки не используется.

Проверки из активного окружения:

```bash
python -m pip install -e '.[desktop,http,telegram,images]'
python -m unittest discover -s tests -v
python -m pip install build twine
python -m build
python -m twine check dist/*
```

На Linux без дисплея задайте `QT_QPA_PLATFORM=offscreen`. В `web` отдельно выполните `npm install` и `npm run build`.

## Публикация

После успешного CI проверенного коммита `main` обновите локальную ветку и проверьте чистоту рабочего дерева. Замените `X.Y.Z` **новой** версией пакета:

```bash
git switch main
git pull --ff-only
git status --short
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

Отправка тега запускает публикацию. Опубликованные теги не перемещаются и не удаляются.

Release проверяет тег, тестирует пакет, собирает wheel/sdist и Web UI, создаёт GitHub Release, затем вызывает сборки PySide6. Ожидаются шесть файлов: wheel, исходный tar.gz, Web UI tar.gz, EXE, DMG, AppImage. Автоматической публикации в PyPI нет.

Предварительный выпуск определяется шаблоном workflow: `a`, `b`, `rc` или `dev` с номером.

## Ошибки сборки

Релиз может уже содержать Python/Web UI до окончания desktop jobs. Проверьте все jobs и assets до объявления выпуска.

Временную ошибку runner можно проверить повторным запуском упавшего job. Он использует прежний коммит. Изменения workflow на другой ветке не исправляют старый тег: для исправления исходников выпускайте новую версию.
