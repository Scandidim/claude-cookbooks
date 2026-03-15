# SCANDIDIM Operations Kit (Protocol #1)

Цей пакет перетворює протокол у **готову до запуску операційну систему**.

## Вміст

1. `implementation_plan_30_60_90.md` — поетапне впровадження 30/60/90 днів.
2. `aiceo_operating_playbook.md` — як AICEO керує потоком задач і контролем дедлайнів.
3. `daily_weekly_rhythm.md` — ритм командних синків, щоденні/щотижневі ритуали.
4. `ceo_channel_escalation_template.md` — єдиний формат ескалацій у CEO Channel.
5. `roles_raci.md` — матриця відповідальності (CEO, AICEO, Leads, Owners).
6. `risk_register_template.csv` — шаблон реєстру ризиків.
7. `task_queue_template.csv` — шаблон TASK_QUEUE з обов’язковими полями.
8. `ssot_data_dictionary.md` — визначення полів і правила якості даних SSOT.
9. `kpi_dashboard_spec.yaml` — специфікація KPI дашборду дисципліни виконання.
10. `automation_rules.yaml` — правила автоперевірок і нотифікацій.

## Як запускати

1. Погодити `roles_raci.md` і призначити owner для кожного процесу.
2. Імпортувати `task_queue_template.csv` у робочу систему.
3. Запустити risk register з `risk_register_template.csv`.
4. Включити правила з `automation_rules.yaml` (або реалізувати через існуючі інструменти).
5. Раз на тиждень оглядати KPI за `kpi_dashboard_spec.yaml`.

