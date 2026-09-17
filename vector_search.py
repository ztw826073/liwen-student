"""选做：小知识库的向量检索。先运行 python vector_search.py 建索引。"""
import hashlib
import json
import math
import tomllib
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from core import DATA, ROOT, load_chunks

INDEX = DATA / "vectors.json"


def fingerprint(chunks, cfg):
    value = {
        "chunks": chunks,
        "model": cfg["EMBED_MODEL"],
        "base": cfg["BASE_URL"],
    }
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def embedding(text, cfg):
    key = str(cfg.get("API_KEY", "")).strip()
    base = str(cfg.get("BASE_URL", "")).strip().rstrip("/")
    model = str(cfg.get("EMBED_MODEL", "")).strip()
    if not key or not base.startswith("https://") or not model:
        raise ValueError("请配置 API_KEY、https 开头的 BASE_URL 和 EMBED_MODEL")
    body = {"model": model, "input": [text], "encoding_format": "float"}
    request = Request(
        base + "/embeddings",
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            vector = json.load(response)["data"][0]["embedding"]
    except HTTPError as error:
        raise RuntimeError(f"向量服务 HTTP {error.code}，见排错表")
    except (URLError, TimeoutError):
        raise RuntimeError("向量服务连接失败或超时")
    norm = math.sqrt(sum(float(v) ** 2 for v in vector))
    if not norm or not math.isfinite(norm):
        raise ValueError("向量为空或数值不合法")
    return [float(v) / norm for v in vector]


def build_index(cfg):
    chunks = load_chunks()
    rows = []
    for i, c in enumerate(chunks):
        vector = embedding(c["title"] + "\n" + c["text"], cfg)
        rows.append({"id": c["id"], "vector": vector})
        print(f"已完成 {i + 1}/{len(chunks)}")
    result = {"fingerprint": fingerprint(chunks, cfg), "rows": rows}
    temporary = INDEX.with_suffix(".tmp")
    temporary.write_text(json.dumps(result), encoding="utf-8")
    temporary.replace(INDEX)
    print("索引已保存：", INDEX)


def retrieve_vector(question, chunks, cfg, k=4):
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    if data["fingerprint"] != fingerprint(chunks, cfg):
        raise ValueError("知识库或向量配置已改变，请重建向量索引")
    query = embedding(question, cfg)
    mapping = {c["id"]: c for c in chunks}
    ranked = []
    for row in data["rows"]:
        if len(row["vector"]) != len(query):
            raise ValueError("向量维度不同，请检查模型并重建")
        score = sum(a * b for a, b in zip(query, row["vector"]))
        ranked.append((score, mapping[row["id"]]))
    ranked.sort(key=lambda item: item[0], reverse=True)
    # 分数仅用于排序，不代表回答正确率；无关证据由回答流程判别。
    return [dict(c, score=round(s, 4)) for s, c in ranked[:k]]


if __name__ == "__main__":
    cfg = tomllib.loads(
        (ROOT / ".streamlit/secrets.toml").read_text(encoding="utf-8"))
    build_index(cfg)
