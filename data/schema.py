"""Synthetic data schema. Mirrors a typical ERP -> portal batch export, with generic field names."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Product:
    material_id: str  # 18 digits, synthetic range 1000000000000xxxxx
    ean13: str
    name_short: str  # e.g. "Панадол таб. п/о 500 мг №12"
    name_full: str
    inn: str  # international nonproprietary name (МНН), Russian
    inn_lat: str
    dosage_form: str
    strength: str
    atc_code: str
    pharm_group: str
    brand: str
    manufacturer: str
    country: str
    is_original: bool
    is_prescription: bool
    is_marked: bool  # subject to mandatory product marking
    order_multiple: int  # 1 / 5 / 10 / 20
    storage_temp: str  # e.g. "15-25", "2-8"
    category_path: str


@dataclass(frozen=True)
class Batch:
    material_id: str
    plant: str  # branch warehouse code, e.g. "P01"
    batch_id: str
    expiry_date: str  # ISO date
    manufacture_date: str
    qty_available: int
    price_customer: float  # KZT, per unit


@dataclass(frozen=True)
class DeliveryPoint:
    point_id: str
    name: str
    address: str


@dataclass(frozen=True)
class Customer:
    customer_id: str
    name: str
    delivery_points: list[DeliveryPoint] = field(default_factory=list)
    branch_plant: str = "P01"
    credit_limit: float = 0.0
    overdue_debt: float = 0.0


@dataclass(frozen=True)
class OrderHistoryLine:
    customer_id: str
    delivery_point: str
    date: str  # ISO date
    material_id: str
    qty: int


# Branch warehouses (synthetic).
PLANTS = {
    "P01": "Филиал Север",
    "P02": "Филиал Центр",
    "P03": "Филиал Юг",
}
