"""
WooCommerce Integration
────────────────────────
WooCommerce REST API v3 wrapper for product and order management.

Docs: https://woocommerce.github.io/woocommerce-rest-api-docs/

Required env vars:
    WOOCOMMERCE_URL              — store root URL (https://yourstore.com)
    WOOCOMMERCE_CONSUMER_KEY     — from WooCommerce → Settings → Advanced → REST API
    WOOCOMMERCE_CONSUMER_SECRET  — same location

Authentication uses HTTP Basic Auth over HTTPS.
"""

from __future__ import annotations

from typing import Any

import httpx

from portal import config

WC_API_VERSION = "wc/v3"


class WooCommerceAPI:
    def __init__(self) -> None:
        base = config.WOOCOMMERCE_URL.rstrip("/")
        self._base = f"{base}/wp-json/{WC_API_VERSION}"
        self._auth = (config.WOOCOMMERCE_CONSUMER_KEY, config.WOOCOMMERCE_CONSUMER_SECRET)
        if not config.WOOCOMMERCE_URL or not config.WOOCOMMERCE_CONSUMER_KEY:
            raise OSError(
                "WOOCOMMERCE_URL, WOOCOMMERCE_CONSUMER_KEY, and WOOCOMMERCE_CONSUMER_SECRET must be set"
            )

    def _get(self, path: str, params: dict | None = None) -> Any:
        resp = httpx.get(f"{self._base}{path}", auth=self._auth, params=params or {}, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: dict) -> Any:
        resp = httpx.post(f"{self._base}{path}", auth=self._auth, json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, payload: dict) -> Any:
        resp = httpx.put(f"{self._base}{path}", auth=self._auth, json=payload, timeout=20)
        resp.raise_for_status()
        return resp.json()

    # ── Products ───────────────────────────────────────────────────────────────

    def list_products(
        self, search: str = "", per_page: int = 20, status: str = "publish"
    ) -> list[dict]:
        """List products, optionally filtered by search query."""
        params: dict[str, Any] = {"per_page": per_page, "status": status}
        if search:
            params["search"] = search
        return self._get("/products", params)

    def get_product(self, product_id: int) -> dict:
        """Get a single product by ID."""
        return self._get(f"/products/{product_id}")

    def create_product(
        self,
        name: str,
        regular_price: str,
        description: str = "",
        short_description: str = "",
        sku: str = "",
        stock_quantity: int | None = None,
        categories: list[str] | None = None,
        status: str = "publish",
    ) -> dict:
        """Create a new product. Returns the created product dict."""
        payload: dict[str, Any] = {
            "name": name,
            "regular_price": regular_price,
            "description": description,
            "short_description": short_description,
            "status": status,
        }
        if sku:
            payload["sku"] = sku
        if stock_quantity is not None:
            payload["manage_stock"] = True
            payload["stock_quantity"] = stock_quantity
        if categories:
            payload["categories"] = [{"name": c} for c in categories]
        return self._post("/products", payload)

    def update_product(self, product_id: int, **fields: Any) -> dict:
        """Update product fields (price, stock, description, etc.)."""
        return self._put(f"/products/{product_id}", fields)

    def update_stock(self, product_id: int, quantity: int) -> dict:
        """Set stock quantity for a product."""
        return self._put(
            f"/products/{product_id}",
            {"manage_stock": True, "stock_quantity": quantity},
        )

    # ── Orders ─────────────────────────────────────────────────────────────────

    def list_orders(
        self,
        status: str = "any",
        per_page: int = 20,
        search: str = "",
    ) -> list[dict]:
        """List orders, optionally filtered by status or search."""
        params: dict[str, Any] = {"per_page": per_page, "status": status}
        if search:
            params["search"] = search
        return self._get("/orders", params)

    def get_order(self, order_id: int) -> dict:
        """Get a single order by ID."""
        return self._get(f"/orders/{order_id}")

    def update_order_status(self, order_id: int, status: str) -> dict:
        """Update order status (pending, processing, on-hold, completed, cancelled, refunded)."""
        return self._put(f"/orders/{order_id}", {"status": status})

    def create_order(
        self,
        billing: dict,
        line_items: list[dict],
        payment_method: str = "bacs",
        payment_method_title: str = "Bank Transfer",
        status: str = "pending",
    ) -> dict:
        """
        Create an order manually.

        billing example:
            {"first_name": "Ivan", "last_name": "Petrenko",
             "email": "ivan@example.com", "phone": "+380991234567"}
        line_items example:
            [{"product_id": 42, "quantity": 2}]
        """
        payload = {
            "payment_method": payment_method,
            "payment_method_title": payment_method_title,
            "status": status,
            "billing": billing,
            "line_items": line_items,
        }
        return self._post("/orders", payload)

    # ── Customers ──────────────────────────────────────────────────────────────

    def search_customers(self, search: str, per_page: int = 10) -> list[dict]:
        """Search customers by name or email."""
        return self._get("/customers", {"search": search, "per_page": per_page})

    # ── Report helpers ─────────────────────────────────────────────────────────

    def sales_summary(self, period: str = "week") -> dict:
        """
        Return a basic sales summary.
        period: 'day', 'week', 'month', 'year', 'last_month', 'last_year'
        """
        return self._get("/reports/sales", {"period": period})

    def top_sellers(self, period: str = "week", per_page: int = 5) -> list[dict]:
        """Return top-selling products."""
        return self._get("/reports/top_sellers", {"period": period, "per_page": per_page})
