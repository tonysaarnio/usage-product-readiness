"""`usage-readiness scan` — scan many usage products in an org for readiness."""

from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Any, Iterable

from ._soql import describe_picklist, run_soql, soql_literal
from .models import USAGE_MODEL_TYPES
from .readiness import evaluate_product


def _chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _resolve_model_types(org: str, override: str | None) -> list[str]:
    """Explicit --usage-model-types wins; otherwise discover from the org, falling
    back to the documented static picklist."""
    if override:
        return [x.strip() for x in override.split(",") if x.strip()]
    discovered = describe_picklist(org, "Product2", "UsageModelType")
    return discovered or list(USAGE_MODEL_TYPES)


def _get_products(org: str, model_types: list[str], active_only: bool) -> list[dict[str, Any]]:
    values = ",".join(f"'{soql_literal(x)}'" for x in model_types)
    where = f"UsageModelType IN ({values})"
    if active_only:
        where += " AND IsActive = true"
    return run_soql(
        org,
        "SELECT Id, Name, ProductCode, StockKeepingUnit, IsActive, UsageModelType "
        f"FROM Product2 WHERE {where} ORDER BY Name ASC",
    )


def run(args: argparse.Namespace) -> int:
    model_types = _resolve_model_types(args.org, args.usage_model_types)
    products = _get_products(args.org, model_types, args.active_only)
    if not products:
        print("No products matched the filter.")
        return 0

    product_ids = [p["Id"] for p in products]
    pur_by_product: dict[str, list] = defaultdict(list)
    purp_by_product: dict[str, list] = defaultdict(list)
    pug_by_product: dict[str, list] = defaultdict(list)
    binding_by_product: dict[str, list] = defaultdict(list)
    usage_def_ids: set[str] = set()

    for batch in _chunked(product_ids, 150):
        in_clause = ",".join(f"'{soql_literal(x)}'" for x in batch)

        for row in run_soql(
            args.org,
            "SELECT Id, ProductId, Status, UsageResource.Code "
            f"FROM ProductUsageResource WHERE ProductId IN ({in_clause})",
        ):
            pur_by_product[row["ProductId"]].append(row)

        for row in run_soql(
            args.org,
            "SELECT Id, ProductUsageResourceId, ProductUsageResource.ProductId "
            f"FROM ProductUsageResourcePolicy WHERE ProductUsageResource.ProductId IN ({in_clause})",
        ):
            purp_by_product[row["ProductUsageResource"]["ProductId"]].append(row)

        for row in run_soql(
            args.org,
            "SELECT Id, Status, ProductUsageResource.ProductId, UsageDefinitionProductId, "
            "UsageDefinitionProduct.ProductCode "
            f"FROM ProductUsageGrant WHERE ProductUsageResource.ProductId IN ({in_clause})",
        ):
            pug_by_product[row["ProductUsageResource"]["ProductId"]].append(row)
            if row.get("UsageDefinitionProductId"):
                usage_def_ids.add(row["UsageDefinitionProductId"])

        for row in run_soql(
            args.org,
            "SELECT Id, Product2Id, GrantBindingType, GrantBindingTargetType "
            f"FROM UsagePrdGrantBindingPolicy WHERE Product2Id IN ({in_clause})",
        ):
            binding_by_product[row["Product2Id"]].append(row)

    usage_def_active: dict[str, bool] = {}
    for batch in _chunked(sorted(usage_def_ids), 150):
        in_clause = ",".join(f"'{soql_literal(x)}'" for x in batch)
        for row in run_soql(args.org, f"SELECT Id, IsActive FROM Product2 WHERE Id IN ({in_clause})"):
            usage_def_active[row["Id"]] = bool(row.get("IsActive"))

    print("Usage Product Readiness Scan")
    print(f"Org: {args.org}")
    print(f"UsageModelType filter: {', '.join(model_types)}")
    print(f"Products scanned: {len(products)}")
    print("")

    ready = not_ready = 0
    for p in products:
        pid = p["Id"]
        result = evaluate_product(
            p,
            pur_rows=pur_by_product.get(pid, []),
            purp_rows=purp_by_product.get(pid, []),
            pug_rows=pug_by_product.get(pid, []),
            binding_rows=binding_by_product.get(pid, []),
            usage_def_active=usage_def_active,
        )
        status = "READY" if result.is_ready else "NOT_READY"
        detail = "; ".join(result.reasons()) if not result.is_ready else "all checks passed"
        code = p.get("ProductCode") or "-"
        sku = p.get("StockKeepingUnit") or "-"
        model = p.get("UsageModelType") or "-"
        print(f"{status:10} {p['Name']} | code={code} | sku={sku} | model={model} | {detail}")
        if result.is_ready:
            ready += 1
        else:
            not_ready += 1

    print("")
    print(f"Summary: READY={ready}, NOT_READY={not_ready}")
    if not_ready and args.fail_on_not_ready:
        return 1
    return 0
