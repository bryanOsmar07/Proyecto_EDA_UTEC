"""Grafo ponderado de co-compra y análisis de influencia/comunidades."""
from itertools import combinations
from time import perf_counter
import networkx as nx
import numpy as np
from sklearn.metrics import adjusted_rand_score


def graph_from_orders(orders):
    graph = nx.Graph()
    for products in orders:
        products = sorted(set(products))
        graph.add_nodes_from(products)
        for a, b in combinations(products, 2):
            graph.add_edge(a, b, weight=graph.get_edge_data(a, b, {}).get("weight", 0) + 1)
    return graph


def partition_labels(nodes, communities):
    mapping = {node: i for i, community in enumerate(communities) for node in community}
    return [mapping[n] for n in nodes]


def analyze_graph(graph, seed=42, stability_runs=3):
    if stability_runs < 1:
        raise ValueError("stability_runs debe ser positivo")
    if not len(graph):
        return {"nodes": 0, "edges": 0, "pagerank": {}, "degree": {}, "communities": {}, "comparison": []}
    start = perf_counter()
    rank = nx.pagerank(graph, alpha=0.85, weight="weight", max_iter=500, tol=1e-8)
    pagerank_time = perf_counter()-start
    start = perf_counter()
    degree = dict(graph.degree(weight="weight"))
    degree_time = perf_counter()-start
    rows, partitions = [], {}
    nodes = sorted(graph)
    for name in ["louvain", "label_propagation"]:
        runs, times, modularities = [], [], []
        for r in range(stability_runs):
            start = perf_counter()
            if not graph.number_of_edges():
                groups = [{n} for n in nodes]
            elif name == "louvain":
                groups = nx.community.louvain_communities(graph, weight="weight", seed=seed+r)
            else:
                groups = list(nx.community.asyn_lpa_communities(graph, weight="weight", seed=seed+r))
            times.append(perf_counter()-start)
            runs.append(groups)
            modularities.append(nx.community.modularity(graph, groups, weight="weight") if graph.number_of_edges() else 0.0)
        labels = [partition_labels(nodes, c) for c in runs]
        ari = [adjusted_rand_score(labels[i], labels[j]) for i in range(len(labels)) for j in range(i)]
        sizes = sorted((len(c) for c in runs[0]), reverse=True)
        rows.append({"algorithm": name, "mean_time_s": float(np.mean(times)),
                     "std_time_s": float(np.std(times, ddof=1)) if len(times)>1 else 0.0,
                     "modularity": float(np.mean(modularities)), "community_count": len(sizes),
                     "community_sizes": sizes, "stability_ari": float(np.mean(ari)) if ari else None,
                     "stability_runs": stability_runs})
        partitions[name] = {n: i for i, c in enumerate(sorted(runs[0], key=lambda c: min(c))) for n in c}
    return {"nodes": len(graph), "edges": graph.number_of_edges(), "pagerank": rank,
            "degree": degree, "pagerank_time_s": pagerank_time, "degree_time_s": degree_time,
            "communities": partitions["louvain"], "comparison": rows}
