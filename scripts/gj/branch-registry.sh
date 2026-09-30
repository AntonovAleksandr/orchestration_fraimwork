#!/usr/bin/env bash
# Сверяет реестр веток с GitLab: какие ветки защищены, какие джобы деплоя есть.
#
#   branch-registry.sh check <проект>    показать ветки и джобы деплоя проекта
#   branch-registry.sh refresh           пройти по известным проектам и напечатать сводку
#
# Реестр правится руками: docs/deploy/branch-registry.md. Скрипт даёт данные для правки,
# сам файл не переписывает — раскладка требует решения, а не автозаписи.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
H=gitlab.gloria.aaanet.ru
IP=${GJ_GITLAB_IP:-10.61.64.83}
T=$(cat ~/.config/gj/gitlab_pat 2>/dev/null) || { echo "нет токена ~/.config/gj/gitlab_pat" >&2; exit 2; }

api() {
  curl -4 -s --noproxy '*' --resolve "$H:443:$IP" --connect-timeout 15 --max-time 60 \
       -H "PRIVATE-TOKEN: $T" "https://$H/api/v4/$1"
}

one() {
  local p=${1//\//%2F}
  echo "=== $1"
  api "projects/$p/repository/branches?per_page=100" \
    | python3 -c '
import json,sys
try: b=json.load(sys.stdin)
except Exception: print("  ветки не получены (сеть?)"); raise SystemExit
if not isinstance(b,list): print("  ",b); raise SystemExit
for x in sorted(b,key=lambda y:(not y.get("default"),y["name"])):
    m=[]
    if x.get("default"): m.append("по умолчанию")
    if x.get("protected"): m.append("защищена")
    if x["name"] in ("master","main","production","stage") or x["name"].startswith(("release","release-")):
        print("  %-34s %s" % (x["name"], ", ".join(m)))' 2>/dev/null
  echo "  джобы деплоя:"
  api "projects/$p/jobs?per_page=100&scope[]=success&scope[]=manual" \
    | python3 -c '
import json,sys,collections
try: j=json.load(sys.stdin)
except Exception: raise SystemExit
if not isinstance(j,list): raise SystemExit
ok=collections.OrderedDict()   # последний УСПЕШНЫЙ прогон — он и показывает, с чего собран стенд
any_=collections.OrderedDict()  # последняя созданная джоба, в т.ч. никогда не запущенная
for x in j:
    n=x.get("name","")
    if not any(k in n for k in ("deploy","prod","stag")): continue
    any_.setdefault(n, (x.get("ref",""), x.get("status","")))
    if x.get("status")=="success":
        ok.setdefault(n, x.get("ref",""))
for n,(ref,st) in list(any_.items())[:12]:
    good=ok.get(n)
    if good and good!=ref:
        print("    %-32s успешно с: %s   (свежая джоба %s — %s, не показатель)" % (n,good,ref,st))
    elif good:
        print("    %-32s успешно с: %s" % (n,good))
    else:
        print("    %-32s успешных прогонов нет (свежая: %s — %s)" % (n,ref,st))' 2>/dev/null
  echo
}

case "${1:-refresh}" in
  check) one "${2:?укажите путь проекта}" ;;
  refresh)
    for p in \
      greensight/gj/customer-gui/customers-api-web \
      greensight/gj/catalog/pim \
      greensight/gj/catalog/catalog-cache \
      avg-integration-service/integration \
      site-front/gj-ng-front \
      mobapp/gj-app ; do one "$p"; done
    echo "Сверьте вывод с $ROOT/docs/deploy/branch-registry.md и поправьте файл руками."
    ;;
  *) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
