"""
命令行：
    python extract_excel_qa.py 文件.xlsx 文献编号

功能：
    将“论文人工整理”Excel中的问答记录提取为 JSON。
    默认读取“人工整理”工作表，按列名：
    原文件名、研究方向、问题、答案、出处页码

输出：
    data/pending/DOC001.json

JSON结构示例：
[
  {
    "id": "DOC001",
    "title": "板栗淀粉糊化特性与淀粉粒粒径及直链淀粉含量的关系_梁丽松",
    "source": "板栗淀粉糊化特性与淀粉粒粒径及直链淀粉含量的关系_梁丽松.pdf",
    "scope": "加工与品质",
    "approved": false,
    "demo": false,
    "qa": [
      {
        "question": "评价板栗的糯性品质，可以参考哪些指标？",
        "answer": "可以参考直链淀粉含量和淀粉糊化峰值黏度。...",
        "source_pages": "第1页摘要；\\n第8页结论"
      }
    ],
    "pages": [
      {
        "page": 1,
        "text": "问题\\n答案\\n出处：第1页摘要"
      }
    ]
  }
]
"""

import json
import sys
from pathlib import Path

from openpyxl import load_workbook
from core import qa_to_pages


REQUIRED_COLUMNS = ["原文件名", "研究方向", "问题", "答案", "出处页码"]
OVERVIEW_COLUMNS = [
    "论文标题(中文)", "作者", "期刊名称", "年份",
    "关键词", "研究主题", "摘要/主要内容",
]


def clean(value):
    """把 Excel 单元格转成干净字符串；空单元格返回空字符串。"""
    if value is None:
        return ""
    return str(value).strip()


def next_doc_id(doc_id, offset):
    prefix = "".join(ch for ch in doc_id if ch.isalpha()) or "DOC"
    digits = "".join(ch for ch in doc_id if ch.isdigit()) or "1"
    width = max(len(digits), 3)
    return prefix + str(int(digits) + offset).zfill(width)


def paper_page(row, col):
    title = clean(row[col["论文标题(中文)"]])
    authors = clean(row[col["作者"]]) if "作者" in col else ""
    journal = clean(row[col["期刊名称"]]) if "期刊名称" in col else ""
    year = clean(row[col["年份"]]) if "年份" in col else ""
    pages = clean(row[col["页码"]]) if "页码" in col else ""
    doi = clean(row[col["文章编号/DOI"]]) if "文章编号/DOI" in col else ""
    keywords = clean(row[col["关键词"]]) if "关键词" in col else ""
    topic = clean(row[col["研究主题"]]) if "研究主题" in col else ""
    abstract = clean(row[col["摘要/主要内容"]]) if "摘要/主要内容" in col else ""
    text = "\n".join(part for part in [
        "标题：" + title,
        "作者：" + authors if authors else "",
        "期刊：" + " ".join(x for x in (journal, year, pages) if x),
        "DOI：" + doi if doi else "",
        "关键词：" + keywords if keywords else "",
        "研究主题：" + topic if topic else "",
        "摘要：" + abstract if abstract else "",
    ] if part)
    return title, topic, journal, year, text


def excel_point(source, sheet, row_no, seq="", item=""):
    loc = {
        "file": Path(source).name,
        "sheet": sheet,
        "row": int(row_no),
    }
    if seq:
        loc["seq"] = str(seq)
    if item:
        loc["item"] = str(item)
    return loc


def extract_overview(ws, start_id, source: Path):
    rows = ws.iter_rows(values_only=True)
    try:
        headers = [clean(x) for x in next(rows)]
    except StopIteration:
        raise SystemExit("Excel为空，无法提取。")
    missing = [c for c in OVERVIEW_COLUMNS if c not in headers]
    if missing:
        raise SystemExit(
            "汇总表缺少必要列：" + "、".join(missing)
        )
    col = {name: headers.index(name) for name in headers if name}
    records = []
    for row_no, row in enumerate(rows, start=2):
        row = list(row) + [None] * max(0, len(headers) - len(row))
        title, topic, journal, year, text = paper_page(row, col)
        if not title and not text:
            continue
        if not text:
            print(f"警告：第{row_no}行缺少摘要，已跳过。")
            continue
        doc_id = next_doc_id(start_id, len(records))
        seq = clean(row[col["序号"]]) if "序号" in col else str(row_no)
        loc = excel_point(source, ws.title, row_no, seq=seq)
        records.append({
            "id": doc_id,
            "title": title or doc_id,
            "source": source.name + "｜" + (journal or title),
            "scope": topic or "板栗文献",
            "approved": True,
            "demo": False,
            "excel": loc,
            "pages": [{"page": 1, "text": text, "excel": loc}],
        })
    if not records:
        raise SystemExit("汇总表没有可导入的论文记录。")
    return records


def extract_qa(ws, source: Path, doc_id: str):
    rows = ws.iter_rows(values_only=True)
    try:
        headers = [clean(x) for x in next(rows)]
    except StopIteration:
        raise SystemExit("Excel为空，无法提取。")

    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise SystemExit(
            "缺少必要列：" + "、".join(missing)
            + "\n需要的列为：" + "、".join(REQUIRED_COLUMNS)
        )

    col = {name: headers.index(name) for name in REQUIRED_COLUMNS}
    qa = []
    source_name = ""
    scope = ""

    for row_no, row in enumerate(rows, start=2):
        row = list(row) + [None] * max(0, len(headers) - len(row))

        source_file = clean(row[col["原文件名"]])
        direction = clean(row[col["研究方向"]])
        question = clean(row[col["问题"]])
        answer = clean(row[col["答案"]])
        source_pages = clean(row[col["出处页码"]])

        if not any([source_file, direction, question, answer, source_pages]):
            continue

        if not question or not answer:
            print(f"警告：第{row_no}行缺少“问题”或“答案”，已跳过。")
            continue

        if not source_name:
            source_name = source_file
        if not scope:
            scope = direction

        qa.append({
            "question": question,
            "answer": answer,
            "source_pages": source_pages,
            "excel": excel_point(source, ws.title, row_no),
        })

    record = {
        "id": doc_id,
        "title": source.stem,
        "source": source_name or "待补充原文件名",
        "scope": scope or "待补充研究方向",
        "approved": False,
        "demo": False,
        "qa": qa,
        "pages": qa_to_pages(qa),
    }
    if qa:
        record["excel"] = excel_point(source, ws.title, qa[0]["excel"]["row"])
    return [record]


def colmap(headers):
    return {name: i for i, name in enumerate(headers) if name}


def cell(row, col, name):
    if name not in col:
        return ""
    idx = col[name]
    if idx >= len(row):
        return ""
    return clean(row[idx])


def extract_kb110(wb, start_id, source: Path):
    ws = wb["论文总表"]
    rows = ws.iter_rows(values_only=True)
    try:
        headers = [clean(x) for x in next(rows)]
    except StopIteration:
        raise SystemExit("论文总表为空。")
    col = colmap(headers)
    if "序号" not in col or "标题中文" not in col:
        raise SystemExit("论文总表需要“序号”和“标题中文”列。")
    papers = {}
    for row_no, row in enumerate(rows, start=2):
        row = list(row or [])
        seq = cell(row, col, "序号")
        title = cell(row, col, "标题中文") or cell(row, col, "标题原文")
        if not seq or not title:
            continue
        text = "\n".join(part for part in [
            "标题：" + title,
            "原文标题：" + cell(row, col, "标题原文"),
            "作者：" + cell(row, col, "作者"),
            "来源：" + " ".join(x for x in (
                cell(row, col, "期刊/来源"), cell(row, col, "年份"),
                cell(row, col, "语言")) if x),
            "文件名：" + cell(row, col, "文件名"),
            "分类：" + " / ".join(x for x in (
                cell(row, col, "一级分类"), cell(row, col, "二级方向")) if x),
            "关键词：" + cell(row, col, "关键词"),
            "研究材料：" + cell(row, col, "研究材料"),
            "研究方法：" + cell(row, col, "研究方法"),
            "核心结论：" + cell(row, col, "核心结论"),
            "关键数据：" + cell(row, col, "关键数据"),
            "实践应用价值：" + cell(row, col, "实践应用价值"),
            "摘要：" + cell(row, col, "摘要中文"),
        ] if "：" in part and not part.endswith("："))
        papers[seq] = {
            "title": title,
            "file": cell(row, col, "文件名"),
            "scope": cell(row, col, "一级分类") or "板栗文献",
            "source": cell(row, col, "期刊/来源") or cell(row, col, "文件名"),
            "text": text,
            "excel": excel_point(source, ws.title, row_no, seq=seq),
        }

    items = {}
    if "知识条目" in wb.sheetnames:
        ws2 = wb["知识条目"]
        rows2 = ws2.iter_rows(values_only=True)
        headers2 = [clean(x) for x in next(rows2, [])]
        col2 = colmap(headers2)
        for row_no, row in enumerate(rows2, start=2):
            row = list(row or [])
            src = cell(row, col2, "来源序号")
            topic = cell(row, col2, "知识点主题")
            content = cell(row, col2, "知识内容")
            if not src or not content:
                continue
            scene = cell(row, col2, "适用场景")
            paper_title = cell(row, col2, "论文标题中文")
            page_text = "\n".join(part for part in [
                "知识点：" + topic if topic else "",
                "适用场景：" + scene if scene else "",
                "来源论文：" + paper_title if paper_title else "",
                content,
            ] if part)
            items.setdefault(src, []).append({
                "text": page_text,
                "excel": excel_point(
                    source, ws2.title, row_no, seq=src,
                    item=cell(row, col2, "条目序号")),
            })

    seqs = sorted(papers, key=lambda s: int(s) if str(s).isdigit() else 0)
    records = []
    for seq in seqs:
        paper = papers[seq]
        pages = [{"page": 1, "text": paper["text"], "excel": paper["excel"]}]
        for i, item in enumerate(items.get(seq, []), start=2):
            pages.append({
                "page": i, "text": item["text"], "excel": item["excel"],
            })
        records.append({
            "id": next_doc_id(start_id, len(records)),
            "title": paper["title"],
            "source": source.name + "｜" + (paper["source"] or paper["file"]),
            "scope": paper["scope"],
            "approved": True,
            "demo": False,
            "excel": paper["excel"],
            "pages": pages,
        })
    if not records:
        raise SystemExit("知识库没有可导入的论文记录。")
    return records


def extract_excel(source: Path, doc_id: str):
    wb = load_workbook(source, data_only=True, read_only=True)
    if "论文总表" in wb.sheetnames:
        return extract_kb110(wb, doc_id, source)
    if "论文总览" in wb.sheetnames:
        return extract_overview(wb["论文总览"], doc_id, source)
    if "人工整理" in wb.sheetnames:
        return extract_qa(wb["人工整理"], source, doc_id)
    return extract_qa(wb[wb.sheetnames[0]], source, doc_id)


def main():
    if len(sys.argv) != 3:
        raise SystemExit(
            "用法：python extract_excel_qa.py 文件.xlsx DOC001"
        )

    source = Path(sys.argv[1])
    doc_id = sys.argv[2]

    if source.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise SystemExit("请输入 .xlsx 或 .xlsm Excel 文件。")

    if not source.exists():
        raise SystemExit(f"文件不存在：{source}")

    if not doc_id.isalnum():
        raise SystemExit(
            "文献编号只用英文字母和数字，例如 DOC001"
        )

    records = extract_excel(source, doc_id)

    out = Path("data") / "pending"
    out.mkdir(parents=True, exist_ok=True)
    target = out / (doc_id + ".json")

    if target.exists():
        raise SystemExit(
            f"同编号待审核文件已存在：{target}，"
            "请更换编号或先人工归档。"
        )

    target.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    if records and "qa" in records[0]:
        print(f"已提取 {len(records[0]['qa'])} 条QA问答。")
    else:
        print(f"已提取 {len(records)} 篇论文。")
        if len(records) <= 15:
            for rec in records:
                print(rec["id"], rec["title"])
        else:
            print(records[0]["id"], records[0]["title"])
            print("...")
            print(records[-1]["id"], records[-1]["title"])
    print("已生成待审核文件：", target)
    print("尚未加入正式知识库，必须先人工核对。")

if __name__ == "__main__":
    main()
