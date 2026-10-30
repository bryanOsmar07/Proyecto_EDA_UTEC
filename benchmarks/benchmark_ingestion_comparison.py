
from pathlib import Path
import sys
import os
import time
import threading
import gc

import pandas as pd
import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline import run_ingestion_pipeline
from src.streaming_ingestion import StreamingIngestion

DATA_PATH = ROOT / "data" / "raw" / "2019-Oct.csv"


def iter_events(n, chunk_size=2000):
    offset = 0

    for chunk in pd.read_csv(
        DATA_PATH, nrows=n, chunksize=chunk_size
    ):
        chunk["event_id"] = np.arange(
            offset, offset + len(chunk)
        )
        chunk["event_timestamp"] = pd.to_datetime(
            chunk["event_time"], utc=True
        )

        offset += len(chunk)
        yield from chunk.to_dict("records")


def main():
    method = sys.argv[1]
    n = int(sys.argv[2])

    if method not in ("original", "streaming"):
        raise ValueError("Método inválido")

    process = psutil.Process(os.getpid())
    gc.collect()

    rss_before = process.memory_info().rss
    peak = [rss_before]
    stop = threading.Event()

    def monitor():
        while not stop.wait(0.005):
            rss = process.memory_info().rss
            peak[0] = max(peak[0], rss)

    thread = threading.Thread(
        target=monitor, daemon=True
    )
    thread.start()

    start = time.perf_counter()

    try:
        if method == "original":
            events = list(iter_events(n))

            result = run_ingestion_pipeline(
                events,
                batch_size=1000,
                dedup_method="set"
            )
            metrics = result["metrics"]
            count = len(result["events"])

        else:
            ingestion = StreamingIngestion(
                batch_size=1000
            )

            count = sum(
                1 for _ in ingestion.process(
                    iter_events(n)
                )
            )
            metrics = ingestion.metrics

        elapsed = time.perf_counter() - start

    finally:
        stop.set()
        thread.join()

    rss_final = process.memory_info().rss
    peak[0] = max(peak[0], rss_final)

    print(f"\n=== {method.upper()} ===")
    print(f"Eventos: {n:,}")
    print(f"Salida: {count:,}")
    print(f"Tiempo: {elapsed:.4f} s")
    print(f"Throughput: {count/elapsed:,.0f} ev/s")
    print(f"RSS inicial: {rss_before/1024**2:.2f} MiB")
    print(f"Pico RSS: {peak[0]/1024**2:.2f} MiB")
    print(
        "Incremento pico RSS:",
        f"{(peak[0]-rss_before)/1024**2:.2f} MiB"
    )
    print("Métricas:", metrics)

    assert count == n


if __name__ == "__main__":
    main()
