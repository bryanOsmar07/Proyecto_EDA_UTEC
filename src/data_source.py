"""Lectores reproducibles y stream sintético con órdenes explícitas."""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import random


def semantic_digest(event):
    """Identidad por contenido normalizado; no incorpora el número de fila.

    Política: filas idénticas en todos los campos del evento son duplicados
    técnicos. Acciones legítimas idénticas requieren un ID externo distinto.
    """
    if event.get("source_event_id") is not None:
        fields = ["external", str(event["source_event_id"])]
    else:
        fields = [event["event_timestamp"].isoformat(), event["event_type"],
                  int(event["product_id"]), int(event["user_id"]), float(event["price"]),
                  str(event.get("user_session", "unknown")), str(event.get("category_id", 0)),
                  str(event.get("category_code", "unknown")), str(event.get("brand", "unknown")),
                  str(event.get("order_id", ""))]
    return hashlib.blake2b(json.dumps(fields, ensure_ascii=False, separators=(",", ":")).encode(), digest_size=16).digest()


def iter_rees46(path, limit=None):
    with open(path, encoding="utf-8", newline="") as stream:
        for i, row in enumerate(csv.DictReader(stream)):
            if limit is not None and i >= limit:
                return
            try:
                row["event_id"] = i
                row["event_timestamp"] = datetime.fromisoformat(row["event_time"].replace(" UTC", "+00:00"))
                row["product_id"], row["user_id"] = int(row["product_id"]), int(row["user_id"])
                row["price"] = float(row["price"])
                row["category_id"] = int(row["category_id"] or 0)
                for key in ("category_code", "brand", "user_session"):
                    row[key] = row.get(key) or "unknown"
                row["_dedup_key"] = semantic_digest(row)
                # REES46 lacks order_id. This explicit proxy is not a confirmed order.
                if row["event_type"] == "purchase":
                    hour = row["event_timestamp"].strftime("%Y%m%d%H")
                    session = row["user_session"] if row["user_session"] != "unknown" else f"user:{row['user_id']}"
                    row["order_id"] = f"inferred-session-hour:{session}:{hour}"
                    row["order_is_inferred"] = True
                yield row
            except (ValueError, TypeError, KeyError):
                # Preserve row accounting; preprocessing will reject this record.
                yield {"event_id": i, "_source_invalid": True}


def synthetic_events(n=1000, seed=42, products=200, duplicate_every=97):
    rng = random.Random(seed)
    base = datetime(2026, 10, 30, tzinfo=timezone.utc)
    previous = None
    for i in range(n):
        if previous is not None and duplicate_every and i % duplicate_every == 0:
            yield dict(previous)
            continue
        # Planted product groups produce non-trivial co-purchase communities.
        order = i // 4
        group = order % max(1, min(5, products//4))
        width = max(1, products//max(1, min(5, products//4)))
        pid = 1 + min(products-1, group*width + (order*7+(i%4)*(1+order%7)) % width)
        event = {"event_id": i, "event_timestamp": base+timedelta(seconds=i),
                 "event_type": "purchase" if i % 4 in (0, 1) else rng.choice(["view", "cart"]),
                 "product_id": pid, "user_id": 1+(order % 300),
                 "price": round(10 + pid*1.7, 2), "category_id": 1+group,
                 "category_code": f"electronics.group{group}", "brand": f"marca{group}",
                 "user_session": f"session{order}", "order_id": f"synthetic-order{order}",
                 "order_is_inferred": False, "is_synthetic": True,
                 "is_critical_alert": i % 997 == 17,
                 "shipping_priority": ("express", "standard", "scheduled")[order % 3]}
        # Controlled high-frequency account for demonstrating verified alerts.
        if event["event_type"] == "purchase" and i < 100:
            event["user_id"] = 999999
        event["_dedup_key"] = semantic_digest(event)
        previous = event
        yield event
