
import unittest

from src.bloom_filter import BloomFilter


class TestBloomFilter(unittest.TestCase):

    def test_inserted_items_present(self):
        bloom = BloomFilter(
            expected_items=1000,
            false_positive_rate=0.01
        )

        for event_id in range(1000):
            bloom.add(event_id)

        self.assertTrue(
            all(event_id in bloom for event_id in range(1000))
        )

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            BloomFilter(expected_items=0)

        with self.assertRaises(ValueError):
            BloomFilter(false_positive_rate=0)

        with self.assertRaises(ValueError):
            BloomFilter(false_positive_rate=1)

    def test_memory_size(self):
        bloom = BloomFilter(
            expected_items=10000,
            false_positive_rate=0.01
        )

        self.assertEqual(
            bloom.memory_bytes(),
            (bloom.num_bits + 7) // 8
        )

    def test_estimated_fpr(self):
        bloom = BloomFilter(
            expected_items=10000,
            false_positive_rate=0.01
        )

        for event_id in range(10000):
            bloom.add(event_id)

        self.assertAlmostEqual(
            bloom.estimated_fpr(),
            0.01,
            delta=0.002
        )

    def test_repeated_insertion(self):
        bloom = BloomFilter(expected_items=100)

        bloom.add("event-123")
        bloom.add("event-123")

        self.assertTrue(bloom.contains("event-123"))
        self.assertEqual(bloom.items_added, 2)


if __name__ == "__main__":
    unittest.main()
