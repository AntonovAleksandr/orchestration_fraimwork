#!/usr/bin/env python3
"""Сверка снимка экрана с эталоном без зависимостей и без траты контекста.

Сравнение идёт числами. Картинка попадает к агенту только если расхождение выше
порога, и то — уменьшенная и обрезанная по области расхождения.

Работает на чистом Python 3 + sips (входит в macOS). numpy/PIL/ImageMagick не нужны.

    visual-check.py <снимок.png> <эталон.png> [--tolerance 2.0] [--out ДИР]

Коды возврата: 0 — совпало, 1 — расхождение, 2 — ошибка запуска.
"""
import os, sys, json, struct, subprocess, tempfile, argparse

CMP_W = 420          # ширина, до которой ужимаем перед сравнением
CH_TOL = 12          # допуск на канал: ниже — пиксель считаем совпавшим
REPORT_W = 760       # ширина картинки для отчёта
GRID = 16            # сетка для локализации области расхождения


def to_bmp(src, dst, width):
    r = subprocess.run(["sips", "-Z", str(width), "-s", "format", "bmp", src, "--out", dst],
                       capture_output=True)
    if r.returncode != 0 or not os.path.exists(dst):
        raise RuntimeError(f"sips не смог обработать {src}: {r.stderr.decode()[:200]}")


def load_bmp(path):
    d = open(path, "rb").read()
    if d[:2] != b"BM":
        raise RuntimeError(f"{path}: не BMP")
    off = struct.unpack_from("<I", d, 10)[0]
    w, h = struct.unpack_from("<ii", d, 18)
    bpp = struct.unpack_from("<H", d, 28)[0]
    if bpp not in (24, 32):
        raise RuntimeError(f"{path}: неподдержанная глубина {bpp}")
    return {"w": w, "h": abs(h), "bpp": bpp, "data": d, "off": off,
            "row": ((w * bpp + 31) // 32) * 4, "px": bpp // 8}


def compare(a, b):
    """Возвращает долю расхождения и сетку GRID x GRID с числом отличий в клетке."""
    w, h = min(a["w"], b["w"]), min(a["h"], b["h"])
    cells = [[0] * GRID for _ in range(GRID)]
    diff = total = 0
    da, db, pa, pb = a["data"], b["data"], a["px"], b["px"]
    for y in range(h):
        oa = a["off"] + y * a["row"]
        ob = b["off"] + y * b["row"]
        gy = min(GRID - 1, y * GRID // h)
        for x in range(w):
            ia, ib = oa + x * pa, ob + x * pb
            total += 1
            if (abs(da[ia] - db[ib]) > CH_TOL or
                    abs(da[ia + 1] - db[ib + 1]) > CH_TOL or
                    abs(da[ia + 2] - db[ib + 2]) > CH_TOL):
                diff += 1
                cells[gy][min(GRID - 1, x * GRID // w)] += 1
    return (100.0 * diff / total if total else 0.0), cells, w, h


def bbox(cells, w, h):
    """Прямоугольник, накрывающий клетки с расхождением, в долях 0..1."""
    pts = [(r, c) for r in range(GRID) for c in range(GRID) if cells[r][c] > 0]
    if not pts:
        return None
    r0 = min(p[0] for p in pts); r1 = max(p[0] for p in pts)
    c0 = min(p[1] for p in pts); c1 = max(p[1] for p in pts)
    return (c0 / GRID, r0 / GRID, (c1 + 1) / GRID, (r1 + 1) / GRID)


def describe(cells, box):
    """Человеческое описание, где именно разошлось."""
    if not box:
        return "расхождений нет"
    x0, y0, x1, y1 = box
    vert = "верх" if y1 <= 0.4 else "низ" if y0 >= 0.6 else "середина"
    horz = "слева" if x1 <= 0.4 else "справа" if x0 >= 0.6 else "по ширине"
    frac = (x1 - x0) * (y1 - y0)
    scale = "точечно" if frac < 0.08 else "локально" if frac < 0.35 else "по всему экрану"
    return f"{vert} экрана, {horz} ({scale}), полоса Y {y0:.0%}–{y1:.0%}"


def crop_report(src, box, out):
    """Уменьшенная вырезка области расхождения с запасом — её и смотрит агент."""
    dims = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", src],
                          capture_output=True, text=True).stdout
    w = h = None
    for line in dims.splitlines():
        if "pixelWidth" in line: w = int(line.split(":")[1])
        if "pixelHeight" in line: h = int(line.split(":")[1])
    if not w or not h:
        return None
    pad = 0.06
    x0 = max(0.0, box[0] - pad); y0 = max(0.0, box[1] - pad)
    x1 = min(1.0, box[2] + pad); y1 = min(1.0, box[3] + pad)
    cw = max(48, int((x1 - x0) * w)); chh = max(48, int((y1 - y0) * h))
    ox = int(x0 * w) + cw // 2 - w // 2
    oy = int(y0 * h) + chh // 2 - h // 2
    r = subprocess.run(["sips", "-c", str(chh), str(cw), "--cropOffset", str(oy), str(ox),
                        "-Z", str(REPORT_W), "-s", "format", "jpeg",
                        "-s", "formatOptions", "55", src, "--out", out],
                       capture_output=True)
    return out if r.returncode == 0 and os.path.exists(out) else None


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("shot"); ap.add_argument("golden")
    ap.add_argument("--tolerance", type=float, default=2.0,
                    help="допустимая доля расхождения в процентах (по умолчанию 2.0)")
    ap.add_argument("--out", default=None, help="куда класть картинку отчёта")
    ap.add_argument("--json", action="store_true", help="только JSON, без текста")
    a = ap.parse_args()

    for p in (a.shot, a.golden):
        if not os.path.exists(p):
            print(json.dumps({"ok": False, "error": f"нет файла: {p}"}, ensure_ascii=False))
            return 2

    tmp = tempfile.mkdtemp(prefix="vcheck-")
    try:
        to_bmp(a.shot, f"{tmp}/s.bmp", CMP_W)
        to_bmp(a.golden, f"{tmp}/g.bmp", CMP_W)
        s, g = load_bmp(f"{tmp}/s.bmp"), load_bmp(f"{tmp}/g.bmp")
        if abs(s["w"] - g["w"]) > 2 or abs(s["h"] - g["h"]) > 2:
            res = {"ok": False, "reason": "разный размер кадра",
                   "shot": [s["w"], s["h"]], "golden": [g["w"], g["h"]]}
            print(json.dumps(res, ensure_ascii=False))
            return 1
        pct, cells, w, h = compare(s, g)
        box = bbox(cells, w, h)
        ok = pct <= a.tolerance
        res = {"ok": ok, "diff_pct": round(pct, 3), "tolerance": a.tolerance,
               "where": describe(cells, box) if not ok else "совпало"}
        if not ok and box:
            out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.shot)),
                                        "diff-" + os.path.basename(a.shot).rsplit(".", 1)[0] + ".jpg")
            img = crop_report(a.shot, box, out)
            if img:
                res["report_image"] = img
                res["hint"] = "смотреть только эту вырезку, полный кадр в контекст не тянуть"
        print(json.dumps(res, ensure_ascii=False, indent=None if a.json else 2))
        return 0 if ok else 1
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2
    finally:
        for f in ("s.bmp", "g.bmp"):
            try: os.unlink(f"{tmp}/{f}")
            except OSError: pass
        try: os.rmdir(tmp)
        except OSError: pass


if __name__ == "__main__":
    sys.exit(main())
