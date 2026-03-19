"""
Portal configuration — reads from environment variables / .env file.
Copy .env.example to .env and fill in your keys.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from portal directory, fall back to repo root
_env_file = Path(__file__).parent / ".env"
if not _env_file.exists():
    _env_file = Path(__file__).parent.parent / ".env"
load_dotenv(_env_file)


def _require(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        raise OSError(f"Missing required env var: {key}")
    return val


def _optional(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# ── Core AI ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = _require("ANTHROPIC_API_KEY")
GEMINI_API_KEY: str = _optional("GEMINI_API_KEY")

# Claude model aliases (never use dated IDs per CLAUDE.md)
MODEL_ORCHESTRATOR = "claude-opus-4-6"  # smartest decisions
MODEL_EXECUTOR = "claude-sonnet-4-6"  # artifact generation
MODEL_REGISTRAR = "claude-haiku-4-5"  # cheap classification
MODEL_MARKET_BOT = "claude-haiku-4-5"  # high-volume market tasks

# ── Telegram ────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = _optional("TELEGRAM_BOT_TOKEN")

# ── Google Workspace ───────────────────────────────────────────────────────────
GOOGLE_SERVICE_ACCOUNT_FILE: str = _optional("GOOGLE_SERVICE_ACCOUNT_FILE")
GOOGLE_DELEGATED_USER: str = _optional("GOOGLE_DELEGATED_USER")

# ── KOMMO CRM ──────────────────────────────────────────────────────────────────
KOMMO_BASE_URL: str = _optional("KOMMO_BASE_URL")  # e.g. https://yourcompany.kommo.com
KOMMO_ACCESS_TOKEN: str = _optional("KOMMO_ACCESS_TOKEN")

# ── Tilda ──────────────────────────────────────────────────────────────────────
TILDA_PUBLIC_KEY: str = _optional("TILDA_PUBLIC_KEY")
TILDA_SECRET_KEY: str = _optional("TILDA_SECRET_KEY")

# ── WooCommerce Store ──────────────────────────────────────────────────────────
WOOCOMMERCE_URL: str = _optional("WOOCOMMERCE_URL")
WOOCOMMERCE_CONSUMER_KEY: str = _optional("WOOCOMMERCE_CONSUMER_KEY")
WOOCOMMERCE_CONSUMER_SECRET: str = _optional("WOOCOMMERCE_CONSUMER_SECRET")

# ── Nova Poshta ────────────────────────────────────────────────────────────────
NOVA_POSHTA_API_KEY: str = _optional("NOVA_POSHTA_API_KEY")

# Claude model alias for store agent
MODEL_STORE_AGENT = "claude-haiku-4-5"  # fast responses for store queries

# ── S-VAULT Phantom (Firebase / Firestore) ─────────────────────────────────────
FIREBASE_SERVICE_ACCOUNT_FILE: str = _optional("FIREBASE_SERVICE_ACCOUNT_FILE")
SVAULT_APP_ID: str = _optional("SVAULT_APP_ID", "phantom-final-v1")
SVAULT_USER_ID: str = _optional("SVAULT_USER_ID")

# ── Portal settings ────────────────────────────────────────────────────────────
PORTAL_NAME: str = _optional("PORTAL_NAME", "AI Portal")
MAX_TASK_HISTORY: int = int(_optional("MAX_TASK_HISTORY", "20"))
