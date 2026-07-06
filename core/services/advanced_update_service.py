from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from django.conf import settings


def parse_version(value: str) -> tuple[int, ...]:
    cleaned = (value or "").strip().lower().replace("v", "")
    parts: list[int] = []
    for token in cleaned.split("."):
        token = "".join(ch for ch in token if ch.isdigit())
        parts.append(int(token) if token else 0)
    return tuple(parts or [0])


def normalize_channel(value: str | None) -> str:
    """توحيد اسم قناة التحديث بين النظام المحلي والخادم المركزي."""
    raw = (value or "").strip().lower()
    if raw in {"stable", "release", "main"}:
        return "stable"
    if raw in {"test", "beta", "testing"}:
        return "test"
    return "stable"


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _signature_payload(payload: dict[str, Any]) -> bytes:
    protected = {
        "latest_version": str(payload.get("latest_version") or payload.get("version") or ""),
        "package_type": str(payload.get("package_type") or ""),
        "package_name": str(payload.get("package_name") or ""),
        "download_url": str(payload.get("download_url") or ""),
        "sha256": str(payload.get("sha256") or ""),
        "channel": normalize_channel(payload.get("channel")),
        "minimum_supported_version": str(payload.get("minimum_supported_version") or ""),
    }
    return json.dumps(protected, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def expected_signature(payload: dict[str, Any], signing_key: str) -> str:
    return hmac.new(
        signing_key.encode("utf-8"),
        _signature_payload(payload),
        hashlib.sha256,
    ).hexdigest()


def verify_manifest_signature(payload: dict[str, Any]) -> tuple[bool, str]:
    required = bool(getattr(settings, "UPDATE_SIGNATURE_REQUIRED", False))
    signing_key = str(getattr(settings, "UPDATE_SIGNING_KEY", "") or "")
    provided = str(payload.get("signature") or "").strip().lower()

    if not signing_key:
        if required:
            return False, "تم تفعيل التوقيع الإلزامي لكن UPDATE_SIGNING_KEY غير مضبوط."
        return True, ""

    if not provided:
        if required:
            return False, "ملف التحديث لا يحتوي على توقيع رقمي."
        return True, ""

    expected = expected_signature(payload, signing_key)
    if not hmac.compare_digest(provided, expected):
        return False, "توقيع ملف التحديث غير صالح."
    return True, ""


def validate_remote_payload(payload: dict[str, Any], current_version: str, current_channel: str) -> tuple[bool, str]:
    latest_version = str(payload.get("latest_version") or payload.get("version") or "").strip()
    if not latest_version:
        return False, "ملف latest.json لا يحتوي على latest_version."

    payload_channel = normalize_channel(payload.get("channel"))
    chosen_channel = normalize_channel(current_channel)

    if payload_channel != chosen_channel:
        return False, f"التحديث المنشور مخصص لقناة {payload_channel} وليس للقناة الحالية {chosen_channel}."

    minimum_supported = str(payload.get("minimum_supported_version") or "").strip()
    if minimum_supported and parse_version(current_version) < parse_version(minimum_supported):
        return False, "هذا التحديث لا يدعم الإصدار الحالي ويحتاج ترقية مرحلية أولاً."

    if parse_version(latest_version) <= parse_version(current_version):
        return False, "الإصدار المنشور ليس أحدث من الإصدار الحالي."

    ok, message = verify_manifest_signature(payload)
    if not ok:
        return False, message

    if bool(getattr(settings, "UPDATE_SHA256_REQUIRED", True)) and not str(payload.get("sha256") or "").strip():
        return False, "ملف latest.json لا يحتوي على sha256 المطلوب للتحقق من سلامة الحزمة."

    return True, ""
