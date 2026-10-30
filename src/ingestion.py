
from collections import deque


class EventBufferFIFO:
    """
    Buffer FIFO para eventos de comercio electrónico.

    Estructura: collections.deque
    - enqueue: O(1)
    - dequeue: O(1)
    - peek: O(1)
    - Espacio: O(n)
    """

    def __init__(self):
        self._queue = deque()
        self.total_received = 0
        self.total_processed = 0

    def enqueue(self, event):
        """Agrega un evento al final de la cola."""
        self._queue.append(event)
        self.total_received += 1

    def dequeue(self):
        """Extrae el evento más antiguo."""
        if not self._queue:
            return None

        self.total_processed += 1
        return self._queue.popleft()

    def peek(self):
        """Consulta el primer evento sin extraerlo."""
        if not self._queue:
            return None

        return self._queue[0]

    def __len__(self):
        return len(self._queue)

    def is_empty(self):
        return len(self._queue) == 0
