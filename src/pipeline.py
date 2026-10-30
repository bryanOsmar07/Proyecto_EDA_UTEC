
from src.ingestion import EventBufferFIFO
from src.preprocessing import preprocess_batch
from src.priority_queue import EventPriorityQueue
from src.storage import ProductStore, LRUCache
from src.sparse_matrix import UserProductMatrix
from src.bplus_tree import BPlusTree
from src.product_features import (
    build_product_features,
    FEATURE_COLUMNS
)
from src.multidimensional_index import ProductKDTree




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
    # Registro exacto de IDs aceptados en lotes anteriores
    seen_event_ids = set()

    metrics = {
        "received": 0,
        "valid": 0,
        "invalid": 0,
        "duplicates": 0,
        "output": 0
    }

    
    def process_batch(batch):
        result = preprocess_batch(batch)

        metrics["valid"] += result["valid"]
        metrics["invalid"] += result["invalid"]
        metrics["duplicates"] += result["duplicates"]

        # Deduplicar también contra lotes anteriores
        for event in result["events"]:
            event_id = event["event_id"]

            if event_id in seen_event_ids:
                metrics["duplicates"] += 1
                continue

            seen_event_ids.add(event_id)
            processed_events.append(event)


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


def run_indexed_pipeline(
    events,
    batch_size=1000,
    cache_capacity=100,
    max_keys=32
):
    """
    Integra las etapas 0, 1, 2, 3 y 4.

    Construye una instantánea del índice B+Tree
    a partir del catálogo actualizado.
    """

    # Ejecutar etapas 0-3
    storage_result = run_storage_pipeline(
        events=events,
        batch_size=batch_size,
        cache_capacity=cache_capacity
    )

    catalog = storage_result["catalog"]

    # Etapa 4: construir índice de precios
    price_index = BPlusTree(max_keys=max_keys)

    for product in catalog.products.values():
        price_cents = round(product["price"] * 100)

        price_index.insert(
            price_cents,
            product["product_id"]
        )

    # Registrar métricas
    metrics = {
        **storage_result["metrics"],
        "bptree_indexed_products": len(price_index),
        "bptree_root_keys": len(price_index.root.keys)
    }

    return {
        **storage_result,
        "price_index": price_index,
        "metrics": metrics
    }


def run_multidimensional_pipeline(
    events,
    batch_size=1000,
    cache_capacity=100,
    max_keys=32,
    leaf_size=40
):
    """
    Integra las etapas 0 a 5 del proyecto.

    Etapa 5:
    - Generación de características por producto
    - Normalización StandardScaler
    - Construcción KD-Tree para KNN exacto
    """

    # Ejecutar etapas 0 a 4
    indexed_result = run_indexed_pipeline(
        events=events,
        batch_size=batch_size,
        cache_capacity=cache_capacity,
        max_keys=max_keys
    )

    clean_events = indexed_result["events"]

    # Construir características a partir de eventos
    # válidos, deduplicados y priorizados
    features = build_product_features(clean_events)

    # Construir índice multidimensional
    product_index = ProductKDTree(
        leaf_size=leaf_size
    )

    product_index.fit(
        product_ids=features["product_id"].to_numpy(),
        features=features[FEATURE_COLUMNS].to_numpy()
    )

    # Registrar métricas
    metrics = {
        **indexed_result["metrics"],
        "kdtree_products": len(product_index.product_ids),
        "kdtree_dimensions": product_index.X_scaled.shape[1]
    }

    return {
        **indexed_result,
        "product_features": features,
        "product_kdtree": product_index,
        "metrics": metrics
    }
