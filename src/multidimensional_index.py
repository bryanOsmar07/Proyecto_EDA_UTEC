
import numpy as np
from sklearn.neighbors import KDTree, NearestNeighbors
from sklearn.preprocessing import StandardScaler


class ProductKDTree:
    """
    Índice multidimensional de productos.

    - Normalización: StandardScaler
    - Índice: KDTree
    - Distancia: euclidiana
    - Referencia exacta: búsqueda por fuerza bruta
    """

    def __init__(self, leaf_size=40):
        if leaf_size < 1:
            raise ValueError("leaf_size debe ser positivo")

        self.leaf_size = leaf_size
        self.scaler = StandardScaler()
        self.tree = None
        self.brute_model = None
        self.product_ids = None
        self.X_scaled = None
        self.id_to_position = {}

    def fit(self, product_ids, features):
        """Construye los índices sobre los vectores."""

        X = np.asarray(features, dtype=np.float64)
        ids = np.asarray(product_ids)

        if X.ndim != 2 or len(X) == 0:
            raise ValueError("Se requiere una matriz 2D no vacía")

        if len(ids) != len(X):
            raise ValueError("IDs y vectores no coinciden")

        if len(set(ids.tolist())) != len(ids):
            raise ValueError("Los product_id deben ser únicos")

        if not np.isfinite(X).all():
            raise ValueError("Las características deben ser finitas")

        self.product_ids = ids.copy()
        self.id_to_position = {
            int(pid): i for i, pid in enumerate(ids)
        }

        self.X_scaled = self.scaler.fit_transform(X)

        self.tree = KDTree(
            self.X_scaled,
            leaf_size=self.leaf_size,
            metric="euclidean"
        )

        self.brute_model = NearestNeighbors(
            algorithm="brute",
            metric="euclidean"
        )
        self.brute_model.fit(self.X_scaled)

        return self

    def query(self, product_id, k=5, method="kd_tree"):
        """Devuelve k vecinos excluyendo el producto consultado."""

        if self.tree is None:
            raise RuntimeError("Ejecuta fit() primero")

        if k < 1 or k >= len(self.product_ids):
            raise ValueError("k fuera de rango")

        position = self.id_to_position[int(product_id)]
        vector = self.X_scaled[position:position + 1]

        if method == "kd_tree":
            distances, indices = self.tree.query(
                vector, k=k + 1
            )
        elif method == "brute":
            distances, indices = self.brute_model.kneighbors(
                vector, n_neighbors=k + 1
            )
        else:
            raise ValueError("Método desconocido")

        neighbors = []

        for idx, distance in zip(indices[0], distances[0]):
            if idx == position:
                continue

            neighbors.append({
                "product_id": int(self.product_ids[idx]),
                "distance": float(distance)
            })

            if len(neighbors) == k:
                break

        return neighbors
