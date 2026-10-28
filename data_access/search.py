"""Catalog search tolerant to typos, Latin transliteration, Kazakh letters and pharmacy shorthand.

Scoring: fuzzy name score (brand / INN) plus small bonuses or penalties for strength,
dosage form and pack size mentioned in the query.
"""

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from data.schema import Product

# Kazakh-specific Cyrillic letters folded to their closest Russian counterparts.
_KK_FOLD = str.maketrans({"ә": "а", "і": "и", "ң": "н", "ғ": "г", "қ": "к", "ө": "о",
                          "ұ": "у", "ү": "у", "һ": "х", "ё": "е", "й": "и"})

# Latin -> Cyrillic, multi-letter sequences first.
_LAT_MULTI = [("shch", "щ"), ("sch", "щ"), ("ch", "ч"), ("sh", "ш"), ("zh", "ж"), ("kh", "х"),
              ("ts", "ц"), ("yu", "ю"), ("ya", "я"), ("yo", "е"), ("ph", "ф"), ("th", "т"),
              ("ck", "к"), ("qu", "кв"), ("ee", "и"), ("oo", "у")]
_LAT_SINGLE = str.maketrans({"a": "а", "b": "б", "c": "ц", "d": "д", "e": "е", "f": "ф", "g": "г",
                             "h": "х", "i": "и", "j": "дж", "k": "к", "l": "л", "m": "м", "n": "н",
                             "o": "о", "p": "п", "q": "к", "r": "р", "s": "с", "t": "т", "u": "у",
                             "v": "в", "w": "в", "x": "кс", "y": "и", "z": "з"})

# Dosage form keywords (Russian, Kazakh, shorthand) -> canonical form family.
_FORM_WORDS = {
    "таб": "tab", "табл": "tab", "таблетки": "tab", "таблетка": "tab", "таблеток": "tab", "tab": "tab",
    "драже": "tab", "шип": "tab",
    "капс": "caps", "капсулы": "caps", "капсула": "caps", "капсул": "caps", "caps": "caps",
    "сироп": "syrup", "шарбат": "syrup", "syr": "syrup",
    "сусп": "susp", "суспензия": "susp", "суспензиясы": "susp",
    "капли": "drops", "кап": "drops", "тамшы": "drops", "тамшылар": "drops",
    "спрей": "spray", "спреи": "spray",
    "мазь": "ointment", "жакпамаи": "ointment", "жакпа": "ointment",
    "крем": "cream", "гель": "gel",
    "супп": "supp", "свечи": "supp", "суппозитории": "supp", "шам": "supp",
    "амп": "inj", "ампулы": "inj", "инъекции": "inj", "инъекций": "inj", "уколы": "inj", "ин": "inj",
    "порошок": "powder", "пор": "powder", "унтак": "powder",
    "р-р": "solution", "раствор": "solution", "ерітінді": "solution", "еритинди": "solution",
}

# Product dosage_form substrings -> form family (checked in order).
_PRODUCT_FORM_RULES = [
    ("инъекц", "inj"), ("инфуз", "inj"), ("подкожн", "inj"), ("суппозит", "supp"),
    ("суспенз", "susp"), ("сироп", "syrup"), ("капли", "drops"), ("спрей", "spray"),
    ("мазь", "ointment"), ("крем", "cream"), ("гель", "gel"), ("капсул", "caps"),
    ("таблет", "tab"), ("драже", "tab"), ("порошок", "powder"), ("раствор", "solution"),
]

_STOP_WORDS = {"мг", "мл", "г", "ед", "ме", "шт", "уп", "упак", "штук", "дана", "пачка", "кор",
               "mg", "ml", "по", "и", "для", "детский", "детскии", "балалар", "форте"}

# Common names pharmacies use instead of the INN (normalized INN -> aliases).
_INN_ALIASES = {
    "колекальциферол": ["витамин д", "витамин д3", "д3", "вит д"],
    "аскорбиновая кислота": ["витамин с", "витамин ц", "аскорбинка", "вит с"],
    "ацетилсалициловая кислота": ["аспирин", "кардиоаспирин"],
    "метамизол натрия": ["анальгин"],
    "магния лактат + пиридоксин": ["магний б6", "магне б6"],
    "смектит диоктаэдрический": ["смекта"],
    "натрия хлорид": ["физраствор", "физ раствор"],
    "морская вода": ["аквамарис"],
    "железа (iii) гидроксид полимальтозат": ["железо", "мальтофер"],
}

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
_PACK_RE = re.compile(r"(?:№|\b(?:n|no|х|x))\s*(\d+)\b")


def normalize(text: str) -> str:
    """Lowercase, fold Kazakh letters, transliterate Latin, keep letters/digits/%/№."""
    t = text.lower().translate(_KK_FOLD)
    if re.search(r"[a-z]", t):
        for src, dst in _LAT_MULTI:
            t = t.replace(src, dst)
        t = t.translate(_LAT_SINGLE)
    t = t.replace(",", ".")
    t = re.sub(r"[^0-9а-я%№.\-\s]", " ", t)
    t = re.sub(r"(?<=\d)(?=[а-я])|(?<=[а-я])(?=\d)", " ", t)  # "500мг" -> "500 мг"
    return re.sub(r"\s+", " ", t).strip(" .-")


def product_form_family(dosage_form: str) -> str | None:
    df = dosage_form.lower()
    for sub, fam in _PRODUCT_FORM_RULES:
        if sub in df:
            return fam
    return None


@dataclass
class _Indexed:
    product: Product
    brand: str
    inn: str
    inn_lat: str
    aliases: list[str]
    numbers: set[str]
    form: str | None
    pack: str | None


@dataclass
class SearchHit:
    product: Product
    score: float
    matched_on: str  # "material_id" | "ean13" | "brand" | "inn"


@dataclass
class _ParsedQuery:
    name: str
    numbers: set[str]
    form: str | None
    pack: str | None


def _numbers(text: str) -> set[str]:
    return {n.rstrip("0").rstrip(".") if "." in n else n for n in _NUM_RE.findall(text.replace(",", "."))}


def _parse_query(query: str) -> _ParsedQuery:
    q = normalize(query)
    pack_m = _PACK_RE.search(query.lower())
    pack = pack_m.group(1) if pack_m else None
    form = None
    name_tokens = []
    for tok in q.split():
        if tok in _FORM_WORDS:
            form = form or _FORM_WORDS[tok]
        elif _NUM_RE.fullmatch(tok) or tok in _STOP_WORDS or tok in {"№", "%"}:
            continue
        else:
            name_tokens.append(tok.replace("-", " "))
    numbers = _numbers(_PACK_RE.sub(" ", query.lower()))
    return _ParsedQuery(" ".join(name_tokens), numbers, form, pack)


class CatalogSearch:
    def __init__(self, products: list[Product]):
        self._items = [
            _Indexed(
                product=p,
                brand=normalize(p.brand).replace("-", " "),
                inn=normalize(p.inn),
                inn_lat=normalize(p.inn_lat),
                aliases=[normalize(a) for a in _INN_ALIASES.get(p.inn.lower(), [])],
                # strength plus volume/mass from the pack ("1 л", "100 мл"), not the "№N" count
                numbers=_numbers(p.strength) | _numbers(re.sub(r"№\s*\d+", " ", p.name_short)),
                form=product_form_family(p.dosage_form),
                pack=(m.group(1) if (m := re.search(r"№\s*(\d+)", p.name_short)) else None),
            )
            for p in products
        ]
        self._by_id = {i.product.material_id: i.product for i in self._items}
        self._by_ean = {i.product.ean13: i.product for i in self._items}

    def search(self, query: str, limit: int = 10, min_score: float = 60.0) -> list[SearchHit]:
        code = re.sub(r"\D", "", query)
        if re.fullmatch(r"\s*\d[\d\s]*", query):
            if len(code) == 18 and code in self._by_id:
                return [SearchHit(self._by_id[code], 100.0, "material_id")]
            if len(code) == 13 and code in self._by_ean:
                return [SearchHit(self._by_ean[code], 100.0, "ean13")]
            if len(code) >= 5:  # trailing digits of a material number
                hits = [p for mid, p in self._by_id.items() if mid.endswith(code)]
                if len(hits) == 1:
                    return [SearchHit(hits[0], 95.0, "material_id")]

        pq = _parse_query(query)
        if not pq.name:
            return []
        hits = []
        for it in self._items:
            brand_s = _name_score(pq.name, it.brand)
            inn_s = max([_name_score(pq.name, it.inn), _name_score(pq.name, it.inn_lat)]
                        + [_name_score(pq.name, a) for a in it.aliases])
            score, matched_on = (brand_s, "brand") if brand_s >= inn_s else (inn_s, "inn")
            if score < min_score - 15:
                continue
            if pq.numbers:
                matched = len(pq.numbers & it.numbers)
                if matched == len(pq.numbers):
                    score += 8
                elif matched:
                    score += 8 * matched / len(pq.numbers) - 3
                else:
                    score -= 6
            if pq.form and it.form:
                score += 5 if pq.form == it.form else -8
            if pq.pack and it.pack:
                score += 4 if pq.pack == it.pack else -2
            if score >= min_score:
                hits.append((score, it.product.material_id, SearchHit(it.product, 0.0, matched_on)))
        # Raw score first; ties go to catalog order (base packs before pack variants).
        hits.sort(key=lambda h: (-h[0], h[1]))
        out = []
        for score, _, hit in hits[:limit]:
            hit.score = round(min(score, 100.0), 1)
            out.append(hit)
        return out


def _name_score(query_name: str, field: str) -> float:
    if not field:
        return 0.0
    full = fuzz.ratio(query_name, field)
    # Query may hold extra words ("нурофен экспресс"); field words missing from the query cost a
    # little, so "амоксициллин" prefers plain amoxicillin over amoxicillin + clavulanic acid.
    q_tokens, f_tokens = set(query_name.split()), field.split()
    extra = sum(1 for t in f_tokens if t not in q_tokens and len(t) > 2 and t != "+")
    partial = fuzz.token_set_ratio(query_name, field) * 0.95 - 4 * extra
    prefix = fuzz.partial_ratio(query_name, field) * 0.9 - 4 * extra if len(query_name) >= 4 else 0
    return max(full, partial, prefix)
