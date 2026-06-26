# Platform: Non-Platform / Adjacent Services

Adjacent services and utilities that do not belong cleanly to the main platform groups but can still influence e-commerce behavior, feeds, reporting, reviews, stock, and merchandising.

## Что здесь лежит

```
non-platform/
├── ecom-auto-merch/
├── ecom-stat-service/
├── event-dispatcher/
├── feed-generator/
├── stock-inventory-service/
├── dwh-exporter/
├── OzonReviews/
├── GjReportViwer/
└── bots/
```

## Когда смотреть сюда

- feeds, merchandising, reporting, reviews, or stock side services;
- legacy or support services that are not part of ENSI / OMS / Integration / Site / Mobile / OTS;
- cross-system investigations where the source is known to be outside the six primary platforms.

## Git

Each child directory is a separate local clone and is ignored by the workspace root. Keep service changes inside the nested repo.
