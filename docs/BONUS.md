# Tái lập phần cơ bản cải thiện và bonus

## Kết quả đã lưu

- Cơ bản v2: context lân cận sửa q02/q09; dev 2,00/2, test mới 5 câu có đáp án
  đạt 2,00/2, từ chối đúng 2/2. Rà citation nghiêm ngặt còn 6/7.
- Bonus: NASA SE Handbook Rev 2, 356 trang, 1.831 node. Bộ dev 18 câu; test
  30 câu. Cấu hình `reference-8` đạt **27/30 (90%)** sau đối chiếu nguồn bảo thủ.
- Điểm API gốc và nhãn sau rà được giữ riêng. Đây là nhãn có hỗ trợ tự động,
  chưa phải xác nhận của người học hay điểm do giảng viên chấm.

Xem [báo cáo](../report/individual/2A202603745_NguyenNhatMinh.md),
[kết quả cơ bản](../results/extension/basic-v2/README.md) và
[kết quả bonus](../results/extension/advanced-v2/README.md).

## Dữ liệu và môi trường

Môi trường đã kiểm tra: Windows, Python 3.13.7 trong venv Day 6, PyMuPDF 1.26.7,
Windows OCR tiếng Anh, model E5 đã tải và database Day 6. Cài dependency:

```powershell
$labPython = "$env:USERPROFILE\.venvs\day06-dataingestion\Scripts\python.exe"
& $labPython -m pip install -r requirements-advanced.txt
```

NASA công bố [nguồn gốc](https://ntrs.nasa.gov/citations/20170001761) và trạng
thái **Public Use Permitted**. Bản PDF `NASA/SP-2016-6105 Rev 2` được công bố
17/02/2017, SHA-256 `3153ae2e53e29452d5997efafe280a5f05cd21b43a047e988a17e1dd5207a38e`.
Giữ ghi nguồn và các chú thích tài liệu bên thứ ba; PDF, ảnh và vector chỉ lưu local.

Chạy từ gốc repo Day 7, theo đúng thứ tự:

```powershell
& $labPython -B -X utf8 scripts/prepare_advanced.py --phase render
$labOcrDirectory = Join-Path $PWD 'starter/data/advanced/review'
powershell.exe -NoProfile -File scripts/ocr_windows.ps1 -Directory $labOcrDirectory
& $labPython -B -X utf8 scripts/prepare_advanced.py --phase index
& $labPython -B -X utf8 scripts/build_advanced_vectors.py --day6 "..\K5-L3B-DAY06-NguyenNhatMinh-2A202603745-DataIngestion"
```

Lệnh render tự tải PDF từ NASA nếu thiếu, kiểm tra SHA rồi render đủ 356 trang.
OCR dùng `Windows.Media.Ocr` với `en-US`; nếu máy chưa có, cài English OCR trong
Windows Settings → Time & language → Language & region → English → Language options.
Lỗi OCR được báo để xử lý, không thay bằng text giả.

Index giữ text toàn tài liệu, các ô/hàng bảng, text và tọa độ nhãn OCR, caption,
Figure/Table ID, trang và bbox. Bbox hình có thể là toàn trang, với caption để
định vị chính xác; bbox bảng lấy từ grid. Không chỉ index trang benchmark.
Vector E5 384 chiều được ghi `.npy`, kiểm tra chuẩn hóa và signature trước tìm
cosine exact; lexical index giữ đầy đủ text. Có 26/1.831 node bị giới hạn 512
token khi embedding; toàn text vẫn còn trong lexical/context.

Ảnh gốc của tối đa ba trang xuất hiện đầu tiên trong context được gửi DeepSeek
Flash ở chế độ vision. Chọn trang từ kết quả retrieval, không từ gold. Model
thấy ảnh PDF ngoài text/OCR; trace xuất giữ số trang và hash ảnh đã gửi.

## Chạy web

Bấm đúp `CHAY_WEB.cmd`, vào <http://127.0.0.1:8767>, chọn **Bonus · NASA SE
Handbook**. Câu mẫu dev cho phép đọc bảng, biểu đồ và thử thiếu bằng chứng.
Mở citation để xem ảnh trang gốc. Lần đầu cần nạp model; key chỉ ở backend.

## Chạy lại thí nghiệm độc lập

Giữ kết quả đã chốt; dùng tên thư mục mới. Các lệnh sau gọi API thật, cần `.env`:

```powershell
& $labPython -B -X utf8 scripts/reproduce_extension.py --scope basic-v2 --name basic-reproduction-01 --phase dev --day6 "..\K5-L3B-DAY06-NguyenNhatMinh-2A202603745-DataIngestion"
& $labPython -B -X utf8 scripts/reproduce_extension.py --scope basic-v2 --name basic-reproduction-01 --phase test --day6 "..\K5-L3B-DAY06-NguyenNhatMinh-2A202603745-DataIngestion"
& $labPython -B -X utf8 scripts/reproduce_extension.py --scope advanced --name nasa-reproduction-01 --phase dev --day6 "..\K5-L3B-DAY06-NguyenNhatMinh-2A202603745-DataIngestion"
& $labPython -B -X utf8 scripts/reproduce_extension.py --scope advanced --name nasa-reproduction-01 --phase test --day6 "..\K5-L3B-DAY06-NguyenNhatMinh-2A202603745-DataIngestion"
```

Dev chốt cấu hình bằng tiêu chí công bố trước; test chỉ nhận đúng hash lúc chốt.
Không sửa pipeline theo kết quả test rồi báo lại trên cùng bộ test. OCR có thể
khác giữa các phiên bản Windows; khi corpus khác hash cần coi là nghiên cứu mới.

Khi chỉ xem kết quả trên Git, không cần key/PDF/model. `traces.public.json` và
`reviews.public.json` đã có tool, nguồn, context, đáp án, usage, model và nhãn.
Xuất lại sau chạy local bằng `scripts/export_results.py`; không commit file thô.

## Rà trước nộp

Mở `results/extension/advanced-v2/test_source_audit.json`, đọc từng `query_id`,
`source_note`, `original_pdf_pages`, `citations` và so với PDF gốc. Có đủ 60
bản rà cho hai cấu hình; không bỏ lỗi khỏi mẫu số. Nếu xác nhận, ghi tên/ngày
và quyết định từng câu trong một bản rà riêng; không sửa nhãn API gốc hoặc tự
đánh dấu toàn bộ chỉ vì chương trình chạy hết. Tham khảo
[lỗi nhãn trục và cách chấm bảo thủ](../advanced/README.md).
