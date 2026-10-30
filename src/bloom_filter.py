
import math
import hashlib


class BloomFilter:
    """
    Bloom Filter clásico sin eliminación.

    Permite:
    - Agregar elementos
    - Consultar posible pertenencia
    - Estimar memoria utilizada

    Puede producir falsos positivos,
    pero no falsos negativos.
    """

    def __init__(self, expected_items=100000, false_positive_rate=0.01):
        if expected_items <= 0:
            raise ValueError("expected_items debe ser positivo")

        if not 0 < false_positive_rate < 1:
            raise ValueError(
                "false_positive_rate debe estar entre 0 y 1"
            )

        self.expected_items = expected_items
        self.false_positive_rate = false_positive_rate

        # Número óptimo aproximado de bits
        self.num_bits = math.ceil(
            -expected_items * math.log(false_positive_rate)
            / (math.log(2) ** 2)
        )

        # Número óptimo aproximado de hashes
        self.num_hashes = max(
            1,
            round(
                (self.num_bits / expected_items)
                * math.log(2)
            )
        )

        # Almacenamiento compacto
        self.bit_array = bytearray(
            (self.num_bits + 7) // 8
        )

        self.items_added = 0

    def _hashes(self, item):
        """
        Genera posiciones usando double hashing.
        Se utiliza BLAKE2b para obtener resultados
        deterministas entre ejecuciones.
        """
        data = str(item).encode("utf-8")

        digest = hashlib.blake2b(
            data,
            digest_size=16
        ).digest()

        h1 = int.from_bytes(digest[:8], "little")
        h2 = int.from_bytes(digest[8:], "little")

        for i in range(self.num_hashes):
            yield (h1 + i * h2) % self.num_bits

    def add(self, item):
        for position in self._hashes(item):
            byte_index = position // 8
            bit_index = position % 8

            self.bit_array[byte_index] |= (
                1 << bit_index
            )

        self.items_added += 1

    def contains(self, item):
        for position in self._hashes(item):
            byte_index = position // 8
            bit_index = position % 8

            if not (
                self.bit_array[byte_index]
                & (1 << bit_index)
            ):
                return False

        return True

    def __contains__(self, item):
        return self.contains(item)

    def memory_bytes(self):
        return len(self.bit_array)

    def estimated_fpr(self):
        """
        Aproximación de la probabilidad de
        falsos positivos según inserciones.
        """
        m = self.num_bits
        k = self.num_hashes
        n = self.items_added

        return (1 - math.exp(-k * n / m)) ** k
