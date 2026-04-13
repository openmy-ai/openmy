from __future__ import annotations

from dataclasses import dataclass


DEFAULT_DOC_URL = "https://github.com/openmy-ai/openmy#readme"


def doc_url(anchor: str) -> str:
    final_anchor = str(anchor or "").strip().lstrip("#")
    if not final_anchor:
        return DEFAULT_DOC_URL
    return f"https://github.com/openmy-ai/openmy#{final_anchor}"


@dataclass(slots=True)
class FriendlyErrorDetails:
    code: str
    message: str
    fix: str
    doc_url: str = DEFAULT_DOC_URL
    message_en: str = ""
    fix_en: str = ""


class FriendlyCliError(RuntimeError):
    """给最终用户看的错误，带修复动作和文档链接。"""

    def __init__(
        self,
        message: str,
        *,
        code: str = "cli_error",
        fix: str = "",
        doc_url: str = DEFAULT_DOC_URL,
        message_en: str = "",
        fix_en: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.fix = fix
        self.doc_url = doc_url
        self.message_en = message_en or message
        self.fix_en = fix_en or fix

    def __str__(self) -> str:
        if self.fix:
            return f"{self.message} {self.fix}"
        return self.message


def friendly_error(
    *,
    code: str,
    message: str,
    fix: str,
    doc_url: str = DEFAULT_DOC_URL,
    message_en: str = "",
    fix_en: str = "",
) -> FriendlyCliError:
    return FriendlyCliError(
        message,
        code=code,
        fix=fix,
        doc_url=doc_url,
        message_en=message_en or message,
        fix_en=fix_en or fix,
    )


def skill_error(
    *,
    code: str,
    message: str,
    fix: str,
    doc_url: str = DEFAULT_DOC_URL,
    message_en: str = "",
    fix_en: str = "",
    extra: dict | None = None,
) -> dict:
    payload = {
        "error": True,
        "error_code": code,
        "message": message,
        "message_en": message_en or message,
        "fix": fix,
        "fix_en": fix_en or fix,
        "doc_url": doc_url,
    }
    if extra:
        payload["data"] = extra
    return payload
