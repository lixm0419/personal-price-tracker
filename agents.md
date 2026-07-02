# AGENTS.md

# Personal Shopping Price Tracker

## Project Goal

Build a modular personal shopping price tracker.

The tracker should support monitoring products from any retail category.

The initial use cases include baby products, but the architecture should remain category-agnostic and easily extensible.

Users should be able to add or remove products by editing configuration files without changing application code.

---

# Design Philosophy

Prioritize maintainability over adding new features.

Whenever implementing a new feature, prefer extending the existing architecture rather than creating special-case logic.

Avoid introducing one-off code paths for individual stores or products.

Design for long-term extensibility.

---

# Tech Stack

- Python 3.12+
- SQLite
- PyYAML
- pytest
- CLI first
- Email notification
- GitHub Actions compatible

Do not build a web frontend unless explicitly requested.

---

# Architecture

Use a modular architecture.

Project layout should resemble:

src/
    adapters/
    alerts/
    config/
    database/
    models/
    services/
    utils/

One adapter per store.

Never mix scraping logic with business logic.

Business logic should never depend on a specific retailer.

---

# Product Configuration

Products must be configured through YAML.

Never hardcode:

- product names
- URLs
- stores
- discount thresholds

Configuration should support:

- name
- enabled
- urls
- notification_threshold (optional)

The application should define a global default notification threshold.

Default:

10%

Individual products may override the default threshold.

---

# Store Adapters

Each store has its own adapter.

Adapters should return a normalized object containing:

- product_name
- category
- store
- original_price
- current_price
- discount_amount
- discount_percent
- currency
- availability
- product_url
- checked_at

Adapters should only retrieve and normalize data.

No adapter should know about notification logic, databases, or other stores.

---

# Discount Logic

Calculate:

- discount_amount
- discount_percent

using:

original_price
current_price

Notify the user whenever:

discount_percent >= configured_threshold

Notification should include:

- Product name
- Store
- Original price
- Current price
- Discount amount
- Discount percentage
- Product URL

Future versions may support:

- historical lowest price
- price trend
- price prediction
- price comparison across stores

Design today's implementation so these features can be added later without major refactoring.

---

# Database

Store every successful price check.

SQLite schema should support:

- timestamp
- product
- category
- store
- original_price
- current_price
- discount_percent
- availability

The schema should support future price-history analysis.

---

# Notifications

Support email notifications.

Avoid duplicate notifications for the same unchanged discount.

Only notify when:

discount >= threshold

Future notification channels may include:

- Discord
- Slack
- Pushbullet
- Telegram

Design notifications behind a common interface.

---

# Testing

Use pytest.

Tests should include:

- config loading
- adapter parsing
- discount calculation
- notification logic
- database writes

Parser tests should use saved HTML fixtures whenever possible.

Tests should not depend on live websites.

---

# Scraping

Do not bypass CAPTCHAs.

Do not bypass login walls.

Use a reasonable User-Agent.

Use rate limiting.

Use retries with exponential backoff.

Gracefully handle parsing failures.

Adapters should never crash the application.

---

# Coding Style

Use:

- pathlib
- dataclasses
- type hints
- logging

Avoid:

- print()
- global variables
- duplicated code

Prefer:

- composition over inheritance
- small focused functions
- readable code over clever code

---

# Configuration Philosophy

The application should require code changes only when adding support for a new retailer.

Adding or removing products should never require changing Python code.

Whenever possible, prefer configuration over implementation.

---

# Before Completing Any Task

Always:

- Run tests.
- Update README if behavior changes.
- Keep functions focused.
- Avoid unnecessary refactoring.
- Maintain backward compatibility whenever possible.

Do not mark a task as complete unless the implementation is tested and documented.