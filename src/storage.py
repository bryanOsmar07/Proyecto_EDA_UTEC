
from collections import OrderedDict


class ProductStore:
    """
    Catálogo de productos mediante Hash Table.

    Conserva los atributos del evento más reciente
    según timestamp y event_id.

    Lookup: O(1) promedio.
    """

    def __init__(self):
        self.products = {}
        self.last_update = {}

    def add_product(self, product, timestamp, event_id):
        product_id = product["product_id"]

        # Timestamp y event_id sirven para determinar
        # qué registro debe prevalecer.
        version = (timestamp, int(event_id))

        if (
            product_id not in self.last_update
            or version > self.last_update[product_id]
        ):
            self.products[product_id] = product.copy()
            self.last_update[product_id] = version
            return True

        return False

    def get_product(self, product_id):
        return self.products.get(product_id)

    def __len__(self):
        return len(self.products)



class LRUCache:
    """
    Caché Least Recently Used.

    get: O(1) promedio
    put: O(1) promedio
    """

    def __init__(self, capacity=1000):
        if capacity <= 0:
            raise ValueError("La capacidad debe ser positiva")

        self.capacity = capacity
        self.cache = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        if key not in self.cache:
            self.misses += 1
            return None

        self.cache.move_to_end(key)
        self.hits += 1
        return self.cache[key]

    def put(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)

        self.cache[key] = value

        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def hit_rate(self):
        total = self.hits + self.misses
        return self.hits / total if total else 0.0
