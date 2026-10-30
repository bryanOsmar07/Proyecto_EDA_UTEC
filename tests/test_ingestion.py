
import unittest

from src.ingestion import EventBufferFIFO


class TestEventBufferFIFO(unittest.TestCase):

    def test_fifo_order(self):
        buffer = EventBufferFIFO()

        # Insertamos 1000 eventos en orden
        for i in range(1000):
            buffer.enqueue({"event_id": i})

        # Verificamos TODOS los IDs
        resultado = [
            buffer.dequeue()["event_id"]
            for _ in range(1000)
        ]

        self.assertEqual(resultado, list(range(1000)))
        self.assertTrue(buffer.is_empty())

    def test_empty_queue(self):
        buffer = EventBufferFIFO()

        self.assertIsNone(buffer.dequeue())
        self.assertIsNone(buffer.peek())

    def test_counters(self):
        buffer = EventBufferFIFO()

        for i in range(10):
            buffer.enqueue({"event_id": i})

        for _ in range(6):
            buffer.dequeue()

        self.assertEqual(buffer.total_received, 10)
        self.assertEqual(buffer.total_processed, 6)
        self.assertEqual(len(buffer), 4)


if __name__ == "__main__":
    unittest.main()
