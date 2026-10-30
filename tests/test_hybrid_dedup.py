
import unittest

from src.hybrid_dedup import HybridDeduplicator


class TestHybridDeduplicator(unittest.TestCase):

    def test_duplicate_detection(self):
        dedup = HybridDeduplicator(expected_items=100)

        events = [
            {"event_id": 1},
            {"event_id": 2},
            {"event_id": 1},
            {"event_id": 3},
            {"event_id": 2}
        ]

        accepted = [
            event["event_id"]
            for event in events
            if dedup.process(event)
        ]

        self.assertEqual(accepted, [1, 2, 3])
        self.assertEqual(dedup.metrics()["duplicates"], 2)
        self.assertEqual(dedup.metrics()["accepted"], 3)

    def test_no_false_negatives(self):
        dedup = HybridDeduplicator(expected_items=1000)

        for i in range(1000):
            self.assertTrue(
                dedup.process({"event_id": i})
            )

        for i in range(1000):
            self.assertFalse(
                dedup.process({"event_id": i})
            )

        self.assertEqual(dedup.metrics()["duplicates"], 1000)

    def test_false_positive_does_not_drop_event(self):
        dedup = HybridDeduplicator(expected_items=10)

        # Simular una respuesta positiva del filtro
        # para un evento que no está en el Hash Set.
        dedup.bloom.contains = lambda item: True

        accepted = dedup.process({"event_id": 123})

        self.assertTrue(accepted)
        self.assertIn(123, dedup.seen_ids)
        self.assertEqual(
            dedup.metrics()["bloom_false_positives"], 1
        )

    def test_metrics_consistency(self):
        dedup = HybridDeduplicator(expected_items=100)

        for event_id in [1, 2, 3, 1, 2]:
            dedup.process({"event_id": event_id})

        metrics = dedup.metrics()

        self.assertEqual(metrics["received"], 5)
        self.assertEqual(metrics["accepted"], 3)
        self.assertEqual(metrics["duplicates"], 2)

        self.assertEqual(
            metrics["received"],
            metrics["accepted"] + metrics["duplicates"]
        )


if __name__ == "__main__":
    unittest.main()
