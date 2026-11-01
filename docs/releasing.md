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

Release проверяет тег, тестирует пакет, собирает wheel/sdist и Web UI, создаёт GitHub Release, затем вызывает сборки PySide6. Ожидаются шесть файлов: wheel, исходный tar.gz, Web UI tar.gz, EXE, DMG, AppImage. После успешного завершения build и desktop отдельный job публикует только wheel и sdist в PyPI через Trusted Publishing. Web UI и desktop-файлы в PyPI не отправляются.

Предварительный выпуск определяется шаблоном workflow: `a`, `b`, `rc` или `dev` с номером.

## Ошибки сборки

Релиз может уже содержать Python/Web UI до окончания desktop jobs. Проверьте все jobs и assets до объявления выпуска.

Временную ошибку runner можно проверить повторным запуском упавшего job. Он использует прежний коммит. Изменения workflow на другой ветке не исправляют старый тег: для исправления исходников выпускайте новую версию.

## Настройка PyPI (однократно)

В PyPI должен быть зарегистрирован publisher: проект `ranobe-downloader`, владелец `SayatYuss`, репозиторий `ranobe-downloader`, workflow `release.yml`, environment `pypi`.

В GitHub создайте environment `pypi` и разрешите deployment только тегам `v*`. При необходимости добавьте ручное подтверждение. API-токены и секрет PYPI_TOKEN не нужны.

В Settings → Actions → General разрешите **конкретный action** `pypa/gh-action-pypi-publish@release/v1` в списке разрешённых actions. Ограничение только на actions от GitHub и владельца репозитория иначе заблокирует публикацию: PyPA — отдельный владелец. Не требуется разрешать все сторонние actions.

Слияние PR и обычный push ветки не запускают PyPI job. Публикация начинается после отправки нового тега и успешной сборки GitHub Release и desktop-файлов. Job использует environment `pypi` и выдаёт `id-token: write` только шагам загрузки артефактов и публикации; исходники в нём не исполняются.

До первого выпуска команда `pip install ranobe-downloader` не является подтверждением наличия этого проекта в PyPI. После публикации проверьте владельца проекта, версию и установку:

```bash
python -m pip install "ranobe-downloader==0.4.1"
ranobe --version
```

При частичной публикации повторный запуск может встретить существующие файлы PyPI. Не пересобирайте замену под той же версией: проверьте состояние обоих архивов и выпускайте новую версию при изменении файлов. Эта настройка не включает TestPyPI.
