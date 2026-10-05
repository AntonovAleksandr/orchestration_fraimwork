#!/bin/bash
# Проверка для OPSOMN002-289: в диффе ветки ровно 4 файла в webapi-connector
# Используем GitLab API repository/compare вместо локального git diff
PAT="${PAT:-$(cat ~/.config/gj/gitlab_pat 2>/dev/null)}"
[ -n "$PAT" ] || { echo "PAT не найден в ~/.config/gj/gitlab_pat"; exit 2; }
REPO="greensight/gj/connectors/webapi-connector"
FROM="release-26.09-release-26.10"
TO="task-OPSOMN002-289-attempts-limit"
# Получаем количество изменённых файлов через GitLab API
CHANGED=$(curl -s --noproxy '*' \
  -H "PRIVATE-TOKEN: $PAT" \
  "https://gitlab.gloria.aaanet.ru/api/v4/projects/$(python3 -c "import urllib.parse; print(urllib.parse.quote('$REPO', safe=''))")/repository/compare?from=$FROM&to=$TO" \
  2>/dev/null | python3 -c "import sys, json; data = json.load(sys.stdin); print(len(data.get('diffs', [])))" 2>/dev/null)
if [ -z "$CHANGED" ] || ! [[ "$CHANGED" =~ ^[0-9]+$ ]]; then
  echo "Не удалось получить количество файлов из GitLab API"
  exit 2
fi
[ "$CHANGED" -eq 4 ] || { echo "Ожидается 4 файла, в GitLab: $CHANGED"; exit 1; }
