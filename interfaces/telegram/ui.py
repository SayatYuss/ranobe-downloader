"""Telegram inline-keyboard flow backed by the public downloader library."""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup as K, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, ContextTypes, filters

from core.title import parse_title_reference
from ranobe_downloader import Downloader

logger = logging.getLogger(__name__)
MAX_FILE = 45 * 1024 * 1024
PAGE = 10


@dataclass
class Session:
    book: object
    message_id: int
    branch: int | None = None
    start: int | None = None
    end: int | None = None
    limit: int | None = None
    format: str = "epub"
    busy: bool = False


def kb(rows):
    return K([[B(label, callback_data=action) for label, action in row] for row in rows])


def chapters_of(session: Session):
    return session.book.list_chapters(session.branch)


def available_branches(book) -> tuple:
    return book.translations


def range_from_indices(chapters, start: int | None, end: int | None):
    if start is not None and not 0 <= start < len(chapters):
        raise ValueError("Неверная начальная глава")
    if end is not None and not 0 <= end < len(chapters):
        raise ValueError("Неверная конечная глава")
    if start is not None and end is not None and start > end:
        raise ValueError("Конечная глава должна идти после начальной")
    return (
        chapters[start]["id"] if start is not None else None,
        chapters[end]["id"] if end is not None else None,
    )


def format_size(size: int) -> str:
    return f"{size / 1024**2:.1f} МиБ"


def create_application(token: str, *, downloader_factory=None, output_dir="output/telegram",
                       allowed_user_ids: set[int] | None = None, max_concurrent=2):
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")
    if max_concurrent < 1:
        raise ValueError("max_concurrent must be positive")
    downloader_factory = downloader_factory or (
        lambda: Downloader(token=os.getenv("RANOBE_TOKEN") or None))
    directory = Path(output_dir)
    sessions: dict[int, Session] = {}
    semaphore = asyncio.Semaphore(max_concurrent)
    app = Application.builder().token(token).build()

    async def allowed(update):
        user = update.effective_user
        if user is None or (allowed_user_ids is not None and user.id not in allowed_user_ids):
            if update.effective_message:
                await update.effective_message.reply_text("Доступ запрещён.")
            return False
        if update.effective_chat is None or update.effective_chat.type != "private":
            if update.effective_message:
                await update.effective_message.reply_text("Используй бота в личном чате.")
            return False
        return True

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await allowed(update):
            await update.message.reply_text(
                "Отправь HTTPS-ссылку на книгу RanobeLib. "
                "Я покажу информацию и помогу выбрать главы и формат."
            )

    def book_text(s):
        b = s.book
        translators = ", ".join(t.name or f"Ветка {t.branch_id}" for t in b.translations)
        return (f"📖 {b.title}\n"
                f"Автор: {', '.join(b.authors) or 'не указан'}\n"
                f"Глав: {b.chapter_count}\n"
                f"Переводы: {translators or 'без отдельных веток'}")

    async def replace(query, s, text, rows):
        await query.edit_message_text(text, reply_markup=kb(rows))

    async def choose_branch(query, s):
        ts = available_branches(s.book)
        if len(ts) <= 1:
            s.branch = ts[0].branch_id if ts else None
            await choose_scope(query, s)
            return
        rows = [[(f"{t.name or 'Перевод'} · {t.chapter_count} глав", f"b:{i}")]
                for i, t in enumerate(ts)]
        rows.append([("Назад", "home")])
        await replace(query, s, "Выбери перевод:", rows)

    async def choose_scope(query, s):
        chapters = chapters_of(s)
        s.start = s.end = s.limit = None
        await replace(query, s, f"Глав в выбранном переводе: {len(chapters)}\nЧто скачать?", [
            [("Всю книгу", "scope:all")],
            [("Первые 10 глав", "scope:first") , ("Последние 10 глав", "scope:last")],
            [("Выбрать диапазон", "page:start:0")],
            [("Назад", "branch")],
        ])

    async def choose_page(query, s, mode, page):
        chapters = chapters_of(s)
        if not chapters:
            await query.answer("Главы не найдены", show_alert=True)
            return
        total_pages = (len(chapters) + PAGE - 1) // PAGE
        page = min(max(page, 0), total_pages - 1)
        rows = []
        for index in range(page * PAGE, min((page + 1) * PAGE, len(chapters))):
            item = chapters[index]
            label = f"{item['volume']}/{item['number']} · {str(item['name'] or '')[:35]}"
            rows.append([(label, f"pick:{mode}:{index}")])
        nav = []
        if page > 0:
            nav.append(("◀️", f"page:{mode}:{page - 1}"))
        nav.append((f"{page + 1}/{total_pages}", "noop"))
        if page + 1 < total_pages:
            nav.append(("▶️", f"page:{mode}:{page + 1}"))
        rows.append(nav)
        rows.append([("Назад", "scope" if mode == "start" else "page:start:0")])
        title = "начальную" if mode == "start" else "конечную"
        await replace(query, s, f"Выбери {title} главу:", rows)

    async def choose_format(query, s):
        chapters = chapters_of(s)
        lower, upper = range_from_indices(chapters, s.start, s.end)
        if s.limit is not None:
            desc = f"Первые {s.limit} глав"
        elif s.start is None and s.end is None:
            desc = "Вся книга"
        else:
            def label(index):
                if index is None:
                    return "начала" if s.start is None and index == s.start else "конца"
                item = chapters[index]
                return f"{item['volume']}/{item['number']}"
            desc = f"С {label(s.start)} по {label(s.end)}"
        await replace(query, s, f"Выбрано: {desc}\nТеперь выбери формат:", [
            [("EPUB", "fmt:epub"), ("TXT", "fmt:txt"), ("HTML", "fmt:html")],
            [("Изменить главы", "scope")],
        ])

    async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await allowed(update):
            return
        raw = (update.message.text or "").strip()
        try:
            parsed = urlparse(raw)
            if parsed.scheme != "https":
                raise ValueError("Нужна HTTPS-ссылка на книгу RanobeLib")
            parse_title_reference(raw)
        except ValueError:
            await update.message.reply_text("Пришли HTTPS-ссылку на книгу RanobeLib.")
            return
        uid = update.effective_user.id
        if uid in sessions and sessions[uid].busy:
            await update.message.reply_text("Дождись завершения текущей загрузки.")
            return
        notice = await update.message.reply_text("Получаю информацию о книге...")
        try:
            def load():
                with downloader_factory() as client:
                    return client.get_book(raw)
            book = await asyncio.to_thread(load)
            s = Session(book, notice.message_id)
            sessions[uid] = s
            # Cover URL comes from the validated title provider; photo is optional.
            cover = getattr(book._plan.title, "cover_url", None)
            if cover and urlparse(cover).scheme == "https":
                try:
                    await update.message.reply_photo(cover)
                except Exception:
                    logger.debug("Cover could not be sent", exc_info=True)
            await notice.edit_text(book_text(s), reply_markup=kb([
                [("📥 Скачать", "branch")], [("Отмена", "cancel")],
            ]))
        except Exception:
            logger.exception("Book metadata lookup failed")
            await notice.edit_text("Не удалось получить книгу. Проверь ссылку и доступ.")

    async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await allowed(update):
            return
        query = update.callback_query
        await query.answer()
        s = sessions.get(update.effective_user.id)
        if s is None or query.message.message_id != s.message_id:
            await query.answer("Сессия устарела, отправь ссылку снова.", show_alert=True)
            return
        action = query.data or ""
        if s.busy:
            await query.answer("Загрузка уже выполняется", show_alert=True)
            return
        try:
            if action == "noop":
                return
            if action == "cancel":
                sessions.pop(update.effective_user.id, None)
                await query.edit_message_text("Отменено. Можешь прислать новую ссылку.")
            elif action == "home":
                await replace(query, s, book_text(s), [[("📥 Скачать", "branch")], [("Отмена", "cancel")]])
            elif action == "branch":
                await choose_branch(query, s)
            elif action.startswith("b:"):
                index = int(action.split(":")[1])
                s.branch = available_branches(s.book)[index].branch_id
                await choose_scope(query, s)
            elif action == "scope":
                await choose_scope(query, s)
            elif action.startswith("scope:"):
                mode = action.split(":")[1]
                chapters = chapters_of(s)
                s.start = s.end = s.limit = None
                if mode == "first":
                    s.limit = min(10, len(chapters))
                elif mode == "last":
                    s.start = max(0, len(chapters) - 10)
                elif mode != "all":
                    raise ValueError("Неизвестный выбор глав")
                await choose_format(query, s)
            elif action.startswith("page:"):
                _, mode, page = action.split(":")
                await choose_page(query, s, mode, int(page))
            elif action.startswith("pick:"):
                _, mode, index = action.split(":")
                index = int(index)
                if mode == "start":
                    s.start = index
                    await choose_page(query, s, "end", index // PAGE)
                elif mode == "end":
                    s.end = index
                    await choose_format(query, s)
            elif action.startswith("fmt:"):
                s.format = action.split(":")[1]
                await run_download(query, s)
        except (ValueError, IndexError) as exc:
            await query.answer(str(exc)[:180], show_alert=True)
        except Exception:
            logger.exception("Telegram button action failed")
            await query.edit_message_text("Произошла ошибка. Пришли ссылку заново.")
            sessions.pop(update.effective_user.id, None)

    async def run_download(query, s):
        if semaphore.locked():
            await query.answer("Все загрузчики заняты. Повтори позже.", show_alert=True)
            return
        s.busy = True
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{uuid4().hex}.{s.format}"
        try:
            await query.edit_message_text("⏳ Скачиваю и собираю книгу...")
            chapters = chapters_of(s)
            lower, upper = range_from_indices(chapters, s.start, s.end)
            def work():
                with downloader_factory() as client:
                    return client.download(
                        s.book, format=s.format, output=target, branch_id=s.branch,
                        limit=s.limit, chapter_start_id=lower, chapter_end_id=upper,
                        cache_dir=directory / "cache", resume=True,
                    )
            async with semaphore:
                path = Path(await asyncio.to_thread(work))
                if not path.is_file():
                    raise ValueError("Файл не создан")
                if path.stat().st_size > MAX_FILE:
                    await query.edit_message_text(
                        f"Файл получился слишком большим ({format_size(path.stat().st_size)}). "
                        f"Лимит отправки ботом — 45 МиБ.\n\n"
                        "Выбери меньший диапазон глав или скачай всю книгу через CLI: "
                        "ranobe download <ссылка>.\n"
                        "Временный файл удаляется после обработки.",
                        reply_markup=kb([[("Изменить главы", "scope")]]),
                    )
                    return
                with path.open("rb") as document:
                    await query.message.reply_document(document, filename=f"ranobe.{s.format}",
                                                       read_timeout=120, write_timeout=120)
                await query.edit_message_text("✅ Файл отправлен.", reply_markup=kb([
                    [("Другой диапазон", "scope")],
                ]))
        except Exception:
            logger.exception("Telegram download failed")
            await query.edit_message_text("Не удалось скачать книгу. Попробуй другой диапазон или перевод.",
                                          reply_markup=kb([[("Изменить выбор", "scope")]]))
        finally:
            s.busy = False
            target.unlink(missing_ok=True)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(callbacks))
    return app


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN")
    ids = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()
    allowed = {int(item.strip()) for item in ids.split(",") if item.strip()} if ids else None
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    create_application(token, allowed_user_ids=allowed).run_polling()


if __name__ == "__main__":
    main()
