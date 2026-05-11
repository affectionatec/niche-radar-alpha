from niche_radar.nlp.preprocessor import clean_text


def test_clean_text_strips_markup_and_urls():
    text = "<p>Hello</p> https://example.com ```code``` **World** with [link](https://x.y) and enough text"
    cleaned = clean_text(text)
    assert "https://" not in cleaned
    assert "```" not in cleaned
    assert "hello" in cleaned
    assert "world" in cleaned


def test_clean_text_rejects_short_text():
    assert clean_text("too short") == ""
