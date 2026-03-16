# EXECUTE: Browser Hands v1 (absolute priority)

1) **Що вже є в SYNCHRO v3 як готові руки**
- У поточному репозиторії немає артефактів `SYNCHRO v3` або browser-extension runtime (немає директорій/файлів із маркерами `synchro`, `extension`, `playwright`, `puppeteer`, `cdp`).
- Тобто готові "руки" у цьому checkout фактично відсутні як code surface для запуску.

2) **Що конкретно зламано / не добито**
- Відсутній сам execution контур для browser actions (немає entrypoint/background/content flow для extension-automation).
- Немає мінімального e2e сценарію, який доводить autonomous click/type/navigate loop.

3) **Один головний blocker**
- **Blocker #1: не той код у workspace** — у наданому репозиторії немає SYNCHRO v3 extension коду, тому добити "руки" тут технічно неможливо без правильного source tree.

4) **3–5 патчів, які треба зробити першими (коли відкриємо правильний SYNCHRO v3 repo)**
- Patch A: підняти `hands_runner` (single threaded action loop: `navigate -> wait -> click/type -> assert`).
- Patch B: стабілізувати selector strategy (пріоритет: `data-testid` -> aria -> css fallback) + retry/backoff.
- Patch C: додати hard timeout/abort + heartbeat, щоб loop не зависав.
- Patch D: додати deterministic action log (`step_id`, selector, result, screenshot ref).
- Patch E: зафіксувати один smoke e2e тест (логін/форма) у CI-local command.

5) **В яких файлах саме (цільові файли у SYNCHRO v3 repo)**
- `extension/src/hands/runner.ts`
- `extension/src/hands/selectors.ts`
- `extension/src/hands/actions.ts`
- `extension/src/background/command_bus.ts`
- `extension/tests/e2e/hands.smoke.spec.ts`

6) **Мінімальний Definition of Done для "руки працюють"**
- З однієї команди система сама:
  1. відкриває заданий URL,
  2. знаходить елемент,
  3. робить click,
  4. вводить текст,
  5. підтверджує очікуваний DOM-state,
  6. пише action log без ручного кліку людини.

7) **Один перший тестовий сценарій**
- `hands_smoke_login_form`:
  - navigate на test page,
  - type email/password,
  - click submit,
  - assert появу `data-testid="dashboard"`.

8) **Exact run flow після патчу**
- `pnpm install`
- `pnpm build:extension`
- `pnpm test:e2e --grep hands_smoke_login_form`
- `pnpm run hands:smoke`

9) **Що не чіпати зараз взагалі**
- Electron/desktop shell.
- Загальну macro-архітектуру orchestration.
- Нові agent-підсистеми, planner-и, memory/redesign.
- Оптимізації, які не впливають на перший автономний browser loop.
