# Code

| File | Chức năng |
|---|---|
| `day6_connection.py` | Query embedding và kết nối chỉ đọc với pgvector Day 6 |
| `retrieval.py` | TF-IDF, filter metadata, hybrid RRF và chọn context |
| `retrieval_metrics.py` | Chấm retrieval và context chuẩn bị sau truy xuất |
| `retriever_service.py` | Giao diện retrieval dùng trong vòng lặp agent |
| `deepseek_client.py` | API DeepSeek, usage, giới hạn chi phí và xử lý lỗi |
| `agent.py` | Native tool calling, chọn context, trả lời/citation và từ chối |
| `evaluation.py` | Chấm sau khi agent kết thúc, kiểm tra nhãn và tổng hợp metric |
| `web_app.py` | Backend web local, key ở máy chủ, hỏi tài liệu và mở nguồn |
| `context_retriever.py` | Evidence group từ chunk lân cận cùng trang/mục |
| `document_store.py` | E5 vector store local, hybrid và anchor từ câu hỏi |
| `advanced_agent.py` | Nhiều native search call, một context và phục hồi citation có giới hạn |
| `vision_client.py` | Ảnh PDF gốc của trang đã truy xuất gửi DeepSeek Flash, có hash ảnh |

Chạy so sánh dev theo [hướng dẫn retrieval](../docs/CHAY_RETRIEVAL.md).
Chạy agent thật theo [hướng dẫn DeepSeek](../docs/CHAY_AGENT.md), cần key trong
`.env`. Kết quả API chỉ có sau lần chạy thật; unit test không thay benchmark.
Nghiên cứu hoàn chỉnh theo [quy trình dev/test](../docs/THU_NGHIEM.md),
giao diện theo [hướng dẫn web](../docs/CHAY_WEB.md).
