"""Pipeline de diez etapas en microlotes con estado exacto en SQLite.

SQLite conserva deduplicación, interacciones, frecuencias y órdenes sin
retener 10M diccionarios de eventos. El índice de precios es un B+Tree
propio por páginas, independiente de los índices internos de SQLite.
"""
from collections import Counter, defaultdict
from datetime import timezone
from pathlib import Path
import heapq
import json
import sqlite3
import time
import uuid
import numpy as np
import networkx as nx
from scipy.sparse import csr_matrix
from src.ingestion import EventBufferFIFO
from src.preprocessing import preprocess_batch
from src.storage import LRUCache
from src.bloom_filter import BloomFilter
from src.count_min_sketch import CountMinSketch
from src.disk_bplus_tree import DiskBPlusTree
from src.multidimensional_index import ProductKDTree
from src.set_similarity import MinHashLSH
from src.ann_index import IVFFlat
from src.domain_graph import analyze_graph
from src.trie import CatalogTrie


STAGES = ["FIFO", "preprocesamiento", "Heap", "hash_CSR_LRU", "B+Tree_disco",
          "KDTree_exacto", "Bloom_CMS", "MinHash_LSH_IVF", "PageRank_comunidades", "servicio_TopK"]
WEIGHTS = {"view": 1, "cart": 3, "purchase": 5}


class CompletePipeline:
    def __init__(self, workdir="data/processed", batch_size=2000, expected_items=100000,
                 seed=42, alert_threshold=10, nprobe=4, graph_stability_runs=3):
        if batch_size < 1 or expected_items < 1 or alert_threshold < 1:
            raise ValueError("Tamaños y umbral deben ser positivos")
        self.workdir = Path(workdir) / ("run_" + uuid.uuid4().hex[:10])
        self.workdir.mkdir(parents=True)
        self.batch_size, self.seed, self.threshold = batch_size, seed, alert_threshold
        self.nprobe, self.graph_stability_runs = nprobe, graph_stability_runs
        self.db = sqlite3.connect(self.workdir / "state.sqlite")
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        PRAGMA cache_size=-131072;
        CREATE TABLE seen (digest BLOB PRIMARY KEY) WITHOUT ROWID;
        CREATE TABLE products (pid INTEGER PRIMARY KEY, category TEXT, brand TEXT, price REAL,
          timestamp TEXT, event_id INTEGER, views INTEGER DEFAULT 0, carts INTEGER DEFAULT 0,
          purchases INTEGER DEFAULT 0);
        CREATE TABLE interactions (uid INTEGER, pid INTEGER, weight INTEGER,
          PRIMARY KEY(uid,pid)) WITHOUT ROWID;
        CREATE TABLE frequencies (window TEXT, uid INTEGER, frequency INTEGER,
          PRIMARY KEY(window,uid)) WITHOUT ROWID;
        CREATE TABLE order_items (order_id TEXT, pid INTEGER, PRIMARY KEY(order_id,pid)) WITHOUT ROWID;
        CREATE TABLE alerts (window TEXT, uid INTEGER, event_id INTEGER, estimated INTEGER,
          exact INTEGER, PRIMARY KEY(window,uid)) WITHOUT ROWID;
        """)
        self.bloom = BloomFilter(expected_items=expected_items, false_positive_rate=0.01)
        # Temporal keys retain exact calendar-hour identity even after Heap reordering.
        self.cms = CountMinSketch(epsilon=0.00001, delta=0.01)
        self.cache = LRUCache(256)
        self.catalog, self.graph = {}, nx.Graph()
        self.bptree = self.kdtree = self.ann = self.lsh = None
        self.trie = CatalogTrie()
        self.graph_analysis = analyze_graph(self.graph)
        self.csr = csr_matrix((0, 0))
        self.metrics = Counter(received=0, valid=0, invalid=0, duplicates=0, output=0,
                               bloom_positives=0, bloom_false_positives=0, exact_checks=0,
                               cms_candidates=0, cms_false_candidates=0, inferred_purchases=0,
                               synthetic_events=0, snapshots=0)
        self.trace = []
        self.stage_counts = Counter({str(i): 0 for i in range(10)})
        self.last_processed = None
        self.elapsed_s = 0.0
        self._closed = False

    @staticmethod
    def _priority(event):
        if event.get("is_critical_alert"):
            return 0
        if event["event_type"] == "purchase":
            return {"express": 1, "standard": 2, "scheduled": 3}.get(event.get("shipping_priority"), 2)
        return {"cart": 4, "view": 5}[event["event_type"]]

    def _batch(self, events):
        result = preprocess_batch(events)
        self.metrics.update(valid=result["valid"], invalid=result["invalid"], duplicates=result["duplicates"])
        self.stage_counts["1"] += result["received"]
        heap = [(self._priority(e), i, e) for i, e in enumerate(result["events"])]
        heapq.heapify(heap)
        updates, interactions = {}, Counter()
        accepted = 0
        while heap:
            priority, _, event = heapq.heappop(heap)
            self.stage_counts["2"] += 1
            key = event.get("_dedup_key") or ("event-id:"+str(event["event_id"])).encode()
            positive = self.bloom.contains(key)
            if positive:
                self.metrics["bloom_positives"] += 1
                self.metrics["exact_checks"] += 1
                if self.db.execute("SELECT 1 FROM seen WHERE digest=?", (key,)).fetchone():
                    self.metrics["duplicates"] += 1
                    continue
                self.metrics["bloom_false_positives"] += 1
            self.db.execute("INSERT INTO seen VALUES (?)", (key,))
            self.bloom.add(key)
            accepted += 1
            pid, uid = event["product_id"], event["user_id"]
            timestamp = event["event_timestamp"].astimezone(timezone.utc).isoformat()
            old = updates.get(pid)
            if old is None:
                old = [event["category_code"], event["brand"], event["price"], timestamp,
                       event["event_id"], 0, 0, 0]
                updates[pid] = old
            elif (timestamp, event["event_id"]) > (old[3], old[4]):
                old[:5] = [event["category_code"], event["brand"], event["price"], timestamp, event["event_id"]]
            old[5+{"view": 0, "cart": 1, "purchase": 2}[event["event_type"]]] += 1
            interactions[(uid, pid)] += WEIGHTS[event["event_type"]]
            self.stage_counts["3"] += 1
            self.stage_counts["6"] += 1
            if event.get("is_synthetic"):
                self.metrics["synthetic_events"] += 1
            alert = None
            if event["event_type"] == "purchase":
                self.metrics["sales_cents"] += round(event["price"] * 100)
                hour = event["event_timestamp"].astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat()
                cms_key = f"{hour}|{uid}"
                self.cms.update(cms_key)
                self.db.execute("INSERT INTO frequencies VALUES (?,?,1) ON CONFLICT(window,uid) DO UPDATE SET frequency=frequency+1", (hour, uid))
                estimated = self.cms.estimate(cms_key)
                if estimated >= self.threshold:
                    self.metrics["cms_candidates"] += 1
                    exact = self.db.execute("SELECT frequency FROM frequencies WHERE window=? AND uid=?", (hour, uid)).fetchone()[0]
                    if exact < self.threshold:
                        self.metrics["cms_false_candidates"] += 1
                    elif exact == self.threshold:
                        self.db.execute("INSERT OR IGNORE INTO alerts VALUES (?,?,?,?,?)", (hour, uid, event["event_id"], estimated, exact))
                        alert = {"user_id": uid, "window": hour, "exact": exact, "estimated": estimated}
                order = event.get("order_id")
                if order is None:
                    session = event.get("user_session", "unknown")
                    order = f"inferred-session-hour:{session if session != 'unknown' else uid}:{hour}"
                    self.metrics["inferred_purchases"] += 1
                elif event.get("order_is_inferred"):
                    self.metrics["inferred_purchases"] += 1
                self.db.execute("INSERT OR IGNORE INTO order_items VALUES (?,?)", (order, pid))
            if len(self.trace) < 16:
                self.trace.append({"event_id": event["event_id"], "product_id": pid,
                                   "priority": priority, "type": event["event_type"],
                                   "bloom_positive": positive, "alert": alert,
                                   "completed_stages": [0, 1, 2, 3, 6]})
            self.last_processed = {"event_id": event["event_id"], "product_id": pid}
        self.db.executemany("""INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?)
          ON CONFLICT(pid) DO UPDATE SET
          category=CASE WHEN (excluded.timestamp,excluded.event_id)>(products.timestamp,products.event_id) THEN excluded.category ELSE products.category END,
          brand=CASE WHEN (excluded.timestamp,excluded.event_id)>(products.timestamp,products.event_id) THEN excluded.brand ELSE products.brand END,
          price=CASE WHEN (excluded.timestamp,excluded.event_id)>(products.timestamp,products.event_id) THEN excluded.price ELSE products.price END,
          timestamp=MAX(products.timestamp,excluded.timestamp),
          event_id=CASE WHEN (excluded.timestamp,excluded.event_id)>(products.timestamp,products.event_id) THEN excluded.event_id ELSE products.event_id END,
          views=views+excluded.views, carts=carts+excluded.carts, purchases=purchases+excluded.purchases
        """, ((pid, *values) for pid, values in updates.items()))
        self.db.executemany("INSERT INTO interactions VALUES (?,?,?) ON CONFLICT(uid,pid) DO UPDATE SET weight=weight+excluded.weight",
                            ((uid, pid, w) for (uid, pid), w in interactions.items()))
        self.db.commit()
        self.metrics["output"] += accepted

    def run(self, events, snapshot_every=0, progress=None):
        start = time.perf_counter()
        fifo = EventBufferFIFO()
        last_snapshot = 0
        for event in events:
            fifo.enqueue(event)
            self.metrics["received"] += 1
            self.stage_counts["0"] += 1
            if len(fifo) >= self.batch_size:
                batch = [fifo.dequeue() for _ in range(len(fifo))]
                self._batch(batch)
                if snapshot_every and self.metrics["received"]-last_snapshot >= snapshot_every:
                    self.refresh()
                    last_snapshot = self.metrics["received"]
                if progress and self.metrics["received"] % 100000 == 0:
                    progress(dict(self.metrics), time.perf_counter()-start)
        if len(fifo):
            self._batch([fifo.dequeue() for _ in range(len(fifo))])
        self.refresh()
        self.elapsed_s += time.perf_counter()-start
        return self

    def refresh(self):
        rows = self.db.execute("SELECT * FROM products ORDER BY pid").fetchall()
        self.catalog = {r[0]: {"product_id": r[0], "category": r[1], "brand": r[2],
                             "price": r[3], "views": r[6], "carts": r[7], "purchases": r[8]} for r in rows}
        synthetic = self.metrics["output"] > 0 and self.metrics["synthetic_events"] == self.metrics["output"]
        for product in self.catalog.values():
            product["stock"] = max(0, 100-product["purchases"]) if synthetic else None
            product["stock_source"] = "simulated_initial_stock_100" if synthetic else "not_provided"
        self.cache = LRUCache(256)
        ids = np.array(list(self.catalog), dtype=np.int64)
        if self.bptree is not None:
            self.bptree.close()
        self.bptree = DiskBPlusTree(self.workdir / f"prices_{self.metrics['snapshots']}.bpt", cache_pages=32)
        self.trie = CatalogTrie()
        tokens = {}
        for pid, p in self.catalog.items():
            self.bptree.insert(round(p["price"]*100), pid)
            self.trie.add(str(pid)); self.trie.add(p["brand"]); self.trie.add(p["category"])
            tokens[pid] = {"brand:"+p["brand"], "category:"+p["category"],
                           "price_bin:"+str(int(np.log1p(p["price"])*2))}
        self.bptree.flush()
        self.stage_counts["4"] = len(rows)
        if len(rows):
            # Current price is an explicit, bounded-state alternative to historical median.
            X = np.log1p(np.array([[r[3], r[6], r[7], r[8]] for r in rows], dtype=float))
            self.kdtree = ProductKDTree().fit(ids, X)
            self.ann = IVFFlat(nlist=32, nprobe=self.nprobe, seed=self.seed).fit(ids, self.kdtree.X_scaled)
            self.lsh = MinHashLSH(num_perm=32, bands=8, seed=self.seed).fit(tokens)
        else:
            self.kdtree = self.ann = self.lsh = None
        self.stage_counts["5"] = self.stage_counts["7"] = len(rows)
        # Compact typed arrays, rather than a dictionary per user-product pair.
        triples = np.fromiter(self.db.execute("SELECT uid,pid,weight FROM interactions"),
                              dtype=np.dtype([("uid", "i8"), ("pid", "i8"), ("w", "i8")]))
        users = np.unique(triples["uid"])
        self.csr = csr_matrix((triples["w"], (np.searchsorted(users, triples["uid"]),
                               np.searchsorted(ids, triples["pid"]))), shape=(len(users), len(ids)))
        self.popularity = dict(zip(ids.tolist(), np.asarray(self.csr.sum(axis=0)).ravel().tolist()))
        self.graph = nx.Graph()
        self.graph.add_nodes_from(r[0] for r in self.db.execute("SELECT DISTINCT pid FROM order_items"))
        for a, b, w in self.db.execute("""SELECT a.pid,b.pid,COUNT(*) FROM order_items a JOIN order_items b
                       ON a.order_id=b.order_id AND a.pid<b.pid GROUP BY a.pid,b.pid"""):
            self.graph.add_edge(a, b, weight=w)
        self.graph_analysis = analyze_graph(self.graph, self.seed, self.graph_stability_runs)
        self.stage_counts["8"] = self.db.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
        self.metrics["snapshots"] += 1
        # Materialize service responses from actual indices and graph.
        for trace in self.trace:
            trace["completed_stages"] = list(range(10))
            pid = trace["product_id"]
            trace["snapshot"] = {"price_index_contains_product": pid in self.bptree.search(round(self.catalog[pid]["price"]*100)),
                                 "ann_neighbors": self.ann.query(pid, min(3, len(ids)-1)) if len(ids)>1 else [],
                                 "community": self.graph_analysis["communities"].get(pid),
                                 "graph_member": pid in self.graph,
                                 "graph_action": "purchase_updates_order" if trace["type"]=="purchase" else "queries_product_influence"}
        self.stage_counts["9"] = len(self.catalog)

    def product(self, product_id):
        pid = int(product_id)
        cached = self.cache.get(pid)
        if cached is None and pid in self.catalog:
            cached = dict(self.catalog[pid]); self.cache.put(pid, cached)
        return cached

    def recommend(self, product_id, k=5):
        pid = int(product_id)
        if pid not in self.catalog:
            raise KeyError(pid)
        n = min(max(1, k), max(1, len(self.catalog)-1))
        ann = self.ann.query(pid, n) if len(self.catalog)>1 else []
        sets = self.lsh.query(pid, n)
        complement = sorted(self.graph[pid].items(), key=lambda x: (-x[1]["weight"], x[0]))[:n] if pid in self.graph else []
        rank = self.graph_analysis["pagerank"]
        scores, reasons = defaultdict(float), defaultdict(list)
        for row in ann:
            scores[row["product_id"]] += 1/(1+row["distance"]); reasons[row["product_id"]].append("IVF")
        for row in sets:
            scores[row["product_id"]] += row["jaccard"]; reasons[row["product_id"]].append("Jaccard")
        for other, edge in complement:
            scores[other] += np.log1p(edge["weight"]); reasons[other].append("co-compra")
        # Every candidate consumes the graph influence stage, including isolates.
        for other in scores:
            scores[other] += rank.get(other, 0)
            scores[other] += 0.01 * np.log1p(self.popularity.get(other, 0))
        ids = heapq.nlargest(k, scores, key=lambda p: (scores[p], -p))
        return {"product": self.product(pid), "recommendations": [
            {**self.product(p), "score": float(scores[p]), "reasons": reasons[p],
             "pagerank": rank.get(p, 0), "community": self.graph_analysis["communities"].get(p)} for p in ids],
                "ann": ann, "set_similarity": sets,
                "exact_knn": self.kdtree.query(pid, n, "brute") if len(self.catalog)>1 else [],
                "graph_degree": self.graph_analysis["degree"].get(pid, 0)}

    def summary(self):
        return {"metrics": dict(self.metrics), "stage_counts": dict(self.stage_counts), "stages": STAGES,
                "products": len(self.catalog), "users": self.csr.shape[0], "csr_nnz": self.csr.nnz,
                "csr_weight_sum": int(self.csr.sum()), "elapsed_s": self.elapsed_s,
                "throughput": self.metrics["received"]/self.elapsed_s if self.elapsed_s else 0,
                "observed_sales": self.metrics["sales_cents"]/100,
                "alerts_count": self.db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
                "alerts": [{"window": r[0], "user_id": r[1], "event_id": r[2], "estimated": r[3], "exact": r[4]} for r in self.db.execute("SELECT * FROM alerts LIMIT 100")],
                "graph": dict(self.graph_analysis), "trace": self.trace,
                "bptree": {"pages": self.bptree.next_page-1, "page_reads": self.bptree.page_reads,
                           "page_writes": self.bptree.page_writes, "cache_pages": self.bptree.cache_pages},
                "configuration": {"seed": self.seed, "batch_size": self.batch_size, "threshold": self.threshold,
                                  "cms_epsilon": self.cms.epsilon, "cms_delta": self.cms.delta,
                                  "cms_total_purchases": self.cms.total_updates,
                                  "cms_error_bound": self.cms.theoretical_error_bound(),
                                  "window": "calendar-hour UTC in key; whole-run sketch",
                                  "price_feature": "latest observed price", "order_proxy": "session and UTC hour for REES46"}}

    def export(self, output):
        output = Path(output); output.mkdir(parents=True, exist_ok=True)
        (output/"pipeline_summary.json").write_text(json.dumps(self.summary(), ensure_ascii=False, indent=2), encoding="utf-8")
        (output/"catalog.json").write_text(json.dumps(list(self.catalog.values()), ensure_ascii=False), encoding="utf-8")
        sample = list(self.catalog)[:min(100, len(self.catalog))]
        (output/"recommendations.json").write_text(json.dumps({p: self.recommend(p) for p in sample}, ensure_ascii=False), encoding="utf-8")
        return output

    def close(self):
        if not self._closed:
            if self.bptree:
                self.bptree.close()
            self.db.close(); self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
