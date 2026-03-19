# AI Portal — Agent Context

## System Overview
Multi-agent portal that routes user requests to specialist AI agents.

## Agent Roles

| Agent | Model | Purpose |
|-------|-------|---------|
| Orchestrator | — | Routes tasks, coordinates agents, manages lifecycle |
| Registrar | claude-haiku-4-5 | Classifies intent, extracts data, chooses agent |
| Executor | claude-sonnet-4-6 | Produces documents, reports, ad copy, code |
| Market Bot | claude-haiku-4-5 + Gemini | Market analysis, ad copy, competitor research |
| CRM Connector | claude-haiku-4-5 | KOMMO CRM: create/update leads and contacts |

## Data Flow
```
User (Telegram / API)
  → Orchestrator.handle()
  → RegistrarAgent.classify()     # intent + routing
  → [SpecialistAgent].run()       # produce artifact
  → [Integration].push()          # Google / Tilda / KOMMO (optional)
  → Reply to user
```

## Storage
- SQLite at `portal/storage/portal.db`
- Tables: tasks, sessions, artifacts, logs
- All tasks are persisted; agents read/write via `portal.storage`

## Integration Status
- Telegram: fully integrated (python-telegram-bot)
- KOMMO CRM: REST API wrapper ready
- Google Workspace: service account auth, Docs + Sheets + Drive
- Tilda: read/publish API; full page creation requires Zero Block API

## Environment Variables
See `.env.example` in this directory.

## Running
```bash
# Telegram bot
python -m portal.integrations.telegram_bot

# Programmatic use
from portal.orchestrator import Orchestrator
orch = Orchestrator()
result = orch.handle(source="api", source_id="test", text="Write an ad for yoga studio")
```
