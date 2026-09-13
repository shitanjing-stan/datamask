import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from datamask.anonymizer import anonymize_document
from datamask.compliance_engine import build_knowledge_base, ensure_default_sample_docs


st.set_page_config(page_title="DataMask 合规匿名化工作台", layout="wide")
st.title("DataMask：本地数据匿名化与合规处理工作台")


@st.cache_data
def get_default_knowledge():
    sample_dir = Path("sample_data/compliance")
    ensure_default_sample_docs(sample_dir)
    return build_knowledge_base(sample_dir)


with st.sidebar:
    st.header("工作流")
    st.markdown("1. 上传法规与制度文档\n2. 生成规则库和语义知识库\n3. 上传待处理文档\n4. 自动匿名化并输出日志")

    st.subheader("示例数据")
    if st.button("加载默认示例合规文档"):
        st.session_state["knowledge"] = get_default_knowledge()
        st.success("默认示例文档已加载")


if "knowledge" not in st.session_state:
    st.session_state["knowledge"] = get_default_knowledge()

knowledge = st.session_state["knowledge"]


st.subheader("一、合规要求文档与规则库生成")
col1, col2 = st.columns(2)

with col1:
    uploaded_rules = st.file_uploader(
        "上传合规文档（法规标准/内部制度）",
        type=["txt", "md", "docx", "pdf"],
        accept_multiple_files=True,
    )

    if uploaded_rules:
        temp_dir = Path("output/tmp_compliance")
        temp_dir.mkdir(parents=True, exist_ok=True)
        for uploaded in uploaded_rules:
            target = temp_dir / uploaded.name
            with target.open("wb") as f:
                f.write(uploaded.read())
        knowledge = build_knowledge_base(temp_dir)
        st.session_state["knowledge"] = knowledge
        st.success(f"已处理 {len(uploaded_rules)} 份合规文档")

with col2:
    st.write("规则清单概览")
    for rule in knowledge["rules"][:6]:
        st.markdown(f"- **{rule['id']}**：{rule['title']} | {rule['action']}")

st.markdown("### RAG 知识库摘要")
rag_summary = knowledge["rag_summary"]
st.json({
    "document_count": rag_summary["document_count"],
    "chunk_count": rag_summary["chunk_count"],
    "top_keywords": rag_summary["top_keywords"][:10],
})

st.markdown("### 本体语义 Wiki")
st.json(knowledge["ontology"])

st.markdown("### 匿名化算法规则库")
for item in knowledge["algorithm_rules"]:
    st.markdown(f"- **{item['id']}**：{item['name']} -> {item['description']}")

st.subheader("二、文档匿名化处理")
input_files = st.file_uploader(
    "上传待处理文档（支持 .txt/.md/.docx/.pdf/.csv）",
    type=["txt", "md", "docx", "pdf", "csv"],
    accept_multiple_files=True,
)

if input_files:
    output_dir = Path("output/processed")
    output_dir.mkdir(parents=True, exist_ok=True)

    for uploaded in input_files:
        source_name = uploaded.name
        target = output_dir / source_name
        with target.open("wb") as f:
            f.write(uploaded.read())

        result = anonymize_document(target, knowledge)

        st.markdown(f"### {source_name}")
        st.success(f"处理完成，已输出：{result['output_file']}")
        st.text_area("处理后预览", result["masked_text"][:3000], height=220)
        st.json({
            "replacements": result["replacements"],
            "matched_fields": result["matched_fields"],
            "source_file": str(target),
            "log_file": result["log_file"],
        })

        with open(result["log_file"], "r", encoding="utf-8") as log_f:
            log_text = log_f.read()
        st.download_button(
            label=f"下载处理日志 - {source_name}",
            data=log_text,
            file_name=f"{Path(source_name).stem}_process_log.json",
            mime="application/json",
        )

        st.download_button(
            label=f"下载匿名化文件 - {source_name}",
            data=result["masked_text"].encode("utf-8"),
            file_name=Path(result["output_file"]).name,
            mime="text/plain",
        )

else:
    st.info("请在此处上传待匿名化的本地文档，系统将基于已生成的合规规则自动处理。")


st.markdown("---")
st.caption("说明：本工作台为本地原型实现，重点演示中国数据安全合规规则抽取、知识库构建和文档匿名化流程。")
