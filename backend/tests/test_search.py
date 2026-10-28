"""Search tests over the real synthetic catalog (no hardcoded ids)."""

import pytest

from data_access.search import CatalogSearch, normalize, product_form_family
from data_access.synthetic import default_source


@pytest.fixture(scope="session")
def search():
    # Session scope keeps the 400-product index build off the fast path.
    return CatalogSearch(default_source().products())


def top_hit(search, query):
    hits = search.search(query)
    assert hits, f"no hits for {query!r}"
    return hits[0]


def test_normalize_kazakh_letters():
    assert normalize("шәрбат") == "шарбат"


def test_normalize_latin_transliteration():
    assert normalize("nurofen") == "нурофен"


def test_normalize_strength_spacing():
    assert normalize("500мг") == "500 мг"


def test_normalize_comma_decimal():
    assert "0.1" in normalize("0,1%")


def test_exact_material_id(search):
    product = default_source().products()[0]
    hits = search.search(product.material_id)
    assert len(hits) == 1
    assert hits[0].product.material_id == product.material_id
    assert hits[0].matched_on == "material_id"


def test_exact_ean13(search):
    product = default_source().products()[0]
    hits = search.search(product.ean13)
    assert len(hits) == 1
    assert hits[0].product.material_id == product.material_id
    assert hits[0].matched_on == "ean13"


def test_typo_brand(search):
    assert top_hit(search, "нурафен").product.brand == "Нурофен"


def test_strength_number_bonus(search):
    assert top_hit(search, "нурофен 400").product.strength == "400 мг"
    assert top_hit(search, "амоксиклав 875/125").product.strength == "875 мг/125 мг"


def test_form_bonus(search):
    assert "суспензия" in top_hit(search, "ибупрофен суспензия").product.dosage_form
    assert "инъекций" in top_hit(search, "анальгин амп").product.dosage_form


def test_pack_number(search):
    assert top_hit(search, "урсосан 250 №100").product.name_short.endswith("№100")


def test_latin_inn(search):
    assert top_hit(search, "ibuprofen 400").product.inn == "Ибупрофен"


def test_kazakh_form_word(search):
    hit = top_hit(search, "амброксол шәрбат").product
    assert hit.inn == "Амброксол"
    assert hit.dosage_form == "сироп"


def test_aliases(search):
    assert top_hit(search, "витамин д капли").product.inn == "Колекальциферол"
    assert top_hit(search, "анальгин").product.inn == "Метамизол натрия"


def test_hyphenated_brand(search):
    for query in ("но шпа 40", "ношпа 40"):
        hit = top_hit(search, query).product
        assert hit.brand == "Но-шпа"
        assert hit.strength == "40 мг"


def test_single_inn_beats_combination(search):
    assert top_hit(search, "амоксициллин 500").product.inn == "Амоксициллин"


def test_volume_pack(search):
    assert top_hit(search, "хлоргексидин 1л").product.name_short.endswith("1 л")


def test_garbage_and_empty(search):
    assert search.search("qwerty zzz") == []
    assert search.search("") == []


@pytest.mark.parametrize("form,family", [
    ("таблетки, покрытые пленочной оболочкой", "tab"),
    ("капсулы", "caps"),
    ("раствор для инфузий", "inj"),
    ("спрей назальный", "spray"),
    ("суспензия для приема внутрь", "susp"),
])
def test_product_form_family(form, family):
    assert product_form_family(form) == family
