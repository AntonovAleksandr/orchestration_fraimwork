#!/usr/bin/env bash
# Общий прогон: тесты ядра, связки скиллов, граница ядра. Запуск из корня воркспейса: tests/run_all.sh
set -u
cd "$(dirname "$0")/.." || exit 2
fail=0
for t in framework/tests/test_*.py tests/orch/test_*.py; do
  if python3 "$t" >/tmp/fw-test.out 2>&1; then
    echo "OK    $t"
  else
    echo "FAIL  $t"; tail -5 /tmp/fw-test.out; fail=1
  fi
done
[ $fail = 0 ] && echo "все тесты прошли" || echo "есть падения"
exit $fail
