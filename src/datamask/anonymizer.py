import json
import re
from pathlib import Path
from typing import Any, Dict, List


def _mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) >= 11:
        return f"{digits[:3]}****{digits[-4:]}"
    return "[手机号]"


def _mask_id(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) >= 15:
        return f"{digits[:6]}********{digits[-4:]}"
    return "[身份证号]"


def _mask_email(value: str) -> str:
    if "@" in value:
        user, domain = value.split("@", 1)
        return f"{user[:2]}***@{domain}"
    return "[邮箱]"


def _mask_bank(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) >= 8:
        return f"{digits[:4]}********{digits[-4:]}"
    return "[银行卡号]"


def _mask_name(value: str) -> str:
    return "[姓名]"


def _mask_address(value: str) -> str:
    return "[地址]"


PATTERN_RULES = [
    (r"\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx]\b", "身份证号", _mask_id),
    (r"\b1[3-9]\d{9}\b", "手机号", _mask_phone),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "邮箱", _mask_email),
    (r"\b(?:\d{16,19}|\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4,})\b", "银行卡号", _mask_bank),
    (r"\b(?:张三|李四|王五|赵六|钱七|孙八|周九|吴十|陈某|刘某|王某)\b", "姓名", _mask_name),
    (r"\b(?:\d{1,6}省\s*\d{1,6}市\s*\d{1,6}区|\d{1,6}市\s*\d{1,6}区\s*\d{1,6}路)\b", "住址", _mask_address),
]


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return path.read_text(encoding="utf-8", errors="ignore")


def anonymize_document(file_path: str | Path, knowledge: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(file_path)
    text = _load_text(path)
    masked_text = text
    replacements: List[Dict[str, Any]] = []
    matched_fields: List[str] = []

    for pattern, label, mask_fn in PATTERN_RULES:
        matches = list(re.finditer(pattern, masked_text))
        for match in matches:
            raw_value = match.group(0)
            masked_value = mask_fn(raw_value)
            if raw_value != masked_value:
                masked_text = masked_text.replace(raw_value, masked_value)
                replacements.append({"field": label, "old": raw_value, "new": masked_value})
                matched_fields.append(label)

    output_dir = Path("output/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{path.stem}_masked{path.suffix}"
    output_file.write_text(masked_text, encoding="utf-8")

    log = {
        "source_file": str(path),
        "output_file": str(output_file),
        "matched_fields": sorted(set(matched_fields)),
        "replacements": replacements,
        "rules_applied": [rule["id"] for rule in knowledge.get("rules", [])[:5]],
        "algorithm_rules": knowledge.get("algorithm_rules", []),
    }
    log_file = output_dir / f"{path.stem}_process_log.json"
    log_file.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "output_file": str(output_file),
        "masked_text": masked_text,
        "replacements": replacements,
        "matched_fields": sorted(set(matched_fields)),
        "log_file": str(log_file),
    }
