# HTTP API chapter selection

List chapters without downloading chapter bodies:

```http
GET /api/books/chapters?reference=271947--example&branch_id=123
```

Response includes `book_id`, `branch_id`, and an ordered `chapters` array containing `volume`, `number`, and `name`.

Start an inclusive range download:

```json
{
  "reference": "271947--example",
  "format": "epub",
  "branch_id": 123,
  "chapter_from": "13.4",
  "chapter_to": "45",
  "resume": true
}
```

Send the body to `POST /api/downloads` and track it using `GET /api/downloads/{id}`. The chapter numbers are strings to preserve decimal precision; both bounds are optional and must exist in the selected translation. Invalid ranges currently appear as failed asynchronous jobs because they are checked by the core after submission.

The API remains intended for localhost only until authentication and rate limiting are added.
