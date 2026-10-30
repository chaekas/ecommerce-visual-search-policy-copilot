"""Small, on-demand importer for Amazon Reviews'23 item metadata.

Imports a bounded sample from one category. This is not a bulk mirror of the
full dataset and does not create ground-truth policy-violation labels.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import requests
from PIL import Image, UnidentifiedImageError

from core.analysis import assess_listing, image_color_and_histogram
from core.database import add_product, list_products

CATEGORY_CONFIGS = {
    "All Beauty": "raw_meta_All_Beauty",
    "Appliances": "raw_meta_Appliances",
    "Arts, Crafts & Sewing": "raw_meta_Arts_Crafts_and_Sewing",
    "Automotive": "raw_meta_Automotive",
    "Baby": "raw_meta_Baby",
    "Cell Phones & Accessories": "raw_meta_Cell_Phones_and_Accessories",
    "Clothing, Shoes & Jewelry": "raw_meta_Clothing_Shoes_and_Jewelry",
    "Electronics": "raw_meta_Electronics",
    "Grocery & Gourmet Food": "raw_meta_Grocery_and_Gourmet_Food",
    "Health & Household": "raw_meta_Health_and_Household",
    "Home & Kitchen": "raw_meta_Home_and_Kitchen",
    "Musical Instruments": "raw_meta_Musical_Instruments",
    "Office Products": "raw_meta_Office_Products",
    "Pet Supplies": "raw_meta_Pet_Supplies",
    "Sports & Outdoors": "raw_meta_Sports_and_Outdoors",
    "Tools & Home Improvement": "raw_meta_Tools_and_Home_Improvement",
    "Toys & Games": "raw_meta_Toys_and_Games",
}

DATASET_ID = "McAuley-Lab/Amazon-Reviews-2023"
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _clean_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(part) for part in value if part)
    if value is None:
        return ""
    return str(value).strip()


def _image_url(record: dict[str, Any]) -> str:
    images = record.get("images") or {}
    for key in ("large", "hi_res", "thumb"):
        values = images.get(key) or []
        if isinstance(values, list):
            for url in values:
                if isinstance(url, str) and url.startswith("https://"):
                    return url
    return ""


def import_category_sample(
    category: str,
    limit: int,
    upload_dir: str | Path = "data/uploads",
    progress_callback=None,
) -> dict[str, int]:
    """Import at most limit products with downloadable product images."""
    if category not in CATEGORY_CONFIGS:
        raise ValueError("Choose a supported category from the category list.")
    if not 1 <= int(limit) <= 200:
        raise ValueError("Sample size must be between 1 and 200.")

    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError("Dataset import dependency missing. Install requirements.txt.") from exc

    upload_path = Path(upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    existing_titles = {
        re.sub(r"\s+", " ", p.get("title", "").strip().casefold())
        for p in list_products()
    }
    stats = {"scanned": 0, "imported": 0, "skipped_duplicate": 0,
             "skipped_no_image": 0, "skipped_error": 0}

    dataset = load_dataset(
        DATASET_ID,
        CATEGORY_CONFIGS[category],
        split="full",
        streaming=True,
    )
    with requests.Session() as session:
        for record in dataset:
            if stats["imported"] >= limit:
                break
            stats["scanned"] += 1
            title = _clean_text(record.get("title"))
            normalized = re.sub(r"\s+", " ", title.casefold())
            if not title or normalized in existing_titles:
                stats["skipped_duplicate"] += 1
                continue

            url = _image_url(record)
            if not url:
                stats["skipped_no_image"] += 1
                continue

            try:
                response = session.get(url, timeout=12, stream=True)
                response.raise_for_status()
                chunks = []
                size = 0
                for chunk in response.iter_content(64 * 1024):
                    size += len(chunk)
                    if size > MAX_IMAGE_BYTES:
                        raise ValueError("Image exceeds 8 MB limit")
                    chunks.append(chunk)
                image_bytes = b"".join(chunks)
                with Image.open(io.BytesIO(image_bytes)) as image:
                    image.verify()
                color, _ = image_color_and_histogram(image_bytes)
                description = " ".join(filter(None, [
                    _clean_text(record.get("subtitle")),
                    _clean_text(record.get("features")),
                    _clean_text(record.get("description")),
                ]))[:8000]
                category_name = _clean_text(record.get("main_category")) or category
                assessment = assess_listing(title, description, color, category_name)
                with Image.open(io.BytesIO(image_bytes)) as image:
                    extension = ".png" if image.format == "PNG" else ".webp" if image.format == "WEBP" else ".jpg"
                identifier = str(record.get("parent_asin") or record.get("asin") or stats["scanned"])
                identifier = re.sub(r"[^A-Za-z0-9_.-]", "_", identifier)
                image_path = upload_path / f"amazon-{identifier}{extension}"
                image_path.write_bytes(image_bytes)
                raw_price = record.get("price")
                try:
                    price = float(raw_price) if raw_price not in (None, "", "None") else 0.0
                except (TypeError, ValueError):
                    price = 0.0

                add_product({
                    "title": title[:500],
                    "description": description,
                    "category": category_name[:200],
                    "seller": _clean_text(record.get("store"))[:300],
                    "price": max(0.0, price),
                    "image_path": str(image_path),
                    "image_color": color,
                    "risk_score": assessment["risk_score"],
                    "risk_level": assessment["risk_level"],
                    "flags": "\n".join(assessment["flags"]),
                    "status": "Pending review",
                })
                existing_titles.add(normalized)
                stats["imported"] += 1
            except Exception:
                stats["skipped_error"] += 1

            if progress_callback:
                progress_callback(min(1.0, stats["imported"] / limit), stats.copy())

    return stats
