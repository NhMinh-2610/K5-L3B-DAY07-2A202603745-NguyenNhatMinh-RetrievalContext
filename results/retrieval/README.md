# Kết quả retrieval trên dev

Lần chạy ngày 16/11/2026, cấu hình `config/retrieval.json`: cùng corpus 35 trang,
201 chunk, 15 câu có đáp án và 2 câu thiếu bằng chứng. Có 51 trace thực, không
có lỗi kết nối hoặc kết quả giả.

| Phương pháp | Hit@1 | Evidence Hit@3 | Context chuẩn bị đủ evidence | Median retrieval |
|---|---:|---:|---:|---:|
| Dense | 8/15 (53,3%) | 10/15 (66,7%) | 11/15 (73,3%) | 5,49 ms |
| TF-IDF | 6/15 (40,0%) | 7/15 (46,7%) | 7/15 (46,7%) | 0,43 ms |
| Hybrid RRF | 6/15 (40,0%) | 10/15 (66,7%) | 11/15 (73,3%) | 6,15 ms |

Nguồn số liệu: `dev/summary.json`, `dev/metrics.csv`, `dev/traces.jsonl` và
`dev/evaluated_dev.json`. Hai câu thiếu bằng chứng không nằm trong mẫu số
retrieval/context. So khớp tự động giữ định nghĩa một chunk cho Hit@1/Hit@3;
context được phép chứa nhiều chunk phủ đủ bằng chứng.

Thời gian retrieval chưa gồm embedding query hoặc tải model. Median embedding
là 44,56 ms/câu, dùng chung cho dense/hybrid; tải model mất 117,47 giây. Các
phương pháp chạy tuần tự một lần nên có ảnh hưởng của cache. Phí dịch vụ
0 USD, chưa tính điện và phần cứng.

Dense và hybrid cùng đạt 10/15 Evidence Hit@3, trong khi dense có Hit@1 cao hơn.
Trong lần chạy này, hybrid chưa cải thiện ranking so với dense. TF-IDF đơn giản
yếu hơn trên bộ câu hỏi tiếng Việt và tài liệu tiếng Anh. Chưa chốt cấu hình cuối:
cần thử các cấu hình cải thiện và đánh giá agent trên dev.

Context trên chỉ được chuẩn bị, chưa gửi model. Chưa đánh giá câu trả lời,
citation hoặc khả năng từ chối của agent; chưa chạy bộ test Day 7.

Kết nối kiểm tra được PostgreSQL 16.16, pgvector 0.8.7, embedding E5 384 chiều
đúng revision và chữ ký Day 6. Toàn bộ ID, text, metadata và số chiều của
201 dòng cấu hình C khớp bản dữ liệu Day 7. Database được mở ở chế độ chỉ đọc.
Trạng thái rà nguồn của benchmark là 24/24 `confirmed`.
