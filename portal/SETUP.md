# Інструкція запуску Portal — що робити далі

## Що вже зроблено (не чіпай)

Репозиторій містить повністю готовий код:

| Що | Де |
|----|----|
| Мульти-агентний портал | `portal/orchestrator.py` |
| Telegram бот | `portal/integrations/telegram_bot.py` |
| WooCommerce + Нова Пошта | `portal/integrations/` |
| Google Workspace | `portal/integrations/google_workspace.py` |
| KOMMO CRM | `portal/integrations/kommo_crm.py` |
| Chrome розширення (RUKI) | `portal/extension/` |
| **S-VAULT Phantom (Firestore)** | `portal/integrations/vault_client.py` |
| Тести | `portal/tests/test_vault_client.py` |

---

## Твої кроки — по порядку

### Крок 1 — Встанови залежності

```bash
cd claude-cookbooks
uv sync --all-extras
```

> Якщо немає `uv`: `pip install uv` або `curl -LsSf https://astral.sh/uv/install.sh | sh`

---

### Крок 2 — Створи `.env` файл

```bash
cp portal/.env.example portal/.env
```

Відкрий `portal/.env` і заповни:

```env
# ОБОВ'ЯЗКОВО
ANTHROPIC_API_KEY=sk-ant-...        ← з console.anthropic.com

# Telegram бот
TELEGRAM_BOT_TOKEN=...              ← від @BotFather в Telegram

# S-VAULT Phantom
FIREBASE_SERVICE_ACCOUNT_FILE=/повний/шлях/до/serviceAccountKey.json
SVAULT_APP_ID=phantom-final-v1
SVAULT_USER_ID=IQY5kuDzgkeNBeG15eyKQEElVjB2

# WooCommerce (якщо є магазин)
WOOCOMMERCE_URL=https://твій-сайт.com
WOOCOMMERCE_CONSUMER_KEY=ck_...
WOOCOMMERCE_CONSUMER_SECRET=cs_...

# Нова Пошта
NOVA_POSHTA_API_KEY=...             ← з cabinet.novaposhta.ua
```

---

### Крок 3 — Завантаж Firebase ключ

1. Зайди: [console.firebase.google.com](https://console.firebase.google.com)
2. Вибери проєкт → **Project Settings** → **Service Accounts**
3. Натисни **"Generate New Private Key"**
4. Збережи файл як `serviceAccountKey.json` — **поруч зі скриптом або в будь-якому безпечному місці**
5. Пропиши повний шлях у `.env` → `FIREBASE_SERVICE_ACCOUNT_FILE=`

> **Важливо:** цей файл — не в папку репозиторію. Він вже в `.gitignore`.

---

### Крок 4 — Запусти бота

```bash
uv run python -m portal.integrations.telegram_bot
```

Або для тесту без Telegram:

```bash
uv run python -c "
from portal.orchestrator import Orchestrator
orch = Orchestrator()
result = orch.handle(source='api', source_id='test', text='Привіт, що ти вмієш?')
print(result)
"
```

---

### Крок 5 — Перевір S-VAULT

```bash
uv run python -c "
from portal.integrations.vault_client import VaultClient
vault = VaultClient()
secret = vault.get_latest_secret()
print(secret)
"
```

Має вивести останній секрет з Firestore. Якщо `None` — колекція порожня.

---

### Крок 6 — Chrome розширення (RUKI)

Якщо потрібна автоматизація браузера:

1. Відкрий Chrome → `chrome://extensions/`
2. Увімкни **"Developer mode"**
3. **"Load unpacked"** → вибери папку `portal/extension/`
4. Запусти WebSocket сервер:
   ```bash
   uv run python -m portal.hands_server
   ```

---

## Запуск тестів

```bash
uv run pytest portal/tests/test_vault_client.py -v
```

Має бути: **21 passed**

---

## Швидка перевірка що все ок

```bash
uv run python -c "
import portal.config as c
print('Anthropic key:', 'OK' if c.ANTHROPIC_API_KEY else 'MISSING')
print('Firebase file:', c.FIREBASE_SERVICE_ACCOUNT_FILE or 'MISSING')
print('App ID:',        c.SVAULT_APP_ID or 'MISSING')
print('User ID:',       c.SVAULT_USER_ID or 'MISSING')
"
```

---

## Якщо щось не працює

| Помилка | Що зробити |
|---------|-----------|
| `Missing required env var: ANTHROPIC_API_KEY` | Заповни `portal/.env` |
| `No module named 'firebase_admin'` | Запускай через `uv run`, не `python` |
| `get_latest_secret()` повертає `None` | Колекція порожня — перевір Firebase Console |
| `serviceAccountKey.json` не знайдено | Перевір шлях у `FIREBASE_SERVICE_ACCOUNT_FILE` |
