"""Pure, offline readiness evaluation for a single usage product.

No org access happens here — callers (:mod:`product`, :mod:`scan`) gather the
related rows however they like and pass them in, which keeps the logic
unit-testable without a live org.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import COMMITMENT_USAGE_MODELS, GUIDED_USAGE_MODELS


@dataclass
class Check:
    """One readiness assertion.

    ``label`` is the positive phrasing used in the detailed ``product`` report;
    ``fail_reason`` is the concise negative used in the ``scan`` one-liner.
    ``blocking`` checks decide READY vs NOT READY; non-blocking ones are advisory.
    """

    label: str
    ok: bool
    detail: str = ""
    blocking: bool = True
    fail_reason: str = ""

    def reason(self) -> str:
        return self.fail_reason or self.label


@dataclass
class ProductReadiness:
    product: dict[str, Any]
    checks: list[Check] = field(default_factory=list)

    @property
    def blocking_failures(self) -> list[Check]:
        return [c for c in self.checks if c.blocking and not c.ok]

    @property
    def is_ready(self) -> bool:
        return not self.blocking_failures

    def reasons(self) -> list[str]:
        return [c.reason() for c in self.blocking_failures]


def evaluate_product(
    product: dict[str, Any],
    *,
    pur_rows: list[dict[str, Any]],
    purp_rows: list[dict[str, Any]],
    pug_rows: list[dict[str, Any]],
    binding_rows: list[dict[str, Any]],
    usage_def_active: dict[str, bool],
) -> ProductReadiness:
    """Evaluate one product's readiness from its related rows.

    - ``pur_rows``: ProductUsageResource (needs ``Id``, ``Status``)
    - ``purp_rows``: ProductUsageResourcePolicy (needs ``ProductUsageResourceId``)
    - ``pug_rows``: ProductUsageGrant (needs ``Status``, ``UsageDefinitionProductId``)
    - ``binding_rows``: UsagePrdGrantBindingPolicy
    - ``usage_def_active``: ``{Product2Id: IsActive}`` for each grant's definition product
    """
    usage_model = product.get("UsageModelType")

    pur_active = [r for r in pur_rows if r.get("Status") == "Active"]
    pur_ids = [r["Id"] for r in pur_rows]
    pur_with_policy = {r.get("ProductUsageResourceId") for r in purp_rows}
    pur_missing_policy = [i for i in pur_ids if i not in pur_with_policy]

    pug_active = [r for r in pug_rows if r.get("Status") == "Active"]
    usage_def_inactive = [
        r
        for r in pug_rows
        if r.get("UsageDefinitionProductId")
        and not usage_def_active.get(r["UsageDefinitionProductId"], False)
    ]

    binding_required = usage_model not in COMMITMENT_USAGE_MODELS

    checks = [
        Check("Product active", bool(product.get("IsActive")),
              f"IsActive={product.get('IsActive')}", fail_reason="product inactive"),
        Check("Usage model is a real UsageModelType", usage_model in GUIDED_USAGE_MODELS,
              f"UsageModelType={usage_model}", blocking=False,
              fail_reason=f"unknown UsageModelType {usage_model!r}"),
        Check("Has ProductUsageResource rows", bool(pur_rows),
              f"count={len(pur_rows)}", fail_reason="no ProductUsageResource"),
        Check("Has Active ProductUsageResource rows", bool(pur_active),
              f"active={len(pur_active)}", fail_reason="no active ProductUsageResource"),
        Check("Has ProductUsageResourcePolicy rows", bool(purp_rows),
              f"count={len(purp_rows)}", fail_reason="no ProductUsageResourcePolicy"),
        Check("Each ProductUsageResource has a policy", not pur_missing_policy,
              f"missing={len(pur_missing_policy)}",
              fail_reason=f"{len(pur_missing_policy)} ProductUsageResource missing policy"),
        Check("Has ProductUsageGrant rows", bool(pug_rows),
              f"count={len(pug_rows)}", fail_reason="no ProductUsageGrant"),
        Check("Has Active ProductUsageGrant rows", bool(pug_active),
              f"active={len(pug_active)}", fail_reason="no active ProductUsageGrant"),
        Check("All grant UsageDefinitionProducts active", not usage_def_inactive,
              f"inactive={len(usage_def_inactive)}",
              fail_reason=f"{len(usage_def_inactive)} grant UsageDefinitionProduct inactive"),
    ]

    if binding_required:
        checks.append(
            Check("Has UsagePrdGrantBindingPolicy", bool(binding_rows),
                  f"count={len(binding_rows)}", fail_reason="missing UsagePrdGrantBindingPolicy")
        )
    else:
        checks.append(
            Check("Binding policy not required (commitment model)", True,
                  f"UsageModelType={usage_model}", blocking=False)
        )

    return ProductReadiness(product=product, checks=checks)
