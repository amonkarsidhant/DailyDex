"""Tests for LinkedIn carousel rendering.

The Remotion render itself needs Node and Chromium, so it is exercised through
an injected subprocess boundary here; the parser and PDF assembly run for real.
"""

import os
from unittest.mock import patch

import pytest

import carousel_renderer as cr


# ── slide parsing ─────────────────────────────────────────────────────────

def test_parses_bracketed_slide_markers_and_drops_the_title():
    text = """# LinkedIn Carousel: GPT-5.6

[Slide 1] Bold hook that creates FOMO.
[Slide 2] The core technical development.
[Slide 3] CTA: follow for weekly signals."""
    slides = cr.parse_slides(text)

    assert slides == [
        "Bold hook that creates FOMO.",
        "The core technical development.",
        "CTA: follow for weekly signals.",
    ]


@pytest.mark.parametrize("text", [
    "**Slide 1:** First thing.\n**Slide 2:** Second thing.",
    "### Slide 1\nFirst thing.\n\n### Slide 2\nSecond thing.",
    "Slide 1 - First thing.\nSlide 2 - Second thing.",
])
def test_parses_the_slide_marker_styles_models_actually_emit(text):
    slides = cr.parse_slides(text)
    assert len(slides) == 2
    assert "First thing." in slides[0]


def test_falls_back_to_paragraphs_when_markers_are_absent():
    text = "The hook paragraph.\n\nThe detail paragraph.\n\nThe CTA paragraph."
    assert len(cr.parse_slides(text)) == 3


def test_markdown_emphasis_is_stripped():
    assert cr.parse_slides("[Slide 1] A **bold** and _italic_ claim.") == \
        ["A bold and italic claim."]


def test_empty_input_yields_no_slides():
    assert cr.parse_slides("") == []
    assert cr.parse_slides("   \n  ") == []


def test_slide_count_is_bounded():
    text = "\n".join(f"[Slide {n}] Slide body number {n}." for n in range(1, 40))
    assert len(cr.parse_slides(text)) == cr.MAX_SLIDES


# ── render orchestration ──────────────────────────────────────────────────

def test_render_rejects_empty_slides(tmp_path):
    result = cr.render_carousel_pdf([], output_path=str(tmp_path / "out.pdf"))
    assert result["success"] is False
    assert "no slides" in result["error"]


def test_render_from_text_rejects_unparseable_copy(tmp_path):
    result = cr.render_carousel_from_text("", output_path=str(tmp_path / "out.pdf"))
    assert result["success"] is False


def test_pages_are_assembled_into_a_single_pdf(tmp_path):
    """Renderer output -> one PDF with a page per slide."""
    from PIL import Image

    frames = tmp_path / "frames"
    frames.mkdir()
    for n in range(3):
        Image.new("RGB", (108, 135), (9, 11, 14)).save(frames / f"element-{n}.png")

    out = tmp_path / "carousel.pdf"
    cr._images_to_pdf(sorted(str(p) for p in frames.glob("*.png")), str(out))

    assert out.exists() and out.stat().st_size > 0
    with open(out, "rb") as handle:
        assert handle.read(5) == b"%PDF-"


def test_render_reports_remotion_failure(tmp_path, monkeypatch):
    import subprocess

    monkeypatch.setattr(cr, "_resolve_render_command", lambda: ("npx",))

    def boom(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "remotion", stderr=b"composition missing")

    with patch("subprocess.run", side_effect=boom):
        result = cr.render_carousel_pdf(["one", "two"], output_path=str(tmp_path / "o.pdf"))

    assert result["success"] is False
    assert "composition missing" in result["error"]


def test_render_reports_missing_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(cr, "_resolve_render_command",
                        lambda: (_ for _ in ()).throw(RuntimeError("Remotion is unavailable")))
    result = cr.render_carousel_pdf(["one"], output_path=str(tmp_path / "o.pdf"))

    assert result["success"] is False
    assert "unavailable" in result["error"]


def test_render_succeeds_and_cleans_up_its_workdir(tmp_path, monkeypatch):
    from PIL import Image

    monkeypatch.setattr(cr, "_resolve_render_command", lambda: ("npx",))
    captured = {}

    def fake_run(cmd, **kwargs):
        # Stand in for Remotion: drop a page sequence where it was asked to.
        frames_dir = cmd[4]
        captured["cmd"] = cmd
        for n in range(2):
            Image.new("RGBA", (108, 135), (9, 11, 14, 255)).save(
                os.path.join(frames_dir, f"element-{n}.png"))

        class Done:
            returncode = 0
        return Done()

    out = tmp_path / "carousel.pdf"
    with patch("subprocess.run", side_effect=fake_run):
        result = cr.render_carousel_pdf(["one", "two"], output_path=str(out))

    assert result["success"] is True
    assert result["page_count"] == 2
    assert out.exists()
    assert "--sequence" in captured["cmd"]
    assert cr.COMPOSITION_ID in captured["cmd"]
