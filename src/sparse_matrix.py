
from collections import defaultdict

import numpy as np
from scipy.sparse import coo_matrix


EVENT_WEIGHTS = {
    "view": 1,
    "cart": 3,
    "purchase": 5,
}


class UserProductMatrix:
    """
    Acumula interacciones usuario-producto y genera
    una matriz dispersa CSR.

    La actualización utiliza un diccionario mutable.
    La conversión a CSR se realiza bajo demanda.
    """

    def __init__(self):
        self.interactions = defaultdict(float)
        self.user_ids = set()
        self.product_ids = set()
        self.total_events = 0

    def add_event(self, event):
        user_id = int(event["user_id"])
        product_id = int(event["product_id"])
        event_type = event["event_type"]

        if event_type not in EVENT_WEIGHTS:
            raise ValueError(
                f"Tipo de evento no reconocido: {event_type}"
            )

        weight = EVENT_WEIGHTS[event_type]

        self.interactions[(user_id, product_id)] += weight
        self.user_ids.add(user_id)
        self.product_ids.add(product_id)
        self.total_events += 1

    def to_csr(self):
        users = sorted(self.user_ids)
        products = sorted(self.product_ids)

        user_index = {
            user_id: i for i, user_id in enumerate(users)
        }

        product_index = {
            product_id: i for i, product_id in enumerate(products)
        }

        rows = []
        cols = []
        values = []

        for (user_id, product_id), weight in self.interactions.items():
            rows.append(user_index[user_id])
            cols.append(product_index[product_id])
            values.append(weight)

        matrix = coo_matrix(
            (
                np.asarray(values, dtype=np.float32),
                (rows, cols)
            ),
            shape=(len(users), len(products)),
            dtype=np.float32
        ).tocsr()

        return {
            "matrix": matrix,
            "users": users,
            "products": products,
            "user_index": user_index,
            "product_index": product_index
        }
