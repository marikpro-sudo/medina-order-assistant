"""Data source interface. Tools depend only on this protocol.

Synthetic implementation: `data_access.synthetic`. A production adapter would read the same
entities from the portal database or from staging tables filled by the ERP batch export.
"""

from datetime import date
from typing import Protocol

from data.schema import Batch, Customer, OrderHistoryLine, Product


class DataSource(Protocol):
    def today(self) -> date: ...

    def products(self) -> list[Product]: ...

    def get_product(self, material_id: str) -> Product | None: ...

    def get_by_ean(self, ean13: str) -> Product | None: ...

    def batches(self, material_id: str, plant: str | None = None) -> list[Batch]: ...

    def customers(self) -> list[Customer]: ...

    def get_customer(self, customer_id: str) -> Customer | None: ...

    def history(self, customer_id: str) -> list[OrderHistoryLine]: ...
