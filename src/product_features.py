
import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "log_price",
    "log_views",
    "log_carts",
    "log_purchases"
]


def build_product_features(events):
    """
    Genera características de productos a partir
    de eventos REES46 procesados.

    Precio: mediana observada por producto.
    Comportamiento: frecuencia por tipo de evento.
    Transformación: log1p.
    """

    df = pd.DataFrame(events)

    if df.empty:
        raise ValueError("No hay eventos para procesar")

    required = {
        "product_id", "event_type", "price"
    }

    if not required.issubset(df.columns):
        raise ValueError("Faltan columnas requeridas")

    # Contar interacciones por producto y tipo
    counts = pd.crosstab(
        df["product_id"],
        df["event_type"]
    )

    for event_type in ["view", "cart", "purchase"]:
        if event_type not in counts.columns:
            counts[event_type] = 0

    # Calcular precio representativo
    prices = df.groupby("product_id")["price"].median()

    features = pd.DataFrame({
        "product_id": counts.index,
        "price": prices.reindex(counts.index).to_numpy(),
        "views": counts["view"].to_numpy(),
        "carts": counts["cart"].to_numpy(),
        "purchases": counts["purchase"].to_numpy()
    })

    features["log_price"] = np.log1p(
        features["price"].clip(lower=0)
    )

    for column in ["views", "carts", "purchases"]:
        features[f"log_{column}"] = np.log1p(
            features[column]
        )

    if not np.isfinite(
        features[FEATURE_COLUMNS].to_numpy()
    ).all():
        raise ValueError("Se detectaron valores no finitos")

    return features.reset_index(drop=True)
