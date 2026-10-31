"""IVF-Flat euclidiano con centroides MiniBatchKMeans e índices invertidos.

El entrenamiento usa una muestra reproducible, las listas conservan todos
los vectores. nprobe controla el compromiso recall/latencia. nprobe=nlist
examina todo el corpus y constituye una comprobación exacta del índice.
"""
import numpy as np
from sklearn.cluster import MiniBatchKMeans


class IVFFlat:
    def __init__(self, nlist=32, nprobe=4, seed=42, train_size=50000):
        if nlist < 1 or nprobe < 1 or train_size < 1:
            raise ValueError("Los parámetros deben ser positivos")
        self.nlist, self.nprobe, self.seed, self.train_size = nlist, nprobe, seed, train_size
        self.ids = np.array([], dtype=np.int64)
        self.X = np.empty((0, 0), dtype=np.float32)
        self.positions, self.lists = {}, []

    def fit(self, product_ids, features):
        X = np.ascontiguousarray(features, dtype=np.float32)
        ids = np.asarray(product_ids, dtype=np.int64)
        if X.ndim != 2 or not len(X) or len(X) != len(ids) or not np.isfinite(X).all():
            raise ValueError("Se requieren vectores finitos no vacíos e IDs coincidentes")
        if len(np.unique(ids)) != len(ids):
            raise ValueError("Los IDs deben ser únicos")
        self.X, self.ids = X, ids.copy()
        self.positions = {int(p): i for i, p in enumerate(ids)}
        rng = np.random.default_rng(self.seed)
        sample = X[rng.choice(len(X), min(len(X), self.train_size), replace=False)]
        clusters = min(self.nlist, len(sample), len(np.unique(sample, axis=0)))
        self.model = MiniBatchKMeans(n_clusters=max(1, clusters), random_state=self.seed,
                                    batch_size=2048, n_init=3, max_iter=40)
        self.model.fit(sample)
        self.centers = self.model.cluster_centers_
        # Assign in chunks so training/query never creates an N x nlist matrix.
        labels = np.empty(len(X), dtype=np.int32)
        for start in range(0, len(X), 8192):
            labels[start:start+8192] = self.model.predict(X[start:start+8192])
        order = np.argsort(labels, kind="stable")
        offsets = np.searchsorted(labels[order], np.arange(len(self.centers)+1))
        self.lists = [order[offsets[i]:offsets[i+1]] for i in range(len(self.centers))]
        return self

    def query(self, product_id, k=5, exact=False, nprobe=None):
        if k < 1:
            raise ValueError("k debe ser positivo")
        position = self.positions[int(product_id)]
        vector = self.X[position]
        if exact:
            candidates = np.arange(len(self.X))
        else:
            probes = min(nprobe or self.nprobe, len(self.centers))
            center_distances = np.sum((self.centers-vector)**2, axis=1)
            chosen = np.argsort(center_distances, kind="stable")[:probes]
            candidates = np.concatenate([self.lists[i] for i in chosen])
        candidates = candidates[candidates != position]
        # Bounded temporary memory for exact baselines at 10M vectors.
        best = []
        for start in range(0, len(candidates), 65536):
            idx = candidates[start:start+65536]
            dist = np.sum((self.X[idx]-vector)**2, axis=1)
            order = np.lexsort((self.ids[idx], dist))[:k]
            best.extend((float(dist[j]), int(self.ids[idx[j]])) for j in order)
        best.sort()
        return [{"product_id": pid, "distance": float(np.sqrt(d))} for d, pid in best[:k]]

    def memory_bytes(self):
        return self.X.nbytes + self.ids.nbytes + self.centers.nbytes + sum(a.nbytes for a in self.lists)
