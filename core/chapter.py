from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TranslationTeam:
    id: int
    name: str


@dataclass(frozen=True)
class ChapterBranch:
    id: int
    branch_id: int | None
    teams: tuple[TranslationTeam, ...]
    username: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ChapterBranch:
        user = data.get("user") or {}
        teams = data.get("teams") or []
        return cls(
            id=int(data["id"]),
            branch_id=data.get("branch_id"),
            teams=tuple(
                TranslationTeam(id=int(team["id"]), name=team.get("name") or "")
                for team in teams
                if isinstance(team, dict) and team.get("id") is not None
            ),
            username=user.get("username") if isinstance(user, dict) else None,
        )


@dataclass(frozen=True)
class Chapter:
    id: int
    index: int | None
    volume: str
    number: str
    name: str | None
    branches: tuple[ChapterBranch, ...]
    branches_count: int
    number_secondary: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Chapter:
        branches = tuple(ChapterBranch.from_api(b) for b in (data.get("branches") or []))
        return cls(
            id=int(data["id"]),
            index=data.get("index"),
            volume=str(data.get("volume") or "0"),
            number=str(data.get("number") or "0"),
            name=data.get("name"),
            branches=branches,
            branches_count=int(data.get("branches_count") or len(branches)),
            number_secondary=(
                str(data["number_secondary"]) if data.get("number_secondary") is not None else None
            ),
        )
