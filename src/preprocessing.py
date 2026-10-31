
from bisect import bisect_left
from datetime import datetime
from math import isfinite
from numbers import Integral


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

    if not isinstance(event["event_id"], Integral) or isinstance(event["event_id"], bool):
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


def normalize_event(event):
    """Contrato compartido: claves enteras y metadatos opcionales explícitos."""
    if not validate_event(event):
        raise ValueError("Evento inválido")
    result = dict(event)
    for key in ("event_id", "product_id", "user_id"):
        value = result[key]
        if isinstance(value, bool) or float(value) != int(value):
            raise ValueError(f"{key} debe ser entero")
        result[key] = int(value)
    result["price"] = float(result["price"])
    category = result.get("category_id")
    try:
        result["category_id"] = int(category) if category is not None else 0
    except (ValueError, TypeError, OverflowError):
        result["category_id"] = 0
    for key in ("category_code", "brand", "user_session"):
        value = result.get(key)
        result[key] = "unknown" if value is None or str(value).lower() in ("nan", "", "<na>") else str(value)
    return result


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

    valid_events = []
    for event in events:
        try:
            valid_events.append(normalize_event(event))
        except (ValueError, TypeError, OverflowError):
            pass

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
