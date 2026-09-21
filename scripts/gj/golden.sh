#!/usr/bin/env bash
# Прогон набора эталонных экранов: сверяет все снимки с эталонами и печатает сводку.
#
# Смысл в том, что агент читает одну строку итога, а не десяток картинок.
# Картинки попадают в контекст только по разошедшимся экранам, и то вырезками.
#
#   golden.sh check [ДИР_СНИМКОВ] [ДИР_ЭТАЛОНОВ] [--tolerance N]
#   golden.sh accept <имя>        — принять текущий снимок как новый эталон
#   golden.sh list                — что есть в наборе
#
# Раскладка по умолчанию (относительно корня workspace):
#   .golden/shots/<имя>.jpg    текущие снимки
#   .golden/ref/<имя>.png      эталоны (макет или принятый результат)
#   .golden/report/            вырезки расхождений
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE=${GJ_GOLDEN_DIR:-$ROOT/.golden}
cmd=${1:-check}
# каталоги переопределяются только у check: у accept второй аргумент — имя экрана
if [ "$cmd" = "check" ]; then
  case "${2:-}" in ""|--*) SHOTS=$BASE/shots;; *) SHOTS=$2;; esac
  case "${3:-}" in ""|--*) REF=$BASE/ref;;   *) REF=$3;;   esac
else
  SHOTS=$BASE/shots
  REF=$BASE/ref
fi
REPORT=$BASE/report
CHECK="$ROOT/scripts/gj/visual-check.py"
TOL=${GJ_GOLDEN_TOLERANCE:-2.0}

for a in "$@"; do
  case "$a" in --tolerance=*) TOL="${a#*=}";; esac
done

mkdir -p "$SHOTS" "$REF" "$REPORT"

# Ищет файл по имени без расширения. Через ls с шаблоном делать нельзя:
# при nullglob несопоставленный шаблон исчезает и ls печатает текущий каталог.
find_one() {
  local dir=$1 name=$2 e
  for e in png jpg jpeg; do
    [ -f "$dir/$name.$e" ] && { printf '%s' "$dir/$name.$e"; return 0; }
  done
  return 1
}

case "$cmd" in
  list)
    echo "эталоны:"; ls -1 "$REF" 2>/dev/null | sed 's/^/  /' || echo "  (пусто)"
    echo "снимки:";  ls -1 "$SHOTS" 2>/dev/null | sed 's/^/  /' || echo "  (пусто)"
    ;;
  accept)
    N=${2:?укажите имя экрана}
    SRC=$(find_one "$SHOTS" "$N") \
      || { echo "снимок $N не найден в $SHOTS" >&2; exit 1; }
    cp "$SRC" "$REF/$N.png"
    echo "принят как эталон: $REF/$N.png"
    ;;
  check)
    pass=0; fail=0; miss=0; lines=""
    shopt -s nullglob
    for f in "$SHOTS"/*.jpg "$SHOTS"/*.png; do
      n=$(basename "$f"); n="${n%.*}"
      g=$(find_one "$REF" "$n") || g=""
      if [ -z "$g" ]; then
        miss=$((miss+1)); lines+="  БЕЗ ЭТАЛОНА  $n\n"; continue
      fi
      out="$REPORT/$n.jpg"
      if res=$("$CHECK" "$f" "$g" --tolerance "$TOL" --out "$out" --json 2>&1); then
        pass=$((pass+1))
        lines+="  совпало     $n\n"
      else
        fail=$((fail+1))
        pct=$(echo "$res" | sed -n 's/.*"diff_pct": *\([0-9.]*\).*/\1/p')
        where=$(echo "$res" | sed -n 's/.*"where": *"\([^"]*\)".*/\1/p')
        img=$(echo "$res" | sed -n 's/.*"report_image": *"\([^"]*\)".*/\1/p')
        lines+="  РАЗОШЛОСЬ   $n — ${pct:-?}% — ${where:-?}\n"
        [ -n "$img" ] && lines+="              вырезка: $img\n"
      fi
    done
    printf "%b" "$lines"
    echo "---"
    echo "совпало $pass · разошлось $fail · без эталона $miss · допуск ${TOL}%"
    [ "$fail" -eq 0 ] && [ "$miss" -eq 0 ]
    ;;
  *) echo "команды: check | accept <имя> | list" >&2; exit 1 ;;
esac
