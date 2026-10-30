
from collections import defaultdict


class ProductInteractionAggregator:
    """
    Agrega interacciones por producto en streaming.

    No almacena el historial completo de eventos.
    """

    def __init__(self):
        self.counts = defaultdict(
            lambda: {
                "views": 0,
                "carts": 0,
                "purchases": 0
            }
        )
        self.total_events = 0

    def update(self, event):
        product_id = event["product_id"]
        event_type = event["event_type"]

        columns = {
            "view": "views",
            "cart": "carts",
            "purchase": "purchases"
        }

        if event_type not in columns:
            raise ValueError(
                f"Tipo de evento no soportado: {event_type}"
            )

        column = columns[event_type]
        self.counts[product_id][column] += 1
        self.total_events += 1

    def process(self, events):
        for event in events:
            self.update(event)

    def to_dataframe(self):
        import pandas as pd

        rows = [
            {"product_id": product_id, **values}
            for product_id, values in self.counts.items()
        ]

        return pd.DataFrame(
            rows,
            columns=[
                "product_id",
                "views",
                "carts",
                "purchases"
            ]
        )



class UserProductInteractionAggregator:
    """
    Acumula interacciones por combinación usuario-producto.

    Conserva conteos por tipo de evento para poder
    reproducir posteriormente los pesos de la matriz CSR.
    """

    def __init__(self):
        self.counts = defaultdict(
            lambda: {
                "views": 0,
                "carts": 0,
                "purchases": 0
            }
        )
        self.total_events = 0

    def update(self, event):
        key = (
            event["user_id"],
            event["product_id"]
        )

        event_type = event["event_type"]

        columns = {
            "view": "views",
            "cart": "carts",
            "purchase": "purchases"
        }

        if event_type not in columns:
            raise ValueError(
                f"Tipo de evento no soportado: {event_type}"
            )

        column = columns[event_type]

        self.counts[key][column] += 1
        self.total_events += 1

    def process(self, events):
        for event in events:
            self.update(event)

    def to_dataframe(self):
        import pandas as pd

        rows = [
            {
                "user_id": user_id,
                "product_id": product_id,
                **values
            }
            for (user_id, product_id), values
            in self.counts.items()
        ]

        return pd.DataFrame(
            rows,
            columns=[
                "user_id",
                "product_id",
                "views",
                "carts",
                "purchases"
            ]
        )

    
    def to_csr(self):
        """
        Construye una matriz CSR ponderada.

        Devuelve:
        - matrix: matriz dispersa CSR
        - user_ids: usuarios en orden de filas
        - product_ids: productos en orden de columnas
        """
        import numpy as np
        from scipy.sparse import csr_matrix
        from src.sparse_matrix import EVENT_WEIGHTS

        user_ids = sorted({
            user_id
            for user_id, product_id in self.counts
        })

        product_ids = sorted({
            product_id
            for user_id, product_id in self.counts
        })

        user_to_idx = {
            user_id: i
            for i, user_id in enumerate(user_ids)
        }

        product_to_idx = {
            product_id: j
            for j, product_id in enumerate(product_ids)
        }

        rows = []
        cols = []
        values = []

        for (user_id, product_id), counts in self.counts.items():
            weight = (
                counts["views"] * EVENT_WEIGHTS["view"]
                + counts["carts"] * EVENT_WEIGHTS["cart"]
                + counts["purchases"] * EVENT_WEIGHTS["purchase"]
            )

            rows.append(user_to_idx[user_id])
            cols.append(product_to_idx[product_id])
            values.append(weight)

        matrix = csr_matrix(
            (
                np.asarray(values, dtype=np.int64),
                (rows, cols)
            ),
            shape=(len(user_ids), len(product_ids))
        )

        return matrix, user_ids, product_ids


class StreamingProductCatalog:
    """
    Catálogo incremental por product_id.

    Conserva el evento más reciente de cada producto,
    utilizando (event_timestamp, event_id).
    """

    def __init__(self):
        self.products = {}
        self.total_events = 0

    def update(self, event):
        product_id = event["product_id"]

        current = self.products.get(product_id)

        if current is None:
            self.products[product_id] = event.copy()

        else:
            new_key = (
                event["event_timestamp"],
                event["event_id"]
            )

            current_key = (
                current["event_timestamp"],
                current["event_id"]
            )

            if new_key > current_key:
                self.products[product_id] = event.copy()

        self.total_events += 1

    def process(self, events):
        for event in events:
            self.update(event)

    def get(self, product_id):
        return self.products.get(product_id)

    def __len__(self):
        return len(self.products)
