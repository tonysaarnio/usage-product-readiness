# Usage Product Readiness

A small, dependency-free CLI that tells you — from a **live org** — whether a usage
product is actually wired up for the **Manage Usage Resources** guided flow, or
whether it will silently misbehave at quote/rating time.

```
usage-readiness product --org rlm-prod --product-code QB-CMT-TKN-EACH
usage-readiness scan    --org rlm-prod --active-only
```

> Accessory tool for Revenue Cloud Base Foundations. It is **read-only** (issues
> only `sf data query` / `sf sobject describe`), standalone, and installed only if
> you choose to. It is not part of, and does not modify, the main repo.

---

## The gap it closes

A usage product only works end-to-end when a chain of mostly-invisible records all
exist **and** are activated in the right order:

```
Product2 (Anchor/Pack/Commit/…)
  └─ ProductUsageResource (PUR)            active
       ├─ ProductUsageResourcePolicy (PURP)
       └─ ProductUsageGrant (PUG)          active, grant definition product active
  └─ UsagePrdGrantBindingPolicy            (Anchor / Pack only)
```

Nothing in the UI shows this chain in one place. A missing PURP, a Draft PUG, or an
absent binding policy produces **no error** — it surfaces later as a quote line that
won't configure or a rated summary of zero. This tool checks the whole chain at once
and prints a flat PASS/FAIL readiness verdict, for one product or across the org.

---

## What it checks

| Check | Why it matters | Blocking |
|---|---|---|
| Product `IsActive` | Inactive products don't sell | ✅ |
| `UsageModelType` is a real value | Catches typo'd / legacy models | advisory |
| ≥1 `ProductUsageResource`, ≥1 **Active** | No resource → nothing to meter | ✅ |
| ≥1 `ProductUsageResourcePolicy`, one per PUR | Policy drives rating/aggregation | ✅ |
| ≥1 `ProductUsageGrant`, ≥1 **Active** | The entitlement itself | ✅ |
| Grant `UsageDefinitionProduct`s active | A Draft definition strands the grant | ✅ |
| `UsagePrdGrantBindingPolicy` present | Required for **Anchor/Pack**; the platform rejects it for commitment models | ✅ (Anchor/Pack only) |

`product` can additionally check a specific quote line (`QuotLineItmUsageRsrcPlcy`
and `QuoteLineRateCardEntry` rows generated) via `--quote-id` or `--quote-line-id`.

### UsageModelType values

`Product2.UsageModelType` is a **restricted** picklist. On Salesforce 262 and 264 its
values are exactly:

```
Anchor, Pack, Commit, CommitmentQuantity, CommitmentSpend
```

`scan` **discovers** these from the org describe at runtime (and falls back to the
list above). The binding-policy rule follows the platform: binding is required for
`Anchor`/`Pack` and must be absent for `Commit`/`CommitmentQuantity`/`CommitmentSpend`.

---

## Install

Stdlib-only, so there are no Python dependencies to resolve. The only external
requirement is the Salesforce **`sf`** CLI, authenticated to your org(s).

**As a command (recommended):**

```bash
pipx install git+https://<your-host>/usage-product-readiness.git
# or, from a clone:
pipx install .
# or with uv:
uv tool install .
```

**Zero-install (clone & run):**

```bash
git clone https://<your-host>/usage-product-readiness.git
cd usage-product-readiness
python -m usage_product_readiness product --org <alias> --product-code <code>
```

---

## Usage

```bash
# One product, by code or Id
usage-readiness product --org rlm-prod --product-code QB-ANCHOR-API
usage-readiness product --org rlm-prod --product-id 01t...

# Include quote-line readiness (newest line in a quote, or a specific line)
usage-readiness product --org rlm-prod --product-id 01t... --quote-id 0Q0...
usage-readiness product --org rlm-prod --product-id 01t... --quote-line-id 0QL...

# Scan the whole org
usage-readiness scan --org rlm-prod
usage-readiness scan --org rlm-prod --active-only
usage-readiness scan --org rlm-prod --usage-model-types Anchor,Pack
usage-readiness scan --org rlm-prod --fail-on-not-ready   # CI-friendly exit code
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | `product`: READY · `scan`: completed (or no `--fail-on-not-ready`) |
| `1` | `product`: NOT READY · `scan`: a product was NOT READY and `--fail-on-not-ready` was set |
| `2` | Error (no `sf` CLI, query failure, product not found) |

---

## Prerequisites

- Salesforce **`sf`** CLI on `PATH`, authenticated to the target org (pass its alias
  or username to `--org`; this is the `sf` alias, not a CCI alias).
- Read access to `Product2`, `ProductUsageResource`, `ProductUsageResourcePolicy`,
  `ProductUsageGrant`, `UsagePrdGrantBindingPolicy`, and (for quote-line checks)
  `QuoteLineItem`, `QuotLineItmUsageRsrcPlcy`, `QuoteLineRateCardEntry`.
- Python 3.9+.

---

## Scope & limitations

- **Read-only, diagnostic.** It reports configuration state; it never creates,
  activates, or deletes anything.
- **Structural, not semantic.** It confirms the records exist and are active in the
  right shape; it does not re-derive rated amounts or wallet math.
- Object/field names and the `UsageModelType` picklist reflect Salesforce 262–264.
  `scan` discovers the picklist live; the static fallback may need a refresh on a
  newer release.
- Proof-of-concept / internal enablement tool — not production-ready ISV code.

---

## Development

```bash
python -m unittest discover -s tests   # offline tests, no org
python -m usage_product_readiness --version
```
