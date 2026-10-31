import random
import numpy as np
import pytest
from src.disk_bplus_tree import DiskBPlusTree
from src.set_similarity import MinHashLSH
from src.ann_index import IVFFlat
from src.domain_graph import graph_from_orders, analyze_graph
from src.complete_pipeline import CompletePipeline
from src.data_source import synthetic_events
from src.preprocessing import normalize_event
from src.trie import CatalogTrie


def test_disk_tree_reopens_and_reads_pages(tmp_path):
    path = tmp_path/"prices.bpt"
    records = [(i%17, i) for i in range(1000)]
    random.Random(42).shuffle(records)
    with DiskBPlusTree(path, max_keys=3, cache_pages=2) as tree:
        for price, pid in records:
            tree.insert(price, pid)
        assert not tree.insert(*records[0])
        assert len(tree)==1000
    with DiskBPlusTree(path, cache_pages=2) as tree:
        assert len(tree)==1000
        assert tree.range_search(4, 9)==[pid for price,pid in sorted(records) if 4<=price<=9]
        assert tree.search(8)==[pid for price,pid in sorted(records) if price==8]
        assert tree.page_reads>1
        assert len(tree.cache)<=2


def test_minhash_replacement_and_exact_ranking():
    index = MinHashLSH().fit({1:{"a","b"}, 2:{"a","b"}, 3:{"x"}})
    assert index.query(1)[0]["product_id"]==2
    assert index.query(1, exact=True)[0]["jaccard"]==1
    index.add(2, {"x"})
    assert index.query(2)[0]["product_id"]==3


def test_ivf_full_probe_matches_exact_and_excludes_self():
    rng = np.random.default_rng(42)
    index = IVFFlat(nlist=5, nprobe=1).fit(np.arange(200), rng.normal(size=(200,4)))
    assert index.query(2, k=10, nprobe=5)==index.query(2, k=10, exact=True)
    assert all(row["product_id"]!=2 for row in index.query(2))


def test_graph_same_graph_community_comparison():
    graph = graph_from_orders([{1,2,3},{4,5,6},{1,2},{4,5}])
    analysis = analyze_graph(graph, stability_runs=3)
    assert sum(analysis["pagerank"].values())==pytest.approx(1)
    assert len(analysis["comparison"])==2
    assert graph[1][2]["weight"]==2
    for row in analysis["comparison"]:
        assert sum(row["community_sizes"])==6
        assert row["stability_ari"]==pytest.approx(1)


def test_all_ten_stages_and_business_outputs(tmp_path):
    with CompletePipeline(tmp_path, batch_size=32, expected_items=500) as pipeline:
        pipeline.run(synthetic_events(500, products=30))
        summary = pipeline.summary()
        assert summary["metrics"]["received"]==500
        assert summary["metrics"]["duplicates"]>0
        assert summary["alerts_count"]>0
        assert all(summary["stage_counts"][str(i)]>0 for i in range(10))
        assert summary["graph"]["edges"]>0
        assert summary["trace"][0]["completed_stages"]==list(range(10))
        pid = next(iter(pipeline.catalog))
        assert pipeline.recommend(pid)["recommendations"]
        assert pipeline.trie.complete("marca")
        assert pipeline.bptree.search(round(pipeline.catalog[pid]["price"]*100))
        pipeline.product(pid); pipeline.product(pid)
        assert pipeline.cache.hits>0
        # Serializing a reduced dashboard summary must not mutate live graph state.
        reduced=pipeline.summary()
        reduced["graph"].pop("communities")
        assert pipeline.recommend(pid)["recommendations"]


def test_empty_complete_pipeline(tmp_path):
    with CompletePipeline(tmp_path) as pipeline:
        pipeline.run([])
        assert pipeline.summary()["products"]==0
        assert pipeline.summary()["graph"]["edges"]==0


def test_complete_pipeline_is_invariant_to_batch_priority_order(tmp_path):
    events = list(synthetic_events(100, products=20, duplicate_every=0))
    with CompletePipeline(tmp_path, batch_size=100) as a, CompletePipeline(tmp_path, batch_size=1) as b:
        a.run(events); b.run(events)
        assert a.catalog==b.catalog
        assert (a.csr!=b.csr).nnz==0
        assert a.summary()["alerts_count"]==b.summary()["alerts_count"]
        assert dict(a.graph.edges)==dict(b.graph.edges)


def test_normalization_and_trie():
    e=next(synthetic_events(1))
    e["product_id"]="5";e.pop("brand")
    assert normalize_event(e)["product_id"]==5
    assert normalize_event(e)["brand"]=="unknown"
    trie=CatalogTrie();trie.add("Árbol");trie.add("Apple")
    assert trie.complete("AP")==["apple"]


def test_false_bloom_positive_cannot_discard_new_event(tmp_path):
    with CompletePipeline(tmp_path, expected_items=20) as pipeline:
        pipeline.bloom.contains=lambda key: True
        pipeline.run(synthetic_events(20, products=10, duplicate_every=0))
        assert pipeline.metrics["output"]==20
        assert pipeline.metrics["bloom_false_positives"]==20


def test_semantic_retransmission_with_different_row_id(tmp_path):
    events=list(synthetic_events(4, duplicate_every=0))
    repeated=dict(events[0], event_id=100)
    with CompletePipeline(tmp_path, batch_size=2) as pipeline:
        pipeline.run(events+[repeated])
        assert pipeline.metrics["duplicates"]==1
        assert pipeline.metrics["output"]==4


def test_duplicate_purchase_membership_does_not_inflate_graph(tmp_path):
    events=list(synthetic_events(2, duplicate_every=0))
    third=dict(events[0],event_id=100,source_event_id='new-real-action')
    third.pop('_dedup_key')
    with CompletePipeline(tmp_path) as pipeline:
        pipeline.run(events+[third])
        assert pipeline.metrics["output"]==3
        a,b=events[0]['product_id'],events[1]['product_id']
        assert pipeline.graph[a][b]['weight']==1
