"""usage-product-readiness — readiness checks for Revenue Cloud usage products.

A small, dependency-free CLI that interrogates a live org (via the `sf` CLI) and
reports whether a usage product is fully wired for the **Manage Usage Resources**
guided flow: ProductUsageResource → ProductUsageResourcePolicy → ProductUsageGrant
(→ UsagePrdGrantBindingPolicy for Anchor/Pack), plus optional quote-line checks.
"""

__version__ = "0.1.0"
