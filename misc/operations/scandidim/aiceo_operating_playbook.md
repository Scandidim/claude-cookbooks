# AICEO Operating Playbook

## Роль AICEO
AICEO — не чат-асистент, а **операційний контур управління виконанням**.

## Основні функції

1. Intake:
   - конвертує запити у валідні задачі TASK_QUEUE;
   - валідує обов’язкові поля.
2. Clarification:
   - збирає відсутні залежності, критерії приймання і артефакти.
3. Deadline Control:
   - щоденно контролює SLA статусів і дедлайни.
4. Artifact Control:
   - перевіряє наявність результату перед переходом у DONE.
5. Escalation Structuring:
   - формує ескалації в CEO лише у валідному форматі.

## Операційні тригери

- `status_not_updated > 15m` → ping owner.
- `task_blocked > 24h` → lead + AICEO review.
- `deadline_at_risk` → пріоритезована ескалація.
- `done_without_artifact` → rollback у REVIEW.

## Definition of Done контроль

DoD вважається валідним, якщо містить:
- що саме deliverable;
- де він збережений;
- хто підтвердив приймання;
- як перевіряється якість.

