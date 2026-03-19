"""
Store Agent
───────────
Handles online store operations via WooCommerce REST API and Nova Poshta.

Supported actions:
  • product_search   — find products by name/SKU
  • product_create   — add a new product
  • product_update   — update price, stock, description
  • order_list       — list recent or filtered orders
  • order_status     — check/update a specific order status
  • order_create     — create an order manually
  • stock_update     — update inventory quantity
  • tracking         — track Nova Poshta parcel by TTN
  • sales_report     — quick sales summary (day / week / month)

Uses Claude Haiku for intent parsing (cheap, fast classification step).
"""

from __future__ import annotations

import json
import re

import anthropic

from portal import config
from portal.storage import log, save_artifact

SYSTEM_PROMPT = """You are the Store Agent — an assistant for managing an online WooCommerce store.

Parse the user's request and return a JSON action.

Supported actions:
- product_search   → find products
- product_create   → create a new product
- product_update   → update product fields
- order_list       → list orders (with optional status filter)
- order_status     → get or update a specific order
- order_create     → manually create an order
- stock_update     → update product stock quantity
- tracking         → track a Nova Poshta parcel
- sales_report     → sales summary report

Respond ONLY with valid JSON:
{
  "action": "<action_name>",
  "data": {
    "query": "...",          // for search
    "product_id": 0,         // for product/stock actions
    "order_id": 0,           // for order actions
    "name": "...",           // product name
    "price": "...",          // regular_price as string
    "description": "...",
    "sku": "...",
    "stock_quantity": 0,
    "categories": [],        // list of category names
    "status": "...",         // order status or product status
    "ttn": "...",            // Nova Poshta tracking number
    "period": "week",        // for reports: day/week/month/year
    "billing": {},           // for order_create
    "line_items": []         // for order_create
  }
}"""


class StoreAgent:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self._woo = None
        self._np = None

    def _get_woo(self):
        if self._woo is None:
            from portal.integrations.woocommerce import WooCommerceAPI

            self._woo = WooCommerceAPI()
        return self._woo

    def _get_np(self):
        if self._np is None:
            from portal.integrations.nova_poshta import NovaPoshtaAPI

            self._np = NovaPoshtaAPI()
        return self._np

    def run(self, task_id: str, intent: str, user_input: str, extracted: dict) -> str:
        """Parse store request and execute the corresponding action. Returns result text."""
        log(task_id, "store_agent", f"Store task: {intent}")

        if not config.WOOCOMMERCE_URL or not config.WOOCOMMERCE_CONSUMER_KEY:
            return (
                "[Store] WooCommerce not configured.\n"
                "Set WOOCOMMERCE_URL, WOOCOMMERCE_CONSUMER_KEY, "
                "WOOCOMMERCE_CONSUMER_SECRET in .env"
            )

        # Parse action from user input
        response = self._client.messages.create(
            model=config.MODEL_STORE_AGENT,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_input}],
            temperature=0.0,
        )
        raw = response.content[0].text.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            log(task_id, "store_agent", f"Bad JSON from model: {raw}", "warning")
            return "Could not parse store action from request."

        spec = json.loads(match.group())
        action = spec.get("action", "product_search")
        data = spec.get("data", {})
        log(task_id, "store_agent", f"Action: {action} | Data: {json.dumps(data)[:200]}")

        result = self._execute(task_id, action, data)

        save_artifact(
            task_id=task_id,
            artifact_type="store_action",
            title=f"Store: {action}",
            content=result,
            metadata={"action": action, "data": data},
        )
        return result

    # ── Execution ──────────────────────────────────────────────────────────────

    def _execute(self, task_id: str, action: str, data: dict) -> str:  # noqa: C901
        woo = self._get_woo()

        if action == "product_search":
            products = woo.list_products(search=data.get("query", ""), per_page=10)
            if not products:
                return "No products found."
            lines = []
            for p in products:
                stock = p.get("stock_quantity", "–")
                lines.append(
                    f"• [{p['id']}] {p['name']} — {p.get('price', '?')} UAH | stock: {stock}"
                )
            return "Products:\n" + "\n".join(lines)

        elif action == "product_create":
            p = woo.create_product(
                name=data.get("name", "New Product"),
                regular_price=str(data.get("price", "0")),
                description=data.get("description", ""),
                short_description=data.get("short_description", ""),
                sku=data.get("sku", ""),
                stock_quantity=data.get("stock_quantity"),
                categories=data.get("categories"),
            )
            url = p.get("permalink", "")
            return f"Product created: [{p['id']}] {p['name']}\n{url}"

        elif action == "product_update":
            pid = int(data.get("product_id", 0))
            if not pid:
                return "product_id required for update."
            fields = {k: v for k, v in data.items() if k not in ("product_id", "action") and v}
            if "price" in fields:
                fields["regular_price"] = str(fields.pop("price"))
            p = woo.update_product(pid, **fields)
            return f"Product [{p['id']}] {p['name']} updated."

        elif action == "stock_update":
            pid = int(data.get("product_id", 0))
            qty = int(data.get("stock_quantity", 0))
            if not pid:
                return "product_id required."
            p = woo.update_stock(pid, qty)
            return f"Stock updated: [{p['id']}] {p['name']} → {p.get('stock_quantity')} units"

        elif action == "order_list":
            status = data.get("status", "any")
            orders = woo.list_orders(status=status, per_page=10)
            if not orders:
                return f"No orders found (status={status})."
            lines = []
            for o in orders:
                lines.append(
                    f"• #{o['id']} {o['billing'].get('first_name', '')} "
                    f"{o['billing'].get('last_name', '')} — "
                    f"{o.get('total', '?')} UAH | {o['status']}"
                )
            return f"Orders (status={status}):\n" + "\n".join(lines)

        elif action == "order_status":
            oid = int(data.get("order_id", 0))
            if not oid:
                return "order_id required."
            new_status = data.get("status", "")
            if new_status:
                o = woo.update_order_status(oid, new_status)
                return f"Order #{oid} status updated to: {o['status']}"
            else:
                o = woo.get_order(oid)
                billing = o.get("billing", {})
                return (
                    f"Order #{o['id']}\n"
                    f"Customer: {billing.get('first_name', '')} {billing.get('last_name', '')}\n"
                    f"Email: {billing.get('email', '')}\n"
                    f"Phone: {billing.get('phone', '')}\n"
                    f"Status: {o['status']}\n"
                    f"Total: {o.get('total', '?')} UAH\n"
                    f"Date: {o.get('date_created', '')}"
                )

        elif action == "order_create":
            o = woo.create_order(
                billing=data.get("billing", {}),
                line_items=data.get("line_items", []),
                status=data.get("status", "pending"),
            )
            return (
                f"Order created: #{o['id']}\n"
                f"Status: {o['status']}\n"
                f"Total: {o.get('total', '?')} UAH"
            )

        elif action == "tracking":
            ttn = data.get("ttn", "").strip()
            if not ttn:
                return "TTN (tracking number) required."
            try:
                np = self._get_np()
                info = np.track(ttn)
            except OSError:
                return "[Nova Poshta] NOVA_POSHTA_API_KEY not configured."
            except Exception as e:
                return f"Tracking error: {e}"
            if not info:
                return f"No tracking info for TTN: {ttn}"
            return (
                f"TTN: {ttn}\n"
                f"Status: {info.get('StatusDescription', info.get('Status', '?'))}\n"
                f"Warehouse: {info.get('WarehouseRecipient', '–')}\n"
                f"Recipient city: {info.get('CityRecipient', '–')}\n"
                f"Scheduled delivery: {info.get('ScheduledDeliveryDate', '–')}"
            )

        elif action == "sales_report":
            period = data.get("period", "week")
            summary = woo.sales_summary(period=period)
            sellers = woo.top_sellers(period=period)
            top = "\n".join(
                f"  {i + 1}. [{s.get('product_id')}] {s.get('name')} — qty {s.get('quantity')}"
                for i, s in enumerate(sellers)
            )
            return (
                f"Sales report ({period}):\n"
                f"Orders: {summary.get('total_orders', '?')}\n"
                f"Revenue: {summary.get('gross_sales', '?')} UAH\n"
                f"Net sales: {summary.get('net_sales', '?')} UAH\n"
                f"Avg order: {summary.get('average_sales', '?')} UAH\n"
                f"\nTop sellers:\n{top or '  (no data)'}"
            )

        else:
            return f"Unknown store action: {action}"
