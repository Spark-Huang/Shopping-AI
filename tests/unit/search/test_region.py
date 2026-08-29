from search.app.region import DEFAULT_REGION, load_region, save_region


def test_region_configuration_defaults_to_guizhou(tmp_path, monkeypatch):
    monkeypatch.setenv("REGION_FILE", str(tmp_path / "region"))
    monkeypatch.delenv("SHOPPING_REGION", raising=False)
    assert load_region() == DEFAULT_REGION == "贵州"


def test_region_configuration_persists_selected_value(tmp_path, monkeypatch):
    monkeypatch.setenv("REGION_FILE", str(tmp_path / "region"))
    assert save_region("四川") == "四川"
    assert load_region() == "四川"
    try:
        save_region("Invalid region")
    except ValueError:
        pass
    else:
        raise AssertionError("expected invalid region rejection")
