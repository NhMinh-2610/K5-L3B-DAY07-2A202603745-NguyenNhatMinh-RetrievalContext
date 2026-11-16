# Bonus NASA — đánh giá đầy đủ

Nguồn356 trang, index1.831 node, dev18/test30. Cấu hình chọn: **reference-8**.

| Dev | Đạt | Lỗi | Phí sinh + chấm, USD |
|---|---|---|---|
| baseline | 13/18 | 0 | 0.043561 |
| reference-text | 17/18 | 0 | 0.051048 |
| reference-8 | 17/18 | 0 | 0.046546 |
| reference-12 | 17/18 | 0 | 0.058473 |

| Test | API gốc | Sau rà bảo thủ | Tỷ lệ | Lỗi | Phí sinh + chấm, USD |
|---|---|---|---|---|---|
| baseline | 21/30 | 20/30 | 66.7% | 1 | 0.078180 |
| reference-8 | 26/30 | 27/30 | 90.0% | 0 | 0.094767 |

| Nhóm test | Baseline | Đã chọn |
|---|---|---|
| chart | 4/5 | 4/5 |
| image | 1/5 | 5/5 |
| multi_hop | 1/4 | 4/4 |
| table | 6/6 | 6/6 |
| text | 2/4 | 2/4 |
| unanswerable | 6/6 | 6/6 |

**27/30=90%**, đủ ngưỡng số học bonus. Cả30 câu đều trong mẫu số; baseline1 lỗi, cấu hình chọn0. `test_source_audit.json` có60 bản rà và lý do từng câu cho cảhai cấu hình. Nhãn sau rà mang trạng thái `source_check_proposed`: đối chiếu nguồn có hỗ trợ tự động, tách biệt với điểm chấm chính thức.

`at_i2`: OCR không đủ nhưng ảnh trang64 thực gửi hỗ trợ đủ ba ô; chấp nhận sau đối chiếu nguồn. `at_c4`: trụcY thật ghi Some Aspect; gold/mô tả nháp nhầm All Aspects. Baseline All bị hạ; model vision Some đúng nhưng còn cite mô tả sai nên vẫn chấm không đạt bảo thủ. Không đổi snapshot index/gold hoặc chạy lại test để qua ngưỡng. Hai câu text at_x2/at_x3 còn thiếu ý/đúng mục.

Dev preflight dùng agent một tool cũ được giữ ở `../advanced/`; sau phân tích lỗi mới bổ sung multi-tool/ảnh và chạy dev v2, chốt rồi chạy test. Test chỉ chạy ở v2.

File `traces.public.json` giữ native tool/argument, query/filter, ranking, context, đáp án/citation, model/usage/chi phí; file `reviews.public.json` giữ nhãn và lý do. Không commit request/response/messages thô. `run.json`, `selection.json` ghi thời điểm/hash; `test_comparison.json` API gốc được giữ riêng với `test_reviewed_comparison.json`.

Hướng dẫn: [docs/BONUS.md](../../../docs/BONUS.md). Báo cáo: [cá nhân](../../../report/individual/2A202603745_NguyenNhatMinh.md).
