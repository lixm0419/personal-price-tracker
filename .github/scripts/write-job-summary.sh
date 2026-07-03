#!/usr/bin/env bash

set -u

log_file="${1:-price-check.log}"

summary_value() {
  local label="$1"
  local value
  value="$(grep -F "${label}:" "$log_file" | tail -n 1 | cut -d: -f2- | xargs)"
  printf '%s' "${value:-0}"
}

products_checked="$(summary_value "Products checked")"
successful_checks="$(summary_value "Successful checks")"
notifications_sent="$(summary_value "Notifications sent")"
skipped_duplicate="$(summary_value "Skipped (duplicate)")"
skipped_threshold="$(summary_value "Skipped (threshold)")"
errors="$(summary_value "Errors")"
execution_time="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"

sent_products="$(mktemp)"
failed_products="$(mktemp)"
trap 'rm -f "$sent_products" "$failed_products"' EXIT

awk '
  /^Product: / { product = substr($0, 10) }
  /^Notification: SENT$/ && product != "" { print product }
' "$log_file" | sort -u > "$sent_products"

sed -nE \
  's/^(Download failed for|Price check failed for|Notification failed for) (.*) at [^:]+:.*/\2/p' \
  "$log_file" | sort -u > "$failed_products"

{
  echo "# Price Tracker Daily Report"
  echo
  echo "**Execution time:** ${execution_time}"
  echo
  echo "| Metric | Count |"
  echo "| --- | ---: |"
  echo "| Products checked | ${products_checked} |"
  echo "| Successful checks | ${successful_checks} |"
  echo "| Notifications sent | ${notifications_sent} |"
  echo "| Skipped (duplicate) | ${skipped_duplicate} |"
  echo "| Skipped (threshold) | ${skipped_threshold} |"
  echo "| Errors | ${errors} |"

  if [[ "$notifications_sent" =~ ^[1-9][0-9]*$ ]]; then
    echo
    echo "## Notifications sent"
    if [[ -s "$sent_products" ]]; then
      sed 's/^/- /' "$sent_products"
    else
      echo "- See the workflow log for product details."
    fi
  fi

  if [[ "$errors" =~ ^[1-9][0-9]*$ ]]; then
    echo
    echo "## Failed products"
    if [[ -s "$failed_products" ]]; then
      sed 's/^/- /' "$failed_products"
    else
      echo "- See the workflow log for product details."
    fi
  fi
} >> "$GITHUB_STEP_SUMMARY"
