import base64
import json
import time
from pathlib import Path
import streamlit as st
from auth import verify
from vector_search import retrieve_vector
from core import (
    answer, create_issue, create_task, evidence_snapshot, get_run,
    init_db, list_issues, list_tasks, load_cfg, load_chunks, make_version,
    retrieve, save_run, update_task, use_api,
)
st.set_page_config(page_title="栗问", layout="wide")
# Streamlit 不提供项目根目录图片的网页地址，背景必须用 data URI。
# 主区用 1.jpg，左侧栏用 2.jpg（文件稍后放入即可，没有时自动跳过）。
_root = Path(__file__).resolve().parent


def _image_uri(name):
    path = _root / name
    if not path.is_file():
        return ""
    raw = base64.b64encode(path.read_bytes()).decode("ascii")
    kind = "png" if path.suffix.lower() == ".png" else "jpeg"
    return f"data:image/{kind};base64,{raw}"


_css = []
_bg_main = _image_uri("1.jpg")
if _bg_main:
    _css.append(f"""
[data-testid="stAppViewContainer"], .stApp {{
    background-image: url("{_bg_main}");
    background-size: cover;
    background-repeat: no-repeat;
    background-attachment: fixed;
    background-position: center;
}}
[data-testid="stHeader"] {{
    background: transparent;
}}
.stApp::before {{
    content: "";
    position: fixed;
    inset: 0;
    background-color: rgba(255, 255, 255, 0.7);
    pointer-events: none;
    z-index: 0;
}}
""")
_bg_side = _image_uri("2.jpg")
if _bg_side:
    _css.append(f"""
[data-testid="stSidebar"] {{
    background-image: url("{_bg_side}");
    background-size: cover;
    background-repeat: no-repeat;
    background-position: center;
    position: relative;
}}
[data-testid="stSidebar"]::before {{
    content: "";
    position: absolute;
    inset: 0;
    background-color: rgba(255, 255, 255, 0.7);
    pointer-events: none;
    z-index: 0;
}}
[data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"],
[data-testid="stSidebarHeader"] {{
    background: transparent !important;
}}
""")
if _css:
    st.markdown("<style>" + "".join(_css) + "</style>", unsafe_allow_html=True)
st.title("栗问｜知识与农事任务助手")

# secrets.toml 是服务端配置，不放到页面上，也不提交到仓库。
try:
    cfg = load_cfg()
except Exception:
    st.error("尚未配置 .streamlit/secrets.toml，请按指导书创建。")
    st.stop()

users = dict(cfg.get("users", {}))
if "owner" not in st.session_state:
    st.info("欢迎使用栗问！请输入您的账号和密码。")
    with st.form("login"):
        name = st.text_input("账号")
        password = st.text_input("密码", type="password")
        login = st.form_submit_button("登录")
    if login:
        if time.time() < st.session_state.get("retry_at", 0):
            st.warning("请稍后再试。")
        elif verify(password, users.get(name.strip(), "")):
            st.session_state.owner = name.strip()
            st.rerun()
        else:
            st.session_state.retry_at = time.time() + 5
            st.error("账号或密码错误。")
    st.stop()

owner = st.session_state.owner
with st.sidebar:
    st.write("当前账号：" + owner)
    if st.button("退出登录"):
        st.session_state.clear()
        st.rerun()
    page = st.radio("功能", ["知识问答", "我的任务", "问题登记", "资料目录"])
    if not use_api(cfg):
        st.warning("离线教学模式：不调用大模型。")
    else:
        st.caption("使用云端模型生成回答。")

try:
    init_db()
    chunks = load_chunks()
except Exception:
    st.error("资料或数据库未准备好，请检查文件和控制台。")
    st.stop()

if any(c["demo"] for c in chunks):
    st.warning("当前包含虚构教学资料，不可据此开展农业操作。")


def show_evidence(hit):
    label = f'{hit["title"]}｜PDF页序 {hit["page"]}'
    with st.expander(label):
        st.caption("来源：" + hit["source"])
        st.caption("适用条件：" + hit["scope"])
        st.text(hit["text"])
        st.caption("片段编号：" + hit["id"])


if page == "知识问答":
    st.caption("当前范围：采收与贮藏。每次提问请写完整问题。")
    with st.form("ask"):
        question = st.text_area(
            "您的问题", max_chars=1000,
            placeholder="例如：板栗批次记录需要填写哪些信息？")
        context = st.text_area(
            "补充条件", max_chars=1000,
            placeholder="例如：销售目标、现有设施、已经观察到的情况。")
        general = st.checkbox("我只了解一般知识，暂不制定具体贮藏方案")
        submit = st.form_submit_button("查询资料并回答")
    if submit:
        st.session_state.pop("last", None)
        st.session_state.pop("draft_no", None)
        if not question.strip():
            st.warning("请先输入问题。")
        else:
            if (any(w in question for w in ("贮藏", "保存", "储存"))
                    and not context.strip() and not general):
                st.info("建议补充销售时间目标和现有设施；未知可写未知。本次仍继续查询。")
            started = time.perf_counter()
            try:
                with st.spinner("正在查询资料，请稍候……"):
                    try:
                        hits = retrieve_vector(question, chunks, cfg, k=4)
                    except Exception:
                        hits = retrieve(question, chunks, 4)
                    result = answer(question, context, hits, cfg)
                    payload = {
                        "question": question, "context": context,
                        "hits": hits, "result": result,
                        "mode": cfg.get("MODE", "demo"),
                        "model": cfg.get("MODEL", ""),
                        "seconds": round(time.perf_counter() - started, 2),
                    }
                    rid = save_run(owner, payload)
                    st.session_state.last = dict(payload, run_id=rid)
            except Exception as error:
                # 只显示可理解的提示，不把内部请求内容暴露出去。
                st.error("本次未生成可用回答：" + str(error)[:160])

    last = st.session_state.get("last")
    if last:
        result = last["result"]
        st.subheader("回答与依据")
        if result.get("returned_model"):
            st.caption("已调用底座模型：" + str(result["returned_model"])
                       + "；并结合本地知识库。")
        if result["status"] == "insufficient":
            st.info(result["limitations"])
        else:
            hit_map = {h["id"]: h for h in last["hits"]}
            for i, claim in enumerate(result["claims"]):
                st.write(f'{i + 1}. {claim["text"]}')
                refs = list(dict.fromkeys(claim.get("refs") or []))
                if refs:
                    for ref in refs:
                        if ref in hit_map:
                            show_evidence(hit_map[ref])
                else:
                    st.caption("本条为底座模型补充，不是知识库原文。")
                if st.button("将本条转成任务草稿", key=f"draft_{i}"):
                    st.session_state.draft_no = i
            st.caption(result["limitations"])
        export = json.dumps(last, ensure_ascii=False, indent=2)
        st.download_button(
            "下载本次问答记录", export,
            file_name="answer_record.json", mime="application/json")

        index = st.session_state.get("draft_no")
        if index is not None:
            st.subheader("确认任务草稿")
            st.info("先把建议整理成可执行动作，再确认保存。")
            claim = result["claims"][index]
            with st.form("confirm_" + last["run_id"] + str(index)):
                title = st.text_input("任务名称", value="核对并执行本条建议")
                detail = st.text_area("操作说明与完成标准", value=claim["text"])
                due = st.text_input(
                    "计划时间或触发条件（自行确认，可留空）")
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

elif page == "问题登记":
    st.subheader("问题登记")
    st.caption(
        "登记时保留用户输入、实际返回、证据快照和版本。"
        "请标明错误在资料、检索、提示词还是页面，不要只写“模型不行”。")
    last = st.session_state.get("last")
    if last:
        version = make_version(cfg)
        version["model"] = last.get("model") or version["model"]
        st.write("将使用最近一次问答快照：")
        st.write("用户输入：" + last["question"])
        if last.get("context"):
            st.caption("补充条件：" + last["context"])
        st.json({
            "actual": last["result"],
            "evidence": evidence_snapshot(last["hits"]),
            "version": version,
        })
        with st.form("report_issue"):
            layer = st.radio(
                "错误所在层",
                ["资料", "检索", "提示词", "页面"],
                horizontal=True)
            expected = st.text_area(
                "预期结果",
                placeholder="例如：应命中 DEMO001 第1页；页面应显示出处。")
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
        table = [{
            "时间": item["created"],
            "层级": item["layer"],
            "用户输入": item["record"]["question"],
            "实际返回": json.dumps(
                item["record"]["actual"], ensure_ascii=False)[:80],
            "证据条数": len(item["record"].get("evidence") or []),
            "版本": json.dumps(
                item["record"].get("version") or {}, ensure_ascii=False),
            "说明": item["record"]["note"],
        } for item in issues]
        st.dataframe(table, hide_index=True, width="stretch")
        st.download_button(
            "导出问题登记",
            json.dumps(issues, ensure_ascii=False, indent=2),
            file_name="issue_log.json", mime="application/json")
    else:
        st.caption("还没有登记记录。")

elif page == "我的任务":
    st.subheader("我的任务")
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

else:
    st.subheader("当前启用的资料")
    shown = set()
    for chunk in chunks:
        if chunk["doc_id"] not in shown:
            shown.add(chunk["doc_id"])
            st.write(chunk["title"])
            st.caption(chunk["source"])
    st.write(f"已审核资料 {len(shown)} 份；检索片段 {len(chunks)} 条。")
    st.caption("新增、审核和停用由教师在源资料文件中完成。")

