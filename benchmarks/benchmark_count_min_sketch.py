
from collections import Counter
from pathlib import Path
from statistics import mean, stdev
from time import perf_counter
import random
import tracemalloc

import pandas as pd

from src.count_min_sketch import CountMinSketch


SIZES = [1_000, 10_000, 100_000]
REPETITIONS = 5
SEED = 42
THRESHOLD = 10


def generate_events(n):
    rng = random.Random(SEED)
    unique_users = max(1, n // 20)

    # Claves sintéticas usuario + ventana horaria
    return [
        f"user_{rng.randrange(unique_users)}|2026-10-30T16"
        for _ in range(n)
    ]


def measure_build(keys, method):
    tracemalloc.start()
    start = perf_counter()

    if method == "exact":
        structure = Counter()
        structure.update(keys)

    else:
        structure = CountMinSketch(
            epsilon=0.01,
            delta=0.01,
        )
        for key in keys:
            structure.update(key)

    elapsed = perf_counter() - start
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return structure, elapsed, peak_bytes


def benchmark(n):
    keys = generate_events(n)
    times = {"exact": [], "cms": []}
    peaks = {"exact": [], "cms": []}

    exact = None
    cms = None

    for _ in range(REPETITIONS):
        exact, t, peak = measure_build(keys, "exact")
        times["exact"].append(t)
        peaks["exact"].append(peak)

        cms, t, peak = measure_build(keys, "cms")
        times["cms"].append(t)
        peaks["cms"].append(peak)

    errors = [
        cms.estimate(key) - frequency
        for key, frequency in exact.items()
    ]

    # Consultamos claves observadas y no observadas.
    evaluation_keys = list(exact.keys())
    evaluation_keys += [
        f"unseen_{i}|2026-10-30T16"
        for i in range(1000)
    ]

    false_positives = sum(
        exact.get(key, 0) < THRESHOLD
        and cms.estimate(key) >= THRESHOLD
        for key in evaluation_keys
    )

    actual_negatives = sum(
        exact.get(key, 0) < THRESHOLD
        for key in evaluation_keys
    )

    def row(method):
        values = times[method]
        return {
            "events": n,
            "method": method,
            "repetitions": REPETITIONS,
            "mean_time_s": mean(values),
            "std_time_s": stdev(values),
            "mean_peak_mib": mean(peaks[method]) / 1024**2,
            "distinct_keys": len(exact),
            "mean_overestimate": (
                mean(errors) if method == "cms" else 0
            ),
            "max_overestimate": (
                max(errors) if method == "cms" else 0
            ),
            "false_positives": (
                false_positives if method == "cms" else 0
            ),
            "false_positive_rate": (
                false_positives / actual_negatives
                if method == "cms" and actual_negatives
                else 0
            ),
        }

    return [row("exact"), row("cms")]


def main():
    rows = []

    for n in SIZES:
        print(f"Procesando {n:,} eventos...")
        rows.extend(benchmark(n))

    df = pd.DataFrame(rows)

    output = Path("results/benchmark_count_min_sketch.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)

    print("\n=== RESULTADOS COUNT-MIN SKETCH ===")
    print(df.to_string(index=False, float_format="%.6f"))
    print(f"\nResultados guardados en: {output.resolve()}")


if __name__ == "__main__":
    main()
