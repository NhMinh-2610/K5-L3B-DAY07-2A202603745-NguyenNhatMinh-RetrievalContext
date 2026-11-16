# Day 7 — Agentic RAG

**Bài cá nhân · Python 3.11+ · tiếp nối Day 6**

## Dự án Nguyễn Nhật Minh · 2A202603745

Phần cơ bản đã có code, 24 câu benchmark, ba phương pháp retrieval, agent
DeepSeek thật, hai cấu hình thử cải thiện và đánh giá test sau khi chốt.
51 unit test đạt. Chưa thực hiện thử thách nâng cao 100 trang.

- **Mở web local:** mở Docker Desktop, bấm đúp [CHAY_WEB.cmd](CHAY_WEB.cmd),
  giữ terminal rồi vào <http://127.0.0.1:8767>. [Hướng dẫn và câu thử](docs/CHAY_WEB.md).
- **Báo cáo:** [2A202603745_NguyenNhatMinh.md](report/individual/2A202603745_NguyenNhatMinh.md).
- **Kết quả:** [so sánh dev/test, trace và bản rà nguồn](results/study/README.md).
- **Tái lập:** [dữ liệu](docs/CHUAN_BI_DU_LIEU.md), [DeepSeek](docs/CHAY_AGENT.md),
  [retrieval](docs/CHAY_RETRIEVAL.md), [thí nghiệm và chốt test](docs/THU_NGHIEM.md).

Dev đạt 1,80/2 ở cả ba cấu hình; chọn hybrid theo tổng phí sinh + chấm. Test
API chấm 2,00/2 trên 5 câu có đáp án, từ chối đúng 2/2; sau rà nguồn hybrid
còn 5/6 citation đủ hỗ trợ. Nhãn được tạo tự động, cần đọc và xác nhận trước
khi nộp. q02/q09 dev còn thiếu ý/từ chối nhầm; xem giới hạn trong báo cáo.

Máy mới cần cài [requirements.txt](requirements.txt), có repo/dữ liệu và
database Day 6, rồi tạo `.env` từ [.env.example](.env.example) và điền key.
Không đưa `.env` hoặc key lên Git. Nội dung dưới đây là yêu cầu đề bài gốc.

---

Dùng embedding và vector store từ Day 6 để xây một agent biết tìm bằng chứng, trả lời có nguồn và nhận biết khi không đủ thông tin. Bạn tự chọn kiến trúc, số tool và cách tổ chức retrieval.

Dữ liệu của bài hiện tại: [cách chuyển chunk và bộ dev từ Day 6](docs/CHUAN_BI_DU_LIEU.md).
Benchmark của bài hiện tại: [24 câu dev/test và cách kiểm tra nguồn](benchmark/README.md).
Code và kết quả retrieval: [chạy dense, TF-IDF và hybrid trên dev](docs/CHAY_RETRIEVAL.md).
Agent: [điền key DeepSeek và chạy trên dev](docs/CHAY_AGENT.md).

## Bài cần làm

![Agent tìm tài liệu trong kho Day 6 và trả lời có nguồn](assets/retrieval-pipeline.svg)

1. Kết nối dữ liệu, embedding và vector store Day 6.
2. Xây agent dùng model thật và ít nhất một khả năng truy xuất dữ liệu. Agent có thể dùng nhiều tool và nhiều lượt gọi.
3. Thử **ít nhất 3 phương pháp retrieval khác nhau**, trong đó có dense retrieval dùng vector store Day 6. Tự chọn các phương pháp còn lại; xem [gợi ý](GUIDE.md#2-thử-các-phương-pháp-retrieval).
4. Thử nhiều cấu hình, benchmark, phân tích lỗi và chọn cấu hình tốt trên **dev**; sau đó đánh giá trên **test**.

Benchmark tối thiểu có **24 câu**: dev gồm 15 câu có đáp án và 2 câu thiếu bằng chứng; test gồm 5 câu có đáp án và 2 câu thiếu bằng chứng. Xem [benchmark](BENCHMARK.md) và [rubric](RUBRIC.md).

## Thử thách nâng cao · +15 điểm

Index một tài liệu thực tế từ **100 trang** có bảng, ảnh và biểu đồ; xây agent truy xuất và trả lời các câu hỏi về nội dung đó. Hoàn thành [thử thách nâng cao](ADVANCED.md) và đạt **ít nhất 90% benchmark test** để nhận 15 điểm bonus. Phần cơ bản tối đa 85 điểm; toàn bài tối đa 100 điểm.

## Bắt đầu

1. Đọc [hướng dẫn](GUIDE.md), [rubric](RUBRIC.md) và [quy tắc](RULES.md).
2. Tạo repo cá nhân theo [cách nộp bài](SUBMISSION.md), chuẩn bị đầu ra Day 6 và model hỗ trợ tool calling.
3. Dùng hoặc thay thế [starter](starter/README.md); bạn cần kết nối model và vector store thật.
4. Chạy `python -m unittest discover -s tests -v`. Test mock chỉ kiểm tra code, không phải benchmark agent thật.

![Các bước thử nghiệm trên dev và đánh giá trên test](assets/experiment-loop.svg)

Nộp code, cách chạy, cấu hình, benchmark, trace và [báo cáo](report/individual/MSSV_HoTen.md). Thời gian ở [checkpoints](CHECKPOINTS.md) là gợi ý, có thể điều chỉnh theo lớp và phạm vi thử nghiệm.
