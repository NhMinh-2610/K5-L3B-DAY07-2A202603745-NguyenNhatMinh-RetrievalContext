# Cơ bản v2 — context lân cận

Giữ nguyên nghiên cứu đầu; dùng test mới 5+2 câu sau khi chốt trên dev.

| Split | Cấu hình | Điểm /2 | Citation | Từ chối đúng | Lỗi | Phí sinh + chấm, USD |
|---|---|---|---|---|---|---|
| dev | baseline | 1.80 | 18/18 | 2/2 | 0 | 0.021383 |
| dev | neighbors-1 | 2.00 | 19/19 | 2/2 | 0 | 0.029826 |
| dev | neighbors-2 | 2.00 | 18/18 | 2/2 | 0 | 0.032979 |
| test | baseline | 2.00 | 6/6 | 2/2 | 0 | 0.011382 |
| test | neighbors-1 | 2.00 | 6/7 | 2/2 | 0 | 0.013199 |

q02 đã đủ temperaments/self-esteem; q09 có Industrial data. Chọn neighbors-1 vì cùng điểm với radius2 và phí thấp hơn. Context ghép cùng trang/mục, giữ ID thành viên; dense vẫn trên pgvector Day6. Ranking seed gốc và group được lưu riêng.

Test còn một citation chưa tự hỗ trợ qualifier INT8 (trang36); bảng trang19 có thông tin này nên điểm đáp án vẫn2, citation chấm bảo thủ6/7. Xem `test_source_audit.json`; không sửa pipeline sau test.

File `traces.public.json` giữ native tool/argument, query/filter, ranking, context, đáp án/citation, model/usage/chi phí; file `reviews.public.json` giữ nhãn và lý do. Không commit request/response/messages thô. `run.json`, `selection.json` ghi thời điểm/hash; `test_comparison.json` API gốc được giữ riêng với `test_reviewed_comparison.json`.

Hướng dẫn: [docs/BONUS.md](../../../docs/BONUS.md). Báo cáo: [cá nhân](../../../report/individual/2A202603745_NguyenNhatMinh.md).
