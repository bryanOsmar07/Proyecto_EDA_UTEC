
import unittest
from datetime import datetime, timezone, timedelta

from src.pipeline import run_multidimensional_pipeline


def make_event(event_id, product_id, event_type, price):
    return {
        "event_id": event_id,
        "event_time": "2026-10-30 10:00:00 UTC",
        "event_timestamp": (
            datetime(2026, 10, 30, tzinfo=timezone.utc)
            + timedelta(seconds=event_id)
        ),
        "event_type": event_type,
        "product_id": product_id,
        "category_id": 100,
        "category_code": "electronics.smartphone",
        "brand": "test",
        "price": price,
        "user_id": 200 + event_id % 3,
        "user_session": "session-test"
    }


class TestPipelineIntegration(unittest.TestCase):

    def setUp(self):
        self.events = [
            make_event(i, 1000 + i % 6,
                       ["view", "cart", "purchase"][i % 3],
                       100.0 + i)
            for i in range(12)
        ]

    def test_full_pipeline(self):
        result = run_multidimensional_pipeline(
            self.events,
            batch_size=4,
            cache_capacity=3
        )

        metrics = result["metrics"]

        self.assertEqual(metrics["received"], 12)
        self.assertEqual(metrics["output"], 12)
        self.assertEqual(metrics["catalog_products"], 6)
        self.assertEqual(metrics["bptree_indexed_products"], 6)
        self.assertEqual(metrics["kdtree_products"], 6)
        self.assertEqual(metrics["kdtree_dimensions"], 4)

        self.assertEqual(
            result["csr"]["matrix"].sum(),
            36
        )

        query_id = 1000
        neighbors = result["product_kdtree"].query(
            query_id, k=3
        )

        self.assertEqual(len(neighbors), 3)
        self.assertNotIn(
            query_id,
            [n["product_id"] for n in neighbors]
        )

    def test_retransmission_not_double_counted(self):
        # Repetir un evento en un lote posterior
        events = self.events + [self.events[0].copy()]

        result = run_multidimensional_pipeline(
            events,
            batch_size=4
        )

        metrics = result["metrics"]

        self.assertEqual(metrics["received"], 13)
        self.assertEqual(metrics["duplicates"], 1)
        self.assertEqual(metrics["output"], 12)
        self.assertEqual(
            result["csr"]["matrix"].sum(),
            36
        )


if __name__ == "__main__":
    unittest.main()
