# Kiểm tra điều kiện dừng của agent

Ngày chạy: 16/11/2026. Chỉ chạy lại hai câu dev từng bị lỗi; kết quả toàn bộ
dev trước thay đổi được giữ ở `../dev-baseline/`.

## Nguyên nhân và thay đổi

Trước thay đổi, sau ba lượt tìm, request chỉ còn `submit_answer` và `abstain`,
nhưng model vẫn trả `search_documents`. Agent báo `AgentProtocolError` thay vì
kết thúc bằng một quyết định hợp lệ.

Khi hết lượt tìm hoặc đến lượt model cuối, request mới chỉ khai báo
`finish_response` và chỉ định gọi đúng tool này. Model tự chọn trả lời có nguồn
hoặc từ chối theo context hiện có. Giới hạn tìm kiếm, top-k, budget context và
filter được giữ nguyên. Tool không được phép và citation không hợp lệ vẫn bị
từ chối; không đổi lỗi kỹ thuật thành câu trả lời giả.

## Kết quả

| Câu | Trước | Sau | Đánh giá phạm vi sửa lỗi |
|---|---|---|---|
| `q09` | Lỗi tool sau 3 lượt tìm | Từ chối, 3 lượt tìm và 4 lượt model | Hết lỗi dừng; còn từ chối sai vì không lấy được evidence có sẵn |
| `dev_no_evidence_01` | Lỗi tool sau 3 lượt tìm | Từ chối, 3 lượt tìm và 4 lượt model | Hết lỗi dừng; kết quả phù hợp với câu thiếu bằng chứng |

Cả hai response cuối đều gọi `finish_response` đúng yêu cầu của API. Có 8
request DeepSeek, chi phí ước tính theo giá cao điểm là 0,002950944 USD;
đây không phải hóa đơn. Nguồn số liệu: `summary.json`, `traces.jsonl`,
`traces.json`. Kiểm tra mã nguồn: 40 unit test đạt.

Với `q09`, các query đã viết lại chưa lấy được chunk chứa bằng chứng về
`Industrial data` ở trang 23; chunk đó cũng không có trong context cuối.
Corpus có đáp án nên việc từ chối vẫn là lỗi chất lượng. Cần thử retrieval
hybrid hoặc tăng số candidate, rồi đo lại trên dev; riêng tăng context budget
không bảo đảm lấy được đoạn chưa từng được truy xuất.

Các dấu kiểm tra benchmark giữ nguyên. Không chạy test hoặc chốt cấu hình.
Lần kiểm tra hai câu này không thay thế việc chạy lại toàn bộ dev sau thay đổi,
chấm câu trả lời/citation/từ chối và so sánh các cấu hình cải thiện.
