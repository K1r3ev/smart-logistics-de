from etl.dq import classify_reason


def _row(**kwargs):
    base = {
        "price": 85000.0,
        "currency_code": "643",
        "distance": 900.0,
        "total_weight": 20.0,
        "total_volume": 80.0,
        "loading_city_ok": True,
        "unloading_city_ok": True,
        "nearest_rate_date": None,
        "fx_rate": None,
    }
    base.update(kwargs)
    return base


def test_reject_non_positive_price():
    assert classify_reason(_row(price=0)) == "non_positive_price"
    assert classify_reason(_row(price=-1)) == "non_positive_price"


def test_rub_low_price_source_validation():
    assert classify_reason(_row(price=500, currency_code="643")) == "rub_source_validation_low_price"


def test_missing_fx_for_usd():
    assert (
        classify_reason(
            _row(currency_code="840", nearest_rate_date=None, fx_rate=None, price=2000)
        )
        == "missing_fx_rate"
    )


def test_valid_row_passes():
    assert classify_reason(_row()) is None


def test_unknown_city():
    assert classify_reason(_row(loading_city_ok=False)) == "unknown_city"