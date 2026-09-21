# Образец стикера WB сборочного задания (58×40 мм)

Сгенерировано 2026-08-21 из песочницы WB (задание 80005), см.
`platform-new/wbconnector/internal/worker/sticker_sample_test.go`.

Файлы:

- `sticker-58x40-zplh.zpl` — **горизонтальный** разворот (ZPL, то, что просил
  склад). Это сырые команды принтеру — их и шлём на печать.
- `sticker-58x40-zplh.png` — рендер горизонтального для предпросмотра.
- `sticker-58x40-zplv.zpl` / `sticker-58x40-zplv.png` — вертикальный разворот
  (текущий формат коннектора) для сравнения.
- `meta.txt` — реквизиты задания: barcode `sand-!s0t7NMBR`, части стикера
  88445 / 4220, слово TEST — метка песочницы.

## Ручная печать (Zebra, RAW на 9100)

```
# macOS/Linux:
nc <ip-принтера> 9100 < sticker-58x40-zplh.zpl

# или через CUPS (raw queue):
lp -d <printer> -o raw sticker-58x40-zplh.zpl
```

PNG — только для просмотра/проверки верстки, на принтер не отправлять.

## Как перегенерировать

```
cd platform-new/wbconnector
set -a; source .env; set +a
WBCONNECTOR_TEST_DSN=postgres://wb:wb@localhost:55432/wbconnector?sslmode=disable \
WB_SANDBOX_E2E=1 go test ./internal/worker/ -run TestSandboxStickerSample -count=1 -v
```

PNG из ZPL (Labelary, 203 dpi, 58×40 мм = 2.283×1.575"):

```
curl -X POST "http://api.labelary.com/v1/printers/8dpmm/labels/2.283x1.575/0/" \
  -H "Accept: image/png" --data-binary @sticker-58x40-zplh.zpl -o sticker-58x40-zplh.png
```
