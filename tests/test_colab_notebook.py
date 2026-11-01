"""Offline checks for the Colab notebook and chapter selection."""
import ast
import json
from pathlib import Path
import unittest

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "ranobe_downloader_colab.ipynb"


class ColabNotebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        cls.sources = ["".join(cell["source"]) for cell in cls.notebook["cells"] if cell["cell_type"] == "code"]
        tree = ast.parse(next(s for s in cls.sources if "def select_chapter_bounds" in s))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "select_chapter_bounds")
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "<notebook-selection>", "exec"), namespace)
        cls.select = staticmethod(namespace["select_chapter_bounds"])

    def test_notebook_is_clean_and_code_compiles(self):
        self.assertEqual(self.notebook["nbformat"], 4)
        self.assertEqual(len(self.sources), 5)
        for i, cell in enumerate(self.notebook["cells"]):
            if cell["cell_type"] == "code":
                self.assertEqual(cell["outputs"], [])
                self.assertIsNone(cell["execution_count"])
                compile("".join(cell["source"]), f"<cell-{i}>", "exec")

    def test_selection_uses_reading_order_not_numeric_ids(self):
        chapters = [{"id": 90}, {"id": 4}, {"id": 60}]
        self.assertEqual(self.select(chapters, "Все главы"), (90, 60, 3))
        self.assertEqual(self.select(chapters, "Диапазон", 2, 3), (4, 60, 2))
        self.assertEqual(self.select(chapters, "Диапазон", 2, 0), (4, 60, 2))
        self.assertEqual(self.select(chapters, "Диапазон", 2, 2), (4, 4, 1))

    def test_first_and_last_ten(self):
        chapters = [{"id": i} for i in range(15)]
        self.assertEqual(self.select(chapters, "Первые 10"), (0, 9, 10))
        self.assertEqual(self.select(chapters, "Последние 10"), (5, 14, 10))
        self.assertEqual(self.select(chapters[:3], "Последние 10"), (0, 2, 3))

    def test_invalid_selection(self):
        for start, end in [(0, 2), (3, 2), (1, 4), (-1, 0), (1.5, 2), (True, 2)]:
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    self.select([{"id": 1}, {"id": 2}, {"id": 3}], "Диапазон", start, end)
        with self.assertRaises(ValueError):
            self.select([], "Все главы")
        with self.assertRaises(ValueError):
            self.select([{"id": 1}], "unknown")


if __name__ == "__main__":
    unittest.main()
