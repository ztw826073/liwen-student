"""运行：python check_project.py。只使用临时数据库。"""
import json
import tempfile
import gc
import time
from pathlib import Path
from auth import make_hash, verify
from core import (
    answer, create_issue, create_task, get_run, init_db, list_issues,
    list_tasks, load_chunks, retrieve, save_run, update_task, validate_answer,
)

chunks = load_chunks()
assert chunks, "没有已审核资料"
# 有教学卡时沿用 DEMO001；已换成文献问答则检查 DOC001。
demo_ids = {c["doc_id"] for c in chunks}
if "DEMO001" in demo_ids:
    question = "板栗批次记录需要填写哪些信息"
    expected = "DEMO001"
else:
    question = "评价板栗的糯性品质，可以参考哪些指标"
    expected = "DOC001"
hits = retrieve(question, chunks)
assert hits and hits[0]["doc_id"] == expected
assert retrieve("火星轨道计算方法", chunks) == []
result = answer(question, "", hits, {"MODE": "demo"})
assert result["status"] == "ok"
try:
    validate_answer({"status": "ok", "claims": [
        {"text": "错误引用", "refs": ["NOT_REAL"]}]}, hits)
    raise AssertionError("伪造引用未被拦截")
except ValueError:
    pass

# ========== 外层：单独文件夹放数据库 test.db，变量名 db_folder ==========
with tempfile.TemporaryDirectory() as db_folder:
    db = Path(db_folder) / "test.db"
    init_db(db)
    run = {"question": "批次记录", "hits": hits, "result": result}
    rid = save_run("student1", run, db)
    assert get_run("student2", rid, db) is None
    assert create_task("student1", rid, 0, "核对", "核对四项", "", db)
    assert not create_task("student1", rid, 0, "核对", "核对四项", "", db)
    tasks = list_tasks("student1", db)
    assert len(tasks) == 1 and not list_tasks("student2", db)
    assert not update_task("student2", tasks[0]["id"], "已完成", "", db)
    assert update_task("student1", tasks[0]["id"], "已完成", "已核对", db)
    assert list_tasks("student1", db)[0]["state"] == "已完成"

    version = {"app": "liwen-1", "kb": "testhash", "mode": "demo", "model": ""}
    snapshot = {
        "question": "批次记录", "actual": result, "evidence": hits,
        "version": version, "layer": "检索",
    }
    try:
        create_issue("student1", dict(snapshot, note="模型不行"), db)
        raise AssertionError("空泛归因未被拦截")
    except ValueError:
        pass
    iid = create_issue("student1", dict(
        snapshot, note="检索未带回 DEMO001，应检查分块或匹配词",
        expected="命中 DEMO001"), db)
    assert list_issues("student2", db) == []
    rows = list_issues("student1", db)
    assert rows[0]["id"] == iid and rows[0]["layer"] == "检索"
    rec = rows[0]["record"]
    assert rec["question"] == "批次记录"
    assert rec["actual"]["status"] == "ok"
    assert rec["evidence"] and rec["version"]["kb"] == "testhash"

    # ========== 内层：全新独立临时文件夹 json_folder，专门放 off.json ==========
    with tempfile.TemporaryDirectory() as json_folder:
        docs = [{"id": "OFF", "approved": False}]
        off = Path(json_folder) / "off.json"
        off.write_text(json.dumps(docs), encoding="utf-8")
        assert load_chunks(off) == []

    assert get_run("student1", rid, db)["hits"][0]["text"]
    # 全部数据库操作结束，回收连接释放锁
    gc.collect()
    time.sleep(0.5)

hashed = make_hash("Classroom_Test_2026")
assert verify("Classroom_Test_2026", hashed)
assert not verify("wrong", hashed)
print("PASS：检索、无资料、引用、隔离、去重、持久化、停用、密码、问题登记")