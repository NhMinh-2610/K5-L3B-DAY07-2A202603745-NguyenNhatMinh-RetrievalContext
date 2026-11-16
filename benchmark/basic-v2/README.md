# Test cơ bản mới

Dev giữ 17 câu ban đầu để đo cải thiện. Test v2 gồm 5 câu có đáp án và 2 câu
thiếu bằng chứng mới: FPGA, ba trường phái AI, dự báo quy mô thị trường,
full-stack, thông số Ascend 310; thiếu số transistor V100 và giá thuê CLOUD EI.
Không dùng test đợt một để lựa chọn cấu hình v2.

`test.json` chỉ dùng chấm; `test_queries.json` chỉ ID/split/question/filter cho
agent. Gold đối chiếu đúng nguồn/trang trong corpus Day 6; `source_check_proposed`
chưa phải xác nhận mới của người học. Kết quả và các citation còn hạn chế ở
[bảng so sánh](../../results/extension/basic-v2/README.md).
