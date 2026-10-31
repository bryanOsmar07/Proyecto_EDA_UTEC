"""Trie de términos de catálogo; prefijos Unicode normalizados."""
import unicodedata


def normalize_term(value):
    return unicodedata.normalize("NFKC", str(value)).casefold().strip()


class CatalogTrie:
    def __init__(self):
        self.root = {}

    def add(self, term):
        term = normalize_term(term)
        if not term:
            return
        node = self.root
        for char in term:
            node = node.setdefault(char, {})
        node[""] = term

    def complete(self, prefix, limit=10):
        if limit < 1:
            return []
        node = self.root
        for char in normalize_term(prefix):
            if char not in node:
                return []
            node = node[char]
        result, stack = [], [node]
        while stack and len(result) < limit:
            node = stack.pop()
            if "" in node:
                result.append(node[""])
            stack.extend(node[c] for c in sorted(node, reverse=True) if c)
        return result
