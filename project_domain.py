import re
from copy import deepcopy


SECTION_KEYS = (
    ("content", "一、选题内容"),
    ("author", "二、作者情况"),
    ("feasibility", "三、策划过程与可行性"),
    ("award", "四、获奖潜质"),
    ("profit", "五、成本与盈利估算"),
    ("marketing", "六、市场定位与营销"),
)

ALLOWED_SOURCES = {"application", "report", "fixed", "model", "user", "bpm_profile"}
SENSITIVE_KEYS = {"password", "apikey", "authorization", "token", "secret", "cookie"}
EDITOR_IDENTITY_KEYS = {"projectEditorNo", "projectEditorUid", "editorNo", "editorUid"}


def _is_sensitive_key(key) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return normalized in SENSITIVE_KEYS or normalized.endswith(
        ("password", "apikey", "authorization", "token", "secret", "cookie")
    )


def _scrub(value):
    if isinstance(value, dict):
        return {
            str(key): _scrub(child)
            for key, child in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, tuple):
        return [_scrub(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def normalize_project_state(value: dict | None) -> dict:
    source = value if isinstance(value, dict) else {}
    supplied_sections = {}
    if isinstance(source.get("sections"), list):
        for item in source["sections"]:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            if key in {section_key for section_key, _ in SECTION_KEYS}:
                supplied_sections[key] = item

    sections = []
    for key, title in SECTION_KEYS:
        item = supplied_sections.get(key, {})
        sections.append(
            {
                "key": key,
                "title": _text(item.get("title")) or title,
                "text": str(item.get("text", "") or ""),
                "confirmed": bool(item.get("confirmed", False)),
            }
        )

    score_items = []
    if isinstance(source.get("scoreItems"), list):
        for item in source["scoreItems"]:
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                score_items.append(_scrub(list(item[:3])))

    bpm_topic = _scrub(source.get("bpmTopic")) if isinstance(source.get("bpmTopic"), dict) else {}
    author = (
        _scrub(source.get("authorMaintenance"))
        if isinstance(source.get("authorMaintenance"), dict)
        else {}
    )
    field_sources = {}
    if isinstance(source.get("fieldSources"), dict):
        field_sources = {
            str(key): child
            for key, child in source["fieldSources"].items()
            if child in ALLOWED_SOURCES
        }
    source_files = (
        _scrub(source.get("sourceFiles"))
        if isinstance(source.get("sourceFiles"), dict)
        else {}
    )
    return {
        "sections": sections,
        "scoreItems": score_items,
        "bpmTopic": bpm_topic,
        "authorMaintenance": author,
        "fieldSources": field_sources,
        "sourceFiles": source_files,
        "docxExported": bool(source.get("docxExported", False)),
    }


def _score_total(score_items) -> int | float | None:
    if not isinstance(score_items, list) or len(score_items) != len(SECTION_KEYS):
        return None
    total = 0.0
    for item in score_items:
        if not isinstance(item, list) or len(item) < 3:
            return None
        try:
            maximum = float(item[1])
            score = float(item[2])
        except (TypeError, ValueError):
            return None
        if score < 0 or score > maximum:
            return None
        total += score
    return int(total) if total.is_integer() else total


def summarize_project_state(state: dict, editor_name: str) -> dict:
    normalized = normalize_project_state(state)
    topic = normalized["bpmTopic"]
    editor = _text(editor_name)
    if editor:
        topic["projectEditor"] = editor
        topic["editor"] = editor
        normalized["fieldSources"]["bpmTopic.projectEditor"] = "bpm_profile"
    for key in EDITOR_IDENTITY_KEYS:
        topic.pop(key, None)

    sections = normalized["sections"]
    has_report = any(_text(section["text"]) for section in sections)
    report_confirmed = all(
        _text(section["text"]) and section["confirmed"] for section in sections
    )
    report_status = "confirmed" if report_confirmed else "draft" if has_report else "empty"
    author_name = _text(normalized["authorMaintenance"].get("name")) or _text(
        topic.get("authorName")
    )
    author_bio = _text(normalized["authorMaintenance"].get("bio"))
    title = _text(topic.get("bookName")) or "未命名选题"
    return {
        "title": title,
        "authorName": author_name,
        "editorName": editor,
        "reportStatus": report_status,
        "authorStatus": "ready" if author_name and author_bio else "unknown",
        "bpmStatus": "ready" if report_confirmed and _score_total(normalized["scoreItems"]) is not None else "not_ready",
        "state": normalized,
    }


def project_state_from_report(result: dict, *, source_kind: str) -> dict:
    if not isinstance(result, dict):
        raise ValueError("report result must be an object")
    section_source = "model" if source_kind == "generated" else "report"
    state = normalize_project_state(
        {
            "sections": result.get("sections"),
            "scoreItems": result.get("scoreItems", result.get("scores")),
            "bpmTopic": result.get("bpmTopic", {}),
            "authorMaintenance": result.get(
                "authorMaintenance",
                (result.get("bpmTopic") or {}).get("authorMaintenance", {}),
            ),
            "fieldSources": result.get("fieldSources", {}),
            "sourceFiles": result.get("sourceFiles", {}),
            "docxExported": result.get("docxExported", False),
        }
    )
    topic = state["bpmTopic"]
    if not _text(topic.get("bookName")) and _text(result.get("title")):
        topic["bookName"] = _text(result["title"])

    sources = state["fieldSources"]
    for key, _ in SECTION_KEYS:
        sources.setdefault(f"sections.{key}", section_source)
    sources.setdefault("scoreTotal", "report")
    for key in ("bookName", "authorName"):
        sources.setdefault(f"bpmTopic.{key}", "application")
    for key in ("class1", "class2", "gbClass", "readLevel"):
        sources.setdefault(f"bpmTopic.{key}", "fixed")
    for key in ("class3", "class4"):
        sources.setdefault(f"bpmTopic.{key}", "model")
    for key in ("brief", "reader", "compare"):
        sources.setdefault(f"bpmTopic.{key}", "report")
    sources.setdefault("bpmTopic.feature", section_source)
    sources.setdefault("bpmTopic.projectEditor", "bpm_profile")
    return state


def build_bpm_preflight(state: dict, *, bpm_configured: bool) -> dict:
    normalized = normalize_project_state(deepcopy(state))
    topic = normalized["bpmTopic"]
    sources = normalized["fieldSources"]
    rows = []

    def add_row(key, label, value, *, required=False, default_source="report", present=None):
        if present is None:
            present = bool(_text(value)) if isinstance(value, str) else value is not None
        status = "ready" if present else "blocking_missing" if required else "optional_missing"
        rows.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "source": sources.get(key, default_source),
                "status": status,
                "required": required,
            }
        )

    add_row("bpmTopic.bookName", "选题名称", topic.get("bookName", ""), required=True, default_source="application")
    add_row("bpmTopic.authorName", "主要作译者", topic.get("authorName", ""), default_source="application")
    add_row("bpmTopic.projectEditor", "策划编辑", topic.get("projectEditor", ""), required=True, default_source="bpm_profile")
    for key, label, default_source in (
        ("class1", "1级分类", "fixed"),
        ("class2", "2级分类", "fixed"),
        ("class3", "3级分类", "model"),
        ("class4", "4级分类", "model"),
        ("gbClass", "国标分类", "fixed"),
        ("readLevel", "层次", "fixed"),
    ):
        add_row(f"bpmTopic.{key}", label, topic.get(key, ""), default_source=default_source)

    for key, title in SECTION_KEYS:
        section = next(item for item in normalized["sections"] if item["key"] == key)
        add_row(
            f"sections.{key}",
            title,
            section["text"],
            required=True,
            default_source="report",
            present=bool(_text(section["text"]) and section["confirmed"]),
        )

    total = _score_total(normalized["scoreItems"])
    add_row("scoreTotal", "自评总分", total, required=True, default_source="report", present=total is not None)
    for key, label in (
        ("brief", "内容简介"),
        ("reader", "读者对象"),
        ("feature", "选题特色"),
        ("compare", "同类选题比较"),
    ):
        add_row(f"bpmTopic.{key}", label, topic.get(key, ""), default_source="report")
    add_row(
        "bpmCredentials",
        "BPM 账号配置",
        "已配置" if bpm_configured else "未配置",
        required=True,
        default_source="user",
        present=bpm_configured,
    )

    blocking_count = sum(row["status"] == "blocking_missing" for row in rows)
    return {
        "ready": blocking_count == 0,
        "blockingCount": blocking_count,
        "optionalMissingCount": sum(row["status"] == "optional_missing" for row in rows),
        "rows": rows,
    }
