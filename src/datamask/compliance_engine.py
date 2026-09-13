import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

try:
    from docx import Document
except Exception:  # pragma: no cover
    Document = None

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None


DEFAULT_RULES = [
    {
        "id": "CN-DS-001",
        "title": "个人信息最小化收集与使用",
        "category": "个人信息",
        "source": "中国《个人信息保护法》",
        "rule_text": "处理个人信息应遵循最小化原则，避免收集和展示不必要的个人敏感信息。",
        "action": "删除或替换非必要个人字段，保留业务所需匿名化指标。",
        "priority": 1,
        "entity_types": ["姓名", "身份证号", "手机号", "邮箱", "住址"],
    },
    {
        "id": "CN-DS-002",
        "title": "敏感个人信息控制",
        "category": "敏感信息",
        "source": "中国《网络安全法》《数据安全法》",
        "rule_text": "敏感个人信息包括身份证号、金融账号、定位轨迹、健康生理信息等，需经过严格脱敏与控制。",
        "action": "对敏感字段使用掩码、替换、哈希或通用化处理。",
        "priority": 2,
        "entity_types": ["身份证号", "银行卡号", "医疗记录", "住址", "生物识别"],
    },
    {
        "id": "CN-DS-003",
        "title": "匿名化与去标识化评估",
        "category": "匿名化",
        "source": "内部数据安全制度",
        "rule_text": "数据在脱敏后仍可能通过组合重识别，需进行去标识化评估，防止单一字段或组合字段泄露。",
        "action": "合并字段、泛化值域、加标识占位符并记录去标识化日志。",
        "priority": 3,
        "entity_types": ["姓名", "身份证号", "手机号", "地址", "企业名称"],
    },
]


def ensure_default_sample_docs(base_dir: Path):
    base_dir.mkdir(parents=True, exist_ok=True)
    sample_files = {
        "base_law.txt": """中国《个人信息保护法》要求：
处理个人信息应遵循合法、正当、必要原则，明确目的、方式和范围，不得过度收集；涉及个人信息的处理必须采取必要的安全保护措施；对敏感个人信息包括身份证号、银行账号、健康生理信息等，应采取更严格保护措施。匿名化应当降低再识别风险，必要时使用字段替换、哈希、掩码和泛化处理。
""",
        "internal_policy.txt": """内部数据安全管理制度：
1. 员工不得在无授权情况下复制、导出、传输个人信息。
2. 对涉及姓名、身份证号、手机号、邮箱、住址等的文档必须进行脱敏处理。
3. 使用标准字段模板：姓名[姓名]、身份证号[身份证号]、手机号[手机号]、地址[地址]。
4. 处理日志应保留原始字段类型、替换规则、执行人和时间。
""",
    }
    for name, content in sample_files.items():
        file_path = base_dir / name
        if not file_path.exists():
            file_path.write_text(content, encoding="utf-8")


def extract_text_from_file(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix == ".txt":
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".md":
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".csv":
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            if PdfReader is None:
                raise RuntimeError("pypdf not available")
            reader = PdfReader(str(path))
            pages = []
            for page in reader.pages:
                pages.append(page.extract_text() or "")
            return "\n".join(pages)
        if suffix == ".docx":
            if Document is None:
                raise RuntimeError("python-docx not available")
            doc = Document(str(path))
            return "\n".join(paragraph.text for paragraph in doc.paragraphs)
    except Exception:
        pass
    return path.read_text(encoding="utf-8", errors="ignore")


def build_semantic_wiki(rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    concept_map = {
        "个人信息": ["姓名", "身份证号", "手机号", "邮箱", "住址", "银行账号"],
        "敏感信息": ["健康信息", "生物识别", "交易记录", "金融账户", "定位轨迹"],
        "匿名化动作": ["删除", "替换", "掩码", "泛化", "哈希"],
        "风险控制": ["最小化", "去标识化", "合规审批", "访问控制"],
    }
    ontology = {"concepts": [], "links": []}
    for concept, members in concept_map.items():
        ontology["concepts"].append({"name": concept, "members": members, "description": f"{concept}范畴及相关数据项"})
        for member in members:
            ontology["links"].append({"source": concept, "target": member, "relation": "包含"})

    for rule in rules:
        ontology["concepts"].append({
            "name": rule["title"],
            "members": rule["entity_types"],
            "description": rule["rule_text"],
        })
        for entity in rule["entity_types"]:
            ontology["links"].append({"source": rule["title"], "target": entity, "relation": "约束"})
    return ontology


def _tokenize(text: str) -> List[str]:
    cleaned = re.sub(r"[\s\u3000]+", "", text)
    return [part for part in re.split(r"[，。！？；：,.!?;\n\r]+", cleaned) if part.strip()]


def build_knowledge_base(doc_dir: str | Path) -> Dict[str, Any]:
    doc_dir = Path(doc_dir)
    files = sorted(doc_dir.glob("*")) if doc_dir.exists() else []
    legal_docs = []
    for file in files:
        if file.is_file():
            text = extract_text_from_file(file)
            legal_docs.append({"path": str(file), "name": file.name, "text": text})

    chunks: List[Dict[str, Any]] = []
    for doc in legal_docs:
        parts = _tokenize(doc["text"])
        for index, part in enumerate(parts):
            if len(part) < 10:
                continue
            keywords = [token for token in re.findall(r"[\u4e00-\u9fff]{2,}", part) if len(token) >= 2]
            chunks.append({
                "source": doc["name"],
                "chunk_index": index,
                "text": part,
                "keywords": keywords[:10],
            })

    keywords = Counter()
    for chunk in chunks:
        for keyword in chunk["keywords"]:
            keywords[keyword] += 1

    rules = []
    for base_rule in DEFAULT_RULES:
        rules.append(base_rule.copy())

    for doc in legal_docs:
        content = doc["text"]
        if "个人信息" in content or "敏感" in content:
            rules.append({
                "id": f"DOC-{doc['name'][:4]}-001",
                "title": f"从 {doc['name']} 派生的文档规则",
                "category": "合规派生",
                "source": doc["name"],
                "rule_text": "文档中明确要求对个人信息和敏感信息进行最小化、匿名化和脱敏处理。",
                "action": "基于字段标签执行删除、替换或掩码处理，并保留风险审计日志。",
                "priority": 4,
                "entity_types": ["姓名", "身份证号", "手机号", "邮箱", "住址"],
            })

    ontology = build_semantic_wiki(rules)
    algorithm_rules = [
        {"id": "ALG-001", "name": "字段替换", "description": "将姓名、身份证号、手机号等字段替换为标准占位符，如 [姓名]、[身份证号]。"},
        {"id": "ALG-002", "name": "掩码脱敏", "description": "对证件号、银行卡号等长敏感字段仅保留头尾几位，并用 * 代替中间字符。"},
        {"id": "ALG-003", "name": "泛化处理", "description": "将详细住址、日期、企业名称等泛化为区级、月度或行业级粒度。"},
        {"id": "ALG-004", "name": "哈希/去标识", "description": "对可被重识别的低熵值使用哈希或伪匿名化，以降低组合攻击风险。"},
    ]

    evidence_summary = {
        "document_count": len(legal_docs),
        "chunk_count": len(chunks),
        "top_keywords": [item for item, _ in keywords.most_common(15)],
    }

    return {
        "rules": rules,
        "rag_entries": chunks,
        "rag_summary": evidence_summary,
        "ontology": ontology,
        "algorithm_rules": algorithm_rules,
    }
