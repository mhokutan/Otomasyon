import scriptgen


def test_generate_script_crypto_success(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "en")
    monkeypatch.setenv("CRYPTO_COINS", "bitcoin,solana")

    fake_data = {
        "bitcoin": {"usd": 50000.0, "usd_24h_change": 1.5},
        "solana": {"usd": 150.0, "usd_24h_change": -2.1},
    }

    def fake_fetch(ids):
        # ensure generate_script forwards coin list from configuration
        assert ids == ["bitcoin", "solana"]
        return fake_data

    monkeypatch.setattr(scriptgen, "fetch_crypto_simple", fake_fetch)

    script, captions, coins_data = scriptgen.generate_script(mode="crypto")

    assert "60-second crypto brief" in script
    assert "BITCOIN" in script and "24h +1.50%" in script
    assert captions == [
        "BITCOIN: $50,000.00 | 24h +1.50%",
        "SOLANA: $150.00 | 24h -2.10%",
    ]
    assert coins_data == fake_data


def test_generate_script_crypto_fallback(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "en")
    monkeypatch.setenv("CRYPTO_COINS", "bitcoin")

    def fake_fetch(ids):
        assert ids == ["bitcoin"]
        return {}

    monkeypatch.setattr(scriptgen, "fetch_crypto_simple", fake_fetch)

    script, captions, coins_data = scriptgen.generate_script(mode="crypto")

    assert "no data" in script.lower()
    assert captions == ["60-second crypto brief (no data)"]
    assert coins_data == {}


def test_build_titles_returns_metadata_for_standard_use():
    captions = ["Breaking headline", "Second story"]

    meta = scriptgen.build_titles("news", captions=captions)

    assert isinstance(meta, scriptgen.TitleMetadata)
    assert meta.title.startswith("Daily Brief:")
    assert meta.title.endswith("Breaking headline")
    assert meta.captions == captions
    assert meta.captions is not captions
    assert "- Breaking headline" in (meta.description or "")


def test_build_titles_coin_rows_returns_caption_metadata():
    rows = [{"id": "bitcoin", "usd": 12345.0, "usd_24h_change": 2.5}]

    meta = scriptgen.build_titles("crypto", coin_rows=rows)

    assert isinstance(meta, scriptgen.TitleMetadata)
    assert meta.title is None
    assert meta.description is None
    assert meta.captions == ["BITCOIN: $12,345.00 | 24h +2.50%"]


def test_build_titles_headlines_returns_caption_metadata():
    headlines = [("First highlight", "https://example.com"), ("Second highlight", "")]

    meta = scriptgen.build_titles("news", headlines=headlines)

    assert isinstance(meta, scriptgen.TitleMetadata)
    assert meta.title is None
    assert meta.description is None
    assert meta.captions == ["First highlight", "Second highlight"]
