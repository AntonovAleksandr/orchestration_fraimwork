#!/usr/bin/env bash

set -u
set -o pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ORDERS_FILE="$SCRIPT_DIR/orders-active.txt"
OMS_BASE_URL="${OMS_BASE_URL:-https://api-oms.gloria-jeans.ru}"
DELAY_SECONDS="${DELAY_SECONDS:-0.5}"
OUTPUT_DIR="$SCRIPT_DIR/results"
EXECUTE=false

usage() {
  cat <<'USAGE'
Usage:
  ./reconcile-yookassa-active.sh [--orders FILE] [--delay SECONDS]
  OMS_TOKEN='...' GJ_SECRET='...' ./reconcile-yookassa-active.sh --execute [options]

Options:
  --execute          Call the mutating updatePayment=true endpoint.
                     Without this flag the script only validates and prints the plan.
  --orders FILE      Order-ID file (default: orders-active.txt next to the script).
  --delay SECONDS    Pause between orders (default: 0.5).
  --output-dir DIR   Result-log directory (default: results next to the script).
  --base-url URL     OMS base URL (default: https://api-oms.gloria-jeans.ru).
  -h, --help         Show this help.

The JWT is accepted only through OMS_TOKEN and is sent in the access_token
cookie. The ServicePipe secret is accepted only through GJ_SECRET and is sent
in the gj-secret header.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --execute)
      EXECUTE=true
      shift
      ;;
    --orders)
      [ "$#" -ge 2 ] || { echo "ERROR: --orders requires a value" >&2; exit 2; }
      ORDERS_FILE=$2
      shift 2
      ;;
    --delay)
      [ "$#" -ge 2 ] || { echo "ERROR: --delay requires a value" >&2; exit 2; }
      DELAY_SECONDS=$2
      shift 2
      ;;
    --output-dir)
      [ "$#" -ge 2 ] || { echo "ERROR: --output-dir requires a value" >&2; exit 2; }
      OUTPUT_DIR=$2
      shift 2
      ;;
    --base-url)
      [ "$#" -ge 2 ] || { echo "ERROR: --base-url requires a value" >&2; exit 2; }
      OMS_BASE_URL=${2%/}
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[ -r "$ORDERS_FILE" ] || { echo "ERROR: cannot read orders file: $ORDERS_FILE" >&2; exit 2; }

if ! awk -v delay="$DELAY_SECONDS" 'BEGIN {
  exit !(delay ~ /^([0-9]+([.][0-9]*)?|[.][0-9]+)$/)
}'; then
  echo "ERROR: --delay must be a non-negative number" >&2
  exit 2
fi

normalized_file=$(mktemp "${TMPDIR:-/tmp}/yookassa-orders.XXXXXX") || exit 2
body_file=$(mktemp "${TMPDIR:-/tmp}/yookassa-response.XXXXXX") || {
  rm -f "$normalized_file"
  exit 2
}
trap 'rm -f "$normalized_file" "$body_file"' EXIT HUP INT TERM

awk '
  {
    sub(/\r$/, "")
    sub(/#.*/, "")
    gsub(/^[[:space:]]+|[[:space:]]+$/, "")
    if (length($0) > 0) print
  }
' "$ORDERS_FILE" > "$normalized_file"

if ! awk '/^[0-9]+$/ { next } { exit 1 }' "$normalized_file"; then
  echo "ERROR: orders file contains a non-numeric order ID" >&2
  exit 2
fi

order_count=$(wc -l < "$normalized_file" | tr -d ' ')
[ "$order_count" -gt 0 ] || { echo "ERROR: orders file is empty" >&2; exit 2; }

unique_count=$(sort -u "$normalized_file" | wc -l | tr -d ' ')
if [ "$unique_count" -ne "$order_count" ]; then
  echo "ERROR: orders file contains duplicate IDs ($order_count rows, $unique_count unique)" >&2
  exit 2
fi

echo "Orders file : $ORDERS_FILE"
echo "Orders      : $order_count"
echo "OMS         : $OMS_BASE_URL"
echo "Delay       : ${DELAY_SECONDS}s"

if [ "$EXECUTE" != true ]; then
  echo "Mode        : DRY RUN"
  echo
  echo "No HTTP requests were sent. To execute reconciliation:"
  echo "  OMS_TOKEN='...' $0 --execute"
  exit 0
fi

command -v curl >/dev/null 2>&1 || { echo "ERROR: curl is required" >&2; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq is required" >&2; exit 2; }
[ -n "${OMS_TOKEN:-}" ] || { echo "ERROR: OMS_TOKEN is required in --execute mode" >&2; exit 2; }
[ -n "${GJ_SECRET:-}" ] || { echo "ERROR: GJ_SECRET is required in --execute mode" >&2; exit 2; }

case "$OMS_TOKEN" in
  access_token=*) cookie_value=$OMS_TOKEN ;;
  *) cookie_value="access_token=$OMS_TOKEN" ;;
esac

mkdir -p "$OUTPUT_DIR" || exit 2
run_timestamp=$(date -u '+%Y%m%dT%H%M%SZ')
result_file="$OUTPUT_DIR/reconciliation-$run_timestamp.csv"
echo 'timestamp_utc;client_order_id;phase;http_code;yookassa_debit_statuses;result' > "$result_file"

echo "Mode        : EXECUTE"
echo "Result log  : $result_file"
echo

processed=0
updated=0
skipped=0
failed=0

request_payment_list() {
  request_order_id=$1
  request_update=$2
  request_url="$OMS_BASE_URL/v1/payment/list?clientOrderId=$request_order_id&updatePayment=$request_update"
  curl --silent --show-error \
    --connect-timeout 10 \
    --max-time 120 \
    --header "Cookie: $cookie_value" \
    --header "gj-secret: $GJ_SECRET" \
    --header 'Accept: application/json' \
    --output "$body_file" \
    --write-out '%{http_code}' \
    "$request_url"
}

extract_statuses() {
  jq -r '[.[]
    | select((.acquierId // "") == "yookassa" and (.transactionType // "") == "debit")
    | (.acquierTransactionStatusId // "unknown")]
    | unique
    | join(",")' "$body_file"
}

while IFS= read -r order_id; do
  processed=$((processed + 1))
  printf '[%d/%d] %s: reconciling... ' "$processed" "$order_count" "$order_id"
  http_code=$(request_payment_list "$order_id" true)
  curl_exit=$?
  now=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

  if [ "$curl_exit" -ne 0 ]; then
    echo "transport error (curl=$curl_exit); stopped"
    echo "$now;$order_id;update;000;;transport_error_$curl_exit" >> "$result_file"
    exit 1
  fi

  if [ "$http_code" -lt 200 ] || [ "$http_code" -ge 300 ]; then
    case "$http_code" in
      401|403|429)
        echo "HTTP $http_code; stopped"
        echo "$now;$order_id;update;$http_code;;fatal_http_error" >> "$result_file"
        exit 1
        ;;
      *)
        echo "HTTP $http_code; skipped"
        echo "$now;$order_id;update;$http_code;;http_error_skipped" >> "$result_file"
        failed=$((failed + 1))
        sleep "$DELAY_SECONDS"
        continue
        ;;
    esac
  fi

  if ! jq -e 'type == "array"' "$body_file" >/dev/null 2>&1; then
    echo "invalid JSON response; stopped"
    echo "$now;$order_id;update;$http_code;;invalid_json" >> "$result_file"
    exit 1
  fi

  statuses=$(extract_statuses)
  case ",$statuses," in
    *,charged,*|*,charge,*) result=charged ;;
    *,cancelled,*|*,canceled,*) result=cancelled ;;
    *,new,*) result=still_new ;;
    ,,) result=empty ;;
    *) result=updated ;;
  esac

  echo "$result (statuses=$statuses)"
  echo "$now;$order_id;update;$http_code;$statuses;$result" >> "$result_file"
  updated=$((updated + 1))
  sleep "$DELAY_SECONDS"
done < "$normalized_file"

echo
echo "Completed: processed=$processed, reconciled=$updated, skipped=$skipped, errors=$failed"
echo "Result log: $result_file"

[ "$failed" -eq 0 ] || exit 1
