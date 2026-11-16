"""Đọc kho pgvector Day 6 bằng embedding đã chốt; không ghi dữ liệu."""
import hashlib
import importlib.util
import json
import math
import os
import time

from .retrieval import validate_filters


class Day6Connection:
    def __init__(self, source, chunks, imported_manifest):
        import psycopg
        from dotenv import dotenv_values
        from psycopg.rows import dict_row

        self.connection = None
        self.chunks = {chunk["id"]: chunk for chunk in chunks}
        self.strategy = imported_manifest["source_strategy"]
        config = json.loads((source / "starter/embedding.json").read_text(encoding="utf-8"))
        imported_config = {key: value for key, value in imported_manifest["embedding"].items()
                           if key != "model_signature"}
        if config != imported_config:
            raise ValueError("Cấu hình embedding khác bản dữ liệu đã chuyển.")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        module_path = source / "starter/src/embeddings.py"
        spec = importlib.util.spec_from_file_location("day6_local_embeddings", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        started = time.perf_counter()
        self.embedder = module.MyEmbedder(**{key: config[key] for key in
                                           ("model_name", "revision", "device", "batch_size",
                                            "document_prefix", "query_prefix", "dimensions")})
        self.model_load_seconds = time.perf_counter() - started
        if self.embedder.signature != imported_manifest["embedding"]["model_signature"]:
            raise ValueError("Model hoặc thư viện embedding khác lần tạo vector Day 6.")
        dsn = dotenv_values(source / "starter/.env").get("DATABASE_URL")
        if not dsn:
            raise ValueError("Thiếu DATABASE_URL trong cấu hình local Day 6.")
        self.connection = psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5,
                                          options="-c default_transaction_read_only=on", autocommit=True)
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SHOW transaction_read_only")
                read_only = cursor.fetchone()["transaction_read_only"]
                if read_only != "on":
                    raise ValueError("Kết nối benchmark phải ở chế độ chỉ đọc.")
                cursor.execute("SHOW server_version")
                server_version = cursor.fetchone()["server_version"]
                cursor.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
                extension = cursor.fetchone()
                if not extension:
                    raise ValueError("Database chưa bật pgvector.")
                cursor.execute("SELECT model_signature, dimensions FROM lab_vector_spaces WHERE strategy=%s",
                               (self.strategy,))
                space = cursor.fetchone()
                if not space or (space["model_signature"], space["dimensions"]) != (
                        self.embedder.signature, self.embedder.dimensions):
                    raise ValueError("Vector store không cùng không gian embedding với query.")
                cursor.execute("""SELECT chunk_id,document_id,source,page,text,metadata,
                                  vector_dims(embedding) AS dimensions
                                  FROM lab_chunks WHERE strategy=%s""", (self.strategy,))
                rows = cursor.fetchall()
            if len(rows) != len(chunks) or {row["chunk_id"] for row in rows} != set(self.chunks):
                raise ValueError("ID hoặc số chunk trong database khác corpus benchmark.")
            for row in rows:
                canonical = {"id": row["chunk_id"], "source_id": row["document_id"],
                             **{key: row[key] for key in ("source", "page", "text", "metadata")}}
                if canonical != self.chunks[row["chunk_id"]] or row["dimensions"] != self.embedder.dimensions:
                    raise ValueError("Nội dung, metadata hoặc số chiều database không khớp dữ liệu Day 7.")
            self.provenance = {
                "source_repository": source.name, "strategy": self.strategy,
                "database": {"engine": "PostgreSQL", "version": server_version,
                             "pgvector_version": extension["extversion"],
                             "host": self.connection.info.host, "port": self.connection.info.port,
                             "database": self.connection.info.dbname, "table": "lab_chunks",
                             "read_only": True, "chunks_verified": len(rows), "search": "cosine_exact"},
                "embedding": {**self.embedder.info, "model_signature": self.embedder.signature},
                "embedding_code_sha256": hashlib.sha256(module_path.read_bytes()).hexdigest(),
                "model_load_seconds": self.model_load_seconds, "paid_api_calls": 0,
            }
        except Exception:
            self.close()
            raise

    def embed_query(self, question):
        return self.embedder.embed_query(question)

    def search_vector(self, vector, *, filters, top_k):
        from psycopg.types.json import Jsonb

        validate_filters(filters)
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k phải là số nguyên dương.")
        if len(vector) != self.embedder.dimensions or not all(math.isfinite(v) for v in vector) or not any(vector):
            raise ValueError("Query vector không hợp lệ hoặc sai số chiều.")
        encoded = json.dumps(vector, allow_nan=False)
        with self.connection.cursor() as cursor:
            cursor.execute("""SELECT chunk_id, embedding <=> %s::vector AS distance
                              FROM lab_chunks WHERE strategy=%s AND metadata @> %s
                              ORDER BY distance,chunk_id LIMIT %s""",
                           (encoded, self.strategy, Jsonb(filters), top_k))
            rows = cursor.fetchall()
        return [{**self.chunks[row["chunk_id"]], "score": 1.0 - row["distance"], "strategy": "dense"}
                for row in rows]

    def close(self):
        if self.connection is not None:
            self.connection.close()
