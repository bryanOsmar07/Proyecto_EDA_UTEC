"""MinHash + LSH para Jaccard; candidatos aproximados, verificación exacta.

Broder (1997), doi:10.1109/SEQUEN.1997.666900. Semilla reproducible.
No se completa silenciosamente una consulta LSH mediante fuerza bruta.
"""
from collections import defaultdict
import hashlib
import numpy as np


def jaccard(a, b):
    union = a | b
    return len(a & b) / len(union) if union else 1.0


class MinHashLSH:
    def __init__(self, num_perm=64, bands=16, seed=42):
        if num_perm < 1 or bands < 1 or num_perm % bands:
            raise ValueError("num_perm debe ser divisible entre bands")
        self.num_perm, self.bands = num_perm, bands
        self.rows = num_perm // bands
        self.prime = np.uint64(4294967291)
        rng = np.random.default_rng(seed)
        self.a = rng.integers(1, int(self.prime), num_perm, dtype=np.uint64)
        self.b = rng.integers(0, int(self.prime), num_perm, dtype=np.uint64)
        self.sets, self.signatures = {}, {}
        self.buckets = [defaultdict(set) for _ in range(bands)]

    def signature(self, tokens):
        result = np.full(self.num_perm, self.prime, dtype=np.uint64)
        for token in sorted(tokens):
            value = int.from_bytes(hashlib.blake2s(str(token).encode(), digest_size=4).digest(), "little")
            hashes = (self.a * np.uint64(value) + self.b) % self.prime
            np.minimum(result, hashes, out=result)
        return result.astype(np.uint32)

    def add(self, item_id, tokens):
        self.remove(item_id)
        tokens = frozenset(str(t) for t in tokens)
        sig = self.signature(tokens)
        self.sets[item_id], self.signatures[item_id] = tokens, sig
        for i in range(self.bands):
            self.buckets[i][sig[i*self.rows:(i+1)*self.rows].tobytes()].add(item_id)

    def remove(self, item_id):
        if item_id not in self.signatures:
            return
        sig = self.signatures.pop(item_id)
        self.sets.pop(item_id)
        for i in range(self.bands):
            key = sig[i*self.rows:(i+1)*self.rows].tobytes()
            bucket = self.buckets[i][key]
            bucket.discard(item_id)
            if not bucket:
                del self.buckets[i][key]

    def fit(self, records):
        # Fit replaces the corpus; add supports incremental replacement.
        self.sets.clear(); self.signatures.clear()
        self.buckets = [defaultdict(set) for _ in range(self.bands)]
        for item_id, tokens in records.items():
            self.add(item_id, tokens)
        return self

    def query(self, item_id, k=5, exact=False):
        if k < 1:
            raise ValueError("k debe ser positivo")
        tokens = self.sets[item_id]
        if exact:
            candidates = set(self.sets)
        else:
            sig = self.signatures[item_id]
            candidates = set()
            for i in range(self.bands):
                key = sig[i*self.rows:(i+1)*self.rows].tobytes()
                candidates.update(self.buckets[i].get(key, ()))
        candidates.discard(item_id)
        ranked = sorted(((jaccard(tokens, self.sets[p]), p) for p in candidates),
                        key=lambda x: (-x[0], x[1]))
        return [{"product_id": p, "jaccard": score} for score, p in ranked[:k]]

    def memory_bytes(self):
        """Carga útil de firmas; usar RSS/tracemalloc para memoria total."""
        return sum(x.nbytes for x in self.signatures.values())
