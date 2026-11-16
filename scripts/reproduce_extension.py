"""Chạy lại nghiên cứu trong thư mục mới, không ghi đè kết quả đã chốt."""
import argparse
import importlib
import sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope",choices=("basic-v2","advanced"),required=True)
    parser.add_argument("--name",required=True,help="Tên mới, ví dụ nasa-reproduction-01")
    args,remaining=parser.parse_known_args()
    if not args.name.replace("-","").replace("_","").isalnum():parser.error("Tên chỉ dùng chữ, số, dấu - hoặc _.")
    if args.name in ("basic-v2","advanced","advanced-v2"):
        parser.error("Chọn tên mới để giữ nguyên các nghiên cứu đã lưu.")
    module=importlib.import_module("run_basic_v2" if args.scope=="basic-v2" else "run_advanced")
    root=Path(__file__).resolve().parents[1]
    module.OUT=root/"results/extension"/args.name
    sys.argv=[sys.argv[0],*remaining]
    module.main()


if __name__=="__main__":main()
