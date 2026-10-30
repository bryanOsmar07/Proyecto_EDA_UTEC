
import unittest
from datetime import datetime, timezone

from src.streaming_pipeline import run_streaming_pipeline


class TestStreamingPipeline(unittest.TestCase):

    def test_integrated_pipeline_with_duplicates(self):
        timestamp = datetime(
            2026, 10, 30, tzinfo=timezone.utc
        )

        events = []

        for i in range(12):
            events.append({
                "event_id": i,
                "event_timestamp": timestamp,
                "event_type": (
                    "purchase" if i % 3 == 0
                    else "cart" if i % 3 == 1
                    else "view"
                ),
                "product_id": 100 + i % 4,
                "user_id": 200 + i % 3,
                "price": 50.0 + i
            })

        events.extend([
            events[0].copy(),
            events[4].copy(),
            events[8].copy()
        ])

        result = run_streaming_pipeline(
            iter(events),
            batch_size=4
        )

        metrics = result["metrics"]

        self.assertEqual(metrics["received"], 15)
        self.assertEqual(metrics["duplicates"], 3)
        self.assertEqual(metrics["output"], 12)

        self.assertEqual(metrics["catalog_products"], 4)
        self.assertEqual(metrics["bptree_products"], 4)
        self.assertEqual(metrics["kdtree_products"], 4)

        # Cada uno de los 12 pares usuario-producto
        # es único en este conjunto de prueba.
        self.assertEqual(metrics["csr_nnz"], 12)

        # 4 vistas, 4 carritos y 4 compras:
        # 4*1 + 4*3 + 4*5 = 36
        self.assertEqual(metrics["csr_weight_sum"], 36)


if __name__ == "__main__":
    unittest.main()
