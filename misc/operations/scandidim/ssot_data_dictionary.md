# SSOT Data Dictionary

## TASK_QUEUE

- `task_id` (string, required): унікальний ідентифікатор.
- `title` (string, required): коротка назва задачі.
- `context` (string, required): бізнес-контекст.
- `owner` (string, required): відповідальний виконавець.
- `team_lead` (string, required): відповідальний за потік задач.
- `priority` (enum: P0/P1/P2, required).
- `status` (enum, required): див. status model.
- `deadline` (datetime, required).
- `definition_of_done` (string, required).
- `artifact_link` (url/string, required before DONE).
- `dependencies` (string/list, optional).
- `risks` (string/list, optional).
- `created_at`, `updated_at` (datetime, required).

## Якість даних

- Унікальність: `task_id`.
- Повнота: обов'язкові поля не порожні.
- Актуальність: `updated_at` відповідає останній зміні статусу.
- Консистентність: `DONE` неможливий без `artifact_link`.

