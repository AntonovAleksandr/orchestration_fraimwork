---
name: mobile-ios-simulator
description: Use when running, building, installing, debugging, or testing the Gloria Jeans mobile app (React Native) on an iOS Simulator — booting simulators via simctl, xcodebuild/run-ios, install/launch/logs/screenshot, Metro connection, pods, detox e2e. Triggers on "запусти на симуляторе", "simctl", "iOS билд не собирается", "сделай скриншот симулятора", "почему белый экран на iOS", "прогони detox". Supports verification step of `pattern-development-mobile`.
---

# Mobile iOS Simulator (simctl / xcodebuild)

**See also:** [`pattern-development-mobile.md`](../pattern-development-mobile.md) — use this skill in step 6 (Verification) to test changes on iOS Simulator.

Всё про запуск/отладку **gj-app** на iOS Simulator. Android-аналог — `mobile-emulator-adb`. Yarn-скрипты и флейворы — `mobile-build-commands`. Раскладка репо — `mobile-stack-anatomy`.

Рабочая директория yarn: `platform/mobile-app/gj-app/`.
iOS-проект: `platform/mobile-app/gj-app/packages/gj/ios/`.

## Ключевые факты (не переоткрывать)

| Что | Значение |
|-----|----------|
| Workspace | `packages/gj/ios/GloriaJeans.xcworkspace` (всегда `-workspace`, не `-project`) |
| Схема development | `GloriaJeans.Development` (config `Development.Debug`) |
| Схема staging | `GloriaJeans.Staging` (config `Staging.Debug`) |
| Схема production | `GloriaJeans` (config `Debug` / `Release`) |
| bundle id development | `com.gloriajeans.mobile.development` |
| bundle id staging | `com.gloriajeans.mobile.staging` |
| bundle id production | `com.gloriajeans.mobile` |
| App-бандл (dev) | `GJ - Development.app` |
| App-бандл (prod) | `GloriaJeans.app` |
| Дефолтный симулятор | `iPhone 16 Pro` (staging), также есть `ios:prod14pro`, `ios-se` |
| Metro порт | `8081` (на симуляторе reverse НЕ нужен — общий localhost с хостом) |
| env-файлы | `packages/gj/.env.{development,staging,production}` |

> На Apple Silicon staging/prod-скрипты форсят `ARCHS=x86_64` (`--extra-params ARCHS=x86_64`) — если собираешь `xcodebuild` вручную и падает на арке, добавь `ARCHS=x86_64`.

## Первичная настройка (один раз)

```bash
cd platform/mobile-app/gj-app
yarn                     # node_modules всех workspaces
yarn yookassa:prepare    # ОБЯЗАТЕЛЬНО до первого iOS-билда, иначе pod install упадёт
yarn gj:pod-install      # bundle exec pod install --repo-update
```

`gj:pod-install` требует Ruby+bundler+Cocoapods (`bundle install` из Gemfile). Альтернатива: `yarn gj:npxpod-install`.

## Сборка + запуск (проще всего — yarn)

```bash
cd platform/mobile-app/gj-app
yarn gj:start &            # Metro (--reset-cache) в фоне
yarn gj:ios:development    # GloriaJeans.Development на дефолтный симулятор
yarn gj:ios:staging        # iPhone 16 Pro, ARCHS=x86_64
yarn gj:ios:production      # ARCHS=x86_64
# точечный девайс:
yarn workspace GloriaJeans ios:prod14pro   # iPhone 14 Pro
yarn workspace GloriaJeans ios-se          # iPhone SE
```

`run-ios` сам поднимет симулятор, соберёт, поставит и запустит.

## Симулятор: жизненный цикл (simctl)

```bash
xcrun simctl list devices available          # какие симуляторы есть + их UDID/состояние
xcrun simctl boot "iPhone 16 Pro"            # поднять (или по UDID)
open -a Simulator                            # показать окно
xcrun simctl bootstatus "iPhone 16 Pro" -b   # дождаться полной загрузки
xcrun simctl shutdown all                    # погасить все
```

`booted` в командах ниже = «текущий загруженный симулятор» (можно вместо UDID).

## Ручной цикл (когда .app уже собран)

```bash
# путь к собранному .app (detox/xcodebuild кладёт в derivedData):
APP="packages/gj/ios/build/Build/Products/Development.Debug-iphonesimulator/GJ - Development.app"

xcrun simctl install booted "$APP"
xcrun simctl launch booted com.gloriajeans.mobile.development
xcrun simctl terminate booted com.gloriajeans.mobile.development
xcrun simctl uninstall booted com.gloriajeans.mobile.development
```

Ручной `xcodebuild` (если нужен билд без run-ios):

```bash
cd packages/gj
xcodebuild ARCHS=x86_64 \
  -workspace ios/GloriaJeans.xcworkspace \
  -scheme GloriaJeans.Development \
  -configuration Development.Debug \
  -sdk iphonesimulator \
  -derivedDataPath ios/build \
  build
```

## simctl-шпаргалка

```bash
# Состояние
xcrun simctl list devices booted             # что сейчас запущено
xcrun simctl get_app_container booted com.gloriajeans.mobile.development data  # sandbox приложения

# UI / отладка
xcrun simctl io booted screenshot /tmp/shot.png    # скриншот
xcrun simctl io booted recordVideo /tmp/rec.mov    # запись (Ctrl-C стоп)
xcrun simctl openurl booted "<scheme://path>"      # deeplink (роутинг)
xcrun simctl privacy booted grant location com.gloriajeans.mobile.development
xcrun simctl push booted com.gloriajeans.mobile.development payload.json  # тест пуша

# Данные
xcrun simctl spawn booted log stream ...      # см. логи ниже
xcrun simctl erase all                        # СБРОС всех симуляторов (данные!) — nuclear
```

Скриншот удобно прочитать инструментом Read (`/tmp/shot.png`) для верификации UI.

## Логи — экономно по токенам

RN JS-логи и нативка идут в unified log. **Всегда фильтруй по subsystem/процессу**, иначе тысячи строк.

```bash
# Дамп за последнюю минуту, только наш процесс:
xcrun simctl spawn booted log show --last 1m --predicate 'process == "GJ - Development"' --style compact | tail -80

# Живой стрим только ошибок (Ctrl-C):
xcrun simctl spawn booted log stream --level error --predicate 'process CONTAINS "GloriaJeans"'
```

- Используй `log show --last <N>` (дамп) вместо `log stream` там, где не нужен онлайн — иначе команда не завершится.
- Никогда не лей полный лог в ответ; `tail -N` / grep по симптому.
- Metro-консоль (`yarn gj:start`) — основной источник JS `console.log`; часто быстрее unified log.

## Тесты

```bash
cd platform/mobile-app/gj-app
yarn gj:test                 # jest (весь) — симулятор НЕ нужен
yarn workspace GloriaJeans test:unit

# Detox e2e (сконфигурирован под iOS-симулятор iPhone 16 Pro):
yarn gj:ios:detox:debug:build    # detox build --configuration ios.sim.debug
yarn gj:ios:detox:debug:test     # detox test --configuration ios.sim.debug
```

Конфиг detox — `packages/gj/.detoxrc.js`, тесты — `packages/gj/e2e/`. Есть и Android-конфигурации (`android.emu.debug` и т.д.), но yarn-скрипта под них нет, а `binaryPath`/`build` там generic (`assembleDebug`, а не flavored) — то есть под Android detox не поддерживается «из коробки», нужна доводка.

## Стандартный цикл «проверь изменение на симуляторе»

1. `xcrun simctl list devices booted` — есть загруженный симулятор? нет → `simctl boot` + `bootstatus`.
2. `yarn gj:start &` (если Metro не запущен).
3. `yarn gj:ios:development` (сборка+install+launch) — или `simctl install`+`launch`, если .app актуален.
4. Смотреть JS-логи в Metro-консоли; нативка → `simctl spawn booted log show --last 1m --predicate ...`.
5. `xcrun simctl io booted screenshot /tmp/shot.png` → Read для визуальной проверки.
6. Перед «готово»: `yarn lint && yarn gj:ts` (см. `mobile-build-commands`).

## Troubleshooting

| Симптом | Причина / фикс |
|---------|----------------|
| Pods out of sync / нативные ошибки линковки | `yarn gj:pod-install` (после добавления iOS-депа) |
| pod install падает на первом билде | не запущен `yarn yookassa:prepare` |
| белый/красный экран, «No bundle URL» | нет Metro → `yarn gj:start` (reverse на iOS не нужен) |
| старый JS после правок | `yarn gj:clean-cache && yarn gj:start` |
| билд падает на арке (arm64) | добавить `ARCHS=x86_64` в `xcodebuild`/скрипт |
| «мусорный» билд, странные ошибки компиляции | `yarn workspace GloriaJeans clean:deriveddata` (или `clean:cache`) |
| `log stream` не завершается | использовать `log show --last <N>` |
| два симулятора, команда неоднозначна | указывать UDID вместо `booted` |
| скриншот пустой | сначала `open -a Simulator` и дождаться `bootstatus` |

## Anti-patterns

- Полный `log stream`/`log show` без predicate/tail в ответ — сжигает контекст.
- `xcodebuild -project` вместо `-workspace` — не подхватит Pods.
- Прямой `pod install` в `ios/` вместо `yarn gj:pod-install` — минует bundler/patch-хуки.
- `npm install` вместо `yarn` — ломает lockfile-паритет.
- Пропустить `yookassa:prepare` перед первым iOS-билдом.
- `simctl erase` «на всякий случай» — сотрёт данные всех симуляторов.
