# CEO Channel Escalation Template

> Повідомлення без цього формату не вважаються валідною ескалацією.

## Формат

- **Type:** `critical_blocker | approval_required | risk`
- **Issue:** коротко, 1–2 речення
- **Impact:** `money | timeline | client | production`
- **Options:** `A/B/C`
- **Owner recommendation:** конкретний варіант
- **Decision deadline:** дата + час
- **Fallback plan:** що робимо, якщо рішення не прийнято вчасно

## Приклад

- **Type:** risk
- **Issue:** Поставка затримується на 3 дні через зрив постачальника.
- **Impact:** timeline, client
- **Options:** A) термінова заміна постачальника; B) часткова відвантаження; C) перенесення дедлайну.
- **Owner recommendation:** B
- **Decision deadline:** 2026-03-17 14:00
- **Fallback plan:** Автоматичне переключення на A, якщо немає рішення до дедлайну.

