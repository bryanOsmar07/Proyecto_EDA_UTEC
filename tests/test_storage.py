
import unittest
import pandas as pd

from src.storage import ProductStore, LRUCache
from src.sparse_matrix import UserProductMatrix
from src.pipeline import run_storage_pipeline


class TestProductStore(unittest.TestCase):

    def test_latest_product_wins(self):
        catalog = ProductStore()

        recent = pd.Timestamp("2026-10-30 10:00:00", tz="UTC")
        old = pd.Timestamp("2026-10-30 09:00:00", tz="UTC")

        catalog.add_product(
            {"product_id": 1, "price": 500.0},
            recent,
            event_id=2
        )

        updated = catalog.add_product(
            {"product_id": 1, "price": 400.0},
            old,
            event_id=1
        )

        self.assertFalse(updated)
        self.assertEqual(catalog.get_product(1)["price"], 500.0)
        self.assertEqual(len(catalog), 1)


class TestLRUCache(unittest.TestCase):

    def test_eviction(self):
        cache = LRUCache(capacity=2)

        cache.put(1, "A")
        cache.put(2, "B")

        # El producto 1 pasa a ser el más reciente
        self.assertEqual(cache.get(1), "A")

        # Debe expulsarse el producto 2
        cache.put(3, "C")

        self.assertEqual(list(cache.cache.keys()), [1, 3])
        self.assertIsNone(cache.get(2))

        self.assertEqual(cache.hits, 1)
        self.assertEqual(cache.misses, 1)
        self.assertAlmostEqual(cache.hit_rate(), 0.5)


class TestUserProductMatrix(unittest.TestCase):

    def test_interaction_weights(self):
        interactions = UserProductMatrix()

        for event_type in ["view", "view", "cart", "purchase"]:
            interactions.add_event({
                "user_id": 10,
                "product_id": 20,
                "event_type": event_type
            })

        result = interactions.to_csr()
        matrix = result["matrix"]

        self.assertEqual(matrix.shape, (1, 1))
        self.assertEqual(matrix.nnz, 1)
        self.assertAlmostEqual(float(matrix[0, 0]), 10.0)
        self.assertEqual(interactions.total_events, 4)


class TestStorageIntegration(unittest.TestCase):

    def test_cache_uses_latest_product(self):
        # La compra es posterior a la vista, pero el Heap
        # procesa la compra primero por tener mayor prioridad.
        base = {
            "product_id": 123,
            "category_id": 456,
            "category_code": "electronics.smartphone",
            "brand": "test",
            "user_id": 789,
            "user_session": "session-test"
        }

        events = [
            {
                **base,
                "event_id": 1,
                "event_type": "view",
                "price": 400.0,
                "event_timestamp": pd.Timestamp(
                    "2026-10-30 09:00:00", tz="UTC"
                )
            },
            {
                **base,
                "event_id": 2,
                "event_type": "purchase",
                "price": 500.0,
                "event_timestamp": pd.Timestamp(
                    "2026-10-30 10:00:00", tz="UTC"
                )
            }
        ]

        result = run_storage_pipeline(
            events,
            batch_size=2,
            cache_capacity=2
        )

        self.assertEqual(result["metrics"]["output"], 2)
        self.assertEqual(
            result["catalog"].get_product(123)["price"],
            500.0
        )
        self.assertEqual(
            result["cache"].get(123)["price"],
            500.0
        )
        self.assertAlmostEqual(
            float(result["csr"]["matrix"].sum()),
            6.0
        )


if __name__ == "__main__":
    unittest.main()
