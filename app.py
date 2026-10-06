import html
import json
import time
from pathlib import Path

import streamlit as st

from auth import verify
from core import (
    answer, create_issue, create_task, evidence_snapshot, get_run,
    init_db, list_issues, list_tasks, load_cfg, load_chunks, make_version,
    recognize_image, retrieve, save_run, update_task, use_api,
)
from vector_search import retrieve_vector

st.set_page_config(page_title="栗问", page_icon="🌰", layout="wide",
                   initial_sidebar_state="expanded")

PAGES = [
    ("chat", "知识问答"),
    ("tasks", "我的任务"),
    ("issues", "问题登记"),
    ("docs", "资料目录"),
]
SUGGESTIONS = [
    "板栗批次记录需要填写哪些信息？",
    "采收后如何做短期贮藏？",
    "贮藏前需要核对哪些条件？",
]


def inject_css(logged_in):
    hide_side = "" if logged_in else """
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
        display: none !important;
    }
    """
    st.markdown(f"""
<style>
html, body, [data-testid="stAppViewContainer"], .stApp {{
    background: #ffffff !important;
    color: #0d0d0d;
    font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}}
#MainMenu, footer, [data-testid="stHeader"], [data-testid="stToolbar"] {{
    display: none !important;
}}
[data-testid="stSidebar"] {{
    background: #f9fafb !important;
    border-right: 1px solid #ececec;
    min-width: 260px !important;
    width: 260px !important;
}}
[data-testid="stSidebar"] > div:first-child {{
    width: 260px !important;
}}
[data-testid="stSidebarContent"] {{
    padding: 16px 12px 12px;
}}
section.main > div.block-container {{
    max-width: 1180px;
    padding-top: 20px;
    padding-bottom: 120px;
}}
{hide_side}

.ds-brand {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 8px 14px;
}}
.ds-mark {{
    width: 32px;
    height: 32px;
    border-radius: 10px;
    background: #4d6bfe;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 16px;
}}
.ds-brand b {{ font-size: 18px; letter-spacing: .02em; }}
.ds-brand span {{ display: block; color: #8a8a8a; font-size: 12px; font-weight: 400; }}

[data-testid="stSidebar"] [data-testid="stRadio"] label {{
    border-radius: 10px;
    padding: 8px 12px;
    margin: 2px 0;
    font-size: 14px;
    cursor: pointer;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {{
    background: #ececec;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {{
    background: #e8eaf0;
    font-weight: 600;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] div[data-baseweb="radio"] > div:first-child {{
    display: none;
}}

.ds-user {{
    margin-top: 18px;
    padding: 10px 12px;
    border-radius: 12px;
    color: #5c5c5c;
    font-size: 13px;
}}
.ds-hero {{
    text-align: center;
    padding: 72px 12px 12px;
}}
.ds-hero .ds-mark {{
    width: 56px;
    height: 56px;
    border-radius: 16px;
    margin: 0 auto 18px;
    font-size: 26px;
}}
.ds-hero h1 {{
    font-size: 30px;
    font-weight: 600;
    margin: 0;
    letter-spacing: .01em;
}}
.ds-hero p {{ color: #8b8b8b; margin: 10px 0 0; font-size: 14px; }}

.ds-row {{
    display: flex;
    margin: 18px 0;
}}
.ds-row.user {{ justify-content: flex-end; }}
.ds-bubble {{
    max-width: 78%;
    background: #f4f4f5;
    border-radius: 16px;
    padding: 12px 16px;
    line-height: 1.65;
    white-space: pre-wrap;
}}
.ds-assist {{
    display: flex;
    gap: 12px;
    align-items: flex-start;
    margin: 8px 0 4px;
}}
.ds-assist .ds-mark {{
    width: 28px;
    height: 28px;
    border-radius: 8px;
    flex: none;
    font-size: 14px;
}}
.ds-meta {{ color: #8b8b8b; font-size: 12px; margin: 0 0 8px; }}

[data-testid="stChatInput"] {{
    background: linear-gradient(#fff, #fff) padding-box;
    padding-bottom: 12px;
}}
[data-testid="stChatInput"] > div {{
    border: 1px solid #e6e6e6 !important;
    border-radius: 24px !important;
    box-shadow: 0 8px 28px rgba(0, 0, 0, .06);
    background: #fff;
}}
[data-testid="stChatInput"] textarea {{
    font-size: 16px !important;
    color: #0d0d0d;
}}
[data-testid="stSidebar"] .stButton > button {{
    width: 100%;
    border-radius: 12px;
    border: 1px solid #e5e5e5;
    background: #fff;
    color: #0d0d0d;
    font-weight: 600;
    box-shadow: 0 1px 2px rgba(0,0,0,.04);
    text-align: left;
    padding: 0.55rem 0.9rem;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    border-color: #d0d0d0;
    color: #0d0d0d;
    background: #fff;
}}
[data-testid="stSidebar"] [data-testid="stButton"]:last-of-type > button {{
    border: none;
    background: transparent;
    box-shadow: none;
    color: #666;
    font-weight: 500;
    text-align: center;
}}
div[data-testid="stExpander"] {{
    border: 1px solid #eee;
    border-radius: 12px;
    background: #fafafa;
}}
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {{
    border-radius: 12px !important;
}}
button[kind="primary"], button[data-testid="stBaseButton-primary"] {{
    background: #4d6bfe !important;
    border: none !important;
    color: #fff !important;
    border-radius: 12px !important;
}}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {{
    background: #3d5bef !important;
    color: #fff !important;
}}
.login-wrap {{
    max-width: 400px;
    margin: 12vh auto 0;
    text-align: center;
}}
.login-wrap h1 {{ font-size: 28px; font-weight: 600; margin: 12px 0 4px; }}
.login-wrap p {{ color: #8b8b8b; margin-bottom: 8px; }}
</style>
""", unsafe_allow_html=True)


def show_evidence(hit):
    label = f'{hit["title"]}｜PDF页序 {hit["page"]}'
    with st.expander(label):
        st.caption("来源：" + str(hit.get("source") or ""))
        if hit.get("scope"):
            st.caption("适用条件：" + hit["scope"])
        st.text(hit.get("text") or "")
        st.caption("片段编号：" + str(hit.get("id") or ""))


def run_question(question, context, general, owner, chunks, cfg, image=None):
    st.session_state.pop("draft_no", None)
    if (any(w in question for w in ("贮藏", "保存", "储存"))
            and not context.strip() and not general):
        st.session_state.storage_hint = True
    started = time.perf_counter()
    vision = None
    search_q = question
    extra = context
    if image:
        try:
            vision = recognize_image(
                cfg, image["bytes"], image.get("mime", ""), question)
        except Exception as error:
            st.session_state.messages.append({
                "role": "assistant",
                "error": "图片识别失败：" + str(error)[:160],
            })
            return
        extra = "\n".join(part for part in (
            context.strip(), "图片识别：" + vision["text"]) if part)
        if not search_q.strip():
            search_q = vision["text"][:200]
            question = "请根据这张图片，结合知识库给出建议。"
        else:
            search_q = question + " " + vision["text"][:400]
    try:
        hits = retrieve_vector(search_q, chunks, cfg, k=4)
    except Exception:
        hits = retrieve(search_q, chunks, 4)
    try:
        result = answer(question, extra, hits, cfg)
    except Exception as error:
        st.session_state.messages.append({
            "role": "assistant",
            "error": "本次未生成可用回答：" + str(error)[:160],
        })
        return
    payload = {
        "question": question, "context": extra,
        "hits": hits, "result": result,
        "mode": cfg.get("MODE", "demo"),
        "model": cfg.get("MODEL", ""),
        "seconds": round(time.perf_counter() - started, 2),
    }
    if vision:
        payload["vision"] = {
            "text": vision["text"],
            "returned_model": vision.get("returned_model", ""),
        }
        result.setdefault("limitations", "")
    rid = save_run(owner, payload)
    saved = dict(payload, run_id=rid)
    st.session_state.last = saved
    st.session_state.messages.append({
        "role": "assistant",
        "payload": saved,
    })


def render_sources(payload):
    st.markdown("### 检索来源")
    if not payload:
        st.caption("提问后，检索到的资料会显示在这里。")
        return
    hits = payload.get("hits") or []
    claims = (payload.get("result") or {}).get("claims") or []
    cited = {}
    for i, claim in enumerate(claims, start=1):
        for ref in claim.get("refs") or []:
            cited.setdefault(ref, []).append(str(i))
    if not hits:
        st.info("这次没有检索到资料片段。")
        return
    st.caption(f"共 {len(hits)} 条，对应左侧回答中的引用。")
    for n, hit in enumerate(hits, start=1):
        pages = "、".join(cited.get(hit.get("id"), []))
        tag = f"建议 {pages}" if pages else "本次检索，回答未直接引用"
        st.markdown(f"**{n}. {hit.get('title') or '资料'}**")
        st.caption(f"PDF页序 {hit.get('page')} · {tag}")
        if hit.get("source"):
            st.caption("来源：" + str(hit["source"]))
        if hit.get("scope"):
            st.caption("适用条件：" + str(hit["scope"]))
        st.text(hit.get("text") or "")
        st.caption("片段编号：" + str(hit.get("id") or ""))
        st.divider()


def page_chat(owner, chunks, cfg):
    messages = st.session_state.messages
    if messages:
        answer_col, source_col = st.columns(2, gap="large")
    else:
        answer_col, source_col = st.container(), None
    with answer_col:
        if messages:
            st.markdown("### 回答")
        if not messages:
            st.markdown("""
<div class="ds-hero">
  <div class="ds-mark">栗</div>
  <h1>今天有什么可以帮到你？</h1>
  <p>当前范围：采收与贮藏。每次提问请写完整问题。</p>
</div>
""", unsafe_allow_html=True)
            for text in SUGGESTIONS:
                if st.button(text, use_container_width=True):
                    st.session_state.pending_q = text
                    st.rerun()

        if st.session_state.pop("storage_hint", False):
            st.info("建议补充销售时间目标和现有设施；未知可写未知。本次仍继续查询。")

        for index, msg in enumerate(messages):
            if msg["role"] == "user":
                extra = ""
                if msg.get("context"):
                    extra = "\n\n补充：" + msg["context"]
                if msg.get("image"):
                    st.image(msg["image"], width=280)
                st.markdown(
                    f'<div class="ds-row user"><div class="ds-bubble">'
                    f'{html.escape((msg.get("text") or "请识别这张图片") + extra)}</div></div>',
                    unsafe_allow_html=True)
                continue
            st.markdown(
                '<div class="ds-assist"><div class="ds-mark">栗</div><div>',
                unsafe_allow_html=True)
            if msg.get("error"):
                st.error(msg["error"])
                st.markdown("</div></div>", unsafe_allow_html=True)
                continue
            payload = msg["payload"]
            result = payload["result"]
            if result.get("returned_model"):
                st.markdown(
                    f'<p class="ds-meta">已调用 {html.escape(str(result["returned_model"]))}'
                    f'，并结合本地知识库 · {payload["seconds"]}s</p>',
                    unsafe_allow_html=True)
            if payload.get("vision"):
                with st.expander("图片识别结果", expanded=False):
                    st.write(payload["vision"].get("text") or "")
                    if payload["vision"].get("returned_model"):
                        st.caption("视觉模型：" + str(
                            payload["vision"]["returned_model"]))
            if result["status"] == "insufficient":
                st.info(result["limitations"])
            else:
                for i, claim in enumerate(result["claims"]):
                    refs = list(dict.fromkeys(claim.get("refs") or []))
                    st.markdown(f'{i + 1}. {claim["text"]}')
                    if refs:
                        st.caption("依据见右侧检索来源。")
                    else:
                        st.caption("本条为底座模型补充，不是知识库原文。")
                    is_last = index == len(messages) - 1
                    if is_last and st.button("将本条转成任务草稿", key=f"draft_{payload['run_id']}_{i}"):
                        st.session_state.draft_no = i
                if result.get("limitations"):
                    st.caption(result["limitations"])
            st.markdown("</div></div>", unsafe_allow_html=True)

        last = st.session_state.get("last")
        if last and messages:
            export = json.dumps(last, ensure_ascii=False, indent=2)
            st.download_button(
                "下载本次问答记录", export,
                file_name="answer_record.json", mime="application/json")
            index = st.session_state.get("draft_no")
            result = last["result"]
            claims = result.get("claims") or []
            if index is not None and index < len(claims):
                st.subheader("确认任务草稿")
                st.info("先把建议整理成可执行动作，再确认保存。")
                claim = claims[index]
                with st.form("confirm_" + last["run_id"] + str(index)):
                    title = st.text_input("任务名称", value="核对并执行本条建议")
                    detail = st.text_area("操作说明与完成标准", value=claim["text"])
                    due = st.text_input("计划时间或触发条件（自行确认，可留空）")
                    confirm = st.checkbox("我已核对适用条件，并确认此任务")
                    save = st.form_submit_button("确认保存任务")
                if save:
                    if not confirm:
                        st.warning("请先核对并勾选确认。")
                    else:
                        try:
                            created = create_task(
                                owner, last["run_id"], index, title, detail, due)
                            if created:
                                st.success("任务已保存，请到“我的任务”查看。")
                            else:
                                st.info("这条建议已经保存，不会重复创建。")
                        except ValueError as error:
                            st.error(str(error))

        with st.expander("补充条件", expanded=False):
            st.text_area(
                "补充条件", max_chars=1000, key="ask_context",
                label_visibility="collapsed",
                placeholder="例如：销售目标、现有设施、已经观察到的情况。")
            st.checkbox("我只了解一般知识，暂不制定具体贮藏方案", key="ask_general")

    if source_col is not None:
        with source_col:
            render_sources(st.session_state.get("last"))

    pending = st.session_state.pop("pending_q", None)
    typed = st.chat_input(
        "给栗问发送消息，也可附带图片",
        accept_file=True,
        file_type=["jpg", "jpeg", "png", "webp"],
    )
    question = ""
    image = None
    if pending:
        question = pending
    elif typed:
        if isinstance(typed, str):
            question = typed.strip()
        else:
            question = str(getattr(typed, "text", "") or "").strip()
            files = list(getattr(typed, "files", None) or [])
            if files:
                uploaded = files[0]
                image = {
                    "bytes": uploaded.getvalue(),
                    "mime": getattr(uploaded, "type", "") or "image/jpeg",
                    "name": getattr(uploaded, "name", "image"),
                }
    if question or image:
        context = st.session_state.get("ask_context", "")
        general = st.session_state.get("ask_general", False)
        user_text = question or "请识别这张图片"
        st.session_state.messages.append({
            "role": "user",
            "text": user_text,
            "context": context.strip(),
            "image": image["bytes"] if image else None,
        })
        with st.spinner("正在识别图片并查询资料，请稍候……" if image
                        else "正在查询资料，请稍候……"):
            run_question(
                user_text, context, general, owner, chunks, cfg, image=image)
        st.rerun()


def page_issues(owner, cfg):
    st.markdown("## 问题登记")
    st.caption(
        "登记时保留用户输入、实际返回、证据快照和版本。"
        "请标明错误在资料、检索、提示词还是页面。")
    last = st.session_state.get("last")
    if last:
        version = make_version(cfg)
        version["model"] = last.get("model") or version["model"]
        result = last.get("result") or {}
        st.markdown("**最近一次问答**")
        st.write(last["question"] or "（空）")
        if last.get("context"):
            st.caption("补充条件：" + last["context"])
        st.caption("状态：" + str(result.get("status") or "未知"))
        if result.get("returned_model"):
            st.caption("底座模型：" + str(result["returned_model"]))
        claims = result.get("claims") or []
        if not claims:
            st.write(result.get("limitations") or "（无建议条文）")
        else:
            for i, claim in enumerate(claims, start=1):
                st.write(f'{i}. {claim.get("text", "")}')
                refs = claim.get("refs") or []
                if refs:
                    st.caption("引用：" + "、".join(str(r) for r in refs))
                else:
                    st.caption("本条无知识库引用")
        snaps = evidence_snapshot(last.get("hits") or [])
        for hit in snaps:
            show_evidence(hit)
        st.caption(
            f'程序 {version.get("app", "")}｜知识库 {version.get("kb", "")}'
            f'｜模式 {version.get("mode", "")}｜模型 {version.get("model", "")}'
        )
        with st.form("report_issue"):
            layer = st.radio(
                "错误所在层", ["资料", "检索", "提示词", "页面"], horizontal=True)
            expected = st.text_area(
                "预期结果", placeholder="例如：应命中 DEMO001 第1页；页面应显示出处。")
            note = st.text_area(
                "这一层具体错在哪里",
                placeholder="例如：检索没命中已审核资料，应改分块或匹配词。")
            submit_issue = st.form_submit_button("登记本条问题")
        if submit_issue:
            try:
                create_issue(owner, {
                    "question": last["question"],
                    "context": last.get("context", ""),
                    "actual": last["result"],
                    "evidence": evidence_snapshot(last["hits"]),
                    "version": version,
                    "layer": layer,
                    "note": note,
                    "expected": expected,
                    "run_id": last.get("run_id", ""),
                })
                st.success("已登记。可按层级决定改资料、检索、提示词或页面。")
            except ValueError as error:
                st.error(str(error))
    else:
        st.info("请先在知识问答页完成一次查询，再带着快照登记问题。")

    issues = list_issues(owner)
    if issues:
        table = []
        for item in issues:
            rec = item["record"]
            actual = rec.get("actual") or {}
            claims = actual.get("claims") or []
            texts = "；".join(c.get("text", "") for c in claims if c.get("text"))
            ver = rec.get("version") or {}
            table.append({
                "时间": item["created"],
                "层级": item["layer"],
                "用户输入": rec.get("question", ""),
                "实际返回": texts or str(actual.get("limitations") or actual.get("status") or ""),
                "证据条数": len(rec.get("evidence") or []),
                "版本": f'{ver.get("app", "")} / {ver.get("mode", "")} / {ver.get("model", "")}',
                "说明": rec.get("note", ""),
            })
        st.dataframe(table, hide_index=True, width="stretch")
        st.download_button(
            "导出问题登记",
            json.dumps(issues, ensure_ascii=False, indent=2),
            file_name="issue_log.json", mime="application/json")
    else:
        st.caption("还没有登记记录。")


def page_tasks(owner):
    st.markdown("## 我的任务")
    tasks = list_tasks(owner)
    if not tasks:
        st.info("暂时没有任务。先到知识问答页生成并保存一条。")
    for task in tasks:
        label = task["state"] + "｜" + task["title"]
        with st.expander(label):
            st.write(task["detail"])
            st.caption("计划时间：" + (task["due"] or "未指定"))
            run = get_run(owner, task["run_id"])
            if run:
                st.caption("创建时的问题：" + run["question"])
                claim = run["result"]["claims"][task["claim_no"]]
                for hit in run["hits"]:
                    if hit["id"] in claim["refs"]:
                        show_evidence(hit)
            with st.form("task_" + task["id"]):
                states = ["待完成", "已完成", "已取消"]
                state = st.selectbox(
                    "状态", states, index=states.index(task["state"]))
                note = st.text_area("实际执行记录", value=task["note"])
                update = st.form_submit_button("保存状态和记录")
            if update:
                update_task(owner, task["id"], state, note)
                st.rerun()
    if tasks:
        st.download_button(
            "导出我的任务备份",
            json.dumps(tasks, ensure_ascii=False, indent=2),
            file_name="my_tasks.json", mime="application/json")


def page_docs(chunks):
    st.markdown("## 资料目录")
    shown = set()
    for chunk in chunks:
        if chunk["doc_id"] not in shown:
            shown.add(chunk["doc_id"])
            st.write(chunk["title"])
            st.caption(chunk["source"])
    st.write(f"已审核资料 {len(shown)} 份；检索片段 {len(chunks)} 条。")
    st.caption("新增、审核和停用由教师在源资料文件中完成。")


def login_screen(users):
    st.markdown("""
<div class="login-wrap">
  <div class="ds-mark" style="margin:0 auto;">栗</div>
  <h1>栗问</h1>
  <p>登录后开始提问</p>
</div>
""", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        with st.form("login"):
            name = st.text_input("账号", placeholder="请输入账号")
            password = st.text_input("密码", type="password", placeholder="请输入密码")
            login = st.form_submit_button("登录", use_container_width=True, type="primary")
    if login:
        if time.time() < st.session_state.get("retry_at", 0):
            st.warning("请稍后再试。")
        elif verify(password, users.get(name.strip(), "")):
            st.session_state.owner = name.strip()
            st.rerun()
        else:
            st.session_state.retry_at = time.time() + 5
            st.error("账号或密码错误。")


def sidebar(owner, cfg):
    st.markdown("""
<div class="ds-brand">
  <div class="ds-mark">栗</div>
  <div><b>栗问</b><span>知识与农事任务</span></div>
</div>
""", unsafe_allow_html=True)
    if st.button("＋  开启新对话", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pop("last", None)
        st.session_state.pop("draft_no", None)
        st.session_state.page = "chat"
        st.rerun()
    st.radio(
        "功能",
        [key for key, _ in PAGES],
        format_func=lambda key: dict(PAGES)[key],
        label_visibility="collapsed",
        key="page",
    )
    mode = "云端模型" if use_api(cfg) else "离线教学"
    st.markdown(
        f'<div class="ds-user">{html.escape(owner)} · {mode}</div>',
        unsafe_allow_html=True)
    if st.button("退出登录", use_container_width=True):
        st.session_state.clear()
        st.rerun()


def main():
    try:
        cfg = load_cfg()
    except Exception:
        inject_css(False)
        st.error("尚未配置 .streamlit/secrets.toml，请按指导书创建。")
        st.stop()

    users = dict(cfg.get("users", {}))
    if "owner" not in st.session_state:
        inject_css(False)
        login_screen(users)
        st.stop()

    inject_css(True)
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "page" not in st.session_state:
        st.session_state.page = "chat"
    if "page" in st.query_params:
        st.query_params.clear()

    owner = st.session_state.owner
    with st.sidebar:
        sidebar(owner, cfg)

    try:
        init_db()
        chunks = load_chunks()
    except Exception:
        st.error("资料或数据库未准备好，请检查文件和控制台。")
        st.stop()

    if any(c["demo"] for c in chunks):
        st.warning("当前包含虚构教学资料，不可据此开展农业操作。")

    page = st.session_state.page
    if page == "chat":
        page_chat(owner, chunks, cfg)
    elif page == "issues":
        page_issues(owner, cfg)
    elif page == "tasks":
        page_tasks(owner)
    else:
        page_docs(chunks)


main()
