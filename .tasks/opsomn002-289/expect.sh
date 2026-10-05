#!/bin/bash
# Проверка для OPSOMN002-289: в диффе ветки ровно 4 файла в webapi-connector
cd platform/ensi/apps/connectors/webapi-connector && \
git fetch --unshallow 2>/dev/null || true && \
[ $(git diff --name-only origin/release-26.09-release-26.10...task-OPSOMN002-289-attempts-limit 2>/dev/null | wc -l) -eq 4 ]
