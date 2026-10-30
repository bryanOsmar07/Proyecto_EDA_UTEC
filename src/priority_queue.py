
import heapq
from itertools import count


EVENT_PRIORITIES = {
    "purchase": 1,
    "cart": 2,
    "view": 3,
}


class EventPriorityQueue:
    """
    Cola de prioridad estable utilizando MinHeap.

    Inserción: O(log n)
    Extracción: O(log n)
    Consulta del siguiente: O(1)
    Espacio: O(n)
    """

    def __init__(self):
        self._heap = []
        self._sequence = count()
        self.total_received = 0
        self.total_processed = 0

    def enqueue(self, event):
        # Las alertas críticas son sintéticas, no datos
        # confirmados de fraude de REES46.
        if event.get("is_critical_alert", False):
            priority = 0
        else:
            event_type = event["event_type"]
            if event_type not in EVENT_PRIORITIES:
                raise ValueError(
                    f"Tipo de evento desconocido: {event_type}"
                )
            priority = EVENT_PRIORITIES[event_type]

        sequence = next(self._sequence)

        heapq.heappush(
            self._heap,
            (priority, sequence, event)
        )

        self.total_received += 1

    def dequeue(self):
        if not self._heap:
            return None

        priority, sequence, event = heapq.heappop(
            self._heap
        )

        self.total_processed += 1
        return event

    def peek(self):
        if not self._heap:
            return None

        return self._heap[0][2]

    def is_empty(self):
        return len(self._heap) == 0

    def __len__(self):
        return len(self._heap)
