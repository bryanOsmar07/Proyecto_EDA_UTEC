
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

    
    def test_full_pipeline_hybrid_dedup(self):
        """Compara el pipeline completo con ambos métodos."""

        # 12 eventos originales + 3 retransmisiones
        events = self.events + [
            self.events[0].copy(),
            self.events[3].copy(),
            self.events[7].copy()
        ]

        result_set = run_multidimensional_pipeline(
            events,
            batch_size=4,
            dedup_method="set"
        )

        result_hybrid = run_multidimensional_pipeline(
            events,
            batch_size=4,
            dedup_method="hybrid",
            expected_items=100,
            false_positive_rate=0.01
        )

        metrics_set = result_set["metrics"]
        metrics_hybrid = result_hybrid["metrics"]

        # Verificar que las retransmisiones se eliminan
        self.assertEqual(metrics_set["received"], 15)
        self.assertEqual(metrics_hybrid["received"], 15)

        self.assertEqual(metrics_set["duplicates"], 3)
        self.assertEqual(metrics_hybrid["duplicates"], 3)

        self.assertEqual(metrics_set["output"], 12)
        self.assertEqual(metrics_hybrid["output"], 12)

        # Verificar conservación de eventos
        ids_set = [
            e["event_id"] for e in result_set["events"]
        ]
        ids_hybrid = [
            e["event_id"] for e in result_hybrid["events"]
        ]

        self.assertEqual(ids_set, ids_hybrid)

        # Verificar equivalencia de estructuras
        self.assertEqual(
            metrics_set["catalog_products"],
            metrics_hybrid["catalog_products"]
        )

        self.assertEqual(
            metrics_set["csr_nnz"],
            metrics_hybrid["csr_nnz"]
        )

        self.assertEqual(
            metrics_set["kdtree_products"],
            metrics_hybrid["kdtree_products"]
        )

        # Comprobar que la opción híbrida fue utilizada
        self.assertEqual(
            metrics_hybrid["dedup_method"],
            "hybrid"
        )

        self.assertIn("exact_checks", metrics_hybrid)
        self.assertIn("bloom_memory_bytes", metrics_hybrid)



if __name__ == "__main__":
    unittest.main()
