
import unittest
import random

from src.bplus_tree import BPlusTree


class TestBPlusTree(unittest.TestCase):

    def test_point_search(self):
        tree = BPlusTree(max_keys=3)

        for key in [30, 10, 50, 20, 40]:
            tree.insert(key, f"Producto {key}")

        self.assertEqual(
            tree.search(30),
            ["Producto 30"]
        )
        self.assertEqual(tree.search(99), [])

    def test_duplicate_keys(self):
        tree = BPlusTree(max_keys=3)

        tree.insert(100, "A")
        tree.insert(100, "B")
        tree.insert(100, "C")

        self.assertEqual(tree.search(100), ["A", "B", "C"])
        self.assertEqual(len(tree), 3)

    def test_range_search(self):
        tree = BPlusTree(max_keys=3)

        for key in [80, 150, 300, 120, 500, 200, 450]:
            tree.insert(key, key)

        self.assertEqual(
            tree.range_search(100, 300),
            [120, 150, 200, 300]
        )

    def test_multiple_splits(self):
        tree = BPlusTree(max_keys=3)

        keys = list(range(1000))
        random.Random(42).shuffle(keys)

        for key in keys:
            tree.insert(key, key)

        self.assertEqual(len(tree), 1000)

        for key in range(1000):
            self.assertEqual(tree.search(key), [key])

        self.assertEqual(
            tree.range_search(250, 260),
            list(range(250, 261))
        )

    def test_empty_and_invalid_range(self):
        tree = BPlusTree(max_keys=3)

        self.assertEqual(tree.search(10), [])
        self.assertEqual(tree.range_search(10, 20), [])
        self.assertEqual(tree.range_search(20, 10), [])

    def test_range_matches_linear_search(self):
        tree = BPlusTree(max_keys=4)

        rng = random.Random(42)
        records = []

        for i in range(500):
            price = rng.randint(1, 100)
            tree.insert(price, i)
            records.append((price, i))

        expected = [
            record_id
            for price, record_id in sorted(records)
            if 25 <= price <= 75
        ]

        actual = tree.range_search(25, 75)

        self.assertCountEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
