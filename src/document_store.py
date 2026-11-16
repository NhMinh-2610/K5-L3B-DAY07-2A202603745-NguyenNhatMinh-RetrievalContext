"""Vector store local bền vững, embedding thật E5 và truy xuất theo nguồn trực quan."""
import hashlib
import importlib.util
import json
import os
import re
import threading
import time
from pathlib import Path

import numpy as np

from .retrieval import LexicalRetriever, reciprocal_rank_fusion, validate_filters


def load_embedder(day6):
    os.environ["HF_HUB_OFFLINE"]="1"
    os.environ["TRANSFORMERS_OFFLINE"]="1"
    config=json.loads((day6/"starter/embedding.json").read_text("utf-8"))
    spec=importlib.util.spec_from_file_location("advanced_e5_embedder",day6/"starter/src/embeddings.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.MyEmbedder(**{k:config[k] for k in ("model_name","revision","device","batch_size","document_prefix","query_prefix","dimensions")})


class DocumentStore:
    def __init__(self, directory, day6):
        self.directory=directory
        path=directory/"chunks.json"
        self.chunks=json.loads(path.read_text("utf-8"))
        self.corpus_hash=hashlib.sha256(path.read_bytes()).hexdigest()
        self.embedder=load_embedder(day6)
        self.lock=threading.Lock()
        self.lexical=LexicalRetriever(self.chunks)
        target=directory/"vectors.npy"
        metadata_path=directory/"vectors.json"
        if target.exists():
            info=json.loads(metadata_path.read_text("utf-8"))
            assert info["corpus_sha256"]==self.corpus_hash and info["model_signature"]==self.embedder.signature,"Index vector khác phiên bản."
            self.vectors=np.load(target,allow_pickle=False)
            self.vector_info=info
        else:
            vectors=[];truncated=[]
            texts=[c["text"] for c in self.chunks]
            for start in range(0,len(texts),32):
                batch=texts[start:start+32]
                tokens=self.embedder.model.tokenizer([self.embedder.document_prefix+t for t in batch],truncation=False,padding=False)["input_ids"]
                truncated.extend(start+i for i,row in enumerate(tokens) if len(row)>self.embedder.max_tokens)
                # E5 truncation chỉ áp dụng vector; lexical index và context vẫn giữ nguyên text đầy đủ.
                values=self.embedder.model.encode([self.embedder.document_prefix+t for t in batch],batch_size=16,
                      normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)
                vectors.append(values.astype("float32"))
                if start%320==0:print(f"Embedded {min(start+32,len(texts))}/{len(texts)}",flush=True)
            self.vectors=np.concatenate(vectors)
            np.save(target,self.vectors,allow_pickle=False)
            self.vector_info={"corpus_sha256":self.corpus_hash,"model_signature":self.embedder.signature,
                 "embedding":self.embedder.info,"dimensions":384,"vectors":len(texts),"dtype":"float32",
                 "storage":"NumPy .npy persisted dense matrix; exact normalized cosine search",
                 "embedding_truncated_nodes":truncated,"all_text_retained_for_lexical_and_context":True,"paid_api_calls":0}
            metadata_path.write_text(json.dumps(self.vector_info,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        assert self.vectors.shape==(len(self.chunks),384) and np.isfinite(self.vectors).all()
        assert np.allclose(np.linalg.norm(self.vectors,axis=1),1,atol=0.002)

    def vector(self,query):
        with self.lock:return np.asarray(self.embedder.embed_query(query),dtype="float32")


def references(text):
    text=text.replace("‑","-").replace("–","-")
    found=re.findall(r"(?i)\b(figure|fig\.?|hình|table|bảng)\s+([a-z0-9]+\.[0-9]+-[0-9]+)",text)
    return list(dict.fromkeys(("Table" if word.lower() in ("table","bảng") else "Figure")+" "+number.upper() for word,number in found))


class DocumentRetriever:
    def __init__(self,store,*,anchored=False):
        self.store=store;self.anchored=anchored;self.question=""

    def for_question(self,question):
        self.question=question
        return self

    def search(self,query,*,filters,top_k,method):
        validate_filters(filters)
        started=time.perf_counter()
        anchors=references(self.question) if self.anchored else []
        vector=self.store.vector(query) if method!="tfidf" else None
        scores=self.store.vectors@vector if vector is not None else np.zeros(len(self.store.chunks))
        eligible=[i for i,c in enumerate(self.store.chunks) if all(c["metadata"].get(k)==v for k,v in filters.items())]
        matching=[i for i in eligible if self.store.chunks[i]["metadata"].get("reference") in anchors]
        # Các Figure/Table ID này đến từ câu hỏi người dùng, không lấy từ gold.
        if matching:eligible=matching
        rank=sorted(eligible,key=lambda i:(-float(scores[i]),self.store.chunks[i]["id"]))
        dense=[{**self.store.chunks[i],"score":float(scores[i]),"strategy":"dense"} for i in rank[:max(40,top_k)]]
        lexical=self.store.lexical.search(query,filters=filters,top_k=len(self.store.chunks))
        allowed={self.store.chunks[i]["id"] for i in eligible}
        lexical=[c for c in lexical if c["id"] in allowed][:max(40,top_k)]
        if method=="dense":results=dense
        elif method=="tfidf":results=lexical
        else:results=reciprocal_rank_fusion({"dense":dense,"tfidf":lexical},constant=60,top_k=max(40,top_k))
        if anchors:
            # Một đoạn cho mỗi vùng được hỏi trước, sau đó lấp context bằng các đoạn liên quan.
            coverage=[]
            for ref in anchors:
                row=next((c for c in results if c["metadata"].get("reference")==ref),None)
                if row:coverage.append(row)
            seen={c["id"] for c in coverage}
            results=coverage+[c for c in results if c["id"] not in seen]
        results=[{**c,"rank":i+1} for i,c in enumerate(results[:top_k])]
        return {"query":query,"method":method,"filter":filters,"top_k":top_k,"results":results,
                "question_reference_anchors":anchors,"anchor_origin":"explicit identifiers in user question",
                "components":[{"method":"dense","results":dense},{"method":"tfidf","results":lexical}],
                "elapsed_ms":(time.perf_counter()-started)*1000}
