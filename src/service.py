"""Servicio local de consulta. HTTPServer serializa acceso al estado SQLite."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import json

ROOT = Path(__file__).resolve().parents[1]/"web"


def serve(pipeline, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, payload, content_type="application/json; charset=utf-8", status=200):
            data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers(); self.wfile.write(data)

        def do_GET(self):
            parsed = urlparse(self.path); query = parse_qs(parsed.query)
            value = lambda key, default="": query.get(key, [default])[0]
            try:
                if parsed.path == "/api/summary":
                    s = pipeline.summary()
                    s["graph"]["top_pagerank"] = sorted(s["graph"]["pagerank"].items(), key=lambda x: (-x[1], x[0]))[:15]
                    for key in ("pagerank", "degree", "communities"):
                        s["graph"].pop(key)
                    return self.send(s)
                if parsed.path == "/api/products":
                    text = value("q").casefold()
                    low, high = float(value("min", "0")), float(value("max", "100000000"))
                    ids = pipeline.bptree.range_search(round(low*100), round(high*100))
                    items = [pipeline.product(p) for p in ids]
                    items = [p for p in items if text in f"{p['product_id']} {p['brand']} {p['category']}".casefold()]
                    items.sort(key=lambda p: (-p["purchases"], p["product_id"]))
                    return self.send({"total": len(items), "products": items[:100]})
                if parsed.path == "/api/autocomplete":
                    return self.send(pipeline.trie.complete(value("q")))
                if parsed.path == "/api/recommend":
                    return self.send(pipeline.recommend(int(value("product_id")), min(20, max(1, int(value("k", "5"))))))
                if parsed.path == "/api/graph":
                    graph = pipeline.graph
                    nodes = sorted(graph, key=lambda n: (-graph.degree(n, weight="weight"), n))[:100]
                    subset = graph.subgraph(nodes)
                    return self.send({"nodes": [{"id": n, "community": pipeline.graph_analysis["communities"].get(n, 0),
                                                "pagerank": pipeline.graph_analysis["pagerank"].get(n, 0)} for n in nodes],
                                      "edges": [{"source": a, "target": b, "weight": d["weight"]} for a,b,d in subset.edges(data=True)],
                                      "sampled": len(graph)>len(nodes), "total_nodes": len(graph)})
                filename = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}.get(parsed.path)
                if filename:
                    mime = {"index.html": "text/html", "app.js": "text/javascript", "style.css": "text/css"}[filename]
                    return self.send((ROOT/filename).read_bytes(), mime+"; charset=utf-8")
                self.send({"error": "Recurso inexistente"}, status=404)
            except (ValueError, KeyError, TypeError, OverflowError) as exc:
                self.send({"error": str(exc)}, status=400)
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"Panel disponible en http://127.0.0.1:{port} (Ctrl+C para finalizar)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
