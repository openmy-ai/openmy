from __future__ import annotations

import json
import subprocess
from pathlib import Path

from openmy.services.screen_recognition.capture_common import (
    DEFAULT_OCR_LANGUAGES,
    OcrPayload,
    CaptureMetadata,
    context_helper_binary_path,
    context_helper_source_path,
    ensure_runtime_dir,
    helper_binary_path,
    helper_source_path,
    shutil_which,
)


def compile_vision_helper(data_root: Path | None = None) -> Path:
    ensure_runtime_dir(data_root)
    source = helper_source_path()
    binary = helper_binary_path(data_root)
    if binary.exists() and binary.stat().st_mtime >= source.stat().st_mtime:
        return binary
    cmd = [
        "swiftc",
        str(source),
        "-O",
        "-framework",
        "Foundation",
        "-framework",
        "Vision",
        "-framework",
        "AppKit",
        "-framework",
        "CoreGraphics",
        "-o",
        str(binary),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return binary


def compile_context_helper(data_root: Path | None = None) -> Path:
    ensure_runtime_dir(data_root)
    source = context_helper_source_path()
    binary = context_helper_binary_path(data_root)
    if binary.exists() and binary.stat().st_mtime >= source.stat().st_mtime:
        return binary
    cmd = [
        "swiftc",
        str(source),
        "-O",
        "-framework",
        "Foundation",
        "-framework",
        "AppKit",
        "-framework",
        "CoreGraphics",
        "-o",
        str(binary),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return binary


def capture_screenshot(output_path: Path, display_id: str | None = None) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["screencapture", "-x"]
    if display_id:
        cmd.extend(["-D", str(display_id)])
    cmd.append(str(output_path))
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return output_path


def _run_osascript(script: str) -> str:
    result = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def get_frontmost_context(data_root: Path | None = None) -> CaptureMetadata:
    app_name = ""
    window_name = ""
    browser_url = ""

    try:
        helper = compile_context_helper(data_root)
        result = subprocess.run([str(helper)], check=False, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            payload = json.loads(result.stdout)
            app_name = str(payload.get("app_name", "") or "").strip()
            window_name = str(payload.get("window_name", "") or "").strip()
    except Exception:
        app_name = ""
        window_name = ""

    if not app_name:
        app_name = _run_osascript(
            'tell application "System Events" to get name of first application process whose frontmost is true'
        ).strip()
    if not window_name:
        window_name = _run_osascript(
            'tell application "System Events" to tell (first application process whose frontmost is true) to get name of front window'
        ).strip()

    if app_name == "Google Chrome":
        browser_url = _run_osascript(
            'tell application "Google Chrome" to get URL of active tab of front window'
        )
    elif app_name == "Arc":
        browser_url = _run_osascript(
            'tell application "Arc" to get URL of active tab of front window'
        )
    elif app_name == "Safari":
        browser_url = _run_osascript('tell application "Safari" to get URL of front document')

    return CaptureMetadata(
        app_name=app_name.strip(),
        window_name=window_name.strip(),
        browser_url=browser_url.strip(),
    )


def extract_text_from_image(
    image_path: Path,
    *,
    data_root: Path | None = None,
    languages: list[str] | None = None,
) -> OcrPayload:
    languages = languages or list(DEFAULT_OCR_LANGUAGES)
    helper = compile_vision_helper(data_root)
    cmd = [str(helper), str(image_path), ",".join(languages)]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode == 0:
        try:
            payload = json.loads(result.stdout)
            return OcrPayload(
                text=str(payload.get("text", "") or "").strip(),
                text_json=[item for item in payload.get("text_json", []) if isinstance(item, dict)],
                confidence=float(payload.get("confidence", 0.0) or 0.0),
                engine=str(payload.get("engine", "apple-vision") or "apple-vision"),
            )
        except Exception:
            pass

    if shutil_which("tesseract"):
        return extract_text_with_tesseract(image_path)

    stderr = result.stderr.strip() or "Vision helper failed"
    return OcrPayload(text="", text_json=[], confidence=0.0, engine=f"error:{stderr}")


def extract_text_with_tesseract(image_path: Path) -> OcrPayload:
    cmd = ["tesseract", str(image_path), "stdout", "tsv"]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return OcrPayload(text="", text_json=[], confidence=0.0, engine="tesseract")
    lines = result.stdout.splitlines()
    if not lines:
        return OcrPayload(text="", text_json=[], confidence=0.0, engine="tesseract")
    rows = []
    full_text: list[str] = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 12:
            continue
        text = parts[11].strip()
        if not text:
            continue
        try:
            left, top, width, height = int(parts[6]), int(parts[7]), int(parts[8]), int(parts[9])
            conf = float(parts[10]) if parts[10] not in {"-1", ""} else 0.0
        except ValueError:
            continue
        rows.append(
            {
                "left": str(left),
                "top": str(top),
                "width": str(width),
                "height": str(height),
                "conf": str(conf),
                "text": text,
            }
        )
        full_text.append(text)
    confidence = sum(float(item.get("conf", 0.0)) for item in rows) / len(rows) if rows else 0.0
    return OcrPayload(text=" ".join(full_text).strip(), text_json=rows, confidence=confidence, engine="tesseract")
