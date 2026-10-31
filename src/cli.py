"""Ejecutar: python -m src.cli demo | run | serve."""
import argparse
from pathlib import Path
import json
import os
import platform
import threading
import time
import psutil
from threadpoolctl import threadpool_limits
from src.complete_pipeline import CompletePipeline
from src.data_source import iter_rees46, synthetic_events


def main():
    parser = argparse.ArgumentParser(description="Pipeline EDA de diez etapas")
    parser.add_argument("command", choices=["demo", "run", "serve"])
    parser.add_argument("--source", choices=["synthetic", "rees46"], default=None)
    parser.add_argument("--data", default="data/raw/2019-Oct.csv")
    parser.add_argument("--events", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--snapshot-every", type=int, default=0)
    parser.add_argument("--output", default="results/complete_demo")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.events < 1:
        parser.error("--events debe ser positivo")
    source = args.source or ("rees46" if args.command == "run" else "synthetic")
    events = iter_rees46(args.data, args.events) if source == "rees46" else synthetic_events(args.events, args.seed)
    process = psutil.Process(os.getpid()); rss_start = process.memory_info().rss
    peak = [rss_start]; done = threading.Event()
    def monitor():
        while not done.wait(0.02):
            peak[0] = max(peak[0], process.memory_info().rss)
    thread = threading.Thread(target=monitor, daemon=True); thread.start()
    def progress(metrics, elapsed):
        print(f"{metrics['received']:,} recibidos | {metrics['output']:,} aceptados | {elapsed:.1f} s", flush=True)
    with threadpool_limits(limits=1), CompletePipeline(batch_size=args.batch_size,
                 expected_items=args.events, seed=args.seed) as pipeline:
        try:
            pipeline.run(events, snapshot_every=args.snapshot_every, progress=progress)
        finally:
            done.set(); thread.join()
        peak[0] = max(peak[0], process.memory_info().rss)
        output = pipeline.export(args.output)
        summary = pipeline.summary()
        metadata = {"source": source, "requested_events": args.events,
                    "received_events": summary["metrics"]["received"],
                    "rss_initial_mib": rss_start/1024**2,
                    "rss_final_mib": process.memory_info().rss/1024**2,
                    "rss_peak_mib": peak[0]/1024**2,
                    "rss_peak_increment_mib": (peak[0]-rss_start)/1024**2,
                    "rss_sample_interval_s": 0.02, "python": platform.python_version(),
                    "platform": platform.platform(), "cpu": platform.processor(),
                    "ram_gib": psutil.virtual_memory().total/1024**3,
                    "seed": args.seed, "native_threads": 1,
                    "state_path": str(pipeline.workdir / "state.sqlite"),
                    "elapsed_s": summary["elapsed_s"], "products": summary["products"],
                    "graph_nodes": summary["graph"]["nodes"], "graph_edges": summary["graph"]["edges"]}
        metadata["rss_peak_mib"] = max(metadata["rss_peak_mib"], metadata["rss_final_mib"])
        metadata["rss_peak_increment_mib"] = metadata["rss_peak_mib"] - metadata["rss_initial_mib"]
        (output/"run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)
        print(f"Resultados: {output.resolve()}", flush=True)
        if args.command == "serve":
            from src.service import serve
            serve(pipeline, args.port)


if __name__ == "__main__":
    main()
