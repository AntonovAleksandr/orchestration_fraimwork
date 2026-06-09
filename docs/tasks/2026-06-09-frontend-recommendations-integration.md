# Frontend: подключение к IntGateway за рекомендациями («Похожие товары»)

**Дата:** 2026-06-09
**Кому:** фронтенд
**Цель:** на странице товара показать блок/карусель «Похожие товары», данные — из IntGateway.

## TL;DR
Один GET-запрос в IntGateway по артикулу → получаешь массив **готовых карточек товара** в **том же формате, что уже рисуется в каруселях каталога** (тот же `ProductCard`-контракт). Никакого отдельного обогащения на фронте не нужно — gateway сам собирает карточки (id из движка рекомендаций + обогащение из catalog-cache). Можно сразу переиспользовать существующий компонент карточки/карусели.

## Endpoint

```
GET {GATEWAY_BASE}/api/v1/recommendations/similar?product_id=<артикул>&limit=<1..50>
```
- `product_id` — **обязателен**, артикул товара (напр. `GKT028479-2`).
- `limit` — опц., `1..50`, дефолт `10`.
- `{GATEWAY_BASE}` — базовый URL IntGateway для стенда (уточнить у devops; per-env: test/stage/prod).

## Ответ `200`

```json
{
  "items": [
    {
      "identifier": "GWT005596",
      "name": "Розовая рубашка",
      "text": "Розовая рубашка",
      "sort": 1,
      "availableStatus": "REGULAR",
      "price": 1699,
      "oldPrice": null,
      "images": [ { "guid": 929386, "sort": "01" } ],
      "modifications": [
        { "vendorCodeCc": "GWT005596-1", "imageUrl": "https://.../1.jpg", "isCurrent": true },
        { "vendorCodeCc": "GWT005596-2", "imageUrl": "https://.../2.jpg", "isCurrent": false }
      ],
      "labels": [
        { "name": "Новинка", "type": "new", "place": "down", "sort": 100, "backgroundColor": "#FFFFFF", "textColor": "#000000", "url": "" }
      ],
      "messages": [
        { "name": "Доставка", "sort": 2, "backgroundColor": "#F6F5EF", "textColor": "#000000", "url": "" }
      ],
      "sizes": [
        { "offerId": 504243758, "vendorCodeSku": "GWT005596F0006", "name": "XXS", "sort": "21",
          "availableStatus": "REGULAR", "price": 1699, "oldPrice": null, "message": null }
      ]
    }
  ]
}
```

### Поля `ProductCard`
| Поле | Тип | Назначение |
|---|---|---|
| `identifier` | string | id/артикул карточки (ключ, ссылка на PDP) |
| `name`, `text` | string | название / подпись |
| `sort` | int | порядок в карусели (1..N) |
| `availableStatus` | enum | `REGULAR` \| `SALE` \| `SOLD_OUT` \| `SOON` \| `DIFFERENT_REGULAR` \| `DIFFERENT_SALE` |
| `price` | number | цена (руб.) |
| `oldPrice` | number\|null | старая цена (для зачёркивания) |
| `images[]` | `{guid:int, sort:string}` | картинки (по `guid` → CDN, как в каталоге) |
| `modifications[]` | `{vendorCodeCc, imageUrl, isCurrent}` | цветовые модификации (превью по `imageUrl`; `isCurrent`=текущая) |
| `labels[]` | бейджи | `{name, type, place, sort, backgroundColor, textColor, url}` |
| `messages[]` | плашки | `{name, sort, backgroundColor, textColor, url}` |
| `sizes[]` | размеры | `{offerId, vendorCodeSku, name, sort, availableStatus, price, oldPrice, message}` |

> Это **тот же контракт карточки**, что отдаёт каталог для каруселей. Переиспользуй существующий компонент карточки — отдельная нормализация не нужна.

## Ошибки

JSON `{ "code": "...", "message": "..." }`:
| HTTP | code | когда |
|---|---|---|
| `400` | `invalid_argument` | нет `product_id`, или `limit` вне `1..50` |
| `502` | `source_unavailable` | источник рекомендаций недоступен |
| `500` | `internal` | внутренняя ошибка |

Фронт: при `4xx/5xx` — просто **не показывать блок** «Похожие» (graceful: пустой ответ/ошибка → скрыть секцию), без падения страницы.

## OpenAPI / типы
В репо IntGateway есть спека: `api/v1/openapi.yaml` (+ `api/v1/bundle/openapi.yaml`). Можно сгенерить типы для фронта (или взять схему `SimilarResponse`/`ProductCard` оттуда).

## ⚠️ Важно: что сейчас «настоящее», а что временное
Endpoint и **формат карточек — боевые** (готовы к интеграции прямо сейчас). НО источник рекомендаций пока **заглушка**: gateway возвращает детерминированный набор товаров (обогащённых реальными данными из catalog-cache). То есть:
- **форма ответа и поля карточки финальные** — можно строить UI и считать его готовым;
- **конкретные товары в выдаче — временные**; станут реальными «похожими», когда подключат настоящий движок рекомендаций (на стороне backend, без изменения контракта/формы).

Поэтому: **делай реализацию против этого контракта уже сейчас**; когда backend заменит заглушку — UI менять не придётся, поменяется только содержимое выдачи.

## Definition of Done (фронт)
- На PDP блок «Похожие товары» дёргает `GET /api/v1/recommendations/similar?product_id=<текущий артикул>&limit=N`.
- Рендерит `items` существующим компонентом карточки/карусели (цена/oldPrice, бейджи `labels`, плашки `messages`, картинка, размеры).
- Пустой ответ / ошибка → секция скрыта (без падения).
- `limit` под дизайн карусели (≤50).
