
from pathlib import Path
import sys
import os
import gc
import time
import threading

import numpy as np
import pandas as pd
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline import run_multidimensional_pipeline
from src.streaming_pipeline import run_streaming_pipeline

DATA_PATH = ROOT / "data" / "raw" / "2019-Oct.csv"


def iter_events(n, chunk_size=2000):
    offset = 0

    for chunk in pd.read_csv(
        DATA_PATH,
        nrows=n,
        chunksize=chunk_size
    ):
        chunk["event_id"] = np.arange(
            offset,
            offset + len(chunk)
        )

        chunk["event_timestamp"] = pd.to_datetime(
            chunk["event_time"],
            utc=True
        )

        offset += len(chunk)

        yield from chunk.to_dict("records")


def main():
    if len(sys.argv) != 3:
        raise ValueError(
            "Uso: python benchmarks/"
            "benchmark_full_pipeline_comparison.py "
            "original|streaming N"
        )

    method = sys.argv[1]
    n = int(sys.argv[2])

    if method not in ("original", "streaming"):
        raise ValueError("Método inválido")

    if n <= 0:
        raise ValueError("N debe ser positivo")

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
        target=monitor,
        daemon=True
    )

    thread.start()
    start = time.perf_counter()

    try:
        if method == "original":
            # Acumula los eventos, como la implementación original
            events = list(iter_events(n))

            result = run_multidimensional_pipeline(
                events=events,
                batch_size=1000,
                cache_capacity=100,
                max_keys=32,
                leaf_size=40,
                dedup_method="set"
            )
        else:
            # Consume los eventos incrementalmente
            result = run_streaming_pipeline(
                iter_events(n),
                batch_size=1000
            )

        elapsed = time.perf_counter() - start

    finally:
        stop.set()
        thread.join()

    rss_after = process.memory_info().rss
    peak[0] = max(peak[0], rss_after)

    metrics = result["metrics"]

    print(f"\n=== PIPELINE {method.upper()} ===")
    print(f"Eventos de entrada: {n:,}")
    print(f"Tiempo total: {elapsed:.4f} s")
    print(f"Throughput: {n / elapsed:,.0f} ev/s")

    print(f"RSS inicial: {rss_before / 1024**2:.2f} MiB")
    print(f"RSS final: {rss_after / 1024**2:.2f} MiB")
    print(f"Pico RSS: {peak[0] / 1024**2:.2f} MiB")

    print(
        "Incremento pico RSS:",
        f"{(peak[0] - rss_before) / 1024**2:.2f} MiB"
    )

    print("\n=== MÉTRICAS FUNCIONALES ===")

    for key in [
        "received",
        "output",
        "catalog_products",
        "csr_nnz",
        "kdtree_products"
    ]:
        print(f"{key}: {metrics[key]}")

    assert metrics["received"] == n
    assert metrics["output"] == n


if __name__ == "__main__":
    main()
