"""Cùng một giao diện tìm kiếm cho agent: dense, TF-IDF hoặc hybrid."""
import time

from .retrieval import LexicalRetriever, reciprocal_rank_fusion


class RetrieverService:
    def __init__(self, connection, chunks, retrieval_config):
        self.connection = connection
        self.lexical = LexicalRetriever(chunks)
        self.config = retrieval_config

    def search(self, query, *, filters, top_k, method):
        if method not in ("dense", "tfidf", "hybrid"):
            raise ValueError("Phương pháp retrieval không hợp lệ.")
        started = time.perf_counter()
        embedding_ms, vector = 0.0, None
        if method != "tfidf":
            embedding_started = time.perf_counter()
            vector = self.connection.embed_query(query)
            embedding_ms = (time.perf_counter() - embedding_started) * 1000
        components = []
        if method == "dense":
            results = self.connection.search_vector(vector, filters=filters, top_k=top_k)
        elif method == "tfidf":
            results = self.lexical.search(query, filters=filters, top_k=top_k)
        else:
            candidate_k = max(top_k, self.config["hybrid_candidate_k"])
            dense = self.connection.search_vector(vector, filters=filters, top_k=candidate_k)
            tfidf = self.lexical.search(query, filters=filters, top_k=candidate_k)
            components = [{"method": "dense", "results": dense}, {"method": "tfidf", "results": tfidf}]
            results = reciprocal_rank_fusion({"dense": dense, "tfidf": tfidf},
                                             constant=self.config["rrf_constant"], top_k=top_k)
        return {"query": query, "method": method, "filter": filters, "top_k": top_k,
                "results": [{**row, "rank": rank} for rank, row in enumerate(results, 1)],
                "components": components, "embedding_ms": embedding_ms,
                "elapsed_ms": (time.perf_counter() - started) * 1000}
