
import unittest
from datetime import datetime, timezone

from src.bplus_tree import BPlusTree
from src.streaming_aggregates import StreamingProductCatalog


class TestStreamingBPlusTree(unittest.TestCase):

    def test_price_ranges_match_linear_search(self):
        catalog = StreamingProductCatalog()

        timestamp = datetime(
            2026, 10, 30, tzinfo=timezone.utc
        )

        # Incluye precios repetidos y límites de rangos
        prices = [
            (101, 25.00),
            (102, 50.00),
            (103, 100.00),
            (104, 150.00),
            (105, 150.00),
            (106, 300.00),
            (107, 500.00)
        ]

        for event_id, (product_id, price) in enumerate(
            prices, start=1
        ):
            catalog.update({
                "product_id": product_id,
                "price": price,
                "event_timestamp": timestamp,
                "event_id": event_id
            })

        tree = BPlusTree(max_keys=4)

        for product_id, event in catalog.products.items():
            price_cents = int(round(event["price"] * 100))
            tree.insert(price_cents, product_id)

        self.assertEqual(len(tree), len(catalog))

        ranges = [
            (0, 5000),
            (5000, 10000),
            (10000, 30000),
            (15000, 15000),
            (0, 100000)
        ]

        for minimum, maximum in ranges:
            with self.subTest(
                minimum=minimum,
                maximum=maximum
            ):
                expected = {
                    product_id
                    for product_id, event
                    in catalog.products.items()
                    if minimum <= int(
                        round(event["price"] * 100)
                    ) <= maximum
                }

                actual = tree.range_search(
                    minimum, maximum
                )

                self.assertEqual(
                    set(actual), expected
                )
                self.assertEqual(
                    len(actual), len(expected)
                )


if __name__ == "__main__":
    unittest.main()
