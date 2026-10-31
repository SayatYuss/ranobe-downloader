# CLI: chapter index and ranges

List chapter numbers for one translation without downloading chapter contents:

```bash
ranobe download '271947--example' --branch 123 --list-chapters
```

Download an inclusive range of chapter **numbers** (not positions):

```bash
ranobe download '271947--example' --branch 123 --from 13.4 --to 45 --format epub
```

`--chapter-from` and `--chapter-to` are aliases of `--from` and `--to`. Both bounds are optional. `--limit N` limits the number of chapters **after** the range is applied. Chapter numbers are handled as exact decimal strings. Boundaries must exist in the selected translation branch.

Use `--list-chapters` first to inspect valid numbers. For books with multiple translation branches, use `--branch ID` (or choose interactively if a terminal is attached). Chapter listings contain metadata only; chapter content is not downloaded.
