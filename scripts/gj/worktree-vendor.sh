#!/usr/bin/env bash
# Дешёвый честный vendor в рабочем дереве PHP-репозитория.
#
# Задача: в свежем рабочем дереве нет vendor. Простая ссылка на vendor основного клона
# НЕ работает — __DIR__ в vendor/composer/autoload_real.php разыменовывает ссылку,
# $baseDir указывает на основной клон, и тесты идут по ЧУЖОЙ ветке, молча.
# Полная копия — 17–18 ГБ у BFF. Рецепт даёт своё дерево за секунды и без расхода места.
#
# Три вещи обязаны быть настоящими файлами, остальное — ссылки:
#   vendor/composer/     иначе чужой $baseDir
#   vendor/autoload.php  иначе точка входа ведёт в основной клон
#   vendor/bin/          иначе два автозагрузчика сразу (Cannot declare class ComposerAutoloaderInit…)
#
#   worktree-vendor.sh <дерево> [клон-донор]
#   worktree-vendor.sh --check <дерево>     проверить, своё ли дерево видит автозагрузчик
#
# Проверено 16.09.2026 на platform/integration/integration и customers-api-web.
set -euo pipefail

usage() { sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
[ $# -ge 1 ] || usage

if [ "$1" = "--check" ]; then
  T=${2:?укажите дерево}
  cd "$T"
  [ -f vendor/autoload.php ] || { echo "vendor/autoload.php нет" >&2; exit 1; }
  php -r '
    require "vendor/autoload.php";
    $r = new ReflectionClass("Composer\Autoload\ClassLoader");
    $base = dirname(dirname($r->getFileName()));
    echo "автозагрузчик смотрит в: $base\n";
  ' 2>/dev/null || echo "не удалось определить" >&2
  echo "ожидается путь внутри $T"
  exit 0
fi

T=$(cd "${1:?укажите рабочее дерево}" && pwd)
D=${2:-}

# Донор — основной клон того же репозитория. Определяем через git, если не задан.
if [ -z "$D" ]; then
  D=$(git -C "$T" rev-parse --path-format=absolute --git-common-dir 2>/dev/null | sed 's#/\.git$##') || true
  [ -n "$D" ] && [ -d "$D/vendor" ] || {
    echo "не нашёл клон-донор с vendor; укажите вторым аргументом" >&2; exit 1; }
fi
[ -d "$D/vendor/composer" ] || { echo "в доноре $D нет vendor/composer" >&2; exit 1; }
[ "$T" != "$D" ] || { echo "дерево и донор совпадают — нечего делать" >&2; exit 1; }

echo "дерево: $T"
echo "донор:  $D"

rm -rf "$T/vendor"
mkdir -p "$T/vendor"
for e in "$D"/vendor/*; do
  ln -sfn "$e" "$T/vendor/$(basename "$e")"
done

# Настоящие файлы вместо ссылок — иначе автозагрузчик уедет в донора.
rm -f "$T/vendor/composer" "$T/vendor/autoload.php" "$T/vendor/bin"
cp -R "$D/vendor/composer" "$T/vendor/composer"
cp    "$D/vendor/autoload.php" "$T/vendor/autoload.php"
mkdir -p "$T/vendor/bin" && cp -R "$D"/vendor/bin/. "$T/vendor/bin/"

( cd "$T" && composer dump-autoload --no-interaction --quiet ) \
  || { echo "composer dump-autoload не прошёл — проверьте composer.json в дереве" >&2; exit 1; }

echo "готово. проверка: scripts/gj/worktree-vendor.sh --check $T"
echo
echo "Помнить:"
echo "  · после создания новых классов нужен повторный composer dump-autoload"
echo "    (автозагрузчик собирается оптимизированным)"
echo "  · Pest в BFF по этому рецепту всё равно падает (TestAlreadyExist):"
echo "    его точка входа добирается до исходного vendor мимо ссылок — гонять phpunit"
