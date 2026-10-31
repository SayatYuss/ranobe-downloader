import getpass

import httpx

from core.auth.storage import KeyringTokenStorage
from providers.libsocial.client import LibSocialClient


storage = KeyringTokenStorage()


def _auth_error(exc: httpx.HTTPStatusError) -> str:
    status = exc.response.status_code
    if status == 401:
        return "Токен недействителен или истёк (401)"
    if status == 403:
        return ("API отказал в доступе (403). Проверьте авторизацию в браузере "
                "и доступность API; токен не был изменён.")
    return f"Ошибка API при проверке авторизации: HTTP {status}"


def login() -> None:
    token = getpass.getpass("Bearer token: ").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        print("Токен не указан")
        return

    try:
        with LibSocialClient(token) as client:
            user = client.get_current_user()
    except httpx.HTTPStatusError as exc:
        print(_auth_error(exc))
        return
    except httpx.RequestError as exc:
        print(f"Ошибка соединения с API: {type(exc).__name__}")
        return

    storage.save(token)
    print(f"Авторизован: {user['username']}")


def status() -> None:
    token = storage.load()
    if not token:
        print("Не авторизован")
        return
    try:
        with LibSocialClient(token) as client:
            user = client.get_current_user()
    except httpx.HTTPStatusError as exc:
        print(_auth_error(exc))
        return
    except httpx.RequestError as exc:
        print(f"Ошибка соединения с API: {type(exc).__name__}")
        return
    print(f"Авторизован: {user['username']} (ID: {user['id']})")


def logout() -> None:
    storage.delete()
    print("Локальный токен удалён")
