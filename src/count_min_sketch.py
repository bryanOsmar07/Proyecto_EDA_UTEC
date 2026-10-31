
import hashlib
import math

import numpy as np


class CountMinSketch:
    """
    Count-Min Sketch para estimar frecuencias de claves.

    - update: O(depth)
    - estimate: O(depth)
    - memoria: O(width * depth)

    Los contadores se almacenan como uint64.
    """

    def __init__(self, epsilon=0.01, delta=0.01):
        if not 0 < epsilon < 1:
            raise ValueError("epsilon debe estar entre 0 y 1")

        if not 0 < delta < 1:
            raise ValueError("delta debe estar entre 0 y 1")

        self.epsilon = epsilon
        self.delta = delta

        self.width = math.ceil(math.e / epsilon)
        self.depth = math.ceil(math.log(1 / delta))

        self.table = np.zeros(
            (self.depth, self.width),
            dtype=np.uint64,
        )

        self.total_updates = 0

    def _hashes(self, key):
        """
        Genera índices reproducibles mediante hashes
        criptográficos con semillas por fila.
        """
        key_bytes = str(key).encode("utf-8")

        for row in range(self.depth):
            digest = hashlib.blake2b(
                row.to_bytes(4, "little") + key_bytes,
                digest_size=8,
            ).digest()

            index = int.from_bytes(digest, "little") % self.width
            yield row, index

    def update(self, key, count=1):
        if not isinstance(count, int) or count <= 0:
            raise ValueError("count debe ser un entero positivo")

        max_value = np.iinfo(np.uint64).max

        # Evitar modificaciones parciales por desbordamiento.
        positions = list(self._hashes(key))

        for row, col in positions:
            if int(self.table[row, col]) > max_value - count:
                raise OverflowError("Contador Count-Min Sketch desbordado")

        for row, col in positions:
            self.table[row, col] += np.uint64(count)

        self.total_updates += count

    def estimate(self, key):
        return min(
            int(self.table[row, col])
            for row, col in self._hashes(key)
        )

    def memory_bytes(self):
        return self.table.nbytes

    def theoretical_error_bound(self):
        """
        Cota aditiva epsilon * N con probabilidad
        de éxito al menos 1 - delta, bajo los
        supuestos del análisis probabilístico.
        """
        return self.epsilon * self.total_updates
