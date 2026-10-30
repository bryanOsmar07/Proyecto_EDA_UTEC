
import unittest
from datetime import datetime, timezone

from src.preprocessing import preprocess_batch, binary_search
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


class TestPreprocessing(unittest.TestCase):

    def test_binary_search(self):
        ids = [1, 3, 5, 7, 9]

        self.assertTrue(binary_search(ids, 5))
        self.assertFalse(binary_search(ids, 6))

    def test_duplicates_inside_batch(self):
        events = [
            make_event(1),
            make_event(2),
            make_event(1)
        ]

        result = preprocess_batch(events)

        self.assertEqual(result["duplicates"], 1)
        self.assertEqual(len(result["events"]), 2)

    def test_invalid_event(self):
        valid = make_event(1)
        invalid = make_event(2)
        invalid["event_type"] = "unknown"

        result = preprocess_batch([valid, invalid])

        self.assertEqual(result["valid"], 1)
        self.assertEqual(result["invalid"], 1)

    def test_duplicates_across_batches(self):
        events = [
            make_event(0),
            make_event(1),
            make_event(2),
            make_event(3),
            make_event(0)
        ]

        result = run_ingestion_pipeline(
            events,
            batch_size=2
        )

        ids = [
            event["event_id"]
            for event in result["events"]
        ]

        self.assertEqual(ids, [0, 1, 2, 3])
        self.assertEqual(result["metrics"]["received"], 5)
        self.assertEqual(result["metrics"]["duplicates"], 1)
        self.assertEqual(result["metrics"]["output"], 4)


if __name__ == "__main__":
    unittest.main()
