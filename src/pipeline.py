
from src.ingestion import EventBufferFIFO
from src.preprocessing import preprocess_batch
from src.priority_queue import EventPriorityQueue
from src.storage import ProductStore, LRUCache
from src.sparse_matrix import UserProductMatrix


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


def run_priority_pipeline(events, batch_size=1000):
    """
    Integra las primeras tres etapas:

    0. Ingesta FIFO
    1. Preprocesamiento por lotes
    2. Priorización mediante MinHeap
    """

    # Ejecutar etapas 0 y 1
    ingestion_result = run_ingestion_pipeline(
        events=events,
        batch_size=batch_size
    )

    # Obtener eventos validados y deduplicados
    clean_events = ingestion_result["events"]

    # Etapa 2: insertar eventos en el Heap
    priority_queue = EventPriorityQueue()

    for event in clean_events:
        priority_queue.enqueue(event)

    # Extraer eventos según prioridad
    prioritized_events = []

    while not priority_queue.is_empty():
        event = priority_queue.dequeue()
        prioritized_events.append(event)

    return {
        "events": prioritized_events,
        "metrics": {
            **ingestion_result["metrics"],
            "priority_received": priority_queue.total_received,
            "priority_processed": priority_queue.total_processed
        }
    }


def run_storage_pipeline(events, batch_size=1000, cache_capacity=100):
    """
    Integra las etapas 0, 1, 2 y 3.

    Etapa 0: FIFO
    Etapa 1: Preprocesamiento
    Etapa 2: Heap
    Etapa 3: Hash Table + LRU + matriz CSR
    """

    # Ejecutar etapas 0, 1 y 2
    priority_result = run_priority_pipeline(
        events=events,
        batch_size=batch_size
    )

    prioritized_events = priority_result["events"]

    # Crear estructuras de almacenamiento
    catalog = ProductStore()
    cache = LRUCache(capacity=cache_capacity)
    interactions = UserProductMatrix()

    for event in prioritized_events:
        product_id = int(event["product_id"])

        product = {
            "product_id": product_id,
            "category_id": int(event["category_id"]),
            "category_code": event["category_code"],
            "brand": event["brand"],
            "price": float(event["price"])
        }

        # Actualizar catálogo mediante Hash Table
        #catalog.add_product(product)
        catalog.add_product(
            product,
            timestamp=event["event_timestamp"],
            event_id=event["event_id"]
        )

        # Consultar caché para registrar hit o miss
        cache.get(product_id)

        # Sincronizar la caché con la versión vigente
        # del catálogo, evitando sobrescribir con datos antiguos
        cache.put(product_id, catalog.get_product(product_id))

        # Actualizar interacciones usuario-producto
        interactions.add_event(event)

    # Construir matriz CSR
    csr_result = interactions.to_csr()

    metrics = {
        **priority_result["metrics"],
        "catalog_products": len(catalog),
        "cache_hits": cache.hits,
        "cache_misses": cache.misses,
        "cache_hit_rate": cache.hit_rate(),
        "csr_shape": csr_result["matrix"].shape,
        "csr_nnz": csr_result["matrix"].nnz,
        "interaction_weight": float(
            csr_result["matrix"].sum()
        )
    }

    return {
        "events": prioritized_events,
        "catalog": catalog,
        "cache": cache,
        "csr": csr_result,
        "metrics": metrics
    }
