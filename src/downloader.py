import os
import json
import time
import shutil
import threading
from urllib.parse import urlsplit
import requests
from bs4 import BeautifulSoup
from ebooklib import epub
from concurrent.futures import ThreadPoolExecutor, as_completed
from . import config
from .utils import sanitize_filename, get_slug, convert_to_webp

session = requests.Session()
session.headers.update(config.HEADERS)

def extract_text_with_images(content, book, image_map, manga_id, chapter_id, save_images, log_queue):
    if isinstance(content, dict) and content.get("type") == "doc":
        paragraphs = []
        for block in content.get("content", []):
            if block.get("type") == "paragraph":
                paragraph_text = ''
                for item in block.get("content", []):
                    if item.get("type") == "text":
                        paragraph_text += item.get("text", '')
                paragraphs.append(f"<p>{paragraph_text.strip()}</p>")
            elif block.get("type") == "image" and save_images:
                images = block.get("attrs", {}).get("images", [])
                for img_obj in images:
                    image_id = img_obj.get("image")
                    if image_id:
                        url_base = f"https://ranobelib.me/uploads/ranobe/{manga_id}/chapters/{chapter_id}/{image_id}"
                        local_img = download_image(url_base, book, image_map, log_queue)
                        if local_img:
                            paragraphs.append(f'<img src="{local_img}" alt="image"/>')
        return "\n".join(paragraphs)

    elif isinstance(content, str) and '<' in content:
        soup = BeautifulSoup(content, 'html.parser')
        html_parts = []
        for tag in soup.find_all(['p', 'img']):
            if tag.name == 'img':
                img_url = tag.get('src')
                if img_url and save_images:
                    local_img = download_image(img_url, book, image_map, log_queue)
                    if local_img:
                        html_parts.append(f'<img src="{local_img}" alt="image"/>')
            elif tag.name == 'p':
                html_parts.append(f"<p>{tag.get_text(strip=True)}</p>")
        return "\n".join(html_parts)

    return "<p>[Неподдерживаемый формат контента]</p>"

def get_volume_number_list(manga_id: int, log_queue):
    url = f'https://api.lib.social/api/manga/{manga_id}/chapters'

    try:
        response = session.get(url, headers=config.HEADERS)
        response.raise_for_status()
        parsed = response.json()
        chapters = parsed.get("data", [])

        volume_number_list = []

        for chapter in chapters:
            volume = chapter.get("volume", "0")
            number = chapter.get("number", "0")
            volume_number_list.append((volume, number))

        return volume_number_list

    except requests.RequestException as e:
        log_queue.put(f"Ошибка при запросе списка глав: {e}")
        return []
    except json.JSONDecodeError:
        log_queue.put("Ошибка декодирования JSON при получении списка глав")
        return []

def get_novel_info(slug_id: str, log_queue):
    headers = {
        'Referer': 'https://ranobelib.me/',
        'User-Agent': 'Mozilla/5.0',
        'Content-Type': 'application/json',
    }

    url = f'https://api.cdnlibs.org/api/manga/{slug_id}?fields[]=eng_name&fields[]=authors'

    try:
        response = session.get(url, headers=headers)
        if response.status_code != 200:
            log_queue.put(f"Ошибка запроса информации о новелле: {response.status_code}")
            return None
            
        data = response.json()
        
        if not data.get('data'):
            log_queue.put("Не найдена информация о новелле в ответе API")
            return None

        manga_id = data['data'].get('id')
        name = data['data'].get('rus_name', 'Без названия')
        authors = ', '.join(a.get('name') for a in data['data'].get('authors', [])) or 'Неизвестный автор'

        return {'manga_id': manga_id, 'name': name, 'authors': authors}
    except Exception as e:
        log_queue.put(f"Ошибка при получении информации о новелле: {e}")
        return None

def download_image(url_or_base, book, image_map, log_queue, retries=5, delay=30):
    if url_or_base in image_map:
        return image_map[url_or_base]

    def try_download(url):
        for attempt in range(retries):
            try:
                response = session.get(url, headers=config.HEADERS, timeout=30)
                if response.status_code == 200:
                    webp_content = convert_to_webp(response.content)
                    if webp_content is None:
                        return None

                    # Сохраняем как .webp
                    base_name = os.path.splitext(os.path.basename(urlsplit(url).path))[0]
                    image_name = sanitize_filename(base_name) + ".webp"

                    epub_image = epub.EpubImage()
                    epub_image.file_name = f"images/{image_name}"
                    epub_image.media_type = "image/webp"
                    epub_image.content = webp_content

                    book.add_item(epub_image)
                    image_map[url_or_base] = epub_image.file_name
                    return epub_image.file_name

                elif response.status_code == 429:
                    log_queue.put(f"[429] Слишком много запросов при загрузке изображения. Попытка {attempt+1}/{retries}...")
                    time.sleep(delay)
                else:
                    log_queue.put(f"Ошибка загрузки изображения: HTTP {response.status_code} для {url}")
                    break
            except Exception as e:
                log_queue.put(f"Ошибка загрузки изображения: {e}")
                time.sleep(delay)
        return None

    # Если URL уже содержит расширение
    if '.' in os.path.basename(urlsplit(url_or_base).path):
        return try_download(url_or_base)

    # Попробуем найти изображение с разными расширениями
    for ext in ["jpg", "png", "jpeg", "webp"]:
        url = f"{url_or_base}.{ext}"
        result = try_download(url)
        if result:
            return result

    log_queue.put(f"Не удалось загрузить изображение: {url_or_base}")
    return None


def download_chapters_to_epub(manga_id: int, chapters: list, title: str, author: str, save_images: bool, log_queue, output_dir, slug_url: str):
    # Создаем безопасное имя файла
    safe_title = sanitize_filename(title)
    epub_path = os.path.join(output_dir, f"{safe_title}.epub")
    
    # Проверяем, существует ли файл
    if os.path.exists(epub_path):
        log_queue.put(f"Файл {safe_title}.epub уже существует. Создаем резервную копию.")
        backup_path = os.path.join(output_dir, f"{safe_title}_backup_{int(time.time())}.epub")
        shutil.copy(epub_path, backup_path)
    
    book = epub.EpubBook()
    book.set_identifier(f"ranobe-{manga_id}-{int(time.time())}")
    book.set_title(title)
    book.set_language("ru")
    book.add_author(author)
    
    # Создаем папку для изображений
    book.add_item(epub.EpubNcx())

    chapter_items = [None] * len(chapters)
    image_map = {}
    success_count = 0
    lock = threading.Lock()

    def download_chapter_task(idx, volume, number, manga_id, slug_url, save_images, book, image_map, log_queue, chapter_items, lock):
        log_queue.put(f"Загрузка главы {idx}: Том {volume}, Глава {number}")
        params = {'volume': volume, 'number': number}
        url = f'https://api.lib.social/api/manga/{slug_url}/chapter'

        chapter_data = None
        for attempt in range(5):
            try:
                response = session.get(url, params=params, headers=config.HEADERS, timeout=30)
                if response.status_code == 200:
                    chapter_data = response.json().get("data")
                    break
                elif response.status_code == 429:
                    log_queue.put(f"[429] Слишком много запросов (глава {volume}-{number}). Повтор через 30 сек (попытка {attempt+1}/5)...")
                    time.sleep(30)
                else:
                    log_queue.put(f"Ошибка {response.status_code} при загрузке главы {volume}-{number}")
                    return False
            except Exception as e:
                log_queue.put(f"Ошибка при загрузке главы {volume}-{number}: {e}")
                time.sleep(5)

        if not chapter_data or not chapter_data.get("content"):
            log_queue.put(f"Глава {volume}-{number} пуста или не загружена.")
            return False

        chapter_id = chapter_data.get("id")
        html_content = extract_text_with_images(
            chapter_data["content"], book, image_map, manga_id, chapter_id, save_images, log_queue
        )

        chapter_title = f"Том {volume}, Глава {number}"
        c = epub.EpubHtml(title=chapter_title, file_name=f'chap_{idx}.xhtml', lang='ru')
        c.add_item(epub.EpubItem(uid=f"style_{idx}", file_name="styles/main.css", media_type="text/css"))
        c.content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{chapter_title}</title>
            <link rel="stylesheet" type="text/css" href="../styles/main.css"/>
        </head>
        <body>
            <h1>{chapter_title}</h1>
            {html_content}
        </body>
        </html>
        """

        with lock:
            book.add_item(c)
            chapter_items[idx - 1] = c  # сохраняем на правильное место

        return True

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for idx, (volume, number) in enumerate(chapters, 1):
            futures.append(
                executor.submit(
                    download_chapter_task,
                    idx, volume, number, manga_id, slug_url,
                    save_images, book, image_map,
                    log_queue, chapter_items, lock
                )
            )

        for f in as_completed(futures):
            if f.result():
                success_count += 1



    if success_count == 0:
        log_queue.put("Не удалось загрузить ни одной главы. Создание EPUB отменено.")
        return

    book.toc = tuple(filter(None, chapter_items))
    book.spine = ['nav'] + list(filter(None, chapter_items))
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    try:
        os.makedirs(output_dir, exist_ok=True)
        epub.write_epub(epub_path, book, {})
        log_queue.put(f"\nКнига успешно сохранена: {epub_path}")
        log_queue.put(f"Загружено глав: {success_count}/{len(chapters)}")
        return True
    except Exception as e:
        log_queue.put(f"Ошибка при сохранении EPUB: {e}")
        return False

def run_download(novel_url, save_images, output_dir, log_queue):
    try:
        slug_url = get_slug(novel_url)
    except ValueError as e:
        log_queue.put(f"Ошибка: {e}")
        return
    novel_info = get_novel_info(slug_url, log_queue)
    if not novel_info:
        log_queue.put("Не удалось получить информацию о новелле")
        return
    
    manga_id = novel_info['manga_id']
    title = novel_info['name']
    author = novel_info['authors']
    
    log_queue.put(f"ID новеллы: {novel_info['manga_id']}")
    log_queue.put(f"Slug: {slug_url}") 
    log_queue.put(f"\nНазвание: {title}")
    log_queue.put(f"Автор(ы): {author}")
    log_queue.put(f"Сохранение изображений: {'Да' if save_images else 'Нет'}")
    log_queue.put(f"Папка сохранения: {output_dir}")
    log_queue.put("\nПолучение списка глав...")

    chapters = get_volume_number_list(slug_url, log_queue)
    if not chapters:
        log_queue.put("Главы не найдены или произошла ошибка.")
        return

    log_queue.put(f"Найдено глав: {len(chapters)}")
    log_queue.put("Начало загрузки...\n")

    start_time = time.time()
    success = download_chapters_to_epub(
        manga_id, 
        chapters, 
        title, 
        author, 
        save_images,
        log_queue,
        output_dir,
        slug_url
    )
    
    elapsed = time.time() - start_time
    if success:
        log_queue.put(f"\nУспешно! Время: {int(elapsed // 60)} мин {elapsed % 60:.1f} сек.")
    else:
        log_queue.put("\nПроцесс завершен с ошибками")

