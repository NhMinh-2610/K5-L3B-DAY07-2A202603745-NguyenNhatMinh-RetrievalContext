"""Tạo vector thật local cho index bonus, không gọi API hay ghi database Day 6."""
import argparse
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.document_store import DocumentStore

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day6",required=True,type=Path)
    args=parser.parse_args()
    store=DocumentStore(ROOT/"starter/data/advanced",args.day6.resolve())
    print("Vector store ready:",store.vectors.shape,"model signature:",store.embedder.signature)
