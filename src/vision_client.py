"""Bổ sung ảnh PDF gốc từ trang đã truy xuất; không dùng vùng/trang gold."""
import base64
import copy
import hashlib
import json
from pathlib import Path

from .deepseek_client import DeepSeekClient


class VisionClient(DeepSeekClient):
    def __init__(self,config,key,chunks,directory):
        super().__init__(config,key)
        self.lookup={c["id"]:c for c in chunks}
        self.directory=directory

    def complete(self,messages,tools,tool_choice):
        enriched=copy.deepcopy(messages);images=[]
        for message in reversed(enriched):
            if message["role"]!="tool" or not isinstance(message["content"],str):continue
            payload=json.loads(message["content"])
            if "context_ids" not in payload:continue
            pages=list(dict.fromkeys(self.lookup[i]["page"] for i in payload["context_ids"]))[:3]
            blocks=[{"type":"text","text":message["content"]}]
            import fitz
            pdf=self.directory/"raw/nasa-systems-engineering-handbook-2016.pdf"
            with fitz.open(pdf) as doc:
                for page in pages:
                    data=doc[page-1].get_pixmap(matrix=fitz.Matrix(1.4,1.4)).tobytes("jpg",jpg_quality=78)
                    blocks.extend([{"type":"text","text":f"Ảnh gốc PDF trang {page}; chỉ cite ID của cùng trang trong context, kiểm tra hình và đơn vị trực tiếp."},
                                   {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+base64.b64encode(data).decode(),"detail":"high"}}])
                    images.append({"page":page,"sha256":hashlib.sha256(data).hexdigest(),"format":"jpeg",
                                   "selection":"first distinct pages in retrieved context, no gold", "render_scale":1.4,"jpeg_quality":78})
            message["content"]=blocks
            break
        result=super().complete(enriched,tools,tool_choice)
        result["image_inputs"]=images
        return result
