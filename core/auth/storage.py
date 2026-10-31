from typing import Protocol

import keyring


class TokenStorage(Protocol):
    def save(self, token: str) -> None: ...
    def load(self) -> str | None: ...
    def delete(self) -> None: ...


class KeyringTokenStorage:
    SERVICE = "ranobe-downloader"
    ACCOUNT = "libsocial"

    def save(self, token: str) -> None:
        keyring.set_password(self.SERVICE, self.ACCOUNT, token)

    def load(self) -> str | None:
        return keyring.get_password(self.SERVICE, self.ACCOUNT)

    def delete(self) -> None:
        try:
            keyring.delete_password(self.SERVICE, self.ACCOUNT)
        except keyring.errors.PasswordDeleteError:
            pass