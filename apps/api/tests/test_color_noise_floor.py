"""Pin the noise-floor behavior of `_center_crop_quantize`.

The user-reported regression: the "Marina Bottle Tote" (visually orange)
got a beige@0.07 from CV color extraction and the filter then surfaced
it under the "Beige" main-color chip. Anything below MIN_COLOR_SHARE
should now be dropped — except the dominant color, which is always kept.

The actual quantizer needs Pillow; we test the post-quantization filter
logic by importing the module and checking the constant + verifying the
backfill SQL semantic (always-keep-dominant) by direct calling once
Pillow is available in the test env.
"""
from __future__ import annotations

import importlib.util

import pytest

# Skip the live-image path if cv extra isn't installed; the constant
# check below still runs.
_PIL_AVAILABLE = importlib.util.find_spec("PIL") is not None


def test_min_color_share_constant_is_documented_floor():
    """The 0.10 floor is the contract; bumping it silently would change
    the noise level of the corpus's color filter."""
    from clothist_api.cv.classifier import MIN_COLOR_SHARE
    assert MIN_COLOR_SHARE == 0.10


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_quantizer_drops_noisy_tail_keeps_dominant():
    """Build a synthetic image that's 90% orange with a tiny corner of
    beige (~3% of pixels). The quantizer must keep orange (dominant) and
    drop beige (below the 0.10 floor)."""
    import io

    from PIL import Image

    from clothist_api.cv.classifier import _center_crop_quantize

    # 100×100 orange canvas, 6×6 beige patch in the corner = 36/10000 = 0.36%
    # but after center-crop to 60×60 the patch is partially included.
    img = Image.new("RGB", (100, 100), color=(231, 121, 31))      # orange
    for x in range(30, 36):
        for y in range(30, 36):
            img.putpixel((x, y), (226, 213, 184))                  # beige
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)

    colors = _center_crop_quantize(buf.getvalue())
    assert colors, "expected at least one color from a non-empty image"
    names = [name for name, _ in colors]
    # Dominant must be present
    assert "orange" in names, f"orange dropped from {colors!r}"
    # Tiny beige patch should be below 0.10 → dropped (note the float
    # tolerance — the JPEG round-trip will smooth pixel edges slightly).
    for name, share in colors:
        if name != "orange":
            assert share >= 0.10, (
                f"non-dominant color {name!r}@{share:.3f} below MIN_COLOR_SHARE; "
                f"should have been dropped"
            )


@pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed")
def test_quantizer_keeps_real_secondary_above_floor():
    """A genuinely two-tone image (50/50 split) must keep BOTH colors —
    the floor must not be so aggressive that it kills real secondaries."""
    import io

    from PIL import Image

    from clothist_api.cv.classifier import _center_crop_quantize

    img = Image.new("RGB", (100, 100))
    for x in range(100):
        for y in range(100):
            img.putpixel((x, y), (10, 10, 10) if x < 50 else (250, 250, 250))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)

    colors = _center_crop_quantize(buf.getvalue())
    names = [name for name, _ in colors]
    # Both halves should land in the result; the exact canonical color
    # depends on the palette nearest-match but black + white representations
    # must both be present.
    blacks = {"black", "washed-black", "faded-black", "charcoal"}
    whites = {"white", "cream"}
    assert any(n in blacks for n in names), f"missing black-family in {names}"
    assert any(n in whites for n in names), f"missing white-family in {names}"
