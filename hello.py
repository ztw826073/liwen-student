import streamlit as st

st.title("栗问|从零实现实践指导书")
st.caption("查询资料，核对数据，整理任务")
name = st.text_input("你的名字")
if st.button("打招呼"):
    st.write("你好，" + (name or "同学") + "！")
