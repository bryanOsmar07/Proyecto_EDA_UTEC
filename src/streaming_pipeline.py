
import numpy as np

from src.streaming_ingestion import StreamingIngestion
from src.streaming_aggregates import (
    ProductInteractionAggregator,
    UserProductInteractionAggregator,
    StreamingProductCatalog,
    StreamingProductPriceMedian,
)
from src.bplus_tree import BPlusTree
from src.multidimensional_index import ProductKDTree


FEATURE_COLUMNS = [
    "log_price",
    "log_views",
    "log_carts",
    "log_purchases",
]


def run_streaming_pipeline(events, batch_size=1000):
    """
    Procesa un iterable de eventos sin conservar
    el historial completo en una lista.

    Construye los índices al finalizar la ingesta.
    """

    ingestion = StreamingIngestion(batch_size=batch_size)

    product_counts = ProductInteractionAggregator()
    user_product = UserProductInteractionAggregator()
    catalog = StreamingProductCatalog()
    price_medians = StreamingProductPriceMedian()

    # Un único recorrido de los eventos validados.
    for event in ingestion.process(events):
        product_counts.update(event)
        user_product.update(event)
        catalog.update(event)
        price_medians.update(event)

    # Matriz CSR
    csr, user_ids, csr_product_ids = user_product.to_csr()

    # Índice B+Tree
    bptree = BPlusTree(max_keys=32)

    for product_id, event in catalog.products.items():
        price_cents = int(round(float(event["price"]) * 100))
        bptree.insert(price_cents, product_id)

    # Características para KD-Tree
    counts_df = product_counts.to_dataframe()
    prices_df = price_medians.to_dataframe()

    features = counts_df.merge(
        prices_df,
        on="product_id",
        how="inner",
        validate="one_to_one"
    )

    for destination, source in [
        ("log_price", "median_price"),
        ("log_views", "views"),
        ("log_carts", "carts"),
        ("log_purchases", "purchases"),
    ]:
        features[destination] = np.log1p(
            features[source]
        )

    features = features.sort_values(
        "product_id"
    ).reset_index(drop=True)

    product_ids = features["product_id"].to_numpy()
    feature_matrix = features[
        FEATURE_COLUMNS
    ].to_numpy(dtype=np.float64)

    kdtree = ProductKDTree(leaf_size=40)
    kdtree.fit(product_ids, feature_matrix)

    metrics = {
        **ingestion.metrics,
        "catalog_products": len(catalog),
        "csr_users": len(user_ids),
        "csr_products": len(csr_product_ids),
        "csr_nnz": csr.nnz,
        "csr_weight_sum": int(csr.sum()),
        "bptree_products": len(bptree),
        "kdtree_products": len(product_ids),
    }

    return {
        "metrics": metrics,
        "catalog": catalog,
        "product_counts": product_counts,
        "user_product": user_product,
        "price_medians": price_medians,
        "csr": csr,
        "csr_user_ids": user_ids,
        "csr_product_ids": csr_product_ids,
        "bptree": bptree,
        "features": features,
        "kdtree": kdtree,
    }
