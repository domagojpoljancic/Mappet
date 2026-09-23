"""Local CLIP recognisability scorer against a curated object vocabulary (T0.3)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Curated everyday objects that street loops might resemble.
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


@dataclass(frozen=True)
class RecognitionHit:
    label: str
    score: float


@dataclass
class RecognitionResult:
    label_guess: str
    score: float
    ranked: list[RecognitionHit]


def _prompt_for(label: str) -> str:
    return f"a simple white line drawing of a {label} on a black background"


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


def _encode_texts(labels: Sequence[str]):
    import torch

    model, _, tokenizer, device = _load_clip_model()
    prompts = [_prompt_for(label) for label in labels]
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
) -> RecognitionResult:
    """Score a silhouette PNG against the object vocabulary with local CLIP."""
    import torch

    vocab = tuple(vocabulary) if vocabulary is not None else DEFAULT_VOCABULARY
    model, preprocess, _, device = _load_clip_model()
    text_feats = _encode_texts(vocab)

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
    return RecognitionResult(label_guess=best.label, score=best.score, ranked=ranked)


def clip_available() -> bool:
    try:
        import open_clip  # noqa: F401
        import torch  # noqa: F401

        return True
    except ImportError:
        return False
