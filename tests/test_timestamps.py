from apm_mcp.normalization.apm import normalize_timestamp


def test_normalize_epoch_milliseconds():
    assert normalize_timestamp("1700000000000") == "2023-11-14T22:13:20+00:00"


def test_normalize_iso_timestamp_preserves_timezone():
    assert normalize_timestamp("2024-04-25T15:58:00+05:30") == "2024-04-25T15:58:00+05:30"


def test_normalize_applications_manager_english_datetime_without_guessing_timezone():
    normalized = normalize_timestamp("Apr 25, 2024 3:58 PM")
    assert normalized == "2024-04-25T15:58:00"
    assert not normalized.endswith("Z")
    assert "+00:00" not in normalized


def test_normalize_unknown_timestamp_preserves_original_value():
    assert normalize_timestamp("last Thursday around noon") == "last Thursday around noon"
