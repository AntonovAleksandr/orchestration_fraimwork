#!/usr/bin/env bash
# Снятие контракта внутреннего API pub.fsa.gov.ru (вариант А правки 2.5 ФТ, OPSOMN002-289).
#
# Учётные данные НЕ передаются в переписку: скрипт читает их из окружения и печатает
# только структуру ответа — коды, имена полей, форматы номеров. Токен затирается.
#
#   export FSA_PUBLIC_LOGIN=... FSA_PUBLIC_PASSWORD=... FSA_PUBLIC_ORGANIZATION_NAME='ГЛОРИЯ ДЖИНС'
#   scripts/gj/fsa-probe.sh
#
# Либо без экспорта в историю оболочки:
#   read -rs FSA_PUBLIC_PASSWORD && export FSA_PUBLIC_PASSWORD
#
# Контур недоступен через прокси — curl идёт напрямую (--noproxy).
set -uo pipefail

B=${FSA_PUBLIC_URL:-https://pub.fsa.gov.ru}
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36'
ORG=${FSA_PUBLIC_ORGANIZATION_NAME:-}
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

: "${FSA_PUBLIC_LOGIN:?задайте FSA_PUBLIC_LOGIN}"
: "${FSA_PUBLIC_PASSWORD:?задайте FSA_PUBLIC_PASSWORD}"
[ -n "$ORG" ] || echo "ПРЕДУПРЕЖДЕНИЕ: FSA_PUBLIC_ORGANIZATION_NAME пуст — поиск пойдёт без фильтра по организации" >&2

say() { printf '%s\n' "$*"; }
keys() { python3 -c "
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception as e: print('  (не JSON:', str(e)[:60], ')'); raise SystemExit
if isinstance(d,list): print('  верхний уровень: СПИСОК из', len(d)); d=d[0] if d else {}
else: print('  верхний уровень: объект, ключи:', ', '.join(sorted(d)[:20]))
" "$1" 2>/dev/null; }

say "=== 1. Вход: POST /login ==="
for body in '{"username":"%s","password":"%s"}' '{"login":"%s","password":"%s"}'; do
  printf "$body" "$FSA_PUBLIC_LOGIN" "$FSA_PUBLIC_PASSWORD" > "$TMP/login.json"
  code=$(curl -sS --noproxy '*' --max-time 30 -A "$UA" -H 'Content-Type: application/json' \
    -H 'Accept: application/json' -o "$TMP/login.out" -w '%{http_code}' \
    -X POST --data-binary @"$TMP/login.json" "$B/login")
  shape=$(printf '%s' "$body" | cut -d'"' -f2)
  say "  тело с полем '$shape': код=$code"
  if [ "$code" = "200" ]; then keys "$TMP/login.out"; break; fi
done

TOKEN=$(python3 -c "
import json,sys
try: d=json.load(open('$TMP/login.out'))
except Exception: raise SystemExit
for k in ('token','access_token','accessToken','jwt','id_token'):
    if isinstance(d.get(k),str): print(k+'='+d[k]); break
" 2>/dev/null)
[ -z "$TOKEN" ] && { say "  токен в ответе не найден — дальше идти нечем"; exit 1; }
FIELD=${TOKEN%%=*}; VALUE=${TOKEN#*=}
say "  имя поля токена: $FIELD  (значение получено, длина ${#VALUE}, не печатается)"

say ""
say "=== 2. Перечень: подбор рабочего заголовка и тела ==="
FROM=${FSA_PROBE_FROM:-2026-08-01}; TO=${FSA_PROBE_TO:-2026-08-31}
python3 - "$ORG" "$FROM" "$TO" <<'PY' > "$TMP/bodies.txt"
import json,sys
org,f,t=sys.argv[1],sys.argv[2],sys.argv[3]
variants={
 "filter.regDate.minDate+applicant": {"size":2,"page":0,"filter":{"regDate":{"minDate":f,"maxDate":t},"applicant":org}},
 "filter.regDate.min+applicantName": {"size":2,"page":0,"filter":{"regDate":{"min":f,"max":t},"applicantName":org}},
 "filter.regDateFrom+applicant":     {"size":2,"page":0,"filter":{"regDateFrom":f,"regDateTo":t,"applicant":org}},
 "minimal":                          {"size":2,"page":0,"filter":{}},
}
for name,v in variants.items(): print(name+"\t"+json.dumps(v,ensure_ascii=False))
PY

OK=""
while IFS=$'\t' read -r name body; do
  printf '%s' "$body" > "$TMP/req.json"
  for hdr in "Authorization: Bearer $VALUE" "Authorization: $VALUE" "X-Auth-Token: $VALUE"; do
    code=$(curl -sS --noproxy '*' --max-time 30 -A "$UA" -H 'Content-Type: application/json' \
      -H 'Accept: application/json' -H "Referer: $B/rss/certificate" -H "$hdr" \
      -o "$TMP/search.out" -w '%{http_code}' \
      -X POST --data-binary @"$TMP/req.json" "$B/api/v1/rss/common/certificates/get")
    say "  тело '$name' + заголовок ${hdr%%:*} : код=$code"
    if [ "$code" = "200" ]; then OK="$name|${hdr%%:*}"; break 2; fi
  done
done < "$TMP/bodies.txt"

if [ -z "$OK" ]; then say ""; say "Рабочее сочетание не найдено — покажите вывод, подберём дальше."; exit 1; fi

say ""
say "=== 3. Структура ответа (рабочее сочетание: ${OK}) ==="
keys "$TMP/search.out"
python3 -c "
import json
d=json.load(open('$TMP/search.out'))
rows=None
if isinstance(d,list): rows=d
else:
    for k,v in d.items():
        if isinstance(v,list) and v and isinstance(v[0],dict): rows=v; print('  перечень лежит в поле:',k); break
if not rows: print('  записей в ответе нет — расширьте окно FSA_PROBE_FROM/TO'); raise SystemExit
print('  записей на странице:',len(rows))
r=rows[0]
print('  ключи записи:',', '.join(sorted(r)))
for k in ('id','number','declNumber','regDate','status','idStatus'):
    if k in r: print(f'    {k} = {str(r[k])[:60]}')
"
say ""
say "Пришлите этот вывод — он не содержит учётных данных."
