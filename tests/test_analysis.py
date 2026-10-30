from core.analysis import assess_listing, cosine_histogram_similarity, image_color_and_histogram
from PIL import Image
import io


def test_policy_term_is_flagged():
    result = assess_listing("Replica brand handbag", "A simple handbag for daily use with a shoulder strap.", "black", "Fashion")
    assert result["risk_score"] > 0
    assert any("counterfeit indicators" in flag for flag in result["flags"])


def test_short_description_is_flagged():
    result = assess_listing("Coffee mug", "Mug", "white", "Home & Kitchen")
    assert any("very short" in flag for flag in result["flags"])


def test_histogram_similarity_is_bounded():
    assert cosine_histogram_similarity([1, 0, 0], [1, 0, 0]) == 1.0
    assert 0 <= cosine_histogram_similarity([1, 0], [0, 1]) <= 1


def test_image_features():
    image = Image.new("RGB", (32, 32), (20, 40, 220))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    color, histogram = image_color_and_histogram(buffer.getvalue())
    assert color == "blue"
    assert len(histogram) == 24
