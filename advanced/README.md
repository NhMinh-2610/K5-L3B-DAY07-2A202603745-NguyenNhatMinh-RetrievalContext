# Nguồn và kiểm chứng bonus

Tài liệu: *NASA Systems Engineering Handbook*, NASA/SP-2016-6105 Rev 2.
[NTRS 20170001761](https://ntrs.nasa.gov/citations/20170001761) ghi Public Use
Permitted; ngày công bố 17/02/2017. Bản tải sử dụng có **356 trang vật lý**;
số trang in lệch do phần đầu sách. Mọi gold dùng số trang vật lý từ 1.

Index có 962 node text, 291 OCR/layout, 369 bảng, 206 hình và 3 mô tả trực quan.
Cả 356 trang được render/OCR; text, bảng, hình và nguồn đều được giữ. Có 59
vùng caption được nhận diện. Không phải mọi bbox đều cắt sát đối tượng: các
caption/ID hình cùng trang giúp tìm lại vùng; ảnh gốc vẫn truy cập được trên web.

- `visual_readings.json`: hai bản đọc biểu đồ trước khi soạn benchmark, tách
  khỏi gold; file được giữ như snapshot đã chốt để tái lập lần đánh giá.
- `corpus_absence_checks.json`: quét native text/OCR toàn tài liệu cho 9 câu
  âm tính, kèm lý do và phần nguồn liên quan. Không dùng top-k để chứng minh vắng mặt.
- PDF, ảnh trang, OCR thô và vector nằm trong `starter/data/advanced/`, được ignore.
- [Hướng dẫn chuẩn bị/chạy](../docs/BONUS.md).

## Lỗi đọc trục được phát hiện khi đối chiếu

Trục Y thật của **Figure 4.4-3, PDF trang 96** ghi **Some Aspect of Effectiveness,
Expressed in Quantitative Units**. Tiêu đề/chú thích hình lại nói “All Aspects”,
và bản mô tả/gold nháp đã nhầm tiêu đề thành nhãn trục.

Snapshot index/gold trước test được giữ nguyên, không sửa rồi chạy lại test để
tăng điểm. Bản rà ở `results/extension/advanced-v2/test_source_audit.json` ghi
đúng nhãn theo ảnh gốc. Baseline trả “All” nên bị hạ từ đạt xuống không đạt.
Model có vision trả “Some” đúng, nhưng vẫn dẫn thêm mô tả sai; chấm bảo thủ giữ
câu này **không đạt** vì citation mâu thuẫn. Đây là giới hạn đã biết của snapshot,
không dùng bản mô tả như nguồn chuẩn thay cho ảnh gốc.

Một câu khác, `at_i2`, có hai citation cùng chỉ Figure 4.0-1 trang 64. API chỉ
đọc OCR nên bác một citation; trace chứng minh ảnh trang 64 đã thực gửi, có đủ
ba ô cần hỏi. Đối chiếu ảnh gốc chấp nhận câu đó. Vì vậy kết quả bảo thủ là
**27/30**, so với **26/30** API gốc. Cả hai bảng và toàn bộ lý do được giữ lại.

Nhãn `source_check_proposed` có hỗ trợ tự động, chưa phải xác nhận của người học.
Các lỗi khác gồm hai câu text thiếu ý/đúng mục nguồn. Nếu phát triển tiếp sau
khi đã xem test, cần test mới để đánh giá độc lập.
