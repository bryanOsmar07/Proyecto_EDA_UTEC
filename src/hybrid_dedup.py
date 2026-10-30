
from src.bloom_filter import BloomFilter


class HybridDeduplicator:
    """
    Deduplicador exacto asistido por Bloom Filter.

    Bloom descarta rápidamente posibles ausencias.
    Hash Set confirma los posibles duplicados.
    """

    def __init__(
        self,
        expected_items=100000,
        false_positive_rate=0.01
    ):
        self.bloom = BloomFilter(
            expected_items=expected_items,
            false_positive_rate=false_positive_rate
        )

        self.seen_ids = set()

        self.received = 0
        self.accepted = 0
        self.duplicates = 0
        self.bloom_positives = 0
        self.bloom_false_positives = 0
        self.exact_checks = 0

    def process(self, event):
        """
        Devuelve True si el evento es nuevo.
        Devuelve False si es duplicado.
        """
        event_id = event["event_id"]
        self.received += 1

        if self.bloom.contains(event_id):
            self.bloom_positives += 1
            self.exact_checks += 1

            if event_id in self.seen_ids:
                self.duplicates += 1
                return False

            # Bloom respondió positivo para un ID nuevo
            self.bloom_false_positives += 1

        # Evento nuevo: actualizar ambas estructuras
        self.seen_ids.add(event_id)
        self.bloom.add(event_id)
        self.accepted += 1

        return True

    def metrics(self):
        return {
            "received": self.received,
            "accepted": self.accepted,
            "duplicates": self.duplicates,
            "bloom_positives": self.bloom_positives,
            "bloom_false_positives":
                self.bloom_false_positives,
            "exact_checks": self.exact_checks,
            "bloom_memory_bytes":
                self.bloom.memory_bytes(),
            "unique_ids": len(self.seen_ids)
        }
