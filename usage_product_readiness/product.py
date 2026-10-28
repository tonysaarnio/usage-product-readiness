"""`usage-readiness product` — detailed readiness report for one usage product."""

from __future__ import annotations

import argparse
from typing import Any

from ._soql import run_soql, soql_literal
from .readiness import evaluate_product


def _print_check(label: str, ok: bool, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"[{'PASS' if ok else 'FAIL'}] {label}{suffix}")


def _get_product(org: str, product_id: str | None, product_code: str | None) -> dict[str, Any]:
    if product_id:
        where, key = f"Id = '{soql_literal(product_id)}'", product_id
    else:
        # argparse guarantees exactly one of id/code, so product_code is set here.
        where, key = f"ProductCode = '{soql_literal(product_code or '')}'", product_code
    rows = run_soql(
        org,
        "SELECT Id, Name, ProductCode, StockKeepingUnit, IsActive, UsageModelType "
        f"FROM Product2 WHERE {where} LIMIT 2",
    )
    if not rows:
        print(f"ERROR: No Product2 found for {key!r}.")
        raise SystemExit(2)
    if len(rows) > 1:
        print(f"WARNING: more than one Product2 matched {key!r}; using the first ({rows[0]['Id']}).")
    return rows[0]


def _gather(org: str, product_id: str) -> dict[str, Any]:
    pid = soql_literal(product_id)
    pur_rows = run_soql(
        org,
        "SELECT Id, Status, UsageResourceId, UsageResource.Code "
        f"FROM ProductUsageResource WHERE ProductId = '{pid}'",
    )
    purp_rows = run_soql(
        org,
        "SELECT Id, ProductUsageResourceId "
        f"FROM ProductUsageResourcePolicy WHERE ProductUsageResource.ProductId = '{pid}'",
    )
    pug_rows = run_soql(
        org,
        "SELECT Id, Status, ProductUsageResourceId, UsageDefinitionProductId, "
        "UsageDefinitionProduct.ProductCode "
        f"FROM ProductUsageGrant WHERE ProductUsageResource.ProductId = '{pid}'",
    )
    binding_rows = run_soql(
        org,
        "SELECT Id, GrantBindingType, GrantBindingTargetType "
        f"FROM UsagePrdGrantBindingPolicy WHERE Product2Id = '{pid}'",
    )
    usage_def_ids = sorted(
        {r.get("UsageDefinitionProductId") for r in pug_rows if r.get("UsageDefinitionProductId")}
    )
    usage_def_active: dict[str, bool] = {}
    if usage_def_ids:
        in_clause = ",".join(f"'{soql_literal(x)}'" for x in usage_def_ids)
        for r in run_soql(org, f"SELECT Id, IsActive FROM Product2 WHERE Id IN ({in_clause})"):
            usage_def_active[r["Id"]] = bool(r.get("IsActive"))
    return {
        "pur_rows": pur_rows,
        "purp_rows": purp_rows,
        "pug_rows": pug_rows,
        "binding_rows": binding_rows,
        "usage_def_active": usage_def_active,
    }


def _resolve_quote_line_id(org: str, quote_id: str) -> str | None:
    rows = run_soql(
        org,
        "SELECT Id FROM QuoteLineItem "
        f"WHERE QuoteId = '{soql_literal(quote_id)}' ORDER BY CreatedDate DESC LIMIT 1",
    )
    return rows[0]["Id"] if rows else None


def _check_quote_line(org: str, product_id: str, quote_line_id: str) -> bool:
    """Print quote-line readiness; return True if usage policy rows were generated."""
    qlid = soql_literal(quote_line_id)
    ql_rows = run_soql(
        org,
        "SELECT Id, QuoteId, Product2Id, BindingInstanceTargetId "
        f"FROM QuoteLineItem WHERE Id = '{qlid}'",
    )
    if not ql_rows:
        print(f"ERROR: Quote line {quote_line_id!r} not found.")
        return False
    qli = ql_rows[0]
    if qli.get("Product2Id") != product_id:
        print(f"WARNING: quote line product {qli.get('Product2Id')} != target product {product_id}.")

    usage_rows = run_soql(
        org,
        "SELECT Id, QuoteLineItemId, ProductUsageResourcePolicyId, UsageResourceId "
        f"FROM QuotLineItmUsageRsrcPlcy WHERE QuoteLineItemId = '{qlid}'",
    )
    rate_rows = run_soql(
        org,
        "SELECT Id, QuoteLineItemId, UsageResourceId, RateCardEntryId "
        f"FROM QuoteLineRateCardEntry WHERE QuoteLineItemId = '{qlid}'",
    )
    print("")
    print("Quote-line readiness")
    _print_check("Quote line usage policy rows generated", bool(usage_rows), f"count={len(usage_rows)}")
    _print_check("Quote line rate rows generated (optional by flow timing)", bool(rate_rows), f"count={len(rate_rows)}")
    print(f"  BindingInstanceTargetId: {qli.get('BindingInstanceTargetId')}")
    return bool(usage_rows)


def run(args: argparse.Namespace) -> int:
    product = _get_product(args.org, args.product_id, args.product_code)
    pid = product["Id"]

    print(f"Product: {product.get('Name')} ({pid})")
    print(f"ProductCode: {product.get('ProductCode')}")
    print(f"SKU: {product.get('StockKeepingUnit')}")
    print(f"UsageModelType: {product.get('UsageModelType')}")
    print(f"IsActive: {bool(product.get('IsActive'))}")
    print("")

    rows = _gather(args.org, pid)
    result = evaluate_product(product, **rows)

    print("Product-level readiness")
    for c in result.checks:
        _print_check(c.label, c.ok, c.detail)
    if rows["binding_rows"]:
        b = rows["binding_rows"][0]
        print(f"  Binding sample: type={b.get('GrantBindingType')}, target={b.get('GrantBindingTargetType')}")

    quote_line_ok = True
    quote_line_id = args.quote_line_id
    if not quote_line_id and args.quote_id:
        quote_line_id = _resolve_quote_line_id(args.org, args.quote_id)
        if quote_line_id:
            print(f"\nUsing newest quote line in quote: {quote_line_id}")
        else:
            print(f"\nNo quote lines found for quote {args.quote_id}.")
    if quote_line_id:
        quote_line_ok = _check_quote_line(args.org, pid, quote_line_id)

    print("")
    if result.is_ready and quote_line_ok:
        print("Overall: READY")
        return 0
    blocking = len(result.blocking_failures) + (0 if quote_line_ok else 1)
    print(f"Overall: NOT READY ({blocking} blocking check(s))")
    return 1
