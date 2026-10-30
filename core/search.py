from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from core.analysis import cosine_histogram_similarity, image_histogram_from_path


def text_scores(query: str, products: list[dict]) -> list[float]:
    if not products:
        return []
    documents = [f"{p.get('title','')} {p.get('description','')} {p.get('category','')}" for p in products]
    try:
        matrix = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform([query] + documents)
        return cosine_similarity(matrix[0:1], matrix[1:]).ravel().tolist()
    except ValueError:
        return [0.0] * len(products)


def search_products(products: list[dict], query: str = "", reference_image_path: str = "", limit: int = 20) -> list[dict]:
    if not products:
        return []
    scores = [0.0] * len(products)
    weights = [0.0] * len(products)
    if query.strip():
        for i, score in enumerate(text_scores(query, products)):
            scores[i] += 0.65 * score
            weights[i] += 0.65
    reference = image_histogram_from_path(reference_image_path) if reference_image_path else None
    if reference:
        for i, product in enumerate(products):
            candidate = image_histogram_from_path(product.get("image_path", ""))
            if candidate:
                scores[i] += 0.35 * cosine_histogram_similarity(reference, candidate)
                weights[i] += 0.35
    for i in range(len(scores)):
        scores[i] = scores[i] / weights[i] if weights[i] else 0.0
    results = []
    for product, score in zip(products, scores):
        item = dict(product)
        item["similarity_score"] = round(float(score), 4)
        results.append(item)
    return sorted(results, key=lambda item: (item["similarity_score"], item["created_at"]), reverse=True)[:limit]
