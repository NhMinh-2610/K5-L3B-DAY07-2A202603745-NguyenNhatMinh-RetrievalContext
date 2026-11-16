# Thí nghiệm dev và test

Trang này mô tả nghiên cứu đợt một đã giữ nguyên. Phiên bản cải thiện và bonus
ở [BONUS.md](BONUS.md), có test mới và thư mục kết quả riêng.

Kết quả chính nằm ở [results/study](../results/study/README.md).
Ba cấu hình dev và hai cấu hình test đã chạy API thật; không cần gọi lại để xem.

## Đọc và kiểm tra kết quả

```powershell
$labPython = "$env:USERPROFILE\.venvs\day06-dataingestion\Scripts\python.exe"
& $labPython -B -X utf8 scripts/summarize_study.py
& $labPython -B -X utf8 scripts/export_results.py
& $labPython -B -X utf8 -m unittest discover -s tests -v
```

Lệnh tổng hợp chỉ đọc kết quả có sẵn, kiểm tra hash đã chốt, áp bản rà nguồn
lên một bản sao nhãn rồi tạo CSV và bảng test sau rà; không gọi API. Nhãn API
gốc trong `reviews.json` và `test_comparison.json` được giữ nguyên.
`export_results.py` tạo `traces.public.json`, `reviews.public.json` và manifest
`results/exports.json`; giữ query, tool/argument, kết quả, context, đáp án,
citation, model/usage và nhãn. Không xuất messages, request/response thô hoặc
hội thoại trợ lý. File thô và các lần hỏi web thủ công chỉ lưu local, được ignore.

Bản tải từ Git dùng các file `.public.json` để tổng hợp khi không có file thô;
script kiểm tra hash bản xuất theo manifest, không gọi API. Hash file gốc trong
manifest là dấu đối chiếu của lần chạy local, không thay thế việc có file gốc.

## Quy trình tạo nghiên cứu từ đầu

Sau khi có dữ liệu Day 6, benchmark đã rà nguồn và key theo [CHAY_AGENT.md](CHAY_AGENT.md),
lệnh dùng trong lần nghiên cứu này là:

```powershell
& $labPython -B -X utf8 scripts/complete_lab.py --phase dev --day6 "..\K5-L3B-DAY06-NguyenNhatMinh-2A202603745-DataIngestion"
& $labPython -B -X utf8 scripts/complete_lab.py --phase test --day6 "..\K5-L3B-DAY06-NguyenNhatMinh-2A202603745-DataIngestion"
```

Dev: 3 cấu hình × 17 câu, sau đó API chấm và chọn theo tiêu chí định trước.
Test: baseline và cấu hình được chọn × 7 câu; chỉ chạy sau khi hash code,
config, benchmark và dev summary khớp `selection.json`.
Embedding/SQL dùng chung qua lock; ba cấu hình được xử lý bằng ba worker,
client model/bộ chấm riêng. Tổng phí bao gồm sinh đáp án và chấm.

Trong repo hiện tại đã có test nên chạy lại `--phase dev` **chủ động bị chặn**
để không chọn lại sau khi xem test. `--phase test` cùng phiên bản dùng lại trace
đã lưu, không gọi lại những câu hoàn tất. Khi cần thí nghiệm mới, giữ nguyên
nghiên cứu này, tạo bản sao nghiên cứu/đầu ra mới và test chưa dùng nếu đã chỉnh
dựa trên kết quả test. Không xóa dấu chốt chỉ để vượt hàng rào.

## Thang điểm và phạm vi nhãn

API chấm sau khi agent đã kết thúc: đáp án/context 0–2, hỗ trợ từng citation,
từ chối. Context 2 cần đủ bằng chứng và nguồn; đáp án 2 cần đúng đủ ý.
Ngưỡng 1 là thiếu ý/điều kiện, 0 là sai/không đủ bằng chứng. Từ chối câu có đáp
án chấm 0. Câu âm tính dùng tỷ lệ từ chối riêng, không tăng điểm đáp án dương tính.

`model_proposed` là nhãn API; `source_check_proposed` là nhãn có đối chiếu nguồn
bổ sung bằng quy trình tự động. `benchmark/review.csv` ghi trạng thái nguồn của
gold ban đầu. Các nhãn thí nghiệm được lưu riêng với điểm chấm chính thức.

Kết quả lưu model/fingerprint/usage, có thể biến động khi dịch vụ đổi phiên bản
hoặc cache; temperature 0 không bảo đảm hai lần chạy giống hệt.
