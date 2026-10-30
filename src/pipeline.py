
from src.ingestion import EventBufferFIFO
from src.preprocessing import preprocess_batch


def run_ingestion_pipeline(events, batch_size=1000):
    """
    Integra:
    Etapa 0: Ingesta FIFO
    Etapa 1: Preprocesamiento por lotes
    """

    if batch_size <= 0:
        raise ValueError("batch_size debe ser positivo")

    buffer = EventBufferFIFO()
    processed_events = []

    metrics = {
        "received": 0,
        "valid": 0,
        "invalid": 0,
        "duplicates": 0,
        "output": 0
    }

    def process_batch(batch):
        result = preprocess_batch(batch)

        processed_events.extend(result["events"])

        metrics["valid"] += result["valid"]
        metrics["invalid"] += result["invalid"]
        metrics["duplicates"] += result["duplicates"]

    # Ingesta de eventos
    for event in events:
        buffer.enqueue(event)
        metrics["received"] += 1

        # Procesar cuando alcanza batch_size
        if len(buffer) >= batch_size:
            batch = []

            while not buffer.is_empty():
                batch.append(buffer.dequeue())

            process_batch(batch)

    # Procesar los eventos restantes
    if not buffer.is_empty():
        batch = []

        while not buffer.is_empty():
            batch.append(buffer.dequeue())

        process_batch(batch)

    metrics["output"] = len(processed_events)

    return {
        "events": processed_events,
        "metrics": metrics
    }
