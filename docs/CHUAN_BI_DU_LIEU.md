# Chuẩn bị dữ liệu Day 7

Dữ liệu kế thừa từ Day 6: chương *A General Introduction to Artificial Intelligence*,
Huawei Technologies Co., Ltd. (2023), 35 trang nội dung. Cấu hình C dùng chung
201 chunk và embedding với B, có thể lọc theo mục khi câu hỏi cung cấp phạm vi.
Nguồn: https://doi.org/10.1007/978-981-19-2879-6_1.
Giấy phép: CC BY-NC-ND 4.0; thông tin ghi nguồn được giữ trong manifest xuất.

## Chuyển dữ liệu

Chạy PowerShell tại gốc repo Day 7, với repo Day 6 đặt cùng thư mục cha:

```powershell
$labPython = "$env:USERPROFILE\.venvs\day06-dataingestion\Scripts\python.exe"
& $labPython -B -X utf8 scripts/prepare_day6.py --day6 "..\K5-L3B-DAY06-NguyenNhatMinh-2A202603745-DataIngestion"
```

Có thể dùng Python 3.11+ khác; script chỉ dùng thư viện chuẩn. Đổi `--day6`
nếu repo nguồn nằm ở vị trí khác. Lệnh không cần database, không tạo embedding
và không gọi API. Chạy lại sẽ ghi đè các file xuất, không sửa repo Day 6.

Các file được tạo tại `starter/data/day6/`:

| File | Nội dung |
|---|---|
| `chunks.json` | 201 chunk; giữ nguyên ID, text, nguồn, trang và metadata |
| `questions_dev.json` | 15 câu dev có đáp án và toàn bộ bằng chứng thay thế |
| `queries_dev.json` | Đầu vào retrieval: chỉ ID, split, câu hỏi và filter |
| `embedding.json` | Cấu hình model local `intfloat/multilingual-e5-small`, 384 chiều |
| `evidence_audit.json` | Đối chiếu bằng chứng với text nguồn và từng chunk |
| `manifest.json` | Nguồn, giấy phép, SHA-256, cấu hình và giới hạn dữ liệu |

Thư mục xuất được Git ignore theo cấu hình sẵn có. Tái tạo bằng lệnh trên,
không cần đưa text xử lý hoặc vector cache lên Git. Khi sao chép dự án, cần
cung cấp repo Day 6 và dữ liệu đầu vào tương ứng theo quyền sử dụng nguồn.

## Kiểm tra và giới hạn

Script kiểm tra dữ liệu khớp phiên bản Day 6 đã chốt, ID không trùng, số chunk
đúng và từng bằng chứng xuất hiện ở đúng nguồn/trang trong corpus. Chỉ dùng
NFKC và gộp khoảng trắng để đối chiếu; không sửa text hoặc rút ngắn bằng chứng.
Các phép đối chiếu này chưa phải benchmark retrieval hay chấm câu trả lời.

Hai câu `q02`, `q10` có bằng chứng trải qua nhiều chunk. `q08` cũng có một
bằng chứng như vậy, nhưng có đoạn thay thế nằm trọn trong một chunk khác.
Giữ nguyên các nhãn này; `starter/baseline.py` hiện yêu cầu từng bằng chứng nằm
trọn trong một chunk và không chạy trực tiếp được với toàn bộ bộ dev đã xuất.
Cách đánh giá được ghi trong `benchmark/split.json`; code hiện tại hỗ trợ
đối chiếu ranking và context riêng theo [hướng dẫn retrieval](CHAY_RETRIEVAL.md).

File chuyển từ Day 6 chỉ có 15 câu dev có đáp án. Bộ benchmark Day 7 được
bổ sung riêng: dev gồm 15 câu có đáp án + 2 câu thiếu bằng chứng, test gồm
5 + 2 câu; cách tạo và kiểm tra ở [benchmark/README.md](../benchmark/README.md).
Không dùng lỗi test Day 6 để chỉnh hệ thống rồi coi test đó là đánh giá độc lập.
Chỉ gửi nội dung trong `queries_dev.json` cho retrieval/agent; đáp án và gold
chỉ dùng để chấm sau truy xuất.

Để rà nguồn, mở `questions_dev.json`, tìm ID câu hỏi, mở PDF gốc theo số
`gold.page` tính từ trang vật lý đầu tiên, rồi đọc `gold.evidence` và đoạn
xung quanh để kiểm tra `expected_answer`. Có thể xem đường dẫn PDF và manifest
trong repo Day 6. Trạng thái xác nhận đang dùng của Day 7 nằm trong
`benchmark/review.csv`; trạng thái trong manifest chuyển dữ liệu chỉ phản ánh
lần kế thừa từ Day 6. Kết quả so khớp text không thay thế xác nhận khi đọc PDF.
