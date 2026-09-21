#!/usr/bin/env bash
# Снимок экрана мобильного приложения с уменьшением до разумного веса.
#
# Полноразмерный кадр iPhone — 390 КБ ≈ 97 тыс. токенов. Уменьшенный — 5–8 тыс.
# Поэтому в контекст агента должен попадать только уменьшенный кадр.
#
#   shot.sh ios  <имя.png> [--full]   — снять с загруженного симулятора
#   shot.sh adb  <имя.png> [--full]   — снять с подключённого устройства/эмулятора
#
# --full сохраняет рядом полноразмерный кадр (для эталонов), но в stdout всё равно
# печатает путь к уменьшенному.
set -euo pipefail

W=${GJ_SHOT_WIDTH:-900}
Q=${GJ_SHOT_QUALITY:-60}
MODE=${1:?укажите ios или adb}
OUT=${2:?укажите путь к файлу .png}
FULL=${3:-}

mkdir -p "$(dirname "$OUT")"
RAW="${OUT%.png}.raw.png"

case "$MODE" in
  ios)
    xcrun simctl io booted screenshot "$RAW" >/dev/null 2>&1 \
      || { echo "не удалось снять с симулятора: загружен ли он? (xcrun simctl list devices booted)" >&2; exit 1; }
    ;;
  adb)
    adb exec-out screencap -p > "$RAW" 2>/dev/null \
      || { echo "не удалось снять с устройства: подключено ли? (adb devices)" >&2; exit 1; }
    [ -s "$RAW" ] || { echo "пустой кадр — устройство не отдало экран" >&2; exit 1; }
    ;;
  *) echo "режим должен быть ios или adb" >&2; exit 1 ;;
esac

SMALL="${OUT%.png}.jpg"
sips -Z "$W" -s format jpeg -s formatOptions "$Q" "$RAW" --out "$SMALL" >/dev/null

if [ "$FULL" = "--full" ]; then
  mv "$RAW" "$OUT"
else
  rm -f "$RAW"
fi

SZ=$(du -k "$SMALL" | cut -f1)
echo "$SMALL"
echo "вес ${SZ} КБ ≈ $((SZ * 1000 / 4000)) тыс. токенов" >&2
