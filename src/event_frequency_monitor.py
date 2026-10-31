
from collections import defaultdict
from datetime import datetime, timezone

from src.bloom_filter import BloomFilter
from src.count_min_sketch import CountMinSketch


class EventFrequencyMonitor:
    """
    Monitor experimental de frecuencia de compras.

    Entrada: eventos válidos, con event_id único.
    Ventana: hora calendario UTC.
    Requiere timestamps en orden no decreciente.

    Bloom Filter: registra identificadores observados.
    CMS: estima frecuencia de compras por usuario/hora.
    Diccionario: verifica exactamente las alertas.

    Conserva solo la ventana horaria activa.
    """

    def __init__(
        self,
        epsilon=0.0001,
        delta=0.01,
        threshold=10,
        expected_items=100000,
    ):
        if not isinstance(threshold, int) or threshold <= 0:
            raise ValueError("threshold debe ser entero positivo")

        self.epsilon = epsilon
        self.delta = delta
        self.threshold = threshold
        self.expected_items = expected_items

        self.current_window = None
        self.last_timestamp = None

        self.bloom = None
        self.cms = None
        self.exact_counts = defaultdict(int)

        self.events_processed = 0
        self.purchases_processed = 0
        self.cms_candidate_evaluations = 0
        self.cms_false_positive_evaluations = 0
        self.alerts = []
        self.window_summaries = []

    @staticmethod
    def _normalize_timestamp(value):
        if isinstance(value, str):
            value = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

        if not isinstance(value, datetime):
            raise TypeError("event_timestamp debe ser datetime o ISO")

        if value.tzinfo is None:
            raise ValueError("event_timestamp requiere zona horaria")

        return value.astimezone(timezone.utc)

    def _new_window(self, window):
        self.current_window = window

        self.bloom = BloomFilter(
            expected_items=self.expected_items,
            false_positive_rate=0.01,
        )

        self.cms = CountMinSketch(
            epsilon=self.epsilon,
            delta=self.delta,
        )

        self.exact_counts = defaultdict(int)
        self.window_purchases = 0

    def _close_window(self):
        if self.current_window is None:
            return

        self.window_summaries.append({
            "window": self.current_window.isoformat(),
            "purchases": self.window_purchases,
            "distinct_users": len(self.exact_counts),
        })

    def process(self, event):
        timestamp = self._normalize_timestamp(
            event["event_timestamp"]
        )

        if (
            self.last_timestamp is not None
            and timestamp < self.last_timestamp
        ):
            raise ValueError(
                "Los eventos deben llegar en orden cronológico"
            )

        event_type = event["event_type"]

        if event_type not in {"view", "cart", "purchase"}:
            raise ValueError("Tipo de evento no válido")

        if "event_id" not in event:
            raise ValueError("Falta event_id")

        if event_type == "purchase" and event.get("user_id") is None:
            raise ValueError("Falta user_id en purchase")

        window = timestamp.replace(
            minute=0, second=0, microsecond=0
        )

        if self.current_window != window:
            self._close_window()
            self._new_window(window)

        self.last_timestamp = timestamp
        self.events_processed += 1

        event_id = str(event["event_id"])

        # Registro probabilístico de eventos recibidos.
        # El monitor presupone deduplicación exacta previa.
        possibly_seen = self.bloom.contains(event_id)
        self.bloom.add(event_id)

        result = {
            "event_id": event["event_id"],
            "window": window.isoformat(),
            "bloom_possibly_seen": possibly_seen,
            "estimated_frequency": None,
            "exact_frequency": None,
            "alert": None,
        }

        if event_type != "purchase":
            return result

        user_id = str(event["user_id"])

        self.cms.update(user_id)
        self.exact_counts[user_id] += 1

        self.purchases_processed += 1
        self.window_purchases += 1

        estimated = self.cms.estimate(user_id)
        exact = self.exact_counts[user_id]

        result["estimated_frequency"] = estimated
        result["exact_frequency"] = exact

        # Emitimos una sola alerta cuando se alcanza
        # el umbral exacto de la ventana.
        if estimated >= self.threshold:
            self.cms_candidate_evaluations += 1

            if exact < self.threshold:
                self.cms_false_positive_evaluations += 1

            # Una sola alerta por usuario y ventana:
            # se emite al alcanzar exactamente el umbral.
            if exact == self.threshold:

                alert = {
                    "user_id": user_id,
                    "window": window.isoformat(),
                    "event_id": event["event_id"],
                    "estimated_frequency": estimated,
                    "exact_frequency": exact,
                    "threshold": self.threshold,
                    "alert_type": "high_purchase_frequency",
                    "is_synthetic_alert": True,
                }

                self.alerts.append(alert)
                result["alert"] = alert

        return result

    
    def finalize(self):
        self._close_window()
        self.current_window = None

        return {
            "events_processed": self.events_processed,
            "purchases_processed": self.purchases_processed,
            "alerts": list(self.alerts),
            "window_summaries": list(self.window_summaries),
            "cms_candidate_evaluations": self.cms_candidate_evaluations,
            "cms_false_positive_evaluations": self.cms_false_positive_evaluations,
        }

