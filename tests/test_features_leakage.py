from ml.features import FEATURE_COLS_CAT, FEATURE_COLS_NUM, LEAKAGE_COLS


def test_no_leakage_in_feature_lists():
    feats = set(FEATURE_COLS_NUM) | set(FEATURE_COLS_CAT)
    assert feats.isdisjoint(LEAKAGE_COLS)


def test_expected_core_features_present():
    for col in ("distance", "total_weight", "month_sin", "doy_cos"):
        assert col in FEATURE_COLS_NUM
    for col in ("origin_region", "destination_region", "body_group"):
        assert col in FEATURE_COLS_CAT