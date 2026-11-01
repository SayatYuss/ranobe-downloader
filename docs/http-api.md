# HTTP API (experimental)

Установка и локальный запуск:

```bash
python -m pip install -e '.[http]'
python -m uvicorn interfaces.http.api:app --host 127.0.0.1 --port 8000
```

Swagger: http://127.0.0.1:8000/docs.

| Метод | Endpoint | Назначение |
| --- | --- | --- |
| GET | `/api/health` | Состояние процесса |
| GET | `/api/books?reference=...` | Метаданные и переводы |
| GET | `/api/books/chapters?reference=...&branch_id=...` | Главы с ID, томом и номером |
| POST | `/api/downloads` | Поставить задачу в очередь (202) |
| GET | `/api/downloads` | Все задачи и состояние очереди |
| GET | `/api/downloads/{id}` | Статус и прогресс |
| POST | `/api/downloads/{id}/cancel` | Отмена (работающей — кооперативная) |
| DELETE | `/api/downloads/{id}` | Удаление завершённой задачи и файла |
| GET | `/api/downloads/{id}/file` | Результат загрузки |

Пример:

```bash
curl -X POST http://127.0.0.1:8000/api/downloads \\
  -H 'Content-Type: application/json' \\
  -d '{"reference":"271947--chuanyue-zhi-xian-yu-qie-shi-de-richang","format":"epub"}'
```

В JSON запроса поддерживаются `branch_id`, `limit`, `resume`, `chapter_start_id`, `chapter_end_id`, `chapter_from`, `chapter_to`. Диапазоны по ID и номеру нельзя смешивать.

`create_app(max_workers=2, max_jobs=50, max_queue=20, retention_seconds=3600)` задаёт лимиты. Завершённые задачи и их выходные файлы автоматически удаляются **при последующих запросах к API** после истечения срока хранения; кеш глав сохраняется. Данные очереди находятся в памяти и не переживают перезапуск. См. [управление задачами](http-jobs.md).

**Безопасность:** API не содержит собственной аутентификации, пользовательских ролей и изоляции файлов. Не открывай его в интернет без защищённого шлюза с авторизацией, HTTPS и rate limiting. По умолчанию привязывай сервер к loopback.
