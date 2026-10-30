
from datetime import datetime, timezone, timedelta

from src.priority_queue import EventPriorityQueue
from src.streaming_aggregates import (
    ProductInteractionAggregator,
    UserProductInteractionAggregator,
    StreamingProductCatalog,
    StreamingProductPriceMedian,
)


def build_event(event_id, event_type, product_id, user_id, price, minute):
    base = datetime(2026, 10, 30, tzinfo=timezone.utc)

    return {
        "event_id": event_id,
        "event_type": event_type,
        "product_id": product_id,
        "user_id": user_id,
        "price": price,
        "event_timestamp": base + timedelta(minutes=minute),
    }


def aggregate(events):
    product_counts = ProductInteractionAggregator()
    interactions = UserProductInteractionAggregator()
    catalog = StreamingProductCatalog()
    price_medians = StreamingProductPriceMedian()

    for event in events:
        product_counts.update(event)
        interactions.update(event)
        catalog.update(event)
        price_medians.update(event)

    csr, users, products = interactions.to_csr()

    medians = {
        product_id: price_medians.get_median(product_id)
        for product_id in price_medians.prices
    }

    return {
        "counts": dict(product_counts.counts),
        "interactions": dict(interactions.counts),
        "catalog": dict(catalog.products),
        "csr": csr,
        "users": users,
        "products": products,
        "medians": medians,
    }


def test_streaming_aggregates_are_order_invariant():
    events = [
        build_event(1, "view", 100, 200, 50.0, 1),
        build_event(2, "purchase", 100, 200, 55.0, 2),
        build_event(3, "cart", 200, 201, 80.0, 3),
        build_event(4, "view", 100, 202, 60.0, 4),
        build_event(5, "purchase", 200, 201, 85.0, 5),
    ]

    queue = EventPriorityQueue()

    for event in events:
        queue.enqueue(event)

    prioritized = []

    while not queue.is_empty():
        prioritized.append(queue.dequeue())

    assert [e["event_id"] for e in prioritized] == [2, 5, 3, 1, 4]

    fifo_result = aggregate(events)
    priority_result = aggregate(prioritized)

    assert fifo_result["counts"] == priority_result["counts"]
    assert fifo_result["interactions"] == priority_result["interactions"]
    assert fifo_result["catalog"] == priority_result["catalog"]
    assert fifo_result["medians"] == priority_result["medians"]

    assert fifo_result["users"] == priority_result["users"]
    assert fifo_result["products"] == priority_result["products"]
    assert (
        fifo_result["csr"] != priority_result["csr"]
    ).nnz == 0
