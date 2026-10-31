"""TTY-only presentation of translation choices; never imported by core."""
from __future__ import annotations

import sys
from core.download.plan import Translation


def select_translation(translations: tuple[Translation, ...], *, interactive: bool = True) -> int | None:
    """Return a branch ID (or None for an unbranched title)."""
    if not translations:
        return None
    if len(translations) == 1:
        return translations[0].branch_id
    if not interactive or not sys.stdin.isatty():
        ids = ', '.join(str(t.branch_id) for t in translations)
        raise ValueError(f'Multiple translations available. Specify --branch ID: {ids}')

    print('\nAvailable translations:')
    for index, translation in enumerate(translations, 1):
        name = translation.name or f'Branch {translation.branch_id}'
        print(f'  {index}. {name} ({translation.chapter_count} chapters; ID {translation.branch_id})')
    while True:
        try:
            response = input('Select translation number (q to cancel): ').strip()
        except EOFError as exc:
            raise ValueError('Translation selection cancelled') from exc
        if response.lower() in ('q', 'quit'):
            raise ValueError('Translation selection cancelled')
        if response.isdecimal() and 1 <= int(response) <= len(translations):
            return translations[int(response) - 1].branch_id
        print(f'Enter a number from 1 to {len(translations)}, or q.')
