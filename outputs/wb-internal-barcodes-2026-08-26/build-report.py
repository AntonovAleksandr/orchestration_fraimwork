"""Выгрузка карточек ЛК ВБ, чьи баркоды не сопоставляются с PIM.

Источник — снимок каталога прод-кабинета от 2026-07-27
(platform-new/wbconnector/dev/catalog/wb-catalog-2026-07-27.jsonl.gz).

Два класса, оба измерены 2026-08-25 сверкой всего каталога с прод-БД PIM:

  внутренний  первая цифра «2», длина 13 — префикс EAN-13, зарезервированный
              под внутреннее обращение. В PIM таких нет ни одного, поэтому
              экспорт заказа в OTS остановится с unknown_sku.
  битый       длина не 13 — заведомо не баркод (123, 56-58, серия 46012345678x).

Карточки делятся на «смешанные» (часть размеров на товарном GS1, часть на
внутреннем) и «полностью внутренние». Первые — живой товар с нормальным
vendorCode, где одному размеру завели внутренний баркод; это и есть основная
работа для контент-менеджеров.
"""

import gzip
import json
import sys
from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

SNAPSHOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])


def classify(barcode: str) -> str:
    if len(barcode) != 13:
        return "битый"
    if barcode.startswith("2"):
        return "внутренний"
    return "ok"


def main() -> None:
    rows, summary = [], Counter()
    cards_total = sizes_total = 0

    with gzip.open(SNAPSHOT, "rt", encoding="utf-8") as fh:
        for line in fh:
            card = json.loads(line)
            cards_total += 1

            sizes = card.get("sizes") or []
            bad = []
            for size in sizes:
                for barcode in size.get("skus") or []:
                    sizes_total += 1
                    kind = classify(barcode)
                    if kind != "ok":
                        bad.append((size, barcode, kind))

            if not bad:
                continue

            # Размер может нести несколько баркодов, поэтому считаем именно
            # размеры, а не строки: контент-менеджер правит размер.
            bad_sizes = {s["chrtID"] for s, _, _ in bad}
            card_kind = "полностью внутренняя" if len(bad_sizes) == len(sizes) else "смешанная"
            summary[card_kind] += 1

            for size, barcode, kind in bad:
                summary[kind] += 1
                rows.append(
                    {
                        "Тип карточки": card_kind,
                        "Класс баркода": kind,
                        "nmID": card["nmID"],
                        "vendorCode": card.get("vendorCode", ""),
                        "Предмет": card.get("subjectName", ""),
                        "Размер": size.get("techSize", ""),
                        "Баркод": barcode,
                        "chrtID": size.get("chrtID"),
                        "Проблемных размеров": len(bad_sizes),
                        "Всего размеров": len(sizes),
                        "Обновлена": (card.get("updatedAt") or "")[:10],
                        "Заведена": (card.get("createdAt") or "")[:10],
                    }
                )

    # Смешанные — сначала: это живой товар, где правка одного размера снимает
    # проблему. Внутри — по дате обновления, свежие выше.
    rows.sort(key=lambda r: (r["Тип карточки"] != "смешанная", r["Класс баркода"], -int(r["Обновлена"].replace("-", "") or 0)))

    wb = Workbook()
    write_sheet(wb.active, rows)
    write_summary(wb.create_sheet("Сводка"), summary, cards_total, sizes_total, len(rows))
    wb.save(OUT)

    print(f"карточек в снимке: {cards_total}, размеро-баркодов: {sizes_total}")
    print(f"строк в выгрузке: {len(rows)}")
    for k, v in sorted(summary.items()):
        print(f"  {k}: {v}")


def write_sheet(ws, rows) -> None:
    ws.title = "Карточки к правке"
    headers = list(rows[0].keys())
    ws.append(headers)

    head_fill = PatternFill("solid", fgColor="D9E1F2")
    for col, _ in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col)
        cell.font = Font(bold=True)
        cell.fill = head_fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)

    mixed_fill = PatternFill("solid", fgColor="FFF2CC")
    for row in rows:
        ws.append([row[h] for h in headers])
        if row["Тип карточки"] == "смешанная":
            for col in range(1, len(headers) + 1):
                ws.cell(row=ws.max_row, column=col).fill = mixed_fill

    widths = {"Тип карточки": 22, "Класс баркода": 14, "nmID": 12, "vendorCode": 28,
              "Предмет": 22, "Размер": 10, "Баркод": 16, "chrtID": 12,
              "Проблемных размеров": 12, "Всего размеров": 10, "Обновлена": 12, "Заведена": 12}
    for col, header in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(col)].width = widths.get(header, 14)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def write_summary(ws, summary, cards_total, sizes_total, rows_total) -> None:
    ws.append(["Снимок каталога прод-кабинета", "2026-07-27"])
    ws.append(["Карточек в снимке", cards_total])
    ws.append(["Размеро-баркодов", sizes_total])
    ws.append([])
    ws.append(["Строк в выгрузке (проблемных размеро-баркодов)", rows_total])
    ws.append(["  из них внутренних «2…»", summary["внутренний"]])
    ws.append(["  из них битой длины", summary["битый"]])
    ws.append([])
    ws.append(["Смешанных карточек (часть размеров на GS1)", summary["смешанная"]])
    ws.append(["Полностью внутренних карточек", summary["полностью внутренняя"]])
    ws.append([])
    ws.append(["Сверка с разбором 2026-08-25 (2 035 / 991)"])
    for line in (
        "Тот разбор считал по баркодам и только внутренние «2…» — так выходит ровно 2 035 / 991,",
        "и эта выгрузка воспроизводит его в точности. Здесь разбивка по размерам и с учётом",
        "битых баркодов, поэтому смешанных на 11 больше: 9 карточек содержат только битый",
        "баркод без внутренних, и ещё 2 имеют размер вовсе без баркода.",
    ):
        ws.append([line])
    ws.append([])
    ws.append(["Почему это важно"])
    for line in (
        "Экспорт заказа в OTS идёт с нашим артикулом (vendor_code уровня SKU) из PIM.",
        "Связка PIM ↔ WB — по баркоду: другого общего ключа нет, vendorCode карточки",
        "на проде это «модель/цвет» и товар по нему не опознать.",
        "Баркодов с первой цифрой «2» в PIM нет ни одного (все 626 039 начинаются с «4»),",
        "поэтому такой заказ не уедет на склад и попадёт в реестр отклонений unknown_sku.",
        "Правка — привести баркод размера в ЛК ВБ к товарному EAN: склад и OTS",
        "физически работают по баркоду, обойти это на стороне сервиса нечем.",
        "Жёлтым выделены смешанные карточки — там нормальный vendorCode и обычно",
        "один проблемный размер из нескольких; это самая быстрая и полезная правка.",
    ):
        ws.append([line])

    ws.column_dimensions["A"].width = 82
    ws.column_dimensions["B"].width = 16
    for row in (1, 12, 17):
        ws.cell(row=row, column=1).font = Font(bold=True)


if __name__ == "__main__":
    main()
