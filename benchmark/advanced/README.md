# Benchmark bonus NASA

| Nhóm chính | Dev | Test |
|---|---:|---:|
| Bảng | 3 | 6 |
| Hình/sơ đồ | 3 | 5 |
| Biểu đồ | 3 | 5 |
| Multi-hop | 3 | 4 |
| Text | 3 | 4 |
| Thiếu bằng chứng | 3 | 6 |
| **Tổng** | **18** | **30** |

Mỗi câu có một nhóm chính. Dev/test có câu hỏi và yêu cầu trả lời riêng, không
chỉ đổi cách diễn đạt; cùng tài liệu/figure có thể hỏi các thông tin khác nhau.
Năm câu biểu đồ test dùng ba hình 2.5-1, 4.4-3 và 6.4-2, gồm đọc giá trị/đơn vị,
phép tính và phân bố/bất định. Hình đều chứa nội dung, không phải trang trí.

`dev.json`, `test.json` là gold; `*_queries.json` chỉ có ID/split/question/filter.
Runtime không nhận nhóm, answerable, gold, bbox chuẩn hoặc expected answer.
Figure/Table ID lấy từ câu hỏi người dùng là anchor hợp lệ, không lấy từ nhãn.
Multi-hop có evidence ít nhất hai trang; các phép tính ghi riêng trong `calculation`.

Chấm đạt/không đạt trên **tất cả 30 câu**, kể cả lỗi hệ thống. Câu dương tính
cần đủ ý/điều kiện/đơn vị/phép tính và citation hỗ trợ, định vị đúng trang/vùng.
Câu âm tính phải tìm rồi từ chối, không thêm dữ kiện vô căn cứ. Ngưỡng bonus
là **27/30**, không làm tròn. API grade chỉ là đề xuất; đối chiếu bản PDF cho từng câu.

`errata.json` ghi sửa nháp `at_m4` từ bốn thành sáu Common Areas sau đọc hình,
trước bất kỳ model run trên test. Lỗi nhãn trục phát hiện sau test được ghi riêng
trong kết quả, không ghi đè snapshot benchmark đã chốt. Xem
[đối chiếu nguồn](../../advanced/README.md) và
[kết quả đầy đủ](../../results/extension/advanced-v2/README.md).
