
import unittest
import tempfile
from pathlib import Path

from src.bplus_tree import BPlusTree
from src.index_persistence import (
    save_bplus_tree,
    load_bplus_tree
)


class TestIndexPersistence(unittest.TestCase):

    def test_save_and_load(self):
        tree = BPlusTree(max_keys=3)

        products = [
            (100, "A"),
            (200, "B"),
            (100, "C"),
            (300, "D"),
            (400, "E"),
            (150, "F")
        ]

        for price, product in products:
            tree.insert(price, product)

        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "index.pkl"

            save_bplus_tree(tree, filepath)

            self.assertTrue(filepath.exists())

            recovered = load_bplus_tree(filepath)

            self.assertEqual(len(tree), len(recovered))
            self.assertEqual(
                tree.search(100),
                recovered.search(100)
            )
            self.assertEqual(
                tree.range_search(100, 300),
                recovered.range_search(100, 300)
            )

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "missing.pkl"

            with self.assertRaises(FileNotFoundError):
                load_bplus_tree(filepath)


if __name__ == "__main__":
    unittest.main()
