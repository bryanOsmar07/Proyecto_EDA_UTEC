
from bisect import bisect_left, bisect_right


class BPlusNode:
    def __init__(self, is_leaf=False):
        self.is_leaf = is_leaf
        self.keys = []
        self.children = []
        self.next = None


class BPlusTree:
    """
    B+Tree en memoria.

    max_keys: máximo número de claves por nodo.

    Admite:
    - Inserciones
    - Claves repetidas
    - Búsqueda puntual
    - Búsqueda por rango
    """

    def __init__(self, max_keys=4):
        if max_keys < 3:
            raise ValueError("max_keys debe ser >= 3")

        self.max_keys = max_keys
        self.root = BPlusNode(is_leaf=True)
        self.size = 0

    def insert(self, key, value):
        result = self._insert_recursive(
            self.root, key, value
        )

        if result is not None:
            promoted_key, right_node = result

            new_root = BPlusNode(is_leaf=False)
            new_root.keys = [promoted_key]
            new_root.children = [self.root, right_node]

            self.root = new_root

        self.size += 1

    def _insert_recursive(self, node, key, value):
        if node.is_leaf:
            index = bisect_left(node.keys, key)

            if index < len(node.keys) and node.keys[index] == key:
                node.children[index].append(value)
                return None

            node.keys.insert(index, key)
            node.children.insert(index, [value])

            if len(node.keys) <= self.max_keys:
                return None

            return self._split_leaf(node)

        index = bisect_right(node.keys, key)

        result = self._insert_recursive(
            node.children[index], key, value
        )

        if result is not None:
            promoted_key, right_node = result

            node.keys.insert(index, promoted_key)
            node.children.insert(index + 1, right_node)

            if len(node.keys) > self.max_keys:
                return self._split_internal(node)

        return None

    def _split_leaf(self, node):
        mid = len(node.keys) // 2

        right = BPlusNode(is_leaf=True)
        right.keys = node.keys[mid:]
        right.children = node.children[mid:]

        node.keys = node.keys[:mid]
        node.children = node.children[:mid]

        right.next = node.next
        node.next = right

        return right.keys[0], right

    def _split_internal(self, node):
        mid = len(node.keys) // 2
        promoted_key = node.keys[mid]

        right = BPlusNode(is_leaf=False)
        right.keys = node.keys[mid + 1:]
        right.children = node.children[mid + 1:]

        node.keys = node.keys[:mid]
        node.children = node.children[:mid + 1]

        return promoted_key, right

    def search(self, key):
        node = self.root

        while not node.is_leaf:
            index = bisect_right(node.keys, key)
            node = node.children[index]

        index = bisect_left(node.keys, key)

        if index < len(node.keys) and node.keys[index] == key:
            return list(node.children[index])

        return []

    def range_search(self, min_key, max_key):
        if min_key > max_key:
            return []

        node = self.root

        while not node.is_leaf:
            index = bisect_right(node.keys, min_key)
            node = node.children[index]

        results = []

        while node is not None:
            for key, values in zip(node.keys, node.children):
                if key > max_key:
                    return results

                if key >= min_key:
                    results.extend(values)

            node = node.next

        return results

    def __len__(self):
        return self.size
