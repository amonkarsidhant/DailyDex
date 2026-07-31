"""LinkedIn carousel rendering: slide text -> branded pages -> PDF.

LinkedIn publishes carousels as *document* posts, which means a PDF. The
cross-poster agent already writes an 8-slide script; this module turns that
text into the pages LinkedIn will actually accept, reusing the Remotion engine
so a carousel and a Short share one visual identity.

Pages render as an image sequence (fps 1, one frame per slide) so the whole
deck comes out of a single Remotion bundle rather than one bundle per slide.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from typing import Any, Dict, List, Optional

VIDEO_ENGINE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "video-engine"
)
COMPOSITION_ID = "CarouselSlide"
MAX_SLIDES = 20  # LinkedIn caps document posts well above this; keeps runaway output bounded.

# "[Slide 3]", "Slide 3:", "**Slide 3** -", "### Slide 3" all appear in practice
# depending on which model wrote the script.
_SLIDE_MARKER = re.compile(
    r"^[ \t]*(?:[#>*_\-\s]*)\[?\s*slide\s*(\d+)\s*\]?\s*[:.)\-—]*[ \t]*",
    re.IGNORECASE | re.MULTILINE,
)
_MD_NOISE = re.compile(r"[*_`]+")
_HEADING_LINE = re.compile(r"^\s*#{1,6}\s*.*$", re.MULTILINE)


def _clean(text: str) -> str:
    text = _MD_NOISE.sub("", text or "")
    return re.sub(r"\s+", " ", text).strip()


def parse_slides(text: str, max_slides: int = MAX_SLIDES) -> List[str]:
    """Split generated carousel copy into individual slide strings.

    Falls back to blank-line paragraphs when the model ignored the slide
    markers, so a usable deck still comes out of a loosely formatted response.
    """
    if not text or not text.strip():
        return []

    matches = list(_SLIDE_MARKER.finditer(text))
    slides: List[str] = []
    if matches:
        for position, match in enumerate(matches):
            start = match.end()
            end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
            body = _clean(text[start:end])
            if body:
                slides.append(body)
    else:
        # No markers: drop markdown headings, then treat paragraphs as slides.
        stripped = _HEADING_LINE.sub("", text)
        for block in re.split(r"\n\s*\n", stripped):
            body = _clean(block)
            if body:
                slides.append(body)

    return slides[:max_slides]


def _resolve_render_command() -> tuple:
    engine_dir = os.environ.get("VIDEO_ENGINE_DIR", VIDEO_ENGINE_DIR)
    if shutil.which("npx") is None or not os.path.isdir(os.path.join(engine_dir, "src")):
        raise RuntimeError("Remotion is unavailable; run rendering in the video-worker service")
    return ("npx",)


def _images_to_pdf(image_paths: List[str], output_path: str) -> None:
    """Assemble rendered pages into a single PDF document."""
    from PIL import Image

    pages = []
    try:
        for path in image_paths:
            with Image.open(path) as handle:
                # PDF has no alpha channel; flatten onto the deck's own dark
                # background rather than letting it composite to white.
                page = handle.convert("RGBA")
                flat = Image.new("RGB", page.size, (9, 11, 14))
                flat.paste(page, mask=page.split()[-1])
                pages.append(flat)
        if not pages:
            raise RuntimeError("no rendered pages to assemble")
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
        pages[0].save(output_path, "PDF", save_all=True, append_images=pages[1:], resolution=144.0)
    finally:
        for page in pages:
            page.close()


def render_carousel_pdf(
    slides: List[str],
    output_path: Optional[str] = None,
    brand_label: str = "DAILYDEX • AI REPORT",
    handle: str = "",
    accent_color: str = "#F0B72F",
    topic: str = "",
    timeout: int = 300,
) -> Dict[str, Any]:
    """Render slide text to a branded PDF carousel.

    Returns ``{"success": True, "pdf_path": ..., "slide_count": N}`` or
    ``{"success": False, "error": ...}``.
    """
    slides = [s for s in (slides or []) if str(s).strip()][:MAX_SLIDES]
    if not slides:
        return {"success": False, "error": "no slides to render"}

    engine_dir = os.environ.get("VIDEO_ENGINE_DIR", VIDEO_ENGINE_DIR)
    if not output_path:
        base_dir = os.path.join(
            os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__))), "carousels"
        )
        os.makedirs(base_dir, exist_ok=True)
        output_path = os.path.join(base_dir, f"carousel-{uuid.uuid4().hex[:12]}.pdf")

    try:
        render_cmd = _resolve_render_command()
    except RuntimeError as exc:
        return {"success": False, "error": str(exc)}

    work_dir = tempfile.mkdtemp(prefix="dailydex-carousel-")
    frames_dir = os.path.join(work_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    props_path = os.path.join(work_dir, "props.json")
    with open(props_path, "w", encoding="utf-8") as handle_file:
        json.dump({
            "slides": slides,
            "brandLabel": brand_label,
            "handle": handle,
            "accentColor": accent_color,
            "topic": topic,
        }, handle_file)

    try:
        cmd = list(render_cmd) + [
            "remotion", "render", COMPOSITION_ID, frames_dir,
            "--sequence", "--image-format=png", f"--props={props_path}",
        ]
        browser = os.environ.get("REMOTION_BROWSER_EXECUTABLE")
        if browser:
            cmd.append(f"--browser-executable={browser}")
        subprocess.run(cmd, check=True, capture_output=True, timeout=timeout, cwd=engine_dir)

        pages = sorted(glob.glob(os.path.join(frames_dir, "*.png")))
        if not pages:
            return {"success": False, "error": "Remotion produced no pages"}
        _images_to_pdf(pages, output_path)
        return {
            "success": True,
            "pdf_path": output_path,
            "slide_count": len(slides),
            "page_count": len(pages),
            "file_size_bytes": os.path.getsize(output_path),
        }
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode("utf-8", errors="ignore")[:500]
        return {"success": False, "error": f"Carousel render failed: {detail}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Carousel render timed out after {timeout}s"}
    except Exception as exc:  # pragma: no cover - defensive
        return {"success": False, "error": str(exc)}
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def render_carousel_from_text(text: str, **kwargs) -> Dict[str, Any]:
    """Parse generated carousel copy and render it in one step."""
    slides = parse_slides(text)
    if not slides:
        return {"success": False, "error": "no slides parsed from text"}
    return render_carousel_pdf(slides, **kwargs)
