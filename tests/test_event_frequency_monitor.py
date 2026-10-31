
from datetime import datetime, timezone, timedelta

import pytest

from src.event_frequency_monitor import EventFrequencyMonitor


BASE = datetime(2026, 10, 30, 16, 0, tzinfo=timezone.utc)


def make_event(event_id, user_id, event_type, minute):
    return {
        "event_id": event_id,
        "user_id": user_id,
        "product_id": 100,
        "event_type": event_type,
        "event_timestamp": BASE + timedelta(minutes=minute),
        "price": 50.0,
    }


def test_alert_when_threshold_reached():
    monitor = EventFrequencyMonitor(threshold=3)

    results = [
        monitor.process(
            make_event(i, 200, "purchase", i)
        )
        for i in range(1, 5)
    ]

    assert results[0]["alert"] is None
    assert results[1]["alert"] is None
    assert results[2]["alert"] is not None
    assert results[3]["alert"] is None

    assert len(monitor.alerts) == 1
    assert monitor.alerts[0]["exact_frequency"] == 3


def test_views_and_carts_do_not_increase_purchase_frequency():
    monitor = EventFrequencyMonitor(threshold=2)

    monitor.process(make_event(1, 200, "view", 1))
    monitor.process(make_event(2, 200, "cart", 2))

    result = monitor.process(
        make_event(3, 200, "purchase", 3)
    )

    assert result["exact_frequency"] == 1
    assert result["alert"] is None


def test_hourly_window_resets():
    monitor = EventFrequencyMonitor(threshold=2)

    monitor.process(make_event(1, 200, "purchase", 1))
    monitor.process(make_event(2, 200, "purchase", 2))

    result = monitor.process(
        make_event(3, 200, "purchase", 61)
    )

    assert len(monitor.alerts) == 1
    assert result["exact_frequency"] == 1


def test_bloom_registers_possible_repetition():
    monitor = EventFrequencyMonitor()

    first = monitor.process(
        make_event(1, 200, "view", 1)
    )
    second = monitor.process(
        make_event(1, 200, "view", 2)
    )

    assert first["bloom_possibly_seen"] is False
    assert second["bloom_possibly_seen"] is True

    # No estamos probando deduplicación:
    # este monitor espera eventos únicos de la etapa 1.


def test_out_of_order_timestamps_are_rejected():
    monitor = EventFrequencyMonitor()

    monitor.process(make_event(1, 200, "view", 10))

    with pytest.raises(ValueError):
        monitor.process(
            make_event(2, 200, "view", 5)
        )


def test_cms_candidate_metrics():
    monitor = EventFrequencyMonitor(
        epsilon=0.0001,
        delta=0.01,
        threshold=3,
    )

    for i in range(1, 6):
        monitor.process(
            make_event(i, 200, "purchase", i)
        )

    summary = monitor.finalize()

    # Compras 3, 4 y 5 superan el umbral estimado.
    assert summary["cms_candidate_evaluations"] == 3

    # En este caso no hay colisiones que generen
    # falsos positivos.
    assert summary["cms_false_positive_evaluations"] == 0

    # Solo se emite una alerta al llegar a 3 compras.
    assert len(summary["alerts"]) == 1
    assert summary["alerts"][0]["exact_frequency"] == 3
