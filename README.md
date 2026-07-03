# Personal Shopping Price Tracker

Phase 1 is a category-agnostic, YAML-configured price tracker with a fake
adapter for local development. It stores every successful check in SQLite.
Ergobaby, Woolino, and deterministic fake adapters are included. Discount
alerts can be sent by email.

## Install

Python 3.12 or newer is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Configure the tracker

Configuration is split by responsibility:

- `config/products.yaml` contains product names, categories, enabled state,
  optional per-product thresholds, option selection, and store URLs.
- `config/settings.yaml` contains the default notification threshold (10 when
  omitted), SQLite database path, logging level, and email configuration.

Each product has a `stores` mapping. A store entry currently contains its URL:

```yaml
products:
  - name: Example Product
    enabled: true
    notification_threshold: null
    option_strategy: specific_options
    options:
      color: blue
      size: large
      sku: 12345
    stores:
      fake:
        url: "fake://example-item?original=29.99&current=24.99&available=true&currency=USD"
```

A product can override the settings-level threshold with
`notification_threshold`; `null` or an omitted field uses the global default.
Options are generic scalar key/value pairs, so categories can define whatever
matters to them (for example color, size, SKU, flavor, or storage).

`option_strategy` controls how a store adapter selects variants:

- `lowest_price` (default) filters by concrete configured options, treats
  `any` as a wildcard, and selects the lowest-priced available match. When
  several matches share that price, `PriceData.tied_variants` contains the
  other option labels and the CLI displays them after `tied lowest with:`.
- `specific_options` selects variants matching the configured `options`.
- `all_options` is reserved for returning every available variant.

The Ergobaby adapter currently treats `all_options` like `lowest_price` because
`PriceData` and `PriceChecker` return one result per store URL. Supporting every
variant will require changing the adapter contract to return a collection of
`PriceData` values. The selected Ergobaby variant is represented by its full
variant name in `PriceData.product_name`.

## Adapter architecture

Networking and parsing are separate:

- `PriceChecker` reads each configured URL and coordinates the workflow.
- `HttpClient` downloads source text with a timeout, request headers,
  User-Agent, basic retries, and failure logging.
- `StoreAdapter` exposes `store_name` and `parse(html, product_config)`.
- The parsed `PriceData` is persisted by `PriceChecker`.

`HttpClient` knows nothing about products or prices. Adapters perform no HTTP
requests and know nothing about storage or notifications. Expected parser
failures raise `AdapterError`; exhausted network attempts raise
`HttpClientError`. Both are handled per product so one failure does not stop
other checks.

`ErgobabyAdapter` parses the page's static JSON-LD product variants and selected
Shopify variant data. It performs no networking. `PriceChecker` uses the shared
client to download the configured URL before calling the parser. Parser tests
use saved HTML under `tests/fixtures/ergobaby/` and never contact the live site.

`WoolinoAdapter` parses Woolino's static JSON-LD offers and embedded Shopify
variant JSON. It supports the same configured option strategies and likewise
performs no networking. Its parser tests use saved HTML under
`tests/fixtures/woolino/`.

To add another store URL to an existing product, add another key beneath its
`stores` mapping:

```yaml
stores:
  fake:
    url: "fake://example-item?original=29.99&current=24.99"
  target:
    url: "https://www.target.com/p/example"
```

A configured store requires a corresponding adapter before it can be checked;
unsupported stores are logged and skipped. To add a product, append another
item under `products` with at least `name` and a non-empty `stores` mapping.
`enabled` defaults to true and `option_strategy` defaults to `lowest_price`.

## Email notifications

Keep only SMTP behavior and environment-variable names in
`config/settings.yaml`. Credentials, sender, and recipient are resolved from
the process environment when configuration is loaded:

```yaml
email:
  enabled: true
  smtp_host: smtp.example.com
  smtp_port: 587
  use_tls: true
  username_env: PRICE_TRACKER_EMAIL_USERNAME
  password_env: PRICE_TRACKER_EMAIL_PASSWORD
  sender_env: PRICE_TRACKER_EMAIL_SENDER
  recipient_env: PRICE_TRACKER_EMAIL_RECIPIENT
```

If email is enabled, all four named variables are required. Configuration
loading reports the exact missing variable without displaying secret values.

### Local development on Windows

Copy `.env.example` as a reference, then set the variables in the PowerShell
process that will run the tracker:

```powershell
$env:PRICE_TRACKER_EMAIL_USERNAME = "your-smtp-username"
$env:PRICE_TRACKER_EMAIL_PASSWORD = "your-smtp-password"
$env:PRICE_TRACKER_EMAIL_SENDER = "alerts@example.com"
$env:PRICE_TRACKER_EMAIL_RECIPIENT = "you@example.com"
python -m price_tracker check
```

`.env.example` documents the expected names, but the application deliberately
does not load `.env` files. `.env` is ignored by Git. For persistent Windows
user variables, use `setx NAME "value"` and open a new terminal afterward.

### GitHub Actions Secrets

Create repository or environment secrets named
`PRICE_TRACKER_EMAIL_USERNAME`, `PRICE_TRACKER_EMAIL_PASSWORD`,
`PRICE_TRACKER_EMAIL_SENDER`, and `PRICE_TRACKER_EMAIL_RECIPIENT` under
**Settings → Secrets and variables → Actions → New repository secret**. Secret
values are never stored in the workflow or repository.

`.github/workflows/scheduled-price-check.yml` runs once daily at 12:17 UTC and
can also be started manually from the Actions tab. It installs the package,
restores the SQLite history cache, and runs `python -m price_tracker check`
with those four secrets mapped into the process environment. The history cache
preserves duplicate-notification state between ephemeral Actions runners.

To send scheduled alerts, set `email.enabled: true` in
`config/settings.yaml`. Leave it false if the workflow should record checks
without sending email.

Future deployment platforms should configure the same four names through their
secret/environment management facility rather than committing values to YAML.

Verify SMTP credentials, TLS, sender, and recipient without running product
checks or opening the SQLite database:

```powershell
python -m price_tracker send-test-email
```

The test message uses subject `Price Tracker Test Email` and body
`SMTP configuration is working.` Email must be enabled and all configured
environment variables must be present.

Notifications are sent only when a product's discount meets its configured
threshold (or the global default). A successful alert is recorded in SQLite,
preventing another email for the same product variant and unchanged discount.
Failed sends are logged and remain eligible for retry.

Preview qualifying notifications without connecting to SMTP:

```powershell
python -m price_tracker check --dry-run-notifications
```

Dry runs print one decision for every successful product/store check. Each is
marked `WOULD SEND` or `SKIPPED`; skipped entries explain whether the cause is
the threshold, availability, duplicate history, or missing email
configuration. Sendable entries include the URL and tied variants when ties
exist, followed by a checked/would-notify/skipped summary. Dry runs never send
email or record a notification as sent.

## Run tests

```powershell
python -m pytest
```

## Use the CLI

The CLI loads `config/products.yaml` and `config/settings.yaml` by default.
Use `--products` and `--settings` to select other files. `--config` remains an
alias for `--products`. The database path comes from settings unless
`--database` overrides it.

```powershell
price-tracker list-products
price-tracker check
price-tracker send-test-email
price-tracker latest
price-tracker latest --limit 5
price-tracker --products other-products.yaml --settings other-settings.yaml check
price-tracker --database temporary.db check
```

Equivalent module invocation:

```powershell
python -m price_tracker check
```
