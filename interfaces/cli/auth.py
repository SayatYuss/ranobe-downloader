import getpass

import httpx

from core.auth.storage import KeyringTokenStorage
from providers.libsocial.client import LibSocialClient


storage = KeyringTokenStorage()


def login() -> None:
    token = getpass.getpass("Bearer token: ").strip()

    if not token:
        print("Токен не указан")
        return

    with LibSocialClient(token) as client:
        user = client.get_current_user()

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

        print(f"Авторизован: {user['username']} (ID: {user['id']})")

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            print("Токен недействителен или истёк")
        else:
            raise


def logout() -> None:
    storage.delete()
    print("Локальный токен удалён")