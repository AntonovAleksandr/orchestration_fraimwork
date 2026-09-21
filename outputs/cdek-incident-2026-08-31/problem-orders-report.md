# CDEK incident: confirmed problem orders

Snapshot: 2026-08-31 13:29 MSK  
Log source: `gloria_ots_prod`, `GloriaOTS.Web`

## Selection criteria

An order is included when all conditions are met:

1. During the incident, OTS logged a 100-second `HttpClient.Timeout` in `CdekApiClient.RegisterOrder`.
2. OTS saved the order transition as `CHECKED_INVALID`.
3. No later `ORDER_REGISTER_TRANSPORT complete` event was found by the snapshot time.
4. No later `Publish TgwCreateOrderEvent` event was found by the snapshot time.

There were 40 unique orders with any CDEK timeout during the incident. Eleven of them failed specifically while registering a new order and meet the criteria above.

## Orders

| Order ID | Last registration timeout, MSK | CDEK accepted response in logs | Transport completed later | Sent to warehouse later | Assessment |
|---|---:|---|---|---|---|
| 2011314273 | 10:15:51 | No | No | No | Confirmed problem |
| 2000558826 | 10:47:53 | No | No | No | Confirmed problem |
| 2000304555 | 10:49:34 | No | No | No | Confirmed problem |
| 2010639262 | 10:51:34 | No | No | No | Confirmed problem |
| 2011315134 | 10:53:33 | No | No | No | Confirmed problem |
| 2005037609 | 11:20:58 | No | No | No | Confirmed problem |
| 2010345916 | 11:41:49 | No | No | No | Confirmed problem |
| 2010938111 | 11:57:22 | No | No | No | Confirmed problem |
| 2011315804 | 12:00:15 | Yes, at 11:58:36 | No | No | Confirmed problem; check for duplicate in CDEK before retry |
| 2010715991 | 12:02:07 | No | No | No | Confirmed problem |
| 2008393724 | 12:19:24 | No | No | No | Confirmed problem |

## Required operational check

An HTTP timeout is an ambiguous result: CDEK may have accepted a request even when OTS did not receive the response. Before retrying each order:

1. Search CDEK by the Gloria Jeans order number.
2. If the order exists in CDEK, restore/reconcile the external CDEK identifiers in OTS and continue the workflow without creating a duplicate.
3. If the order does not exist in CDEK, re-run registration and verify both `ORDER_REGISTER_TRANSPORT complete` and `Publish TgwCreateOrderEvent`.
4. For order `2011315804`, an accepted CDEK response is already present, so it must not be blindly registered again.

## Scope note

The other 29 orders from the initial set had timeouts in CDEK status/update operations rather than initial `RegisterOrder`. They are not included in this warehouse-blocking registration list.
