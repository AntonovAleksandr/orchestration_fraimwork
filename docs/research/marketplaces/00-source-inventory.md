# Маркетплейсы GJ — инвентаризация источников

**Дата среза:** 2026-07-25

**Правило:** наличие источника подтверждает только существование документа/задачи.
Фактический процесс подтверждается после чтения содержания и проверки свежести.

## Confluence — прочитаны

| page_id | Заголовок | Последнее изменение / версия | Роль | Оценка |
|---|---|---|---|---|
| `149765159` | ADR Databird — Загрузка цен в Маркетплейсы | 2025-08-05 / v6 | фактическая конфигурация и правила цен | high, но статус «Черновик» |
| attachments `149765163`—`149765188` к `149765159` | DataBird config snapshots | state/lastSync в основном 2025-04 | schedules, mappings и counters импортов | historical; содержат auth material, значения не копировать |
| `130141740` | PF API действующей промо-цены | 2025-02-13 / v6 | daily/on-demand promo source | source-side specification |
| `82015904` | PF API обычных цен | 2023-10-02 / v8 | regular price source и incremental interval | historical specification |
| `149768494` | [draft] Автоматизация загрузки товарных карточек… | 2025-07-11 / v29 | AS-IS/TO-BE контента и карточек | proxy/draft |
| `165381358` | API справочника идентификаторов МП | 2026-04-09 / v4 | централизованный identifier contour | связь с DataBird exporter не доказана |
| `165400156` | DataBird: чтение замеров WB | 2026-04-10 / v7 | DataBird инициирует чтение warehouse measurements | периодичность «по необходимости» |
| `149768487` | Интеграция Databird (черновик) | version 2 | потенциальная интеграция | пустое содержимое |
| `89985772` | Маркетплейсы. Онбординг сотрудника | 2025-05-23 / v17 | роли и рабочие системы | confirmed для документа |
| `81986146` | R-22. Автоматизация фидов для маркетплейсов | 2024-04-27 / v22 | историческая матрица API/моделей | historical |
| `82010279` | ADR Загрузка цен, карточек товаров в Маркетплейсы | 2024-04-23 / v28 | старое решение ENSI connectors | historical draft |
| `82001707` | ADR Загрузка контента, цен и остатков… | 2023-08-09 / v21 | разделение процессов и connectors | historical draft |
| `165382074` | Marketplaces. Поставки из ЛК | 2025-11-07 / v9 | WB/Ozon supply API и ограничения | high |
| `68807090` | Общая информация по поставкам | 2024-11-05 / v59 | AS-IS поставок, УПД и маркировки | historical/proxy |
| `149772921` | Поставки на МП — проблемы и решения | version 7 | ошибки УПД Ozon | узкий operational note |
| `130122967` | Ozon. Отчёт по карточкам товаров | 2025-02-19 / v32 | API и структура отчёта карточек | specification |
| `130122171` | Wildberries. Отчёт по карточкам товаров | 2024-12-24 / v27 | API, MPServiceImport, отчёт | specification |
| `130135456` | Яндекс Маркет. Отчёт по карточкам товаров | version 3 | отчёт по карточкам | прочитан частично |
| `165408341` | Feed-WB для ручного обновления товарного каталога | 2026-06-15 / v3 | товарный contract ENSI→1С/WB | fresh specification |
| `165397303` | WB Orders API contract | 2026-02-27 / v5 | заказы WB | fresh specification |
| `165397510` | WB Sales/Returns API contract | 2026-03-10 / v2 | продажи и возвраты WB | fresh specification |
| `165395786` | ОбменWB | 2026-03-20 / v6 | обработка 1С | fresh specification/history |
| `130128672` | Marketplaces. Данные по остаткам | 2026-07-07 / v32 | **чтение** остатков WB/Ozon/Яндекс в BI (`WB_Stocks`), ключи `nmId`/баркод, лимиты | fresh specification; исходящей загрузки остатков в WB не описывает |
| `149775329` | МаппингМП — справочник идентификаторов МП | v13 | состав полей (`nmID`, `imtID`, `techSize`, `МП`), наполнение `MPToReferenSync` в 01:00 через `POST /content/v2/get/cards/list`, сопоставление по штрихкоду | `chrtID` отсутствует; тождество с `165381358` не подтверждено |
| `165400467` | DataBird/сервис замеров склада WB | 2026-05-13 / v7 | второй потребитель справочника, сопоставление по `nmId`, сообщение в ELK при промахе | расширение справочника требует согласования с этим потребителем |
| `88508013` | WB Connector — получение `nmID` (историческая) | 2023 | исторический подход к получению `nmID` | содержит похожий на рабочий токен WB в открытом виде; требует отзыва |
| `165411281` | WB weekly financial report | 2026-07-17 / v10 | финансы и `wb_weekly` | fresh specification |
| `60694191` | УПДМаркетплейс | 2026-02-11 / v64 | приёмка/УПД WB | fresh specification |
| `165405930` | Ozon FBO orders WebApi contract | 2026-05-22 / v4 | заказы Ozon | fresh specification |
| `44264974` | ОбменOZON | 2025-08-13 / v87 | 1С, продажи/возвраты/приёмка | recent specification/history |
| `165398439` | Ozon financial reconciliation | 2026-07-07 / v7 | месячная сверка | fresh specification |
| `149765469` | [NEW] SD. СверкаРеализацииOZON | 2026-07-08 / v31 | четыре режима двусторонней сверки Ozon | fresh, но до задач `1115/1116` |
| `55008219` | SD. СверкаРеализаций1СВБ | 2026-03-20 / v21 | ручная двусторонняя сверка WB с `wb_weekly` | fresh specification |
| `16844531` | DF. SBR. База возвратов | 2026-06-16 / v20 | актуальный/legacy контур sales and returns | границы площадок не раскрыты |
| `44255961` | Интеграции Lamoda | 2021-07-08 / v9 | SellerCenter/B2B | historical |
| `44256891` | Поставка Lamoda | 2021-06-22 | поставка на ДЦ | historical |
| `49748314` | Регламент Яндекс Маркет | 2023-06-20 | исторический FBO-контур | historical/copy-paste risk |
| `74166710` | СММ FBO Регламент | 2023-12-04 | старый Мегамаркет/FBO | historical |
| `97882640` | Kaspi: модели работы | 2024-08-13 | FBO/СДЭК и C&C design | historical |
| `97898561` | Operations Маркетплейсы Home | version 1 | home space | шаблон, фактов нет |
| `130123316` | Домен. Маркетплейсы | version 1 | ожидаемая карта домена | пустая |
| `130122894` | DF. Потоки данных по маркетплейсам | version 6 | схема потоков | схема только в image/draw.io, не извлечена |
| `118308332` | 15. BP_Управление маркетплейсами | version 1 | ожидаемый BP | пустая |
| `118306158` | Выгрузка товаров и цен на маркетплейсы | version 2 | указатель на доработки offer | содержимого недостаточно |
| `118293200` | Отгрузка в WB из Новосибирска | 2024-06-24 / v44 | batch shipment, маркировка и УПД | historical; не доказательство FBS order flow |
| `118295722` | 1C8 ЛЦ НСК → GJMarkUpdate → МП | version 58 | отбор документов и группировка по поставке | historical; в примерах есть sensitive data, не копировать |
| `118296442` | GJMarkUpdate → WebGJISMP MOVE_STORES | version 19 | движение марок и УПД | historical; не OMS/OTS flow |
| `108045251` | Маркировка для отгрузки на МП c ЛЦ НШ | version 26 | WMS/ТСД/короба/печать/MarkUpdate/УПД | high для warehouse impact, applicability to FBS unknown |
| `130125049` | Отгрузка на маркетплейсы со складов АО | version 12 | изменение движения товара/марок с АО | specification, runtime не проверен |
| `130124899` | 1C7 АО → GJMarkUpdateAO → MP | version 31 | `MP / MOVE / NOACTION` для stock, уже принадлежащего АО | current specification; WB FBS applicability не доказана |
| `118303811` | GJMarkUpdate: таблица инстансов и типов документов | 2026-03-16 / v30 | current PLM/DO/CA/RE/MS/MP marking routes | runtime конкретного ЛЦ отдельно |
| `78755953` | 1C8 ЛЦ → GJMarkUpdate PLM | 2026-07-12 / v15 | eCom `ОтборЛистПеремещ` → УПД1/MOVE_STORES и обратные статусы | current contract; hard WMS gate не доказывает |
| `44256853` | Документ.ОтборЛистПеремещ | 2026-05-19 / v98 | order/application, короба, марки и reserve document model | production handler отдельно |
| `86314165` | WMS → 1C8. Результат отбора (PKS) | version 35 | PKS/PKSBST/PKSBSTMARK создают `ОтборЛистПеремещ` | high documentary; selected-LC runtime unknown |
| `165407793` | Передача данных по маркированному товару / current SD | 2026-06-29 / v34 | WMS-native `GetCheckOrder` перед отгрузкой, synchronous true/false contract | current contract; live UI выбранного ЛЦ не проверен |
| `130131282` | WebGJISMP `GetCheckOrder` | version 5 | поиск КМ заказа и aggregate owner/realizability result для WMS | current contract; online/offline config отдельно |
| `165410951` | AS-IS маркировка eCom WMS→OTS | 2026-07-20 / v66 | ECOMAUFSTAT/ECOMAUPSTAT, `AufStatus`, 13-char serial вместо полного КИЗ | current documentary; one-order trace нужен |
| `60689538` | WMS → 1C8. Загрузка и обработка транзакций | version 81 | `IFOUTFSRSTA` lifecycle и external processing boundary | deployed EPF/schedule неизвестны |
| `97878157` | WMS → 1C8. Отгрузка паллет в машину | version 86 | AUFSHP/AUPSHP, `TeNam`, `PalNam`, ClickAndCollect и документы 1С | high documentary; selected-LC runtime unknown |
| `97879227` | WMS → 1C8. Подтверждение отгрузки паллет | version 21 | `AUFSHPPAL` и создание связанного `Документ.Паллет` | high documentary; selected-LC runtime unknown |
| `108052092` | Формирование паллет | version 28 | TSD formation/reformation, короб→перемещение→паллет | current-ish TSD specification |
| `49752446` | Отгрузка интернет-заказов | version 16 | order→virtual pallet и owner-change hard gate | historical 2021 proxy |
| `49745536` | Перемещение с последующей дистанционной продажей | version 112 | последовательные MOVE_STORES и OUT/SALE | generic/historical mapping; не WB FBS proof |
| `60692097` | OMS-2.1 Остатки | version 41 | stock/reserve/threshold и источники остатков | current-documentary; marketplace split не описан |
| `63470495` | OMS Starfish → OTS. Создание заказа | 2026-06-10 / v76 | current OMS→OTS contract и reserve/check | не WB-specific |
| `63468946` | OTS → 1C8. РегистрСведений.ЗаказыКлиентов | version 13 | realtime order registry, `idd_order`, transport и shipment barcode | не содержит pallet composition |
| `63453034` | OTS → OMS. Статусы заказа | version 54 | warehouse statuses, shipment barcode и marks | не WB-specific |
| `149758157` | Orders by Channels | 2026-07-14 / v60 | planned channel shares, min/max, stop lists | production неизвестен; не runtime ATS |
| `44269101` | WebApi → 1C7 WB. Получение данных по заказам | 2026-03-26 / v28 | current `api/WB/orders`, mapping и создание `РезервКлиента` | FBS cutover/filter не описан |
| `108061252` | OTS → WMS. Создание заказа | 2025-10-15 / v16 | TGW ECOM task, carrier и shipment barcode | не WB-specific |
| `49752540` | WMS → OTS. Статусы заказа | 2024-06-06 / v39 | registered/batch/suspended/pickup, quantities, DataMatrix | current runtime не проверен |
| `63460277` | OTS/WMS. Отмена заказа | 2024-06-26 / v28 | двухфазное подтверждение WMS cancel | не покрывает WB policy after ready |
| `82013706` | OTS → WebGJISMP. Полный КМ | 2023-10-05 / v16 | enrichment serial/DataMatrix криптохвостом | historical/current proxy |
| `44240383` | Печатные формы E-commerce | version 7 | поля текущей внутренней eCom-этикетки из `WMS.ECOMAUF` | не официальный WB sticker |
| `44248846` | МСК. Упаковка интернет-заказа | version 11 | scan товара/марки и три формы на станции упаковки | 2021, physical-process proxy |
| `44242771` | Печатные формы упаковки | historical | лист возврата, накладная и этикетка | 2021, physical-process proxy |
| `108048195` | ARM/TSD. Сборка интернет-заказа | 2026-07-15 / v63 | scan, KIZ validation, shortage/defect | store/SFS proxy, не WB DC |
| `130126638` | TSD. Печать конечного склада | 2026-07-20 / v14 | внутренние коробочные label/scan primitives | не WB parcel/supply sticker |
| `108043931` | ГостПечОтгрузкиМП | 2026-01-13 / v65 | batch marking labels, коробки, SLC/WebGJISMP | не позаказный FBS |
| `149774255` | WB commission marking flow draft | 2026-03-18 / v24 | проект `MOVE_AGENT` после приёмного акта | draft, production не подтверждён |
| `63452624` | Возврат eCom-заказа | 2026-03-18 / v75 | process template для физического возврата | не готовый WB return contract |
| `74155226` | DWH-контроль 1С WB | version 8 | WB accounting/DWH control | current execution не проверен |
| `149779093` | Отчёт поздних исправлений | version 5 | контроль поздних изменений | owner/SLA не подтверждены |

## Jira — ключевые задачи DataBird/карточек

| issue | Заголовок | Статус | Обновлено | Роль |
|---|---|---|---|---|
| `OPSMPC-549` | Внедрение DataBird | Открытый | 2025-09-30 | общий epic |
| `OPSMPC-506` | DataBird PIM | Работа завершена | 2025-02-10 | исследование сервиса цен |
| `OPSMPC-550` | DataBird. WB — Цены | Работа завершена | 2025-05-12 | price rollout |
| `OPSMPC-620` | DataBird. Ozon — Цены | Работа завершена | 2025-05-12 | price rollout |
| `OPSMPC-636` | DataBird. Yandex — Цены | Работа завершена | 2025-06-05 | price rollout |
| `OPSMPC-697` | DataBird. Ozon — Товары | Реализация | 2026-03-05 | cards rollout |
| `OPSMPC-834` | Ozon — формулы маппинга атрибутов | В работе | 2026-03-17 | cards mapping |
| `OPSMPC-862` | DataBird. WB — Товары | Реализация | 2026-03-05 | cards rollout |
| `OPSMPC-863` | WB — формулы маппинга атрибутов | Разработка | 2025-12-18 | cards mapping |
| `OPSMPC-717` | DataBird. Yandex — Товары | Приостановлена | 2025-09-25 | cards rollout |
| `OPSMPC-868` | Доступность ИдентификаторовМП для 1С | Работа завершена | 2026-05-13 | cross-system IDs |
| `OPSMPC-627` | DataBird: удаление старых моделей | Работа завершена | 2025 | catalog cleanup |
| `OPSMPC-810` | DataBird: не выгружать price `<= 1` | Работа завершена | 2025-08-09 | price safety filter |
| `OPSMPC-831` | DataBird: нестабильный доступ/health monitoring | Работа завершена | 2025-12-24 | availability incident |
| `OPSMPC-857` | Ozon: восстановление первоначальных цен | Работа завершена | 2025-09-23 | manual replay |

## Jira — поставки, заказы и финансы

| issue | Заголовок | Статус | Обновлено | Роль |
|---|---|---|---|---|
| `OPSMPC-796` | WB: восстановить загрузку результатов приёмки | Закрыт | 2025-11-10 | WB acceptance |
| `OPSMPC-820` | УПД по Акту приёмки | Закрыт | 2025-12-29 | closing docs/virtual supplies |
| `OPSMPC-948` | Ozon: загрузка приёмки и марок | Приостановлена | 2026-05-21 | acceptance/marking |
| `OPSMPC-951` | Ozon: загрузка приёмки через УПД | Согласовано | 2026-02-02 | design approval |
| `OPSMPC-1005` | WB: статус выгрузки поставок в ЭДО | Запрос закрыт | 2026-05-13 | supply reconciliation |
| `OPSMPC-1047` | WB: новый метод еженедельного отчёта | Реализация | 2026-07-21 | finance report |
| `OPSMPC-1107` | WB: изменить job/mapping недельного отчёта | Ожидание внутреннего теста | 2026-07-22 | API migration |
| `OPSMPC-1080` | SalesAndReturnsApi → SBRService | Работа завершена | 2026-07-16 | sales/returns service |
| `OPSMPC-1082` | Ozon: данные РК- через Orders | Закрыт | 2026-07-21 | returns/corrections |
| `OPSMPC-1103` | Ozon: новая логика пакетов sales | Перенос на prod | 2026-07-21 | sales ingestion |
| `OPSMPC-1116` | Ozon: новый режим отчёта по начислениям | В работе | 2026-07-21 | finance reconciliation |
| `OPSMPC-1111` | Ozon: новая формула суммы в позаказной сверке | Разработка | 2026-07-20 | finance control gap |
| `OPSMPC-1070` | Ozon: отключение старых finance endpoints | UAT | 2026-07-07 | API cutover |
| `OPSMPC-1085` | Ozon: сопровождение finance migration | Сопровождение | 2026-07-21 | API cutover |
| `OPSMPC-431` | WB: 1С падает на полном `wb_weekly` | Приостановлена | 2025-09-01 | full-volume reconciliation gap |
| `OPSMPC-979` | WB: неверная привязка РРН к старой РК | Отложена | 2026-06-30 | document-linking defect |
| `OPSMPC-1009` | WB: исправление неверной привязки РРН | Новая | 2026-03-23 | document-linking defect |
| `OPSMPC-446` | Marketplaces. Инциденты | В работе | 2026-07-21 | ongoing operations |
| `OPSMPC-311` | Marketplaces. Документация | В работе | 2026-07-21 | documentation stream |
| `OPSMPC-200` | Координация разработки Маркетплейсы | В работе | 2026-07-20 | coordination |
| `OPSMPC-1074` | Ozon Orders: переход на FBO v3 | Закрыт | 2026-06-24 | current Ozon orders |
| `OPSMPC-190` | Ozon DBS/FBS | Отмена | 2025-02-24 | model boundary |
| `OPSMPC-983` | Ozon Click&Collect | Отмена | 2026-03-19 | model boundary |
| `OPSRTL-6434` | Lamoda: печать ярлыков в АРМ | Готово к UAT | 2026-07-22 | restart signal |
| `OPSLOG-3386` | Lamoda: вывозы из магазинов | Новая | 2026-07-20 | restart signal |
| `OPSOMN-13016` | Мегамаркет: пилотный проект | Отмена | 2026-04-29 | current-status anchor |
| `OPSMPC-530` | ОбменKaspi orders/sales | Закрыт | 2025-06-26 | last strong Kaspi trace |
| `OPSMPC-1051` | WB: актуализация `srid` и документов | Закрыта | 2026-07-20 | active legacy `ОбменWB`, replay windows |
| `OPSMPC-1030` | WB: блокирующая ошибка обработки | Закрыта | 2026 | legacy operational risk |
| `OPSRTL-4553` | TSD: печать конечного склада | Работа завершена | 2024-11-29 | internal marketplace box label proxy |
| `OPSPLN-1046` | Продажи/остатки по регионам отгрузки МП | Уточнение требований | 2026-03-24 | WB_Stocks/Vertica и warehouse mapping |
| `OPS-8575` | Свободный остаток и Replenishment | Завершено | 2026-05-22 | historical formula и reserve exceptions |

## Jira — WMS, 1С и маркировка для pallet flow

| issue | Что подтверждает | Ограничение |
|---|---|---|
| `DEVLOG001-382` | создание `Документ.Паллет` из WMS marketplace shipment | закрытая разработка не доказывает runtime выбранного ЛЦ |
| `OPSLOG-2004` | актуализация модуля `Отгрузка паллет в машину`; работа с marketplace movements | ручной модуль, не WB FBS contract |
| `OPSLOG-2560`, `OPSLOG-2569` | pallet transaction atomicity и ожидание подтверждения конкретной паллеты | current deployment не проверен |
| `MWHNSK-1293`, `MWHNSK-2375`, `MWHNSK-6522`, `DEVLBL001-3087` | PLM/`ОтборЛистПеремещ`, eCom filter и обратные marking statuses | WB FBS order не прогнан |
| `DEVLBL001-5905`, `DEVLBL001-5906`, `DEVLBL001-5923` | current условия online/offline `GetCheckOrder` и неизменяемый WMS endpoint/config switch | deployed config выбранного ЛЦ не снят |
| `MWHNSK-2387` | недоступность owner-check endpoint блокировала отгрузку паллеты | historical runtime incident; current UI отдельно |
| `DEVLBL001-4876`, `DEVLBL001-4884`, `DEVLBL001-4890` | route от stock АО к marketplace и GJMarkUpdateAO | относится к MP movement со складов АО, не автоматически к eCom FBS |

## Исторические/смежные Jira-якоря

| issue | Роль | Ограничение |
|---|---|---|
| `OPS-10382` | исследование FBS/DBS WB | production-запуск не подтверждён |
| `OPSLOG-754` | отдельная оценка FBS | содержимое и результат не найдены |
| `OPSMPC-131` | Lamoda: расхождения продаж/возвратов | завершена; current activity unknown |
| `OPSMPC-777`, `855` | Яндекс: возвраты/отмены | завершённые изменения 2025 |
| `OPSMPC-744`, `775`, `817` | отчёты/сверки остатков WB/Ozon | закрытые разработки 2025 |

## Локальный код и конфигурации

Код использовался только точечно для разведения одноимённых контуров и проверки
наличия возможностей. Локальный workspace не гарантирует соответствие production.

| Путь | Что проверено | Ограничение |
|---|---|---|
| `platform/1s8-enterprise/1c-retail/src/cf/CommonModules/ИнтеграцияСМаркетплейсомOzonСервер/Ext/Module.bsl` | в общем модуле есть Ozon FBS API-вызовы | наличие кода не доказывает включение схемы GJ |
| `platform/starfish24/core/Delivery/.../LamodaOrderRegistrationServiceImpl.java` | Lamoda как carrier в OMS | не marketplace-order integration |
| `platform/starfish24/core/Parsers/.../LamodaParserServiceImpl.java` | polling статусов перевозчика Lamoda | deployed version не проверена |
| `platform/starfish24/core/Order/.../DispatchExternalServiceImpl.java` | `wildberries-connector` и event-based FBS supply/barcode flow | connector repo/license/deployment не подтверждены |
| `platform/starfish24/core/Order/.../DispatchServiceImpl.java` | FBS external service выбирается по `marketplaceId` | local snapshot, не production proof |
| `platform/starfish24/core/Order/.../PickItemServiceImpl.java` | barcode picking для FBS | local snapshot |
| `platform/starfish24/core/OMS-UI/.../DISPATCH/FBS/` | FBS workplace, registry/labels/scan/ship и WB-specific UI branches | deployed UI release не проверен |
| `platform/starfish24/awg/bpmn-process/.../export.bpmn` | generic export OMS→OTS | marketplace BPMN не найден |
| `platform/integration/integration/.../OrderExportOtsMutator.php` | mapping OMS order в OTS contract | conditional для WB FBS |
| `platform/gloriaots/gloriaots/.../WmsService.cs` и `WmsSync` | OTS→WMS/TGW/1С и обратные statuses/DataMatrix | WB-specific logic не найдена |
| `platform/gloriaots/wmsinserter-2.0/.../{OrderStatusHeader,OrderStatusRow,WmsService}.cs` | `ECOMAUFSTAT/ECOMAUPSTAT`, `AufStatus`, DataMatrix и технический `IFOUTFSRSTA` | local snapshot, не production image |
| `platform/gloriaots/gloriaots/.../BalanceRepository.cs` | OTS free stock = stock - durable reserves | reserve event dedupe не обеспечивает |
| `platform/gloriaots/gloriaots/.../Reserves_ONES_MOSCOW.sql` | stored procedure вставляет physical reserve | unique `ReserveEventId` не найден |
| `platform/gloriaots/gloriaots/.../TgwWmsMapping.cs` | WMS telegram `OrderType=ECOM`, carrier barcode | нужен generic FBS adaptation |
| `platform/gloriaots/gloriaots/.../OneSService.cs` | 1С registry и fixed НСК/МСК mapping | новый склад потребует доработки |
| `platform/gloriaots/gloriaots/.../CreateOrder.cs`, `TelegramSerializer.cs` | поле `CarrierZPL` есть в telegram DTO; `|` используется как delimiter без escaping | реальный WMS consumer/print не найден |
| `platform/gloriaots/gloriaots/.../OrderToPickup.cs`, `MarkUtils.cs`, `WebGjIsmpClient.cs` | full-KM enrichment через WebGJISMP существует, но включён только для marked manual/unpaid order | для `WB_FBS` нужен отдельный gate/callback; full KM нельзя логировать |
| `platform/arm/gloria-jeans-orders/.../OrdersService.java` | scan/short/KIZ primitives | store/SFS proxy |
| `platform/arm/gloria-jeans-orders/.../PrintService.java` | printer/PDF infrastructure | current endpoint не WB |
| `platform/1s8-enterprise/1c-lc/.../ВыгрузкаMarketplaces/.../Module.bsl` | supply number, transfer and UPD grouping | FBO-like batch semantics |
| `platform/1s8-enterprise/1c-lc/.../Documents/{ОтборЛистПеремещ,Доставка,Перемещение,Паллет}.xml` | order/application, короб, `PalNam`, pallet document и основания | checked-in model, не deployed runtime |
| `platform/1s8-enterprise/1c-lc/.../ОбработкаДанныхИзТСД` и `ВзаимодействиеС_WMS` | формирование/переформирование паллет, `AUPSHP.PalNam=AUFSHPPAL.PalNam`, status 50 и публикация `wms_shipment` | deployed EPF и режим запуска требуют trace |
| `platform/gloriaots/gloriaots/.../ShipmentOrder.cs`, `TgwSyncEvent.cs`, `OrderShimpentEventHandler.cs` | из 1С приходит orders+timestamp; OTS создаёт synthetic AUFSHP и `DELIVERING`, pallet composition не приходит | local snapshot |

## Внешние первичные источники

| Источник | Что подтверждает | Ограничение |
|---|---|---|
| `https://dev.wildberries.ru/docs/openapi/orders-fbs` | current FBS orders/statuses, metadata/sgtin, stickers, supplies и rate limits | не подтверждает capability модуля Starfish |
| `https://dev.wildberries.ru/docs/openapi/work-with-products` | seller warehouses и FBS stocks по `warehouseId/chrtId` | GJ allocation/mastership не определяет |
| `https://dev.wildberries.ru/sandbox` | sandbox для FBS orders/metadata/supplies/passes/warehouses/stocks и эмуляция `wbStatus` | 1 req/s; sticker methods дают пустой `200`; metadata необязательна |
| `https://dev.wildberries.ru/ru/knowledge-base/articles/019d49a1-24e3-7642-801f-e1f18c5fe708/ogranicheniia-testovogo-kontura-wb-api` | актуальные ограничения sandbox | real sticker и production metadata gate не покрываются |
| Документация WB API, управление остатками (`PUT/POST/DELETE /api/v3/stocks/{warehouseId}`, `/api/v3/warehouses*`, `/api/v3/offices`) | остатки только по `chrtId`, до 1000 позиций, ложно-успешный ответ при неверных именах параметров, `409`/`406` | не описывает, откуда GJ берёт `chrtId` |
| Официальный журнал изменений WB API | отключение `sku` для остатков с 13:00 МСК 20.05.2026 и ошибка `400 SKUUploadDisabled` | дата подтверждена журналом, не отдельным разделом документации |
| Документация WB API, Контент (`POST /content/v2/get/cards/list`, `POST /content/v2/cards/upload`) | `chrtID` в `sizes[]` рядом с `techSize` и `skus`; в песочнице карточка создаётся синхронно | стабильность `chrtID` при пересоздании/разъединении карточек не описана |
| `https://github.com/eslazarev/wildberries-sdk` (CHANGELOG, сторонний mirror OpenAPI WB) | перечень sandbox-серверов по разделам: `marketplace-api-sandbox`, `content-api-sandbox`, `discounts-prices-api-sandbox`, `supplies-api-sandbox`, `statistics-api-sandbox`, `feedbacks-api-sandbox` | сторонний mirror, не первичный источник |
| `https://infostart.ru/1c/articles/2738614/` | `403 Access denied` на всём marketplace-домене до задания пунктов выдачи для возвратов (порог 5) | `proxy`: сторонняя публикация, требует проверки на нашем кабинете |
| `https://seller.wildberries.ru/instructions/ru/ru/material/stickers-for-marking-orders-fbs-model` | официальный WB order sticker и требования к наклейке | не описывает внутреннюю GJ печать |
| `https://seller.wildberries.ru/instructions/ru/ru/material/verify-product-identifiers` | GS separators, scan и verification полного КИЗ | не задаёт внутренний GJ legal flow |
| WB Seller instruction «Вывод КИЗ… юрлицам и ИП», updated 2026-02-17 | FBS/DBS B2B withdrawal/return duties продавца | B2C/конкретная GJ схема требует Legal |

Перед архитектурными выводами нужна сверка с deployed image/release конкретного
сервиса или версии 1С-обработки.

## GitLab и runtime — проверены

| Источник | Что подтверждено | Ограничение |
|---|---|---|
| GitLab project `820`, `greensight/gj/catalog/mp-connector`, master `3b6dba3e` | отдельный Go-сервис отдаёт обновлённые товары/SKU из ENSI PIM; в конце 2025 добавлены PLM/1С sync и cron | код не доказывает, что DataBird забирает данные |
| Jira `OPSOMN-14316` | CI/CD для `mp-connector` завершён; задача прямо указывает project `820` | статус задачи сам по себе не доказывает runtime |
| K8s deployment `prod/mp-connector-master-ms` | на 2026-07-23 `desired/ready/available = 1/1/1`, image `master-3b6dba3e` | подтверждает доступность deployment, не бизнес-результат импорта |
| K8s service/ingress `prod/mp-connector-master-ms` | внешний TLS route публикует только `/api/v1/updated-products` через service 80→8080 | доступный ENSI app-log target не является ingress access log |
| ENSI production logs, `systemName=mp-connector` | cron `plm_modelcolor_sync` запускался и завершался 2026-07-22 и 2026-07-23 в 05:00 UTC | это внутренняя синхронизация сервиса, не подтверждение DataBird run |
| Expected Starfish deployment/config search | точные deployment/config/repo `wildberries-connector`/`wb-connector` в доступном GJ контуре не найдены | high-confidence absence under expected names, не абсолютное доказательство отсутствия |

## Order identity — исторические и текущие источники

### Confluence

| page_id | Заголовок | Что подтверждает | Ограничение |
|---|---|---|---|
| `15368628` | OMS1 Модель заказа и статусная схема заказа | Hybris order number равен basket number | historical, не содержит формулу генератора |
| `44255279` | Hybris → 1С АРМ. Передача заказа | 10-значный Hybris `order.code`, пример `1...` | historical contract |
| `60687796` | Starfish → Hybris. Получение статуса | OMS `clientOrderId` передавался как Hybris order number, пример `1...` | historical callback |
| `60692293` | OMS Starfish. Создание заказа | `id` — внутренний OMS ID; `clientOrderId` — номер, отображаемый клиенту | current documentary, runtime отдельно |
| `63470445` | OMS Starfish → 1С Ecomm | `idd` string 10; `documentFoundation=0000352+number`, length 17 | v155, 2026-06 |
| `63456564` | OMS Starfish → DWH | DWH `code` берётся из `clientOrderId` и хранится как string | v34, 2025-04 |
| `130151470` | Номера заказов | stub number начинается на `9` и не идёт в OMS; ordinary начинается на `2` | v1, 2025-03, rationale не описано |

### Jira

| issue | Что подтверждает | Ограничение |
|---|---|---|
| `DEVOMN001-2915` | декомпозиция Baskets; `#99027` — адаптация модели данных | содержимое Redmine недоступно |
| `DEVOMN001-6973` | номер корзины — idempotency key attempt; новый номер после неоднозначной ошибки | test/initial rollout 2023 |
| `MWHNSK-7709` | routing `1=Hybris/R000337`, `2=Starfish/R000352` | правило возврата, не исходное ADR |
| `OPSOMN-8271/8272` | номер корзины сохраняют при manual clear из-за одноразовых промокодов | current code/runtime отдельно |
| `OPSOMN-10226` comment `160333` | без корзины OMS должен генерировать number; предложен range `3` | причина фактического `211` не найдена |
| `OPSOMN-11717/12563/13068` | collision ENSI sequence с существующими OMS `clientOrderId` | test/dev incident, но механизм общий |
| `MWHNSK-1106/1107` | историческая инициатива `INT32. 1C7 - WMS` | нет description/field list |
| `MWHNSK-3152` | test order `3000000001` прошёл до 1С7/WMS document; leading-zero bug | не full E2E proof |
| `OPSOMN-13708` | реальный hidden Int32 cast в 1С/WebAPI на другом 10-digit field | не order ID |

### Git / локальный код

| Путь / commit | Что подтверждает | Ограничение |
|---|---|---|
| Baskets `e5af0e10`, 2022-12-15 | первое найденное введение `2 + sprintf('%09d', basket.id)` | rationale отсутствует |
| Baskets `56882338`, 2023-01-09 | восстановление формулы после refactor `#99041` | не источник идеи |
| Baskets `43efaef`, 2023-04-17 | переиздание номера через sequence после ambiguous create error | local history |
| `platform/ensi/apps/orders/baskets/.../Basket.php` | current formula и `updateNumber()` | local snapshot |
| `platform/starfish24/core/Order/.../Order.java` | отдельные DB PK, `orderId`, `clientOrderId` | local snapshot |
| `platform/starfish24/core/Order/.../OrderServiceImpl.java` | internal order ID, duplicate check, template generator | local snapshot |
| `platform/integration/integration/.../OrderExportOtsMutator.php` | OMS `clientOrderId` → OTS `order_id` | local snapshot |
| `platform/integration/integration/.../OrderExportEcomMutator.php` | OMS `clientOrderId` → 1С `idd/documentFoundation` | local snapshot |
| `platform/gloriaots/gloriaots/.../InternalTypes/Order.cs` | OTS order number is `long` and used for tracking/storage | local snapshot |
| `platform/gloriaots/gloriaots/.../TgwWmsMapping.cs` | OTS number → WMS `OrderNr/OrderRefNr` strings | local snapshot |

## Поисковые запросы и ограничения

| Система | Запрос | Результат/заметка |
|---|---|---|
| Confluence | `type=page AND text ~ "DataBird"` | 6 страниц; 3 содержательных |
| Confluence | `text ~ "Data Bird"` / `text ~ "Датаберд"` | 0; не доказательство отсутствия |
| Jira | `text ~ "DataBird"` | 37 задач |
| Jira | `project = OPSMPC ORDER BY updated DESC` | 1111 задач на дату запроса |
| Jira | `project = OPSMPC AND updated >= "2026-07-01"` | 38 задач |
| Confluence | `title ~ "Маркетплейс"` | 51 страница |
| Jira | `text ~ "карточки"` | 6 задач; поиск по другой словоформе дал 0 |
| Jira | `text ~ "поставки"` | 34 задачи |
| Jira | `text ~ "остатки"` | 16 задач |
| Jira | `text ~ "возврат"` | 43 задачи |
| Confluence | `text ~ "FBS" AND text ~ "Wildberries"` | 3 страницы; свежего GJ FBS design не найдено |
| Jira | `text ~ "FBS" AND text ~ "Wildberries"` | `OPS-10382`, `OPSMPC-219` и отменённый смежный pilot; production FBS не доказан |
| Jira/Confluence | seller warehouse / WB labels / FBS marking | найдены historical/proxy процессы, но не готовый end-to-end GJ FBS |
| Jira/Confluence/Git | `2000000000`, `2 вначале`, `9 цифр`, `номер корзины`, `clientOrderId`, `#99027/#99041` | формула и последующая семантика найдены; исходное rationale выбора `2` не найдено |
| Redmine | `https://redmine.greensight.ru/issues/99027` | прямой запрос 2026-07-24 завершился timeout; первичная постановка не получена |

Поиск Jira чувствителен к словоформе; нулевой результат по основе слова не
используется как доказательство отсутствия.

## Ограничения безопасности

В отдельных спецификациях/задачах встречаются примеры авторизационных данных.
Они намеренно не перенесены в research. Источники следует считать требующими
санитарной очистки и ротации секретов владельцами систем.

## Resume pointer

Следующий инвентаризационный проход: свежие регламенты по каждому кабинету,
production-версии 1С-обработок, список DataBird imports/exports, access/run
history вызовов `/api/v1/updated-products` и отчёты последнего успешного обмена.
Для WB FBS — выбранный ЛЦ, документ по выделенным WB-станциям (число станций,
модели принтеров, размер этикетки, сроки), реальный sticker/ZPL и его печать,
reserve retry test, production `ОбменWB` cutover и один закрытый расчётный
период.
