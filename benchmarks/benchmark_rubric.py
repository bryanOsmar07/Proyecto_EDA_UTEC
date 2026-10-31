"""Protocolo reproducible de las cinco familias sobre corpus derivados.

python -m benchmarks.benchmark_rubric --events 1000 10000 100000 1000000 10000000
Cada N es el número de eventos reales de entrada; se registran por separado
productos, usuarios, nodos y aristas. No se confunde N con tamaño de índice.
"""
import argparse
from collections import Counter
import csv
import gc
import json
import os
from pathlib import Path
import platform
import sqlite3
import statistics
import threading
import time
import tracemalloc
import numpy as np
import psutil
from threadpoolctl import threadpool_limits
from sklearn.metrics import adjusted_rand_score
from src.complete_pipeline import CompletePipeline
from src.data_source import iter_rees46
from src.bloom_filter import BloomFilter
from src.count_min_sketch import CountMinSketch
from src.set_similarity import jaccard
import networkx as nx


def measure(fn):
    """Reloj con instrumentación idéntica por alternativa; memoria Python y RSS."""
    gc.collect()
    process = psutil.Process(os.getpid())
    before = process.memory_info().rss; peak = [before]; stop = threading.Event()
    def monitor():
        while not stop.wait(0.005):
            peak[0] = max(peak[0], process.memory_info().rss)
    thread = threading.Thread(target=monitor, daemon=True); thread.start()
    tracemalloc.start()
    start = time.perf_counter()
    try:
        value = fn()
        elapsed = time.perf_counter()-start
        current, py_peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop(); stop.set(); thread.join()
    final = process.memory_info().rss
    peak[0] = max(peak[0], final)
    return value, {"time_s": elapsed, "python_current_mib": current/1024**2,
                   "python_peak_mib": py_peak/1024**2, "rss_current_mib": final/1024**2,
                   "rss_peak_mib": peak[0]/1024**2, "rss_increment_mib": (peak[0]-before)/1024**2}


def recall(reference, approximate, key="product_id"):
    expected = {r[key] for r in reference}
    return len(expected & {r[key] for r in approximate})/len(expected) if expected else 1.0


def experiment(pipeline, n, reps, seed, output):
    raw = []
    ids = sorted(pipeline.catalog)
    rng = np.random.default_rng(seed)
    queries = rng.choice(ids, min(20, len(ids)), replace=False).tolist()
    # Counts are per product over accepted events: weighted stream updates are
    # equivalent to repeated insertion. Both methods receive the same weights.
    counts = {pid: p["views"]+p["carts"]+p["purchases"] for pid,p in pipeline.catalog.items()}
    negatives = [max(ids, default=0)+1+i for i in range(10000)]
    def add(family, method, repetition, stats, **quality):
        raw.append({"input_events": n, "accepted_events": pipeline.metrics["output"],
                    "products": len(ids), "graph_nodes": len(pipeline.graph),
                    "graph_edges": pipeline.graph.number_of_edges(), "repetition": repetition,
                    "seed": seed, "family": family, "method": method, **stats, **quality})
    for r in range(reps):
        # Bloom versus exact membership, including independent absent queries.
        methods = ["set", "bloom"] if r%2==0 else ["bloom", "set"]
        for method in methods:
            def build_membership():
                if method == "set": return set(ids)
                value = BloomFilter(max(1,len(ids)), 0.01)
                for pid in ids:value.add(pid)
                return value
            structure, stats = measure(build_membership)
            if method == "set":
                fp = sum(k in structure for k in negatives)
            else:
                fp = sum(structure.contains(k) for k in negatives)
            add("membership", method, r, stats, false_positive_rate=fp/len(negatives), recall_at_k=1.0)
        for method in (["counter", "cms"] if r%2==0 else ["cms", "counter"]):
            def build_frequency():
                if method == "counter":
                    c=Counter()
                    for key, count in counts.items():c[key]+=count
                    return c
                c=CountMinSketch(epsilon=0.0001,delta=0.01)
                for key,count in counts.items():c.update(key,int(count))
                return c
            structure, stats = measure(build_frequency)
            estimates = [structure.estimate(k) if method=="cms" else structure[k] for k in counts]
            errors = np.asarray(estimates)-np.asarray(list(counts.values()))
            add("frequency",method,r,stats,mean_overestimate=float(np.mean(errors)),
                max_overestimate=int(max(errors,default=0)), normalized_mae=float(np.mean(errors))/max(1,sum(counts.values())))
        # Retrieval benchmarks include candidate search and exact refinement.
        for method in (["lsh","jaccard_brute"] if r%2==0 else ["jaccard_brute","lsh"]):
            _,stats=measure(lambda: [pipeline.lsh.query(q,5,exact=method=="jaccard_brute") for q in queries])
            quality=[];tie_quality=[]
            for q in queries:
                exact=pipeline.lsh.query(q,5,exact=True);approx=pipeline.lsh.query(q,5)
                quality.append(recall(exact,approx))
                threshold=exact[-1]["jaccard"] if exact else 0
                tie_quality.append(sum(x["jaccard"]+1e-12>=threshold for x in approx)/len(exact) if exact else 1)
            add("set_similarity",method,r,stats,queries=len(queries),recall_at_k=float(np.mean(quality)) if method=="lsh" else 1,
                tie_aware_recall=float(np.mean(tie_quality)) if method=="lsh" else 1,
                signature_payload_mib=pipeline.lsh.memory_bytes()/1024**2)
        for method in (["ivf","vector_brute","kd_tree"] if r%2==0 else ["kd_tree","vector_brute","ivf"]):
            def run_queries():
                if method=="kd_tree":return [pipeline.kdtree.query(q,min(5,len(ids)-1)) for q in queries]
                return [pipeline.ann.query(q,5,exact=method=="vector_brute") for q in queries]
            _,stats=measure(run_queries)
            quality=[];tie_quality=[]
            for q in queries:
                exact=pipeline.ann.query(q,5,exact=True);approx=pipeline.ann.query(q,5)
                quality.append(recall(exact,approx))
                threshold=exact[-1]["distance"] if exact else 0
                tie_quality.append(sum(x["distance"]<=threshold+1e-6 for x in approx)/len(exact) if exact else 1)
            add("ann",method,r,stats,queries=len(queries),recall_at_k=float(np.mean(quality)) if method=="ivf" else 1,
                tie_aware_recall=float(np.mean(tie_quality)) if method=="ivf" else 1,
                vector_index_payload_mib=pipeline.ann.memory_bytes()/1024**2)
        graph=pipeline.graph
        for method in (["pagerank","degree"] if r%2==0 else ["degree","pagerank"]):
            fn=(lambda: nx.pagerank(graph,alpha=.85,tol=1e-8,max_iter=500,weight="weight")) if method=="pagerank" else (lambda: dict(graph.degree(weight="weight")))
            ranking,stats=measure(fn)
            top=sorted(ranking,key=lambda x:(-ranking[x],x))[:10]
            add("influence",method,r,stats,top_k_json=json.dumps(top))
        for method in (["louvain","label_propagation"] if r%2==0 else ["label_propagation","louvain"]):
            def communities():
                if not graph.number_of_edges():return [{n} for n in graph]
                if method=="louvain":return nx.community.louvain_communities(graph,weight="weight",seed=seed+r)
                return list(nx.community.asyn_lpa_communities(graph,weight="weight",seed=seed+r))
            groups,stats=measure(communities)
            mapping={node:i for i,g in enumerate(groups) for node in g}
            base=pipeline.graph_analysis["communities"]
            # Same-method run-to-run stability is computed in analyze_graph.
            stability=next(c["stability_ari"] for c in pipeline.graph_analysis["comparison"] if c["algorithm"]==method)
            add("communities",method,r,stats,modularity=nx.community.modularity(graph,groups) if graph.number_of_edges() else 0,
                community_count=len(groups), community_sizes_json=json.dumps(sorted(map(len,groups),reverse=True)),
                stability_ari=stability, stability_runs=pipeline.graph_stability_runs)
        # Real disk query baseline against a scan of the same catalog.
        for method in ["bptree_disk","price_scan"]:
            fn=(lambda: pipeline.bptree.range_search(10000,30000)) if method=="bptree_disk" else (lambda: [p for p in ids if 10000<=round(pipeline.catalog[p]["price"]*100)<=30000])
            value,stats=measure(fn)
            add("price_index",method,r,stats,result_size=len(value))
        if (r+1)%10==0:print(f"N={n:,}: {r+1}/{reps} repeticiones",flush=True)
    import pandas as pd
    frame=pd.DataFrame(raw)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    frame.to_csv(output/f"rubric_raw_{n}.csv",index=False)
    summary=frame.groupby(["input_events","products","graph_nodes","graph_edges","family","method"]).agg(
        repetitions=("time_s","count"),mean_time_s=("time_s","mean"),std_time_s=("time_s","std"),
        mean_python_current_mib=("python_current_mib","mean"),mean_python_peak_mib=("python_peak_mib","mean"),
        mean_rss_current_mib=("rss_current_mib","mean"),max_rss_peak_mib=("rss_peak_mib","max"),
        recall_at_k=("recall_at_k","mean"),tie_aware_recall=("tie_aware_recall","mean"),
        false_positive_rate=("false_positive_rate","mean"),mean_overestimate=("mean_overestimate","mean"),
        max_overestimate=("max_overestimate","max"),modularity=("modularity","mean"),stability_ari=("stability_ari","mean")).reset_index()
    # A single observation has no estimable standard deviation: keep NaN.
    summary.to_csv(output/f"rubric_summary_{n}.csv",index=False)
    return summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--events",nargs="+",type=int,default=[1000,10000,100000,1000000,10000000])
    parser.add_argument("--data",default="data/raw/2019-Oct.csv")
    parser.add_argument("--state",help="Reuse a completed state.sqlite instead of ingesting again")
    parser.add_argument("--repetitions",type=int)
    parser.add_argument("--output",default="results/rubric")
    args=parser.parse_args()
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    (output/"platform.json").write_text(json.dumps({"python":platform.python_version(),"platform":platform.platform(),
          "cpu":platform.processor(),"ram_gib":psutil.virtual_memory().total/1024**3,"seed":42,"native_threads":1,
          "protocol":"time includes tracemalloc; RSS sampled at 5 ms; 20 fixed queries; weighted frequency updates",
          "repetitions_policy":"100 through 100K; 3 for 1M; 1 for 10M due to local resource limits",
          "scale":"N input events; all derived products/graph entities are measured and reported separately"},indent=2),encoding="utf-8")
    with threadpool_limits(1):
        for n in args.events:
            reps=args.repetitions or (100 if n<=100000 else 3 if n<=1000000 else 1)
            with CompletePipeline(expected_items=n) as pipeline:
                if args.state:
                    pipeline.db.close()
                    pipeline.db=sqlite3.connect(args.state)
                    pipeline.metrics["received"]=n
                    pipeline.metrics["output"]=pipeline.db.execute("SELECT COUNT(*) FROM seen").fetchone()[0]
                    pipeline.refresh()
                else:
                    pipeline.run(iter_rees46(args.data,n))
                print(f"Corpus N={n:,}, productos={len(pipeline.catalog):,}, grafo={len(pipeline.graph):,}",flush=True)
                experiment(pipeline,n,reps,42,output)


if __name__=="__main__":main()
