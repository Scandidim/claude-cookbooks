"""
Nova Poshta Integration
────────────────────────
API wrapper for Nova Poshta (Нова Пошта) — Ukraine's largest courier service.

Docs: https://developers.novaposhta.ua/

Required env vars:
    NOVA_POSHTA_API_KEY  — from cabinet.novaposhta.ua → Settings → Security

All requests use the JSON API endpoint via POST.
"""

from __future__ import annotations

from typing import Any

import httpx

from portal import config

NP_API_URL = "https://api.novaposhta.ua/v2.0/json/"


class NovaPoshtaAPI:
    def __init__(self) -> None:
        self._key = config.NOVA_POSHTA_API_KEY
        if not self._key:
            raise OSError("NOVA_POSHTA_API_KEY must be set")

    def _call(self, model: str, method: str, props: dict | None = None) -> list[dict]:
        payload = {
            "apiKey": self._key,
            "modelName": model,
            "calledMethod": method,
            "methodProperties": props or {},
        }
        resp = httpx.post(NP_API_URL, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            errors = data.get("errors") or data.get("errorCodes") or ["Unknown error"]
            raise RuntimeError(f"Nova Poshta API error: {errors}")
        return data.get("data", [])

    # ── Tracking ───────────────────────────────────────────────────────────────

    def track(self, ttn: str) -> dict:
        """Track a parcel by TTN (tracking number). Returns status dict."""
        result = self._call(
            "TrackingDocument", "getStatusDocuments", {"Documents": [{"DocumentNumber": ttn}]}
        )
        return result[0] if result else {}

    def track_many(self, ttns: list[str]) -> list[dict]:
        """Track multiple parcels at once."""
        docs = [{"DocumentNumber": t} for t in ttns]
        return self._call("TrackingDocument", "getStatusDocuments", {"Documents": docs})

    # ── Addresses ──────────────────────────────────────────────────────────────

    def search_cities(self, name: str, limit: int = 10) -> list[dict]:
        """Search cities/towns by name (Ukrainian or transliterated)."""
        return self._call(
            "Address",
            "searchSettlements",
            {"CityName": name, "Limit": limit},
        )

    def list_warehouses(self, city_ref: str, search: str = "") -> list[dict]:
        """List Nova Poshta warehouses (відділення) in a city."""
        props: dict[str, Any] = {"CityRef": city_ref, "Limit": 50}
        if search:
            props["FindByString"] = search
        return self._call("AddressGeneral", "getWarehouses", props)

    # ── Internet Documents (waybills) ──────────────────────────────────────────

    def create_waybill(
        self,
        sender_ref: str,
        sender_contact_ref: str,
        sender_address_ref: str,
        sender_phone: str,
        recipient_name: str,
        recipient_phone: str,
        recipient_city_ref: str,
        recipient_warehouse_ref: str,
        weight: float,
        seats_amount: int = 1,
        description: str = "Товар",
        cost: float = 100.0,
        payer_type: str = "Recipient",
        payment_method: str = "Cash",
    ) -> dict:
        """
        Create an internet document (waybill / накладна).
        Returns dict with IntDocNumber (TTN), Cost, EstimatedDeliveryDate.

        payer_type: 'Sender' | 'Recipient' | 'ThirdPerson'
        payment_method: 'Cash' | 'NonCash'
        """
        props = {
            "PayerType": payer_type,
            "PaymentMethod": payment_method,
            "DateTime": _today(),
            "CargoType": "Cargo",
            "Weight": weight,
            "ServiceType": "WarehouseWarehouse",
            "SeatsAmount": seats_amount,
            "Description": description,
            "Cost": cost,
            "CitySender": sender_city_ref if (sender_city_ref := "") else "",
            "Sender": sender_ref,
            "SenderAddress": sender_address_ref,
            "ContactSender": sender_contact_ref,
            "SendersPhone": sender_phone,
            "CityRecipient": recipient_city_ref,
            "RecipientAddress": recipient_warehouse_ref,
            "RecipientsPhone": recipient_phone,
            "RecipientName": recipient_name,
        }
        result = self._call("InternetDocument", "save", props)
        return result[0] if result else {}

    def delete_waybill(self, document_ref: str) -> bool:
        """Delete (cancel) an internet document before it's picked up."""
        result = self._call("InternetDocument", "delete", {"DocumentRefs": [document_ref]})
        return bool(result)

    # ── Counterparties (sender profiles) ──────────────────────────────────────

    def list_counterparties(self, counterparty_type: str = "Sender") -> list[dict]:
        """List saved counterparties (usually your sender profiles)."""
        return self._call(
            "Counterparty",
            "getCounterparties",
            {"CounterpartyProperty": counterparty_type, "Page": "1"},
        )

    def list_sender_addresses(self, counterparty_ref: str) -> list[dict]:
        """List addresses for a counterparty."""
        return self._call(
            "CounterpartyGeneral",
            "getCounterpartyAddresses",
            {"Ref": counterparty_ref, "CounterpartyProperty": "Sender"},
        )


def _today() -> str:
    from datetime import datetime

    return datetime.now().strftime("%d.%m.%Y")
