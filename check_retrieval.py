"""运行：python check_retrieval.py data/dev_questions.json 4"""
import json
import sys
from core import load_chunks, retrieve

questions = json.load(open(sys.argv[1], encoding="utf-8-sig"))
k = int(sys.argv[2]) if len(sys.argv) > 2 else 4
chunks = load_chunks()
available = {c["doc_id"] for c in chunks}
correct = total = 0
for q in questions:
    # 无依据的问题单独统计，不混入有依据问题的命中率。
    if not q["expected_docs"]:
        print(q["id"], "无依据")
        continue
    missing = set(q["expected_docs"]) - available
    if missing:
        print(q["id"], "资料未启用", sorted(missing))
        continue
    hits = retrieve(q["question"], chunks, k)
    found = {h["doc_id"] for h in hits}
    ok = bool(found & set(q["expected_docs"]))
    total += 1
    correct += int(ok)
    print(q["id"], "命中" if ok else "未命中", sorted(found))
if total:
    print(f"Hit@{k}: {correct}/{total} = {correct / total:.1%}")
else:
    print("没有可评价的有依据问题")
