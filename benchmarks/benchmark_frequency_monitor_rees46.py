
from pathlib import Path
from time import perf_counter

import pandas as pd

from benchmarks.benchmark_full_pipeline_comparison import iter_events
from src.streaming_ingestion import StreamingIngestion
from src.event_frequency_monitor import EventFrequencyMonitor


N_EVENTS = 100_000
BATCH_SIZE = 1_000
THRESHOLD = 10
EPSILON = 0.0001
DELTA = 0.01


def main():
    ingestion = StreamingIngestion(batch_size=BATCH_SIZE)

    monitor = EventFrequencyMonitor(
        epsilon=EPSILON,
        delta=DELTA,
        threshold=THRESHOLD,
        expected_items=N_EVENTS,
    )

    
    start = perf_counter()

    for event in ingestion.process(iter_events(N_EVENTS)):
        monitor.process(event)

    summary = monitor.finalize()
    elapsed = perf_counter() - start

    metrics = ingestion.metrics

    print("\n=== MONITOREO REES46 ===")
    print(f"Eventos de entrada: {metrics['received']:,}")
    print(f"Eventos aceptados: {metrics['output']:,}")
    print(f"Eventos inválidos: {metrics['invalid']:,}")
    print(f"Eventos duplicados: {metrics['duplicates']:,}")
    print(f"Compras monitoreadas: {summary['purchases_processed']:,}")
    print(f"Ventanas horarias: {len(summary['window_summaries'])}")

    print(
        "Candidatos CMS (evaluaciones):",
        f"{summary['cms_candidate_evaluations']:,}"
    )
    print(
        "Falsos positivos CMS (evaluaciones):",
        f"{summary['cms_false_positive_evaluations']:,}"
    )


    print(f"Alertas confirmadas: {len(summary['alerts']):,}")
    print(f"Tiempo total: {elapsed:.4f} s")

    print("\n=== PRIMERAS ALERTAS ===")
    for alert in summary["alerts"][:5]:
        print(alert)

    output_dir = Path("results")
    output_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(summary["window_summaries"]).to_csv(
        output_dir / "frequency_monitor_windows.csv",
        index=False,
    )

    pd.DataFrame(
        summary["alerts"],
        columns=[
            "user_id",
            "window",
            "event_id",
            "estimated_frequency",
            "exact_frequency",
            "threshold",
            "alert_type",
            "is_synthetic_alert",
        ],
    ).to_csv(
        output_dir / "frequency_monitor_alerts.csv",
        index=False,
    )

    print("\nResultados guardados en results/")


if __name__ == "__main__":
    main()
