from apps.inquiry import matching


def test_exact_match_ignores_separators(catalog):
    for query in ["81.50804-6004", "81 50804 6004", "815080460 04"]:
        result = matching.match_number(query)
        assert result[0].product_id == catalog["pad"].id
        assert result[0].score == 100 and result[0].method == matching.EXACT


def test_brand_prefix_is_stripped(catalog):
    result = matching.match_number("Knorr K012345")
    assert result[0].product_id == catalog["pad"].id and result[0].score == 100


def test_one_wrong_digit_is_a_fuzzy_match(catalog):
    result = matching.match_number("20837192")
    assert result[0].product_id == catalog["pad2"].id
    assert result[0].method == matching.FUZZY and 80 <= result[0].score < 100


def test_unrelated_number_does_not_match(catalog):
    assert matching.match_number("99999999") == []


def test_description_uses_semantic_search(catalog):
    result = matching.match_line(None, "air spring", "Volvo FH4")
    assert result[0].product_id == catalog["spring"].id
    assert result[0].method == matching.SEMANTIC and 60 <= result[0].score <= 80


def test_archived_products_are_excluded(catalog):
    catalog["pad"].status = "archived"
    catalog["pad"].save()
    assert matching.match_number("81.50804-6004") == []


def test_image_weight_lowers_score(catalog):
    assert matching.match_line("81.50804-6004", weight=0.9)[0].score == 90
