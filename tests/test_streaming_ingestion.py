
import unittest
from datetime import datetime, timezone

from src.streaming_ingestion import StreamingIngestion
from src.pipeline import run_ingestion_pipeline


def make_event(event_id):
    return {
        "event_id": event_id,
        "event_type": "view",
        "product_id": 100,
        "user_id": 200,
        "price": 50.0,
        "event_timestamp": datetime(
            2026, 10, 30, tzinfo=timezone.utc
        )
    }


class TestStreamingIngestion(unittest.TestCase):

    def test_streaming_matches_original(self):
        events = [make_event(i) for i in range(20)]

        original = run_ingestion_pipeline(
            events, batch_size=5
        )

        streaming = StreamingIngestion(batch_size=5)
        result = list(streaming.process(iter(events)))

        self.assertEqual(
            [e["event_id"] for e in result],
            [e["event_id"] for e in original["events"]]
        )

        self.assertEqual(streaming.metrics["output"], 20)

    def test_duplicates_across_batches(self):
        events = [make_event(i) for i in range(12)]
        events += [
            make_event(0),
            make_event(3),
            make_event(7)
        ]

        streaming = StreamingIngestion(batch_size=4)
        result = list(streaming.process(iter(events)))

        self.assertEqual(len(result), 12)
        self.assertEqual(streaming.metrics["received"], 15)
        self.assertEqual(streaming.metrics["duplicates"], 3)
        self.assertEqual(streaming.metrics["output"], 12)

    def test_invalid_event(self):
        events = [
            make_event(1),
            {**make_event(2), "event_type": "unknown"}
        ]

        streaming = StreamingIngestion(batch_size=2)
        result = list(streaming.process(iter(events)))

        self.assertEqual(len(result), 1)
        self.assertEqual(streaming.metrics["invalid"], 1)

    def test_invalid_batch_size(self):
        with self.assertRaises(ValueError):
            StreamingIngestion(batch_size=0)


if __name__ == "__main__":
    unittest.main()
