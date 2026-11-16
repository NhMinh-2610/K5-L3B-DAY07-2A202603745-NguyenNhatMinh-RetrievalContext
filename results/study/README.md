# Kết quả nghiên cứu Day 7

Ngày chạy: 16/11/2026. Dữ liệu thật Day 6, embedding local và pgvector;
DeepSeek thật để chạy agent và chấm sau khi agent kết thúc.

| Split | Cấu hình | Điểm trả lời /2 | Context ngữ nghĩa | Citation sau rà | Từ chối đúng | Lỗi | Phí sinh + chấm, USD |
|---|---|---|---|---|---|---|---|
| Dev | Dense baseline | 1,80 | 13/15 | 19/19, nhãn API | 2/2 | 0 | 0,026863 |
| Dev | Hybrid | 1,80 | 13/15 | 17/17, nhãn API | 2/2 | 0 | 0,025083 |
| Dev | Dense mở rộng | 1,80 | 13/15 | 20/20, nhãn API | 2/2 | 0 | 0,030409 |
| Test | Dense baseline | 2,00 | 5/5 | 5/5 | 2/2 | 0 | 0,011291 |
| Test | Hybrid đã chọn | 2,00 | 5/5 | **5/6** | 2/2 | 0 | 0,011046 |

Chọn hybrid trên dev vì các tiêu chí chất lượng dùng để chọn bằng nhau và tổng
phí sinh + chấm thấp hơn. Không có tăng điểm trả lời. Riêng phí sinh hybrid
cao hơn baseline; không kết luận tiết kiệm vận hành. Dev còn q02 thiếu ý và
q09 từ chối nhầm ở cả ba cấu hình. Test ít câu, nhãn cần người học rà lại.

| File/thư mục | Nội dung |
|---|---|
| `data_provenance.json` | Model, database, phiên bản và 201 chunk đã kiểm tra |
| `dev/`, `test/` | Mỗi cấu hình có `run.json`, `traces.public.json`, `reviews.public.json`, `summary.json` |
| `dev_comparison.json` | Ba cấu hình dev, nhãn API |
| `selection.json` | Cấu hình hybrid, thời điểm chốt và hash trước test |
| `test_comparison.json` | Kết quả API test gốc, không ghi đè |
| `test/source_audit.json` | 14 bản đối chiếu nguồn, lý do và thay đổi đề xuất |
| `test/*/reviews_source_checked.public.json` | Bản sao nhãn sau đối chiếu; không phải xác nhận của người học |
| `test_reviewed_comparison.json` | Test sau rà, giữ cả metric API gốc để so sánh |
| `comparison.csv` | 5 cấu hình/split; test dùng bản sau rà |
| `costs.json` | Usage/chi phí ước tính nghiên cứu và web, không phải hóa đơn |
| `../exports.json` | Hash và ánh xạ file thô local → bản xuất kết quả lên Git |

Bản `.public.json` giữ trace tool và kết quả của lab, không có messages hoặc
request/response thô. Hội thoại trợ lý, file thô và log hỏi web không commit.
File thô được giữ local; không thay đổi code hay cấu hình chốt để xuất kết quả.

Một citation hybrid test_01 chỉ là đuôi câu, nên giảm từ 6/6 API xuống 5/6 sau
rà. Baseline test_no_evidence_02 bị API gán điểm dương tính sai schema; bản rà
đưa answer/context về 0/1, không ảnh hưởng mẫu số 5 câu có đáp án. Đáp án test_03
cần rà cách dịch “low energy consumption ratio” của bản gốc. Không chỉnh agent
hay chọn lại cấu hình từ các phát hiện test.

Nhãn do API và đối chiếu có hỗ trợ tự động, chưa phải điểm do người học xác nhận.
Xem [báo cáo cá nhân](../../report/individual/2A202603745_NguyenNhatMinh.md),
[cách tổng hợp](../../docs/THU_NGHIEM.md) và bảng query gốc riêng tại
[retrieval/dev](../retrieval/dev/) để tránh trộn ranking gốc với query viết lại.
