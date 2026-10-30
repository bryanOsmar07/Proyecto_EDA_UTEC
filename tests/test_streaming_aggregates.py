
import unittest

from src.streaming_aggregates import (
    ProductInteractionAggregator
)
from src.streaming_ingestion import StreamingIngestion
from src.streaming_aggregates import (
    ProductInteractionAggregator,
    UserProductInteractionAggregator
)


def make_event(event_id, product_id, event_type):
    return {
        "event_id": event_id,
        "product_id": product_id,
        "event_type": event_type
    }


class TestStreamingAggregates(unittest.TestCase):

    def test_count_interactions(self):
        aggregator = ProductInteractionAggregator()

        events = [
            make_event(1, 100, "view"),
            make_event(2, 100, "view"),
            make_event(3, 100, "cart"),
            make_event(4, 100, "purchase"),
            make_event(5, 200, "view")
        ]

        aggregator.process(events)

        self.assertEqual(aggregator.total_events, 5)

        self.assertEqual(
            aggregator.counts[100],
            {"views": 2, "carts": 1, "purchases": 1}
        )

        self.assertEqual(
            aggregator.counts[200],
            {"views": 1, "carts": 0, "purchases": 0}
        )

    def test_multiple_products(self):
        aggregator = ProductInteractionAggregator()

        events = [
            make_event(1, 100, "view"),
            make_event(2, 200, "cart"),
            make_event(3, 300, "purchase")
        ]

        aggregator.process(events)

        self.assertEqual(len(aggregator.counts), 3)
        self.assertEqual(aggregator.total_events, 3)

    def test_invalid_event_type(self):
        aggregator = ProductInteractionAggregator()

        with self.assertRaises(ValueError):
            aggregator.update(
                make_event(1, 100, "unknown")
            )

    def test_retransmissions_with_streaming(self):
        aggregator = ProductInteractionAggregator()
        ingestion = StreamingIngestion(batch_size=2)

        # Estos eventos sí contienen el esquema esperado
        # por el preprocesamiento.
        from datetime import datetime, timezone

        timestamp = datetime(
            2026, 10, 30, tzinfo=timezone.utc
        )

        events = [
            {
                "event_id": i,
                "event_type": "view",
                "product_id": 100,
                "user_id": 200,
                "price": 50.0,
                "event_timestamp": timestamp
            }
            for i in range(4)
        ]

        # Retransmitir un evento ya procesado
        events.append(events[0].copy())

        aggregator.process(
            ingestion.process(iter(events))
        )

        self.assertEqual(ingestion.metrics["duplicates"], 1)
        self.assertEqual(aggregator.total_events, 4)
        self.assertEqual(aggregator.counts[100]["views"], 4)

    def test_dataframe_columns(self):
        aggregator = ProductInteractionAggregator()

        aggregator.update(
            make_event(1, 100, "view")
        )

        result = aggregator.to_dataframe()

        self.assertEqual(
            list(result.columns),
            ["product_id", "views", "carts", "purchases"]
        )

    
class TestStreamingCSR(unittest.TestCase):

    def test_csr_weights(self):
        agg = UserProductInteractionAggregator()

        events = [
            make_event(1, 100, "view"),
            make_event(2, 100, "cart"),
            make_event(3, 100, "purchase"),
        ]

        for event in events:
            event["user_id"] = 10

        agg.process(events)

        matrix, users, products = agg.to_csr()

        self.assertEqual(matrix.shape, (1, 1))
        self.assertEqual(matrix.nnz, 1)
        self.assertEqual(int(matrix[0, 0]), 9)
        self.assertEqual(users, [10])
        self.assertEqual(products, [100])

    def test_csr_multiple_users_products(self):
        agg = UserProductInteractionAggregator()

        events = [
            make_event(1, 200, "view"),
            make_event(2, 100, "cart"),
            make_event(3, 200, "purchase")
        ]

        for event, user_id in zip(events, [20, 10, 10]):
            event["user_id"] = user_id

        agg.process(events)

        matrix, users, products = agg.to_csr()

        self.assertEqual(matrix.shape, (2, 2))
        self.assertEqual(matrix.nnz, 3)
        self.assertEqual(int(matrix.sum()), 9)
        self.assertEqual(users, [10, 20])
        self.assertEqual(products, [100, 200])

    def test_csr_repeated_pair(self):
        agg = UserProductInteractionAggregator()

        for i in range(5):
            event = make_event(i, 100, "view")
            event["user_id"] = 10
            agg.update(event)

        matrix, _, _ = agg.to_csr()

        self.assertEqual(matrix.nnz, 1)
        self.assertEqual(int(matrix[0, 0]), 5)

    def test_csr_empty(self):
        agg = UserProductInteractionAggregator()

        matrix, users, products = agg.to_csr()

        self.assertEqual(matrix.shape, (0, 0))
        self.assertEqual(matrix.nnz, 0)
        self.assertEqual(users, [])
        self.assertEqual(products, [])



if __name__ == "__main__":
    unittest.main()
