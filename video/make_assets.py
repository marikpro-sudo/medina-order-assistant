"""Builds the demo inputs for the video: a portal upload file with typical errors and a handwritten list photo."""

import shutil
from pathlib import Path

import xlwt

from data_access.synthetic import default_source

OUT = Path(__file__).parent / "assets"
CUSTOMER = "C100004"


def broken_upload_file(path: Path) -> None:
    ds = default_source()
    plant = ds.get_customer(CUSTOMER).branch_plant
    stocked = [p for p in ds.products() if sum(b.qty_available for b in ds.batches(p.material_id, plant)) > 500][:6]
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Order")
    for c, h in enumerate(["Штрихкод", "Код товара", "Количество"]):
        ws.write(0, c, h)
    bad_ean = stocked[2].ean13[:12] + str((int(stocked[2].ean13[12]) + 1) % 10)
    rows = [
        (stocked[0].ean13, stocked[0].material_id, str(stocked[0].order_multiple * 2)),
        (stocked[1].ean13, stocked[1].material_id, "7"),             # not a pack multiple
        (bad_ean, stocked[2].material_id, str(stocked[2].order_multiple)),  # wrong check digit
        (stocked[3].ean13, stocked[3].material_id, "10 уп"),          # text instead of a number
        (stocked[4].ean13, stocked[5].material_id, "5"),              # barcode and code of different products
    ]
    for r, row in enumerate(rows, start=1):
        for c, v in enumerate(row):
            ws.write(r, c, v)
    ws.write(6, 0, int(stocked[5].ean13))  # stored as a number, not text
    ws.write(6, 1, stocked[5].material_id)
    ws.write(6, 2, str(stocked[5].order_multiple))
    wb.save(str(path))


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    broken_upload_file(OUT / "zakaz_apteka.xls")
    shutil.copy(Path("evals/cases/files/photo_003.png"), OUT / "spisok_foto.png")
    print(sorted(p.name for p in OUT.iterdir()))
