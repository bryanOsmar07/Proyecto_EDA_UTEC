
from pathlib import Path
import sys
import time
import os
import gc
import threading

import numpy as np
import pandas as pd
import psutil

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from src.pipeline import run_multidimensional_pipeline


def main():
    if len(sys.argv) != 2:
        raise ValueError(
            "Uso: python benchmarks/benchmark_pipeline_memory.py N"
        )

    n = int(sys.argv[1])
    if n <= 0:
        raise ValueError("N debe ser positivo")

    data_path = PROJECT_DIR / "data" / "raw" / "2019-Oct.csv"

    process = psutil.Process(os.getpid())

    # Leer datos y preparar eventos
    df = pd.read_csv(data_path, nrows=n)
    df["event_id"] = np.arange(len(df))
    df["event_timestamp"] = pd.to_datetime(
        df["event_time"], utc=True
    )

    events = df.to_dict("records")

    # Liberar DataFrame previo al procesamiento
    del df
    gc.collect()

    rss_before = process.memory_info().rss
    peak_rss = [rss_before]
    stop_monitor = threading.Event()

    def monitor_memory():
        while not stop_monitor.wait(0.01):
            rss = process.memory_info().rss
            peak_rss[0] = max(peak_rss[0], rss)

    monitor = threading.Thread(
        target=monitor_memory,
        daemon=True
    )
    monitor.start()

    start = time.perf_counter()

    try:
        result = run_multidimensional_pipeline(
            events=events,
            batch_size=1000,
            cache_capacity=100,
            max_keys=32,
            leaf_size=40,
            dedup_method="set"
        )
        elapsed = time.perf_counter() - start

    finally:
        stop_monitor.set()
        monitor.join()

    rss_after = process.memory_info().rss
    peak_rss[0] = max(peak_rss[0], rss_after)

    metrics = result["metrics"]

    print("\n=== BENCHMARK DE MEMORIA RSS ===")
    print(f"Eventos: {n:,}")
    print(f"Tiempo: {elapsed:.4f} s")
    print(f"Throughput: {n / elapsed:,.0f} eventos/s")
    print(f"RSS inicial: {rss_before / 1024**2:.2f} MiB")
    print(f"RSS final: {rss_after / 1024**2:.2f} MiB")
    print(f"Pico RSS muestreado: {peak_rss[0] / 1024**2:.2f} MiB")
    print(
        f"Incremento máximo sobre RSS inicial: "
        f"{(peak_rss[0] - rss_before) / 1024**2:.2f} MiB"
    )
    print("Eventos finales:", metrics["output"])
    print("Productos:", metrics["catalog_products"])


if __name__ == "__main__":
    main()
