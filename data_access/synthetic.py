"""DataSource backed by the generated files in data/synthetic/."""

import csv
import json
from collections import defaultdict
from datetime import date
from functools import lru_cache
from pathlib import Path

from data.schema import Batch, Customer, DeliveryPoint, OrderHistoryLine, Product

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic"
# The synthetic snapshot is "taken" on this date; expiry and seasonality are relative to it.
SNAPSHOT_DATE = date(2026, 10, 28)


class SyntheticDataSource:
    def __init__(self, data_dir: Path = DEFAULT_DIR, snapshot_date: date = SNAPSHOT_DATE):
        self._today = snapshot_date
        self._products = [Product(**p) for p in _load_json(data_dir / "products.json")]
        self._by_id = {p.material_id: p for p in self._products}
        self._by_ean = {p.ean13: p for p in self._products}

        self._batches: dict[str, list[Batch]] = defaultdict(list)
        for b in _load_json(data_dir / "batches.json"):
            self._batches[b["material_id"]].append(Batch(**b))

        self._customers = []
        for c in _load_json(data_dir / "customers.json"):
            points = [DeliveryPoint(**dp) for dp in c.pop("delivery_points")]
            self._customers.append(Customer(delivery_points=points, **c))
        self._customers_by_id = {c.customer_id: c for c in self._customers}

        self._history: dict[str, list[OrderHistoryLine]] = defaultdict(list)
        with open(data_dir / "order_history.csv", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                row["qty"] = int(row["qty"])
                self._history[row["customer_id"]].append(OrderHistoryLine(**row))

    def today(self) -> date:
        return self._today

    def products(self) -> list[Product]:
        return self._products

    def get_product(self, material_id: str) -> Product | None:
        return self._by_id.get(material_id)

    def get_by_ean(self, ean13: str) -> Product | None:
        return self._by_ean.get(ean13)

    def batches(self, material_id: str, plant: str | None = None) -> list[Batch]:
        items = self._batches.get(material_id, [])
        return [b for b in items if plant is None or b.plant == plant]

    def customers(self) -> list[Customer]:
        return self._customers

    def get_customer(self, customer_id: str) -> Customer | None:
        return self._customers_by_id.get(customer_id)

    def history(self, customer_id: str) -> list[OrderHistoryLine]:
        return self._history.get(customer_id, [])


def _load_json(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def default_source() -> SyntheticDataSource:
    return SyntheticDataSource()
