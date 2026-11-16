"""Tải, render và index toàn bộ NASA SE Handbook; không đọc benchmark/gold."""
import argparse
import hashlib
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"starter/data/advanced"
PDF=DATA/"raw/nasa-systems-engineering-handbook-2016.pdf"
URL="https://ntrs.nasa.gov/api/citations/20170001761/downloads/20170001761.pdf"
SHA="3153ae2e53e29452d5997efafe280a5f05cd21b43a047e988a17e1dd5207a38e"
SOURCE="nasa-se-2016-rev2"


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def normalize(text):
    return " ".join(text.translate(str.maketrans({"‑":"-","–":"-","−":"-","‐":"-"})).split())


def pieces(text,limit=1100,overlap=120):
    text=normalize(text)
    start=0
    while start<len(text):
        end=min(start+limit,len(text))
        if end<len(text):
            boundary=text.rfind(" ",start+limit//2,end)
            if boundary>start:end=boundary
        yield text[start:end]
        if end==len(text):break
        start=max(start+1,end-overlap)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase",choices=("render","index"),required=True)
    args=parser.parse_args()
    if not PDF.exists():
        PDF.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(URL,timeout=90) as response:PDF.write_bytes(response.read(35_000_000))
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA,"Snapshot PDF thay đổi; cần rà phiên bản mới."
    import fitz
    doc=fitz.open(PDF)
    assert len(doc)>=100
    if args.phase=="render":
        directory=DATA/"review";directory.mkdir(exist_ok=True)
        for i,page in enumerate(doc):
            target=directory/f"page-{i+1}.png"
            if not target.exists():page.get_pixmap(matrix=fitz.Matrix(1.6,1.6)).save(target)
            if (i+1)%50==0:print(f"Rendered {i+1}/{len(doc)}",flush=True)
        return
    readings_path=ROOT/"advanced/visual_readings.json"
    readings=json.loads(readings_path.read_text(encoding="utf-8")) if readings_path.exists() else []
    notes={row["reference"]:row for row in readings}
    nodes=[];page_stats=[];all_regions=[]
    for i,page in enumerate(doc):
        n=i+1;bounds=[round(v,2) for v in page.rect]
        native=page.get_text(sort=True)
        ocr_path=DATA/f"review/page-{n}.ocr.json"
        assert ocr_path.exists(),f"Chưa OCR trang {n}."
        ocr=json.loads(ocr_path.read_text(encoding="utf-8-sig"))
        refs=[]
        for line in native.splitlines():
            line=normalize(line)
            match=re.match(r"^(Figure|Table)\s+([A-Z0-9]+\.[0-9]+-?[0-9]*)\s+(.+)",line)
            if match and i>=13 and match[3][:1].isupper() and not re.search(r"\.{4}|shows|provides|illustrates|taken from",match[3]):
                refs.append({"kind":"figure" if match[1]=="Figure" else "table", "reference":match[1]+" "+match[2],"caption":line,"bbox":bounds,"region_precision":"full_page_with_caption"})
        def add(kind,text,bbox=None,reference="",extra=None):
            for part in pieces(text):
                identifier=f"nasa_p{n:03d}_{kind}_{len(nodes):05d}"
                prefix=f"NASA SE Handbook Rev 2 | PDF page {n} | {reference} | {kind}\n"
                nodes.append({"id":identifier,"source_id":SOURCE,"source":URL+f"#page={n}","page":n,
                              "text":prefix+part,"metadata":{"kind":kind,"reference":reference,
                              "bbox":bbox or bounds,"pdf_page":n,"coordinate_system":"PDF points, top-left origin",
                              "page_char_start":len(nodes),"license":"Public Use Permitted (NTRS)",**(extra or {})}})
        add("text",native)
        # Mọi trang đều có OCR và vị trí nhãn, kể cả chữ nằm trong ảnh raster.
        lines=[]
        for line in ocr["lines"]:
            words=line["words"]
            if words:
                x=min(w["x"] for w in words)/ocr["width"]*page.rect.width
                y=min(w["y"] for w in words)/ocr["height"]*page.rect.height
                lines.append(f"[x={x:.0f}, y={y:.0f}] {line['text']}")
        if page.get_images() or refs or "Table" in native:
            add("ocr_layout","\n".join(lines),extra={"ocr_engine":ocr["engine"]})
        found=[]
        if "Table" in native and i>=13:
            try:
                found=page.find_tables().tables
                for table in found:
                    rows=table.extract()
                    if len(rows)<2:continue
                    header=[normalize(cell or "") for cell in rows[0]]
                    ref=next((r["reference"] for r in refs if r["kind"]=="table"),"")
                    for row_number,row in enumerate(rows[1:],1):
                        cells=[f"{header[j] or 'Column '+str(j+1)} = {normalize(cell or '')}" for j,cell in enumerate(row)]
                        add("table",f"{ref}; row {row_number}: "+" | ".join(cells),[round(v,2) for v in table.bbox],ref,
                            {"row":row_number,"columns":header,"extraction":"native_grid_cells"})
            except Exception as error:
                found=[]
                page_stats.append({"page":n,"table_parser_warning":type(error).__name__,"fallback":"native text + full-page OCR layout"})
        for region in refs:
            # Reference/caption plus label layout and explanatory source text, all derived before benchmark.
            add(region["kind"],region["caption"]+"\n"+native+"\nLabel layout:\n"+"\n".join(lines),reference=region["reference"],extra={"region_precision":region["region_precision"]})
            if region["reference"] in notes:
                note=notes[region["reference"]]
                assert note["page"]==n
                add("visual_reading",note["description"],note["bbox"],region["reference"],{"reading_origin":"source_checked_visual_description","student_confirmed":False})
            all_regions.append({"page":n,**region})
        page_stats.append({"page":n,"native_chars":len(native),"ocr_chars":len(ocr["text"]),"raster_images":len(page.get_images()),
                           "tables_detected":len(found),"regions":len(refs),"indexed":bool(native.strip() or ocr["text"].strip())})
        if n%50==0:print(f"Indexed {n}/{len(doc)}",flush=True)
    save(DATA/"chunks.json",nodes)
    save(DATA/"regions.json",all_regions)
    save(DATA/"page_audit.json",page_stats)
    save(DATA/"manifest.json",{"source_id":SOURCE,"title":"NASA Systems Engineering Handbook, Revision 2",
         "report_number":"NASA/SP-2016-6105 Rev 2","publication_date":"2017-02-17","source_url":"https://ntrs.nasa.gov/citations/20170001761",
         "download_url":URL,"pdf_sha256":SHA,"physical_pages":len(doc),"license":"Public Use Permitted (NTRS record)",
         "pages_processed":len(doc),"page_labels":"Gold uses 1-based physical PDF pages; printed numbers differ by front matter.",
         "chunks":len(nodes),"kinds":dict(Counter(c["metadata"]["kind"] for c in nodes)),"regions":len(all_regions),
         "ocr":"Windows.Media.Ocr en-US; all 356 page renders; original PDF and crops stay local.",
         "limitations":["OCR is not automatically correct; table/image/chart benchmark must be checked against renders.",
                         "Full-page region bounds are conservative; figure/table identifiers locate the exact visual.",
                         "Arbitrary arrow connectivity and dense curves are not reconstructed automatically.",
                         "Source-checked visual descriptions are separate from gold and remain proposed until student review."]})
    print("Index complete:",len(nodes),"nodes;",len(all_regions),"regions",flush=True)


if __name__=="__main__":main()
