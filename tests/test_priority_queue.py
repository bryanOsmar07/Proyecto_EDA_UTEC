
import unittest

from src.priority_queue import EventPriorityQueue


class TestEventPriorityQueue(unittest.TestCase):

    def test_priority_order(self):
        """Los eventos salen según su prioridad."""

        queue = EventPriorityQueue()

        events = [
            {"event_id": 1, "event_type": "view"},
            {"event_id": 2, "event_type": "cart"},
            {"event_id": 3, "event_type": "purchase"},
            {
                "event_id": 4,
                "event_type": "view",
                "is_critical_alert": True
            }
        ]

        for event in events:
            queue.enqueue(event)

        result = [
            queue.dequeue()["event_id"]
            for _ in range(4)
        ]

        self.assertEqual(result, [4, 3, 2, 1])

    def test_same_priority_fifo(self):
        """Eventos con igual prioridad mantienen FIFO."""

        queue = EventPriorityQueue()

        for i in range(100):
            queue.enqueue({
                "event_id": i,
                "event_type": "view"
            })

        result = [
            queue.dequeue()["event_id"]
            for _ in range(100)
        ]

        self.assertEqual(result, list(range(100)))

    def test_empty_queue(self):
        """Una cola vacía devuelve None."""

        queue = EventPriorityQueue()

        self.assertIsNone(queue.dequeue())
        self.assertIsNone(queue.peek())

    def test_counters(self):
        """Los contadores reflejan las operaciones."""

        queue = EventPriorityQueue()

        for i in range(10):
            queue.enqueue({
                "event_id": i,
                "event_type": "cart"
            })

        for _ in range(6):
            queue.dequeue()

        self.assertEqual(queue.total_received, 10)
        self.assertEqual(queue.total_processed, 6)
        self.assertEqual(len(queue), 4)

    def test_invalid_event_type(self):
        """Rechaza tipos de eventos desconocidos."""

        queue = EventPriorityQueue()

        with self.assertRaises(ValueError):
            queue.enqueue({
                "event_id": 1,
                "event_type": "unknown"
            })


if __name__ == "__main__":
    unittest.main()
