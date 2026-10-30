
from src.preprocessing import preprocess_batch


class StreamingIngestion:
    """
    Ingesta incremental y deduplicación global.

    Conserva solamente:
    - IDs ya observados
    - Métricas
    - Lote actual

    No almacena todos los eventos procesados.
    """

    def __init__(self, batch_size=1000):
        if batch_size <= 0:
            raise ValueError("batch_size debe ser positivo")

        self.batch_size = batch_size
        self.seen_ids = set()

        self.metrics = {
            "received": 0,
            "valid": 0,
            "invalid": 0,
            "duplicates": 0,
            "output": 0
        }

    def _process_batch(self, batch):
        result = preprocess_batch(batch)

        self.metrics["valid"] += result["valid"]
        self.metrics["invalid"] += result["invalid"]
        self.metrics["duplicates"] += result["duplicates"]

        for event in result["events"]:
            event_id = event["event_id"]

            if event_id in self.seen_ids:
                self.metrics["duplicates"] += 1
                continue

            self.seen_ids.add(event_id)
            self.metrics["output"] += 1
            yield event

    def process(self, events):
        """
        Recibe un iterable de eventos y produce
        eventos válidos sin acumular la salida.
        """
        batch = []

        for event in events:
            self.metrics["received"] += 1
            batch.append(event)

            if len(batch) >= self.batch_size:
                yield from self._process_batch(batch)
                batch = []

        if batch:
            yield from self._process_batch(batch)
