"""Local CLIP recognisability scorer against a curated object vocabulary (T0.3)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Sequence

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Everyday objects street loops might resemble (doodle-friendly).
DEFAULT_VOCABULARY: tuple[str, ...] = (
    "duck",
    "heart",
    "fish",
    "key",
    "star",
    "dog",
    "cat",
    "bird",
    "rabbit",
    "horse",
    "elephant",
    "butterfly",
    "flower",
    "tree",
    "house",
    "car",
    "bicycle",
    "boat",
    "airplane",
    "guitar",
    "apple",
    "banana",
    "smile",
    "circle",
    "square",
    "triangle",
    "letter a",
    "letter s",
    "letter m",
    "number 8",
)

# Drop abstract geometry / letters that steal weak matches; keep concrete nouns.
SKETCH_VOCABULARY: tuple[str, ...] = (
    "duck",
    "heart",
    "fish",
    "key",
    "star",
    "dog",
    "cat",
    "bird",
    "rabbit",
    "horse",
    "elephant",
    "butterfly",
    "flower",
    "tree",
    "house",
    "car",
    "bicycle",
    "boat",
    "airplane",
    "guitar",
    "apple",
    "banana",
    "boot",
    "umbrella",
    "anchor",
    "mushroom",
    "snail",
    "swan",
    "teddy bear",
    "ice cream",
)

PromptFn = Callable[[str], str]

PROMPT_STYLES: dict[str, PromptFn] = {
    "line_drawing": lambda label: (
        f"a simple white line drawing of a {label} on a black background"
    ),
    "sketch": lambda label: f"a hand-drawn sketch of a {label}",
    "silhouette": lambda label: f"a white silhouette of a {label} on black",
    "route_map": lambda label: (
        f"a GPS running route on a map that looks like a {label}"
    ),
    "doodle": lambda label: f"a simple doodle of a {label}",
}


@dataclass(frozen=True)
class RecognitionHit:
    label: str
    score: float


@dataclass
class RecognitionResult:
    label_guess: str
    score: float
    ranked: list[RecognitionHit]
    prompt_style: str = "line_drawing"


def _prompt_for(label: str, style: str = "line_drawing") -> str:
    fn = PROMPT_STYLES.get(style, PROMPT_STYLES["line_drawing"])
    return fn(label)


@lru_cache(maxsize=1)
def _load_clip_model():
    import open_clip
    import torch

    model_name = "ViT-B-32"
    pretrained = "openai"
    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name, pretrained=pretrained
    )
    tokenizer = open_clip.get_tokenizer(model_name)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    model.eval()
    return model, preprocess, tokenizer, device


@lru_cache(maxsize=32)
def _encode_texts_cached(labels: tuple[str, ...], style: str):
    import torch

    model, _, tokenizer, device = _load_clip_model()
    prompts = [_prompt_for(label, style) for label in labels]
    with torch.no_grad():
        tokens = tokenizer(prompts).to(device)
        feats = model.encode_text(tokens)
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats


def score_silhouette(
    image: Image.Image,
    vocabulary: Sequence[str] | None = None,
    *,
    top_k: int = 5,
    prompt_style: str = "line_drawing",
) -> RecognitionResult:
    """Score a silhouette PNG against the object vocabulary with local CLIP."""
    import torch

    vocab = tuple(vocabulary) if vocabulary is not None else DEFAULT_VOCABULARY
    model, preprocess, _, device = _load_clip_model()
    text_feats = _encode_texts_cached(vocab, prompt_style)

    rgb = image.convert("RGB")
    tensor = preprocess(rgb).unsqueeze(0).to(device)
    with torch.no_grad():
        img_feats = model.encode_image(tensor)
        img_feats = img_feats / img_feats.norm(dim=-1, keepdim=True)
        sims = (img_feats @ text_feats.T).squeeze(0).detach().cpu().numpy()

    order = np.argsort(-sims)
    ranked = [
        RecognitionHit(label=vocab[i], score=float(sims[i]))
        for i in order[: max(1, top_k)]
    ]
    best = ranked[0]
    return RecognitionResult(
        label_guess=best.label,
        score=best.score,
        ranked=ranked,
        prompt_style=prompt_style,
    )


def score_silhouette_ensemble(
    image: Image.Image,
    vocabulary: Sequence[str] | None = None,
    *,
    styles: Sequence[str] = ("line_drawing", "sketch", "silhouette", "doodle"),
    top_k: int = 5,
) -> RecognitionResult:
    """Max-pool similarities across prompt styles (helps weak line drawings)."""
    vocab = tuple(vocabulary) if vocabulary is not None else SKETCH_VOCABULARY
    best_per_label = {label: -1.0 for label in vocab}
    best_style = {label: styles[0] for label in vocab}

    for style in styles:
        result = score_silhouette(
            image, vocabulary=vocab, top_k=len(vocab), prompt_style=style
        )
        for hit in result.ranked:
            if hit.score > best_per_label[hit.label]:
                best_per_label[hit.label] = hit.score
                best_style[hit.label] = style

    ordered = sorted(best_per_label.items(), key=lambda kv: -kv[1])
    ranked = [RecognitionHit(label=lab, score=sc) for lab, sc in ordered[:top_k]]
    best = ranked[0]
    return RecognitionResult(
        label_guess=best.label,
        score=best.score,
        ranked=ranked,
        prompt_style=f"ensemble:{best_style[best.label]}",
    )


def clip_available() -> bool:
    try:
        import open_clip  # noqa: F401
        import torch  # noqa: F401

        return True
    except ImportError:
        return False
