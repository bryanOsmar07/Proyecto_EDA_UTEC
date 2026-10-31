"""B+Tree persistente por páginas binarias de 4096 bytes.

Claves compuestas (precio en centavos, product_id), hojas enlazadas y caché
LRU acotada. Las búsquedas leen páginas bajo demanda, no cargan todo el
árbol. Inserción sin eliminación. No es un motor transaccional concurrente.
"""
from bisect import bisect_left, bisect_right
from collections import OrderedDict
from pathlib import Path
import struct

PAGE_SIZE = 4096
MAGIC = b"EDABPT01"
HEADER = struct.Struct("<8sQQQQ")  # magic, root, next_page, size, max_keys
NODE_HEADER = struct.Struct("<BHq")  # leaf, nkeys, next leaf
KEY = struct.Struct("<qq")
POINTER = struct.Struct("<q")


class DiskBPlusTree:
    def __init__(self, path, max_keys=64, cache_pages=64, create=False):
        if not 3 <= max_keys <= 100 or cache_pages < 1:
            raise ValueError("max_keys debe estar entre 3 y 100; cache_pages positivo")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_pages, self.cache = cache_pages, OrderedDict()
        self.page_reads = self.page_writes = self.cache_hits = 0
        if self.path.exists() and create:
            raise FileExistsError(self.path)
        new = not self.path.exists()
        self.file = self.path.open("w+b" if new else "r+b")
        if new:
            self.root, self.next_page, self.size, self.max_keys = 1, 2, 0, max_keys
            self._write(1, {"leaf": True, "keys": [], "children": [], "next": -1})
            self.flush()
        else:
            self.file.seek(0)
            data = self.file.read(HEADER.size)
            if len(data) != HEADER.size or data[:8] != MAGIC:
                self.file.close()
                raise ValueError("Archivo B+Tree inválido")
            _, self.root, self.next_page, self.size, self.max_keys = HEADER.unpack(data)

    def _remember(self, page, node):
        self.cache[page] = node
        self.cache.move_to_end(page)
        if len(self.cache) > self.cache_pages:
            self.cache.popitem(last=False)

    def _read(self, page):
        if page in self.cache:
            self.cache_hits += 1
            self.cache.move_to_end(page)
            return self.cache[page]
        self.file.seek(page * PAGE_SIZE)
        data = self.file.read(PAGE_SIZE)
        self.page_reads += 1
        if len(data) != PAGE_SIZE:
            raise ValueError("Página B+Tree incompleta")
        leaf, count, nxt = NODE_HEADER.unpack_from(data)
        offset = NODE_HEADER.size
        keys = [KEY.unpack_from(data, offset+i*KEY.size) for i in range(count)]
        offset += count * KEY.size
        children = [] if leaf else [POINTER.unpack_from(data, offset+i*8)[0] for i in range(count+1)]
        node = {"leaf": bool(leaf), "keys": keys, "children": children, "next": nxt}
        self._remember(page, node)
        return node

    def _write(self, page, node):
        data = bytearray(NODE_HEADER.pack(node["leaf"], len(node["keys"]), node["next"]))
        for key in node["keys"]:
            data.extend(KEY.pack(*key))
        if not node["leaf"]:
            for child in node["children"]:
                data.extend(POINTER.pack(child))
        if len(data) > PAGE_SIZE:
            raise OverflowError("El nodo no cabe en una página")
        self.file.seek(page * PAGE_SIZE)
        self.file.write(data + b"\0" * (PAGE_SIZE-len(data)))
        self.page_writes += 1
        self._remember(page, node)

    def _allocate(self):
        page = self.next_page
        self.next_page += 1
        return page

    def insert(self, price_cents, product_id):
        key = (int(price_cents), int(product_id))
        promoted, inserted = self._insert(self.root, key)
        if promoted:
            separator, right = promoted
            root = self._allocate()
            self._write(root, {"leaf": False, "keys": [separator], "children": [self.root, right], "next": -1})
            self.root = root
        self.size += int(inserted)
        return inserted

    def _insert(self, page, key):
        node = self._read(page)
        if node["leaf"]:
            i = bisect_left(node["keys"], key)
            if i < len(node["keys"]) and node["keys"][i] == key:
                return None, False
            node["keys"].insert(i, key)
        else:
            i = bisect_right(node["keys"], key)
            result, inserted = self._insert(node["children"][i], key)
            if not result:
                return None, inserted
            separator, right = result
            node["keys"].insert(i, separator)
            node["children"].insert(i+1, right)
        if len(node["keys"]) <= self.max_keys:
            self._write(page, node)
            return None, True
        mid = len(node["keys"])//2
        right_page = self._allocate()
        if node["leaf"]:
            right = {"leaf": True, "keys": node["keys"][mid:], "children": [], "next": node["next"]}
            node["keys"] = node["keys"][:mid]
            node["next"] = right_page
            separator = right["keys"][0]
        else:
            separator = node["keys"][mid]
            right = {"leaf": False, "keys": node["keys"][mid+1:], "children": node["children"][mid+1:], "next": -1}
            node["keys"], node["children"] = node["keys"][:mid], node["children"][:mid+1]
        self._write(page, node); self._write(right_page, right)
        return (separator, right_page), True

    def range_search(self, minimum, maximum, limit=None):
        if minimum > maximum:
            return []
        page = self.root
        key = (int(minimum), -(2**63))
        node = self._read(page)
        while not node["leaf"]:
            page = node["children"][bisect_right(node["keys"], key)]
            node = self._read(page)
        result = []
        while True:
            for price, product_id in node["keys"]:
                if price > maximum:
                    return result
                if price >= minimum:
                    result.append(product_id)
                    if limit is not None and len(result) >= limit:
                        return result
            if node["next"] < 0:
                return result
            node = self._read(node["next"])

    def search(self, price):
        return self.range_search(price, price)

    def flush(self):
        self.file.seek(0)
        self.file.write(HEADER.pack(MAGIC, self.root, self.next_page, self.size, self.max_keys))
        self.file.flush()

    def close(self):
        if not self.file.closed:
            self.flush(); self.file.close()

    def __len__(self):
        return self.size

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
