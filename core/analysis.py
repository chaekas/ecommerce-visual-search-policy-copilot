from __future__ import annotations

import io
import re
from collections import Counter

import numpy as np
from PIL import Image

# Demonstration rules only. Configure these for the marketplace's actual policy.
PROHIBITED_TERMS = {
    "weapons": ("firearm", "gun for sale", "explosive", "silencer"),
    "controlled substances": ("cocaine", "heroin", "methamphetamine"),
    "counterfeit indicators": ("replica brand", "fake designer", "counterfeit"),
    "regulated goods": ("prescription-only", "stolen goods"),
}
COLOR_NAMES = {
    "red": (220, 45, 45), "orange": (230, 130, 35), "yellow": (225, 205, 40),
    "green": (55, 155, 75), "blue": (55, 105, 205), "purple": (135, 70, 170),
    "pink": (220, 125, 160), "black": (35, 35, 35), "white": (235, 235, 235),
    "brown": (125, 85, 55), "gray": (130, 130, 130), "grey": (130, 130, 130),
}


def image_color_and_histogram(image_bytes: bytes) -> tuple[str, list[float]]:
    """Return a rough dominant color and normalized RGB histogram for similarity search."""
    with Image.open(io.BytesIO(image_bytes)) as source:
        image = source.convert("RGB").resize((128, 128))
        arr = np.asarray(image)
    pixels = arr.reshape(-1, 3)
    mean = pixels.mean(axis=0)
    color = min(COLOR_NAMES, key=lambda name: float(np.linalg.norm(mean - COLOR_NAMES[name])))
    hist = []
    for channel in range(3):
        bins, _ = np.histogram(pixels[:, channel], bins=8, range=(0, 256), density=False)
        hist.extend((bins / max(1, bins.sum())).tolist())
    return color, [float(v) for v in hist]


def image_histogram_from_path(path: str) -> list[float] | None:
    if not path:
        return None
    try:
        with Image.open(path) as image:
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="PNG")
        return image_color_and_histogram(buffer.getvalue())[1]
    except (OSError, ValueError):
        return None


def assess_listing(title: str, description: str, image_color: str, category: str = "") -> dict:
    text = f"{title} {description} {category}".casefold()
    flags: list[str] = []
    for policy, terms in PROHIBITED_TERMS.items():
        matches = [term for term in terms if term in text]
        if matches:
            flags.append(f"Possible {policy} policy issue: matched '{matches[0]}'.")
    if not title.strip():
        flags.append("Missing product title.")
    if len(description.strip()) < 20:
        flags.append("Description is very short; verify that key product details are present.")
    color_match = re.search(r"\b(red|orange|yellow|green|blue|purple|pink|black|white|brown|gray|grey)\b", title.casefold())
    if color_match and image_color not in {color_match.group(1), "unknown"}:
        # Color is a rough average-color estimate, not a reliable object-color classifier.
        flags.append(f"Possible color mismatch: title says '{color_match.group(1)}', image's rough dominant color is '{image_color}'. Verify manually.")
    score = 0
    score += min(80, sum(35 if "policy issue" in flag else 12 if "Missing" in flag else 8 if "short" in flag else 15 for flag in flags))
    score = min(100, score)
    level = "High" if score >= 50 else "Medium" if score >= 20 else "Low"
    return {"risk_score": score, "risk_level": level, "flags": flags}


def cosine_histogram_similarity(left: list[float], right: list[float]) -> float:
    a, b = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.clip(np.dot(a, b) / denom, 0.0, 1.0))
