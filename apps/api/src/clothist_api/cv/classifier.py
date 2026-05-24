"""Zero-shot CLIP classifier for category / gender / color.

Heavy ML imports (transformers / torch / PIL / numpy) are late-bound inside
the class so `from clothist_api.cv import classifier` succeeds even when
the `cv` optional-extra hasn't been installed. Only **instantiating**
`CLIPClassifier(...)` actually loads the model.

Spec: plans/cv_classify/senior_dev_v2.md §2c (CLIP math), §3a-3c (prompts),
§3c Option (a) (center-crop quantize color extraction).
"""
from __future__ import annotations

import io
import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING

from clothist_api.cv.palette import COLOR_HEX, hex_to_rgb, nearest_palette_color
from clothist_api.cv.types import CVVerdict

if TYPE_CHECKING:  # pragma: no cover — type-only imports
    import numpy as np
    import torch
    from PIL import Image as PILImage

logger = logging.getLogger(__name__)


# ---------------- Prompt sets (locked per §3a-3c) ---------------- #


CATEGORY_PROMPTS: dict[str, list[str]] = {
    "hoodies":     ["a photo of a hoodie",
                    "a product photo of a sweatshirt"],
    "tshirts":     ["a photo of a t-shirt",
                    "a product photo of a tank top"],
    "pants":       ["a photo of trousers",
                    "a product photo of pants"],
    "jeans":       ["a photo of a pair of jeans",
                    "a denim trouser product photo"],
    "shorts":      ["a photo of shorts",
                    "a product photo of athletic shorts"],
    "skirts":      ["a photo of a skirt",
                    "a midi skirt product photo"],
    "dresses":     ["a photo of a dress",
                    "a midi dress product photo",
                    "a photo of a romper or playsuit"],
    "jackets":     ["a photo of a jacket",
                    "a product photo of an outerwear coat",
                    "a photo of a blazer"],
    "sneakers":    ["a photo of sneakers",
                    "a product photo of athletic shoes",
                    "a photo of loafers or flats"],
    "sweaters":    ["a photo of a sweater",
                    "a knit cardigan product photo"],
    "accessories": ["a photo of a bag, hat, belt, or accessory",
                    "a product photo of a wallet, jewelry, or sunglasses"],
    "swimwear":    ["a photo of a bikini or swimsuit",
                    "a product photo of swimwear"],
    "underwear":   ["a photo of underwear, briefs, or socks",
                    "a product photo of a bra or lingerie"],
}


GENDER_PROMPTS: dict[str, list[str]] = {
    "women":  ["a product photo of women's clothing",
               "a piece of clothing worn by a woman",
               "a women's fashion product photo"],
    "men":    ["a product photo of men's clothing",
               "a piece of clothing worn by a man",
               "a men's fashion product photo"],
    "unisex": ["a flat-lay product photo on a neutral background",
               "a clothing item with no person in the photo",
               "a unisex or gender-neutral clothing product photo"],
}


def _color_prompts() -> dict[str, list[str]]:
    """One prompt per palette color, used in the cross-check step of the
    center-crop hybrid (§3c step 6)."""
    return {name: [f"a {name} product photo"] for name in COLOR_HEX}


# ---------------- Image preprocessing helpers ---------------- #


CENTER_CROP_RATIO = 0.6

# Minimum share-of-pixels a color must reach to be retained. Tertiary colors
# below this floor are background bleed / corner noise — they leak into the
# coarse filter facets (a 7%-of-image beige patch on an obviously-orange
# tote would surface the product under the "Beige" filter chip) and break
# the user's expectation that the filter and product page agree on color.
# 0.10 was picked from the corpus distribution: it drops 66/341 (~19%) of
# detected tertiaries — the entire bottom decile, where colors are below
# 0.05 and pure noise — while preserving real two-tone products with a
# meaningful 0.15+ secondary color.
MIN_COLOR_SHARE = 0.10


def _center_crop_quantize(image_bytes: bytes, *, k: int = 5) -> list[tuple[str, float]]:
    """Center-crop the image and return up to top-3 palette colors above the
    MIN_COLOR_SHARE noise floor. Falls back gracefully if Pillow isn't
    installed (returns []).
    """
    try:
        from PIL import Image as PILImage
    except ImportError:  # pragma: no cover — cv extra not installed
        return []
    img = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    cw = int(w * CENTER_CROP_RATIO)
    ch = int(h * CENTER_CROP_RATIO)
    cx, cy = (w - cw) // 2, (h - ch) // 2
    crop = img.crop((cx, cy, cx + cw, cy + ch)).resize((64, 64), PILImage.LANCZOS)
    # MEDIANCUT quantize → k dominant RGB tuples.
    quant = crop.quantize(colors=k, method=PILImage.Quantize.MEDIANCUT)
    palette = quant.getpalette()  # flat [r0,g0,b0,r1,g1,b1,...]
    # Count pixels assigned to each palette index.
    counts = quant.getcolors() or []  # [(count, palette_index), ...]
    total = sum(c for c, _ in counts) or 1

    bucket: dict[str, float] = defaultdict(float)
    for count, idx in counts:
        if palette is None:
            continue
        r, g, b = palette[idx * 3], palette[idx * 3 + 1], palette[idx * 3 + 2]
        canonical = nearest_palette_color((r, g, b))
        bucket[canonical] += count / total

    ranked = sorted(bucket.items(), key=lambda kv: -kv[1])[:3]
    # Always keep the dominant color even if a degenerate image with ~5
    # equal clusters pushes it below the floor; drop only the trailing
    # noise.
    if not ranked:
        return ranked
    head, tail = ranked[0], ranked[1:]
    return [head] + [(name, share) for name, share in tail if share >= MIN_COLOR_SHARE]


# ---------------- CLIP classifier ---------------- #


class CLIPClassifier:
    """Wraps a HuggingFace CLIP model with our category/gender/color prompts.

    Late-imports heavy deps so `from clothist_api.cv.classifier import ...`
    works on a vanilla `uv sync` runtime.

    Per spec §2c:
      logits = (image_embeds @ text_embeds.T) * logit_scale.exp()
      probs  = softmax(logits)
    """

    def __init__(self, model_id: str = "openai/clip-vit-base-patch32") -> None:
        # Late imports — fail fast and loud with a clear message if cv extra
        # isn't installed.
        try:
            from transformers import CLIPModel, CLIPProcessor
            import torch
        except ImportError as e:
            raise RuntimeError(
                "CLIPClassifier requires the `cv` optional-extra. "
                "Run `uv sync --extra cv` first."
            ) from e

        self.model_id = model_id
        self.model = CLIPModel.from_pretrained(model_id)
        self.processor = CLIPProcessor.from_pretrained(model_id)
        # Per §2c CR-1: capture the model's learned temperature once at init.
        # CLIP's `logit_scale` is the log of the temperature; `.exp()` is the
        # multiplier we apply before softmax.
        self.logit_scale = float(self.model.logit_scale.exp().item())

        # Device autodetect: MPS → CUDA → CPU.
        if torch.backends.mps.is_available():
            self._device = "mps"
        elif torch.cuda.is_available():
            self._device = "cuda"
        else:
            self._device = "cpu"
        self.model = self.model.to(self._device).eval()
        self._torch = torch

        # Pre-encode all prompts once. We store them on-device + L2-normalized;
        # per-image classification is just a matmul.
        self._cat_keys, self._cat_embeds = self._encode_prompt_set(CATEGORY_PROMPTS)
        self._gen_keys, self._gen_embeds = self._encode_prompt_set(GENDER_PROMPTS)
        self._color_keys, self._color_embeds = self._encode_prompt_set(_color_prompts())
        logger.info(
            "cv_classifier_ready model=%s device=%s logit_scale=%.2f",
            model_id, self._device, self.logit_scale,
        )

    def _encode_prompt_set(self, prompts: dict[str, list[str]]) -> tuple[list[str], "torch.Tensor"]:
        """For each class with N prompts, return ONE embedding (mean of N L2-normalized prompts).

        Returns (class_names_in_order, tensor of shape (num_classes, dim)).
        """
        torch = self._torch
        keys = list(prompts.keys())
        with torch.no_grad():
            class_vectors: list["torch.Tensor"] = []
            for k in keys:
                texts = prompts[k]
                inputs = self.processor(text=texts, return_tensors="pt", padding=True)
                inputs = {kk: vv.to(self._device) for kk, vv in inputs.items()}
                # transformers ≥5 wraps the projected text embedding in
                # `BaseModelOutputWithPooling.pooler_output`. Older
                # versions returned the tensor directly; tolerate both.
                emb_out = self.model.get_text_features(**inputs)
                emb = getattr(emb_out, "pooler_output", emb_out)  # (N, dim)
                emb = emb / emb.norm(dim=-1, keepdim=True)
                # Mean over N prompts, then re-normalize.
                mean = emb.mean(dim=0)
                mean = mean / mean.norm()
                class_vectors.append(mean)
            stacked = torch.stack(class_vectors)  # (num_classes, dim)
        return keys, stacked

    def encode_images(self, images: list["PILImage.Image"]) -> "torch.Tensor":
        """Encode a batch of PIL images. Returns (N, dim) L2-normalized tensor."""
        torch = self._torch
        inputs = self.processor(images=images, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}
        with torch.no_grad():
            feats_out = self.model.get_image_features(**inputs)
            feats = getattr(feats_out, "pooler_output", feats_out)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats

    def _softmax_top(
        self, image_embeds: "torch.Tensor", class_embeds: "torch.Tensor",
        class_keys: list[str],
    ) -> list[tuple[str, float, tuple[str, float] | None]]:
        """For each image vector, return (top-1 class, prob, runner-up)."""
        # Logits per CLIP convention: dot product × logit_scale.
        logits = image_embeds @ class_embeds.T * self.logit_scale  # (N, num_classes)
        probs = logits.softmax(dim=-1).cpu().numpy()
        out: list[tuple[str, float, tuple[str, float] | None]] = []
        for row in probs:
            top1_idx = int(row.argmax())
            top1 = (class_keys[top1_idx], float(row[top1_idx]))
            ordered = sorted(enumerate(row), key=lambda kv: -kv[1])
            runner_up: tuple[str, float] | None = None
            if len(ordered) >= 2:
                ru_idx, ru_prob = ordered[1]
                runner_up = (class_keys[ru_idx], float(ru_prob))
            out.append((top1[0], top1[1], runner_up))
        return out

    def classify_batch(
        self,
        images: list["PILImage.Image"],
        urls: list[str],
        image_bytes_list: list[bytes],
    ) -> list[CVVerdict]:
        """Classify a batch of images. Returns a CVVerdict per image."""
        started = time.perf_counter()
        image_embeds = self.encode_images(images)

        cats = self._softmax_top(image_embeds, self._cat_embeds, self._cat_keys)
        gens = self._softmax_top(image_embeds, self._gen_embeds, self._gen_keys)

        verdicts: list[CVVerdict] = []
        for i, url in enumerate(urls):
            # Color via center-crop quantize on the source bytes (more robust
            # than CLIP-only color matching on fashion photography).
            color_pairs = _center_crop_quantize(image_bytes_list[i])
            cat_top, cat_conf, cat_ru = cats[i]
            gen_top, gen_conf, gen_ru = gens[i]
            verdicts.append(CVVerdict(
                category=cat_top,
                category_confidence=cat_conf,
                category_runner_up=cat_ru,
                gender=gen_top,
                gender_confidence=gen_conf,
                gender_runner_up=gen_ru,
                colors=color_pairs,
                model_id=self.model_id,
                image_url=url,
                duration_ms=int((time.perf_counter() - started) * 1000 / max(1, len(images))),
            ))
        return verdicts
