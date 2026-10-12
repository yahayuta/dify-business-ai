"""Generate synthetic purchase-order PDFs used to test the order-sheet extractor.

All companies, products and numbers are invented. Each sheet is written the way
real ones often are: different layouts, full-width digits, a typo in the total,
so the workflow's checks have something to catch.

    python scripts/make_order_sheets.py   # writes samples/order_sheets/*.pdf + expected.json
"""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

FONT = "HeiseiKakuGo-W5"
pdfmetrics.registerFont(UnicodeCIDFont(FONT))
OUT = Path(__file__).resolve().parent.parent / "samples" / "order_sheets"

# expected = what a correct extraction should return (used by tests and the README).
SHEETS = [
    {
        "file": "po_01_standard.pdf",
        "buyer": "株式会社サンプル雑貨店",
        "po_number": "PO-2026-0412",
        "order_date": "2026年10月1日",
        "delivery_date": "2026年10月10日",
        "lines": [
            ("MUG-BLU-01", "ストーンマグ ブルー", 24, 980),
            ("MUG-RED-01", "ストーンマグ レッド", 12, 980),
            ("TWL-WHT-M", "コットンタオル ホワイト M", 30, 1200),
        ],
        "stated_total": None,  # computed correctly
        "note": "",
    },
    {
        "file": "po_02_total_mismatch.pdf",
        "buyer": "合同会社テスト商会",
        "po_number": "TS-88120",
        "order_date": "2026/10/03",
        "delivery_date": "2026/10/15",
        "lines": [
            ("CND-LAV-200", "アロマキャンドル ラベンダー 200g", 40, 1500),
            ("CND-CIT-200", "アロマキャンドル シトラス 200g", 40, 1500),
        ],
        "stated_total": 125000,  # wrong on purpose: lines add up to 120,000
        "note": "",
    },
    {
        "file": "po_03_fullwidth.pdf",
        "buyer": "株式会社みほんマート",
        "po_number": "ＭＨ－００７７",
        "order_date": "令和8年10月5日",
        "delivery_date": "至急",
        "lines": [
            ("ＢＴＬ－５００", "ステンレスボトル ５００ｍｌ", 18, 2400),
            ("ＢＴＬ－７５０", "ステンレスボトル ７５０ｍｌ", 6, 2800),
        ],
        "stated_total": None,
        "note": "数量・単価は全角数字で記載",
        "fullwidth": True,
    },
]

_FW = str.maketrans("0123456789,", "０１２３４５６７８９，")


def _num(value: int, fullwidth: bool) -> str:
    text = f"{value:,}"
    return text.translate(_FW) if fullwidth else text


def draw(sheet: dict) -> dict:
    path = OUT / sheet["file"]
    fw = sheet.get("fullwidth", False)
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(f"注文書 {sheet['po_number']}")
    width, height = A4
    y = height - 25 * mm

    c.setFont(FONT, 18)
    c.drawString(20 * mm, y, "注 文 書")
    c.setFont(FONT, 10)
    y -= 12 * mm
    c.drawString(20 * mm, y, "株式会社ダミーリテール 御中")
    c.drawRightString(width - 20 * mm, y, sheet["buyer"])
    y -= 7 * mm
    c.drawString(20 * mm, y, f"注文番号：{sheet['po_number']}")
    c.drawRightString(width - 20 * mm, y, f"注文日：{sheet['order_date']}")
    y -= 7 * mm
    c.drawString(20 * mm, y, f"納品希望日：{sheet['delivery_date']}")

    y -= 14 * mm
    cols = [20 * mm, 55 * mm, 125 * mm, 150 * mm, width - 20 * mm]
    c.drawString(cols[0], y, "品番")
    c.drawString(cols[1], y, "品名")
    c.drawRightString(cols[3] - 4 * mm, y, "数量")
    c.drawRightString(cols[4] - 30 * mm, y, "単価")
    c.drawRightString(cols[4], y, "金額")
    c.line(20 * mm, y - 2 * mm, width - 20 * mm, y - 2 * mm)

    total = 0
    for sku, name, qty, price in sheet["lines"]:
        y -= 8 * mm
        amount = qty * price
        total += amount
        c.drawString(cols[0], y, sku)
        c.drawString(cols[1], y, name)
        c.drawRightString(cols[3] - 4 * mm, y, _num(qty, fw))
        c.drawRightString(cols[4] - 30 * mm, y, _num(price, fw))
        c.drawRightString(cols[4], y, _num(amount, fw))

    stated = sheet["stated_total"] if sheet["stated_total"] is not None else total
    y -= 4 * mm
    c.line(20 * mm, y, width - 20 * mm, y)
    y -= 8 * mm
    c.drawRightString(cols[4] - 30 * mm, y, "合計（税抜）")
    c.drawRightString(cols[4], y, _num(stated, fw) + "円")
    if sheet["note"]:
        y -= 14 * mm
        c.drawString(20 * mm, y, f"備考：{sheet['note']}")
    c.showPage()
    c.save()

    return {
        "file": sheet["file"],
        "po_number": sheet["po_number"].translate(str.maketrans("ＭＨ－０１２３４５６７８９", "MH-0123456789")),
        "lines": [
            {"sku": sku.translate(str.maketrans("ＢＴＬ－０１２３４５６７８９", "BTL-0123456789")),
             "quantity": qty, "unit_price": price}
            for sku, _, qty, price in sheet["lines"]
        ],
        "lines_total": total,
        "stated_total": stated,
        "expect_review": stated != total,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    expected = [draw(s) for s in SHEETS]
    (OUT / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(expected)} sheets to {OUT}")


if __name__ == "__main__":
    main()
