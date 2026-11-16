# Day 7 — Agentic RAG

Nguyễn Nhật Minh · 2A202603745 · K5-L3B · 16/11/2026

## Dữ liệu và liên hệ Day 6

Day 6 cung cấp dữ liệu đã xử lý, chunk, embedding và vector store. Day 7 dùng
những đầu ra đó để tìm bằng chứng, xây agent trả lời có nguồn và đánh giá.
Không tạo vector ngẫu nhiên hay thay embedding khi truy vấn.

| Thành phần | Phiên bản và phạm vi |
|---|---|
| Nguồn | Huawei Technologies Co., Ltd. (2023), *A General Introduction to Artificial Intelligence*, [DOI](https://doi.org/10.1007/978-981-19-2879-6_1), CC BY-NC-ND 4.0 |
| Corpus | 35 trang nội dung được chọn trong PDF 41 trang; cấu hình C, 201 chunk dùng chung với B; giữ ID, text, trang, nguồn và metadata |
| Embedding | `intfloat/multilingual-e5-small`, revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`, 384 chiều, chuẩn hóa; tiền tố `passage: ` / `query: ` |
| Thư viện | sentence-transformers 6.2.0, transformers 5.22.1, torch 2.15.0; CPU float32 |
| Vector store | PostgreSQL 16.16, pgvector 0.8.7, `lab_chunks`, cổng 15433; cosine exact, kết nối chỉ đọc |
| Agent và bộ chấm | DeepSeek API `deepseek-flash`, phiên bản tài liệu `DeepSeek-V4.1-Flash-1017`, thinking tắt, temperature 0 |

Kết nối kiểm tra đủ 201 ID, nội dung, metadata, chiều vector và chữ ký embedding
`0dfa971762747459e20d16f5fbcf31c26eceda7c23e38efd1ad3af675ad2b835` trước khi chạy.
Model tải khoảng 145 giây trong lần nghiên cứu; không tính thời gian này vào
median mỗi câu. Response lưu model/fingerprint thực tế; ví dụ fingerprint
`bc19ba97cbe016479903222bb1578db6`. Chi tiết ở
[data_provenance.json](../../results/study/data_provenance.json).

Benchmark có **24 câu**: dev 15 có đáp án + 2 thiếu evidence, test 5 + 2.
Dev kế thừa 15 câu Day 6; test dùng câu mới, không dùng lại test Day 6 đã phân tích.
`benchmark/review.csv` có 24/24 xác nhận nguồn; đây là rà gold, không phải xác
nhận điểm câu trả lời của model. Có 22 evidence thay thế cho 20 câu có đáp án.
Các câu âm tính có `absence_reason` và kiểm tra toàn corpus, không kết luận từ
một lượt top-k. [Schema và split](../../benchmark/README.md) tách query khỏi gold.

## Retrieval trên query gốc

Ba phương pháp cùng corpus, filter từ câu hỏi, top-3, budget 3.000 ký tự gồm
header, không cắt chunk. Dense dùng pgvector; TF-IDF dùng từ khóa; hybrid dùng
RRF với hằng số 60, tối đa 10 candidate mỗi nhánh. Không có reranker.

| Phương pháp / dev | Hit@1 | Evidence Hit@3 | Context chuẩn bị đủ gold | Median retrieval | Embedding query |
|---|---|---|---|---|---|
| Dense | 8/15 (53,3%) | 10/15 (66,7%) | 11/15 (73,3%) | 5,49 ms | 44,56 ms |
| TF-IDF | 6/15 (40,0%) | 7/15 (46,7%) | 7/15 (46,7%) | 0,43 ms | Không dùng |
| Hybrid | 6/15 (40,0%) | 10/15 (66,7%) | 11/15 (73,3%) | 6,15 ms | 44,56 ms |

Median retrieval tách khỏi embedding; hybrid dùng lại vector query. Phí dịch vụ
retrieval local bằng 0, chưa tính phần cứng/điện. Context ở bảng này mới được
chuẩn bị, chưa gửi LLM. Nguồn: [51 trace và summary](../../results/retrieval/dev/).

Hit yêu cầu một chunk đúng nguồn/trang chứa đủ gold; context có thể ghép nhiều
chunk. Gold của q02/q10 và một số câu test trải qua nhiều chunk, nên metric
khớp nguyên văn nghiêm ngặt có thể thấp dù context đủ ý. Giữ nguyên gold,
báo thêm context ngữ nghĩa 0/1/2 thay vì rút ngắn evidence để tăng điểm.

## Agent, thử nghiệm và chọn cấu hình

Model gọi native tool `search_documents(query)`, rồi `submit_answer` hoặc
`abstain`. Mọi câu phải tìm trước; filter không được model sửa. Giới hạn 3 lượt
tìm và 5 lượt model, output 800 token/lượt. Context ưu tiên lượt tìm gần nhất,
khử ID trùng, giữ nguyên chunk và chỉ ghi nhận phần thực gửi. Hết lượt tìm hoặc
đến lượt model cuối thì ép tool `finish_response` chọn trả lời/từ chối.
Tool lạ, JSON sai, citation không ở context hoặc không khớp văn bản là lỗi riêng.
Kiểm tra ID không thay thế việc đọc nguồn để chấm citation.

Hai giả thuyết được ghi trước chạy trong [experiment_plan.json](../../config/experiment_plan.json):
hybrid có thể lấy được thuật ngữ Industrial data mà dense bỏ sót; dense mở rộng
có thể giữ thêm bằng chứng/điều kiện qua nhiều chunk. Các biến khác giữ nguyên.

| Cấu hình / dev | Thay đổi | Hit@1 lượt đầu | Hit@3 lượt đầu | CER nguyên văn | CER ngữ nghĩa | Điểm /2 | Median /câu | Phí sinh + chấm, USD |
|---|---|---|---|---|---|---|---|---|
| Baseline | Dense, k=3, budget=3.000 | 10/15 (66,7%) | 11/15 (73,3%) | 13/15 (86,7%) | 13/15 (86,7%) | 1,80 | 2,66 s | 0,012071 + 0,014792 |
| Hybrid | RRF, k=3, budget=3.000 | 9/15 (60,0%) | 10/15 (66,7%) | 12/15 (80,0%) | 13/15 (86,7%) | 1,80 | 2,80 s | 0,012498 + 0,012586 |
| Dense mở rộng | k=5, budget=6.000 | 10/15 (66,7%) | 11/15 (73,3%) | 12/15 (80,0%) | 13/15 (86,7%) | 1,80 | 2,68 s | 0,015790 + 0,014619 |

Lượt đầu của agent có query được model viết lại; không đồng nhất với bảng query
gốc. Cả ba có 0 lỗi kỹ thuật, phân bố điểm 0/1/2 là 1/1/13, hai câu âm tính
đều từ chối đúng, một câu dương tính bị từ chối nhầm.

Chọn **hybrid** lúc `2026-11-16T08:04:38.477109+00:00` theo tiêu chí đã đặt:
lỗi, điểm trả lời, từ chối, citation/context ngữ nghĩa, rồi chi phí và thời gian.
Các tiêu chí chất lượng dùng để chọn bằng nhau; tổng phí **sinh + chấm** hybrid
thấp nhất: 0,025083 USD, so với 0,026863 và 0,030409 USD. Riêng phí sinh câu
trả lời hybrid cao hơn baseline; chưa chứng minh hybrid tiết kiệm khi vận hành.
CER nguyên văn baseline tốt hơn. Không có cải thiện điểm trả lời sau hai thử nghiệm.
Đây là một lần đo có ảnh hưởng cache/API, không phải kết luận thống kê.

[selection.json](../../results/study/selection.json) khóa hash code, config,
benchmark và dev summary trước chạy test. Hai run test bắt đầu sau thời điểm
chốt, giữ nguyên code/config; kiểm tra lại hash sau đánh giá đều khớp.

## Phân tích lỗi dev

| Câu / lỗi | Nguyên nhân qua trace | Cách thử và kết quả |
|---|---|---|
| q02: đúng một phần, 1/2 | Chunk trả về có strengths, weaknesses, hobbies, moods, intentions; thiếu chunk kế tiếp chứa temperaments và self-esteem. Context cuối cả ba cấu hình thiếu ID `d2b8d4…`. | Hybrid và k=5/budget=6.000 vẫn không lấy đủ đoạn nối; điểm giữ 1. Tăng budget không tự bổ sung chunk chưa truy xuất. |
| q09: từ chối nhầm, 0/2 | Evidence Industrial data có ở trang 23, chunk `6469c77d…`, đúng filter 1.2, nhưng không xuất hiện trong kết quả/context sau 3 lượt tìm. | Hybrid bổ sung lexical, dense mở rộng thêm candidate; cả hai vẫn bỏ sót đoạn nên chưa giải quyết. Không được coi từ chối này là đúng. |

Trước đó q09 và dev_no_evidence_01 còn lỗi model gọi search sau khi hết lượt.
Ép tool kết thúc đã đưa lỗi kỹ thuật từ 2 xuống 0 trong lần chạy dev đầy đủ;
q09 vẫn sai chất lượng. [Kiểm tra trước/sau](../../results/agent/dev-stop-fix/README.md)
giữ nguyên trace lịch sử. Hướng phát triển sau này là lấy chunk liền kề hoặc
đa dạng hóa candidate, đo trên dev và dùng test mới nếu thay đổi sau lần đánh giá này.

## Test sau khi chốt

Baseline và hybrid đều chạy 7 câu, chấm sau khi agent kết thúc; đã đối chiếu
cả 5 câu có đáp án và 2 câu âm tính của từng cấu hình. Điểm API là đề xuất.
Bản rà nguồn bổ sung vẫn cần người học xác nhận, không ghi thành điểm thủ công.

| Chỉ số test | Baseline | Hybrid đã chọn |
|---|---|---|
| Hit@1 / Evidence Hit@3 lượt đầu | 2/5 (40%) / 3/5 (60%) | 2/5 (40%) / 3/5 (60%) |
| CER nguyên văn / ngữ nghĩa | 3/5 (60%) / 5/5 (100%) | 4/5 (80%) / 5/5 (100%) |
| Context 0/1/2, câu có đáp án | 0 / 0 / 5 | 0 / 0 / 5 |
| Điểm trả lời 0/1/2; trung bình | 0 / 0 / 5; 2,00/2 | 0 / 0 / 5; 2,00/2 |
| Citation API → sau rà nguồn | 5/5 → 5/5 (100%) | 6/6 → **5/6 (83,3%)** |
| Câu trả lời có citation | 5/5 (100%) | 5/5 (100%) |
| Từ chối đúng / từ chối nhầm | 2/2 (100%) / 0/5 (0%) | 2/2 (100%) / 0/5 (0%) |
| Có gọi retrieval / lỗi kỹ thuật | 7/7 (100%) / 0 | 7/7 (100%) / 0 |
| Phân bố số lượt tìm | 1 lượt: 5; 2 lượt: 1; 3 lượt: 1 | 1 lượt: 5; 3 lượt: 2 |
| Median thời gian agent | 2,71 s | 3,25 s |
| Số request sinh + chấm | 24 | 25 |
| Phí sinh + chấm | 0,005786 + 0,005505 = 0,011291 USD | 0,005996 + 0,005050 = 0,011046 USD |

Citation tính mỗi ID duy nhất trong một câu, không đếm lặp cùng ID. Mẫu số
điểm trả lời/context chỉ gồm 5 câu có đáp án; hai câu âm tính chấm từ chối riêng.
Trường hợp lỗi kỹ thuật tách riêng, không biến thành từ chối đúng.

| Query ID | Đối chiếu đầu ra và nguồn của cả hai cấu hình |
|---|---|
| test_01 | Năm thuộc tính âm nhạc đúng ở trang 2. Hybrid thêm khẳng định về độ nhạy cảm nhưng citation thứ hai chỉ là đuôi câu, thiếu chủ thể/mệnh đề; giữ điểm đáp án 2, hạ một citation. |
| test_02 | ELIZA: luật + câu hỏi người dùng + kho trả lời viết sẵn ở trang 8; đủ cơ chế dù chunk không chứa toàn bộ gold dài. |
| test_03 | Ba hạn chế GPU khớp trang 17. Cụm “low energy consumption ratio” trong bản gốc mơ hồ; cách dịch/diễn giải năng lượng cần rà, nhãn 2 vẫn là đề xuất. |
| test_04 | Trang 21 nêu lặp thu thập/làm sạch dữ liệu, huấn luyện/tinh chỉnh/tối ưu khi đổi kịch bản; chunk thiếu đầu mục nhưng đủ ý cần trả lời. |
| test_05 | Ba nguyên tắc MindSpore đúng trang 35, phạm vi 1.4. |
| test_no_evidence_01 | Đã tìm rồi từ chối số GPU chính xác của AlphaGo, không đưa số ngoài nguồn. |
| test_no_evidence_02 | Đã tìm rồi từ chối giá USD Ascend 310; corpus chỉ có thông số liên quan. |

API từng gán điểm answer/context 2 cho baseline test_no_evidence_02; bản rà đưa
về 0/1 theo schema câu âm tính. Không ảnh hưởng trung bình trên câu dương tính.
Nhãn API gốc được giữ nguyên; [source_audit.json](../../results/study/test/source_audit.json)
ghi từng lý do và thay đổi, [comparison sau rà](../../results/study/test_reviewed_comparison.json)
tách khỏi [comparison API gốc](../../results/study/test_comparison.json).

## Tái lập, chi phí và giới hạn

Lệnh chuẩn bị/chạy ở [hướng dẫn dữ liệu](../../docs/CHUAN_BI_DU_LIEU.md),
[agent](../../docs/CHAY_AGENT.md), [thí nghiệm](../../docs/THU_NGHIEM.md) và
[web local](../../docs/CHAY_WEB.md). Mở `CHAY_WEB.cmd`, giữ terminal rồi truy cập
`http://127.0.0.1:8767`. Web có ví dụ dev, chọn retrieval/filter, mở nguồn/trang,
log lượt tìm và bảng kết quả; key chỉ đọc ở backend, không phục vụ `.env`.

Mỗi thư mục `results/study/{dev,test}/{cấu_hình}/` có run, trace, nhãn API và
summary. Bản nộp Git dùng `traces.public.json`, `reviews.public.json` và
`reviews_source_checked.public.json`: giữ tool/argument, query/filter,
ranking/score, context thực gửi, câu trả lời/citation, model, token, thời gian,
chi phí, lỗi và nhãn. Request/response thô cùng hội thoại chỉ giữ local,
không commit; `results/exports.json` ghi hash file gốc và bản xuất.
Bản rà bổ sung không ghi đè nhãn API.
[comparison.csv](../../results/study/comparison.csv) tổng hợp 5 cấu hình/split.

Nghiên cứu có 223 request, phí ước tính 0,104693 USD gồm sinh 0,052141 và chấm
0,052552 USD. Hai lần kiểm thử web có 4 request, 0,001105 USD; các smoke run
lịch sử ở `results/agent/` tách riêng. Usage lấy từ API, quy đổi theo giá cao điểm
đã lưu 16/11/2026; **không phải hóa đơn hoặc toàn bộ lịch sử tài khoản**.
Xem [costs.json](../../results/study/costs.json).

51 unit test đạt; JavaScript kiểm tra cú pháp đạt; web đã gọi API thật, hiển thị
đáp án và nguồn. Kiểm thử mock chỉ xác minh logic, không dùng làm điểm benchmark.

Giới hạn: corpus nhỏ, một chương, chưa OCR đầy đủ hình/bảng; benchmark test chỉ
5 câu dương tính; câu hỏi Việt trên nguồn Anh; exact-gold có thể phạt đoạn đủ ý;
dùng cùng họ model để sinh và chấm có thiên lệch. q02/q09 dev chưa được giải quyết,
một citation test còn thiếu ngữ cảnh, bản dịch GPU cần rà. Kết quả không chứng minh
chất lượng trên tài liệu mới hoặc đạt điểm rubric tuyệt đối.

Phạm vi đã thực hiện là **phần cơ bản**. Chưa làm thử thách tài liệu từ 100 trang
có bảng/ảnh/biểu đồ và benchmark nâng cao; không yêu cầu cộng 15 điểm bonus.
