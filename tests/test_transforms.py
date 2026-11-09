from etl.transforms import map_body_group, volume_category, weight_category


def test_weight_category_boundaries():
    assert weight_category(30.0) == "G20T"
    assert weight_category(29.9) == "FTL"
    assert weight_category(10.0) == "FTL"
    assert weight_category(9.9) == "10T"
    assert weight_category(5.0) == "10T"
    assert weight_category(2.5) == "5T"
    assert weight_category(0.5) == "L5T"
    assert weight_category(0.4) == "OTH"


def test_volume_category():
    assert volume_category(0) == "OTH"
    assert volume_category(120) == "FTL"
    assert volume_category(120.1) == "OTH"
    assert volume_category(40) == "FTL"


def test_body_group_mapping():
    assert map_body_group(56) == ("Тент", 56)
    assert map_body_group(61) == ("Тент", 56)
    assert map_body_group(46) == ("Рефрижератор", 4)
    assert map_body_group(1) == ("Борт", 15)
    assert map_body_group(None) == ("Не указан", None)
    assert map_body_group(68)[0] == "Прочие"