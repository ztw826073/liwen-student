"""合并已审核文件；不覆盖原 knowledge.json，会先备份。"""
import json
import sys
from datetime import datetime
from pathlib import Path

target = Path("data/knowledge.json")
if len(sys.argv) != 2:
    raise SystemExit("用法：python merge_kb.py data/pending/DOC001.json")
records = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
if not records or any(d.get("approved") is not True for d in records):
    raise SystemExit("存在未审核资料，请审核后再合并")
old = json.loads(target.read_text(encoding="utf-8-sig"))
ids = [d["id"] for d in old + records]
if len(ids) != len(set(ids)):
    raise SystemExit("资料编号重复；更新旧资料请先停机备份再人工替换")
stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
backup = target.with_name("knowledge_backup_" + stamp + ".json")
backup.write_bytes(target.read_bytes())
combined = json.dumps(old + records, ensure_ascii=False, indent=2)
temporary = target.with_suffix(".tmp")
temporary.write_text(combined, encoding="utf-8")
temporary.replace(target)
print("合并成功。备份：", backup)
