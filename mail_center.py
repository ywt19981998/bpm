"""Utilities for parsing teacher recipient lists and composing mail."""

from __future__ import annotations

import csv
import io
import re
from pathlib import PurePath
from typing import Any, Iterable

from openpyxl import load_workbook


NAME_HEADERS = {"姓名", "教师姓名", "老师姓名", "name"}
EMAIL_HEADERS = {"邮箱", "电子邮箱", "e-mail", "email"}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
VARIABLE_RE = re.compile(r"\{\{\s*(.*?)\s*\}\}")


def normalize_header(value: Any) -> str:
    """Normalize a column or variable name for matching."""
    return str(value or "").strip().lower()


def render_mail_text(template: str, variables: dict) -> str:
    normalized = {
        normalize_header(key): str(value or "") for key, value in variables.items()
    }
    return VARIABLE_RE.sub(
        lambda match: normalized.get(normalize_header(match.group(1)), ""),
        str(template or ""),
    )


def validate_mail_compose(
    subject: str, body: str, recipients: list[dict]
) -> list[str]:
    errors = []
    if not str(subject or "").strip():
        errors.append("邮件主题不能为空")
    if not str(body or "").strip():
        errors.append("邮件正文不能为空")
    if not recipients:
        errors.append("至少需要一位收件人")
    return errors


def parse_recipient_file(data: bytes, filename: str) -> dict:
    rows = _read_rows(data, filename)
    columns = _columns_from_rows(rows)
    name_column = _find_column(columns, NAME_HEADERS)
    email_column = _find_column(columns, EMAIL_HEADERS)
    if name_column is None or email_column is None:
        raise ValueError("名单必须包含姓名和邮箱表头")

    valid = []
    invalid = []
    duplicates = 0
    seen_emails = set()
    for row_number, row in enumerate(rows, start=2):
        record = _record_from_row(row, columns, name_column, email_column)
        name = record["name"]
        email = record["email"]
        if not name:
            invalid.append(
                {"row": row_number, "name": name, "email": email, "reason": "姓名不能为空"}
            )
            continue
        if not EMAIL_RE.fullmatch(email):
            invalid.append(
                {"row": row_number, "name": name, "email": email, "reason": "邮箱格式无效"}
            )
            continue
        email_key = email.casefold()
        if email_key in seen_emails:
            duplicates += 1
            continue
        seen_emails.add(email_key)
        valid.append(record)

    return {
        "valid": valid,
        "invalid": invalid,
        "duplicates": duplicates,
        "columns": columns,
    }


def _read_rows(data: bytes, filename: str) -> list[dict[str, Any]]:
    suffix = PurePath(filename).suffix.casefold()
    if suffix in {".xlsx", ".xlsm"}:
        return _read_xlsx_rows(data)
    if suffix != ".csv":
        raise ValueError("仅支持 CSV 或 XLSX 文件")
    return _read_csv_rows(data)


def _read_csv_rows(data: bytes) -> list[dict[str, Any]]:
    last_error = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = data.decode(encoding)
            reader = csv.DictReader(io.StringIO(text))
            if reader.fieldnames is None:
                return []
            return [dict(row) for row in reader]
        except UnicodeDecodeError as exc:
            last_error = exc
    raise ValueError("CSV 文件编码无法识别") from last_error


def _read_xlsx_rows(data: bytes) -> list[dict[str, Any]]:
    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        worksheet = workbook.active
        values = worksheet.iter_rows(values_only=True)
        try:
            header_row = next(values)
        except StopIteration:
            return []
        columns = [str(value or "").strip() for value in header_row]
        return [
            {column: value for column, value in zip(columns, row)}
            for row in values
        ]
    finally:
        workbook.close()


def _columns_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return []
    return list(rows[0].keys())


def _find_column(columns: Iterable[str], aliases: set[str]) -> str | None:
    for column in columns:
        if normalize_header(column) in aliases:
            return column
    return None


def _record_from_row(
    row: dict[str, Any], columns: list[str], name_column: str, email_column: str
) -> dict[str, str]:
    name = "" if row.get(name_column) is None else str(row.get(name_column)).strip()
    email = "" if row.get(email_column) is None else str(row.get(email_column)).strip()
    record = {
        column: "" if row.get(column) is None else str(row.get(column)).strip()
        for column in columns
    }
    record["name"] = name
    record["email"] = email
    return record
