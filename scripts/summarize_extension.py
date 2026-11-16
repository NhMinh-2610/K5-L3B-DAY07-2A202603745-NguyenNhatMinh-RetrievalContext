"""Tổng hợp các nghiên cứu bổ sung đã lưu, không gọi API hoặc sửa pipeline."""
import csv
import hashlib
import json
import statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"results/extension"


def read(path):
    if not path.exists():path=path.with_name(path.stem+".public.json")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def main():
    ledger=[]
    for scope in ("basic-v2","advanced","advanced-v2"):
        folder=OUT/scope
        for split in ("dev","test"):
            path=folder/f"{split}_comparison.json"
            if not path.exists():continue
            for summary in read(path):
                traces=read(folder/split/summary["configuration"]/"traces.json")
                ledger.append({"scope":scope,"split":split,"configuration":summary["configuration"],
                               "cases":len(traces),"median_seconds":statistics.median(t["elapsed_seconds"] for t in traces),
                               "generation_cost_upper_usd":summary["generation_cost_upper_usd"],
                               "judge_cost_upper_usd":summary["judge_cost_upper_usd"],
                               "total_cost_upper_usd":summary["total_cost_upper_usd"]})
    with (OUT/"comparison.csv").open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(ledger[0]));writer.writeheader();writer.writerows(ledger)
    save(OUT/"costs.json",{"scope":"Saved extension runs only; excludes legacy study and manual web calls.",
        "recorded_generation_upper_usd":sum(r["generation_cost_upper_usd"] for r in ledger),
        "recorded_judge_upper_usd":sum(r["judge_cost_upper_usd"] for r in ledger),
        "recorded_total_upper_usd":sum(r["total_cost_upper_usd"] for r in ledger),
        "cost_is_invoice":False,"grading_incident":"Initial basic-v2 dev grading stopped on malformed JSON; failed call usage was not saved. Total only sums recorded successful responses for that study; bonus records every grading attempt.",
        "runs":ledger})
    for scope in ("basic-v2","advanced-v2"):
        folder=OUT/scope
        dev=read(folder/"dev_comparison.json");test=read(folder/"test_reviewed_comparison.json")
        selected=read(folder/"selection.json")["selected_configuration"]
        if scope=="basic-v2":
            text="# Cơ bản v2 — context lân cận\n\nGiữ nguyên nghiên cứu đầu; dùng test mới 5+2 câu sau khi chốt trên dev.\n\n"
            text+="| Split | Cấu hình | Điểm /2 | Citation | Từ chối đúng | Lỗi | Phí sinh + chấm, USD |\n|---|---|---|---|---|---|---|\n"
            for split,rows in (("dev",dev),("test",test)):
                for row in rows:
                    m=row["metrics"];c=m["citation_validity"];a=m["abstention"]
                    text+=f"| {split} | {row['configuration']} | {m['answer_mean']:.2f} | {c['n']}/{c['N']} | {a['n']}/{a['N']} | {m['errors']} | {row['total_cost_upper_usd']:.6f} |\n"
            text+="\nq02 đã đủ temperaments/self-esteem; q09 có Industrial data. Chọn neighbors-1 vì cùng điểm với radius2 và phí thấp hơn. Context ghép cùng trang/mục, giữ ID thành viên; dense vẫn trên pgvector Day6. Ranking seed gốc và group được lưu riêng.\n\nTest còn một citation chưa tự hỗ trợ qualifier INT8 (trang36); bảng trang19 có thông tin này nên điểm đáp án vẫn2, citation chấm bảo thủ6/7. Xem `test_source_audit.json`; không sửa pipeline sau test.\n"
        else:
            text="# Bonus NASA — đánh giá đầy đủ\n\nNguồn356 trang, index1.831 node, dev18/test30. Cấu hình chọn: **"+selected+"**.\n\n"
            text+="| Dev | Đạt | Lỗi | Phí sinh + chấm, USD |\n|---|---|---|---|\n"
            for row in dev:text+=f"| {row['configuration']} | {row['passed']}/{row['total']} | {row['errors']} | {row['total_cost_upper_usd']:.6f} |\n"
            text+="\n| Test | API gốc | Sau rà bảo thủ | Tỷ lệ | Lỗi | Phí sinh + chấm, USD |\n|---|---|---|---|---|---|\n"
            for row in test:text+=f"| {row['configuration']} | {row['raw_api_passed']}/{row['total']} | {row['passed']}/{row['total']} | {100*row['rate']:.1f}% | {row['errors']} | {row['total_cost_upper_usd']:.6f} |\n"
            text+="\n| Nhóm test | Baseline | Đã chọn |\n|---|---|---|\n"
            for group in test[0]["by_group"]:
                a,b=test[0]["by_group"][group],test[1]["by_group"][group]
                text+=f"| {group} | {a['n']}/{a['N']} | {b['n']}/{b['N']} |\n"
            text+="\n**27/30=90%**, đủ ngưỡng số học bonus. Cả30 câu đều trong mẫu số; baseline1 lỗi, cấu hình chọn0. `test_source_audit.json` có60 bản rà và lý do từng câu cho cảhai cấu hình. Nhãn sau rà mang trạng thái `source_check_proposed`: đối chiếu nguồn có hỗ trợ tự động, tách biệt với điểm chấm chính thức.\n\n`at_i2`: OCR không đủ nhưng ảnh trang64 thực gửi hỗ trợ đủ ba ô; chấp nhận sau đối chiếu nguồn. `at_c4`: trụcY thật ghi Some Aspect; gold/mô tả nháp nhầm All Aspects. Baseline All bị hạ; model vision Some đúng nhưng còn cite mô tả sai nên vẫn chấm không đạt bảo thủ. Không đổi snapshot index/gold hoặc chạy lại test để qua ngưỡng. Hai câu text at_x2/at_x3 còn thiếu ý/đúng mục.\n\nDev preflight dùng agent một tool cũ được giữ ở `../advanced/`; sau phân tích lỗi mới bổ sung multi-tool/ảnh và chạy dev v2, chốt rồi chạy test. Test chỉ chạy ở v2.\n"
        text+="\nFile `traces.public.json` giữ native tool/argument, query/filter, ranking, context, đáp án/citation, model/usage/chi phí; file `reviews.public.json` giữ nhãn và lý do. Không commit request/response/messages thô. `run.json`, `selection.json` ghi thời điểm/hash; `test_comparison.json` API gốc được giữ riêng với `test_reviewed_comparison.json`.\n\nHướng dẫn: [docs/BONUS.md](../../../docs/BONUS.md). Báo cáo: [cá nhân](../../../report/individual/2A202603745_NguyenNhatMinh.md).\n"
        (folder/"README.md").write_text(text,encoding="utf-8")
    print("Đã tổng hợp",len(ledger),"cấu hình/split; không gọi API.")


if __name__=="__main__":main()
