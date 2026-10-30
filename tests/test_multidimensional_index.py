
import unittest
import numpy as np

from src.multidimensional_index import ProductKDTree


class TestProductKDTree(unittest.TestCase):

    def setUp(self):
        # Dataset sintético pequeño para pruebas
        self.ids = np.array([101, 102, 103, 104, 105, 106])

        self.features = np.array([
            [10.0, 1.0],
            [20.0, 2.0],
            [30.0, 3.0],
            [40.0, 4.0],
            [50.0, 5.0],
            [60.0, 6.0]
        ])

        self.index = ProductKDTree(leaf_size=2)
        self.index.fit(self.ids, self.features)

    def test_dimensions(self):
        """Verifica los productos y dimensiones."""

        self.assertEqual(
            self.index.X_scaled.shape, (6, 2)
        )

        self.assertEqual(len(self.index.product_ids), 6)

    def test_original_product_excluded(self):
        """El producto consultado no aparece."""

        neighbors = self.index.query(
            product_id=101,
            k=3
        )

        result_ids = [n["product_id"] for n in neighbors]

        self.assertEqual(len(neighbors), 3)
        self.assertNotIn(101, result_ids)
        self.assertEqual(len(set(result_ids)), 3)

    def test_kdtree_matches_brute(self):
        """Compara las distancias de ambos métodos."""

        for product_id in self.ids:
            kd = self.index.query(
                int(product_id), k=3, method="kd_tree"
            )

            brute = self.index.query(
                int(product_id), k=3, method="brute"
            )

            kd_dist = sorted(n["distance"] for n in kd)
            brute_dist = sorted(n["distance"] for n in brute)

            np.testing.assert_allclose(
                kd_dist,
                brute_dist,
                atol=1e-7,
                rtol=0
            )

    def test_invalid_k(self):
        """Rechaza valores de k fuera de rango."""

        with self.assertRaises(ValueError):
            self.index.query(101, k=0)

        with self.assertRaises(ValueError):
            self.index.query(101, k=6)

    def test_duplicate_product_ids(self):
        """Rechaza identificadores repetidos."""

        index = ProductKDTree()

        with self.assertRaises(ValueError):
            index.fit(
                product_ids=[1, 1],
                features=[[10, 2], [20, 3]]
            )


if __name__ == "__main__":
    unittest.main()
