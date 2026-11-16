# Chạy agent DeepSeek

`run_agent.py` là baseline đối chứng. Web mặc định dùng cấu hình lân cận đã
chốt trên dev v2; chạy lại phần cải thiện/bonus theo [BONUS.md](BONUS.md).

Agent dùng DeepSeek để chọn query, gọi retrieval và quyết định trả lời có nguồn
hoặc từ chối. Embedding và database vẫn dùng Day 6. Bộ test chỉ dành cho lần
đánh giá sau khi chốt cấu hình; các lệnh dưới đây chỉ chạy dev.

Kết quả chính thức sau sửa điều kiện dừng nằm ở `results/study/`; xem
[nghiên cứu dev/test](THU_NGHIEM.md). Các thư mục `results/agent/` giữ lịch sử
smoke/baseline cũ. Khi chạy thử thêm, dùng `--output` khác để giữ lịch sử.

## 1. Điền API key

File `.env` ở gốc Day 7 đã có sẵn dòng:

```dotenv
DEEPSEEK_API_KEY=
```

Tạo key tại [DeepSeek API Keys](https://platform.deepseek.com/api_keys), điền
key sau dấu `=` rồi lưu. File `.env` được Git ignore; `.env.example` chỉ là
mẫu trống để tái tạo cấu hình. Không đưa key vào mã nguồn, báo cáo hoặc trace.
Cấu hình kết nối database vẫn đọc từ `starter/.env` của Day 6.

## 2. Chạy thử hai câu

Mở Docker Desktop; nếu database đang dừng, chạy:

```powershell
docker start day6_student_starter-postgres-1
```

Mở PowerShell tại gốc repo Day 7, chạy từng lệnh:

```powershell
$labPython = "$env:USERPROFILE\.venvs\day06-dataingestion\Scripts\python.exe"
& $labPython -B -X utf8 scripts/run_agent.py --check-config
& $labPython -B -X utf8 scripts/run_agent.py --day6 "..\K5-L3B-DAY06-NguyenNhatMinh-2A202603745-DataIngestion" --query-id q01 dev_no_evidence_01 --output results/agent/manual-smoke
```

`--check-config` chỉ kiểm tra cấu hình và có key, chưa xác minh key với dịch vụ.
Lệnh tiếp theo gọi API thật cho một câu có đáp án và một câu thiếu bằng chứng.
Kết quả ở `results/agent/manual-smoke/`. Chạy lại ghi đè file cùng tên.

## 3. Chạy toàn bộ dev

Sau khi chạy thử thành công:

```powershell
& $labPython -B -X utf8 scripts/run_agent.py --day6 "..\K5-L3B-DAY06-NguyenNhatMinh-2A202603745-DataIngestion" --all-dev --output results/agent/manual-dev
```

Lệnh chạy 17 câu, lưu ở `results/agent/manual-dev/`; không chọn lại cấu hình
trên nghiên cứu đã xem test.

| File | Nội dung |
|---|---|
| `traces.jsonl` | Ghi từng câu ngay khi hoàn tất, kể cả lỗi |
| `traces.json` | Request/response model, tool call, query, filter, kết quả, context thực gửi, câu trả lời và citation |
| `summary.json` | Model/cấu hình, phiên bản, token/chi phí, số lượt tool, trạng thái và context evidence |
| `reviews_template.json` | Nhãn chấm câu trả lời/citation/từ chối để trống, chưa phải điểm đã xác nhận |

Console báo `answered`, `abstain` hoặc `error`. Cần đọc `summary.json` để biết
lần chạy đủ toàn bộ câu hay chỉ hoàn tất một phần. Lỗi key, số dư hoặc mạng
được báo riêng, không thay bằng câu trả lời giả và không tự retry API.

## Cấu hình và đánh giá

Baseline ở `config/agent.json`: `deepseek-flash`, tắt thinking, dense retrieval,
top-3, tối đa 3 lượt tìm và 5 lượt model/câu, context 3.000 ký tự, output tối đa
800 token/lượt. Đây là lựa chọn thử nghiệm, không phải giới hạn bắt buộc của đề.
DeepSeek hỗ trợ giao diện OpenAI và native function calling; cấu hình đã đối chiếu
với [tài liệu API](https://api-docs.deepseek.com/guides/tool_calls/).

Model có thể viết lại query để tìm thêm bằng chứng, nhưng filter luôn giữ theo
đầu vào. Context ưu tiên lượt tìm gần nhất, loại ID trùng và chỉ giữ chunk nguyên
vẹn trong budget; context cũ không được gửi lặp ngoài budget. Nội dung tài liệu
được đặt trong phản hồi tool, không được xem là chỉ dẫn hệ thống.

Khi hết lượt tìm hoặc đến lượt model cuối, request chỉ khai báo `finish_response`
và chỉ định gọi đúng tool này. Model chọn trả lời có citation hoặc từ chối theo
context hiện có. Số lượt tìm không tăng thêm; tool ngoài danh sách và citation
không hợp lệ vẫn được báo lỗi. Các lần chạy lại nên dùng `--output` riêng để giữ
nguyên kết quả trước thay đổi.

Mọi câu đều phải tìm trước. Câu trả lời chỉ được chấp nhận khi citation ID có
trong context thực gửi và khớp citation trong nội dung trả lời. Kiểm tra này chưa
chứng minh nguồn hỗ trợ câu trả lời; cần chấm riêng 0–2, đọc citation và kiểm tra
từ chối. Đáp án, gold và nhãn có/thiếu bằng chứng không được gửi cho agent.

Usage được lấy từ API. Chi phí được ước tính theo giá token giờ cao điểm đã lưu
ngày 16/11/2026 từ [bảng giá DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/),
không phải hóa đơn. Có ngưỡng dừng chi phí ước tính 1 USD/client; script nghiên
cứu tạo client sinh và chấm riêng cho từng cấu hình. Request lỗi
được dự phòng bảo thủ. Khi đổi model hoặc đơn giá, cần cập nhật cấu hình trước
khi chạy lại. Embedding local không có phí dịch vụ, chưa tính điện và phần cứng.

HTTP 401: kiểm tra key. HTTP 402: kiểm tra số dư API. HTTP 429/503: chạy lại sau.
Lỗi database: kiểm tra Docker, cổng `15433` và dữ liệu Day 6. Không gửi key khi
chia sẻ thông báo lỗi.
