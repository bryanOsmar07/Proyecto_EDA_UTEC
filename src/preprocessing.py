
from bisect import bisect_left
from datetime import datetime
from math import isfinite


VALID_EVENT_TYPES = {"view", "cart", "purchase"}


def validate_event(event):
    """Valida los campos fundamentales del evento."""

    required = [
        "event_id",
        "event_type",
        "product_id",
        "user_id",
        "price",
        "event_timestamp"
    ]

    if any(field not in event for field in required):
        return False

    if event["event_type"] not in VALID_EVENT_TYPES:
        return False

    if not isinstance(event["event_id"], int):
        return False

    if event["event_id"] < 0:
        return False

    if not isinstance(event["event_timestamp"], datetime):
        return False

    if event["event_timestamp"].tzinfo is None:
        return False

    try:
        if int(event["product_id"]) <= 0:
            return False

        if int(event["user_id"]) <= 0:
            return False

        if not isfinite(float(event["price"])):
            return False

        if float(event["price"]) < 0:
            return False

    except (TypeError, ValueError, OverflowError):
        return False

    return True


def binary_search(sorted_ids, target):
    """
    Búsqueda binaria sobre IDs ordenados.

    Complejidad: O(log n).
    """
    index = bisect_left(sorted_ids, target)

    return index < len(sorted_ids) and sorted_ids[index] == target


def preprocess_batch(events):
    """
    Valida, ordena y deduplica eventos por event_id.

    Ordenación: O(n log n)
    Búsqueda binaria: O(log n) por consulta
    """

    valid_events = [
        event for event in events
        if validate_event(event)
    ]

    # Ordenar por ID para agrupar repeticiones técnicas
    sorted_events = sorted(
        valid_events,
        key=lambda event: event["event_id"]
    )

    unique_events = []
    sorted_ids = []

    for event in sorted_events:
        event_id = event["event_id"]

        if not binary_search(sorted_ids, event_id):
            unique_events.append(event)
            sorted_ids.append(event_id)

    # Restaurar orden temporal, con desempate por event_id
    unique_events.sort(
        key=lambda event: (
            event["event_timestamp"],
            event["event_id"]
        )
    )

    return {
        "events": unique_events,
        "received": len(events),
        "valid": len(valid_events),
        "invalid": len(events) - len(valid_events),
        "duplicates": len(valid_events) - len(unique_events)
    }
