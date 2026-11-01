# Telegram bot — inline interface

The Telegram bot is optional and runs **without** FastAPI, Web UI, webhooks, or a public server.

## Installation

1. Create a bot with [@BotFather](https://t.me/BotFather) and obtain a token.
2. Install the bot dependencies: `python -m pip install -e '.[telegram]'`
3. Set environment variables (fish example):

```fish
set -x TELEGRAM_BOT_TOKEN 'NEW_TOKEN_FROM_BOTFATHER'
set -x TELEGRAM_ALLOWED_USER_IDS 'YOUR_NUMERIC_TELEGRAM_ID'
# Optional RanobeLib token:
set -x RANOBE_TOKEN 'RANOBELIB_TOKEN'
ranobe-bot
```

Send a RanobeLib HTTPS book URL as a **normal message** in a private chat. The bot displays book metadata, translators and an optional cover, with a Download button. Next: translation selection (skipped if one or none), chapter selection (all, first 10, last 10, or a paginated start/end choice), and format (EPUB/TXT/HTML). The downloader is invoked through the existing Python Library, reusing the prepared chapter index in memory.

Large files: the standard configuration refuses to upload files greater than **45 MiB** and suggests a smaller chapter range or the CLI (`ranobe download <reference>`). Temporary generated files are deleted after handling; verified chapter caches remain.

## Constraints

- Session and selections exist only in process memory and are lost on restart.
- One running download per user, two concurrent downloads per process by default.
- Keep `TELEGRAM_ALLOWED_USER_IDS` set when using a personal bot. Without it, any Telegram account can request downloads.
- Выбор диапазона выполняется по ID глав в пределах выбранного перевода; том и номер показываются только для удобства пользователя.
- No full-book search, inline Telegram mode, Telegram payments, or externally hosted infrastructure is required.
- Library HTTP logs are reduced to WARNING to avoid exposing bot tokens in request URLs. Revoke any BotFather token already exposed in logs.
