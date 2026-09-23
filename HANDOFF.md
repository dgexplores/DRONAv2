# HANDOFF — SRMS Drona (DRONAv2)

**Purpose:** durable state so that no remaining work depends on an agent's conversation
context. If you are a teammate or a fresh session, read this file plus `ENGINEERING.md`
and you are current.

**Last updated:** 2026-09-23 (session 6 — backlog drain: fast boot, triple keep-alive, stable Gemini pin, scheduler on, venv 3.12, media purge; email delivery still blocked on SMTP creds)

---

## 1. Where things stand

| Item | State |
|---|---|
| Working tree | clean (`git status --porcelain` empty) |
| Branch | `main`, in sync with `origin/main` (0 behind / 0 ahead) |
| HEAD | `f8d12c0` — *chore: prefer stable Gemini models…* (plus this HANDOFF update) |
| CI | green — run `35889396418`, success (on Python 3.12, suite = 120 tests) |
| Test suite | 120 tests, all passing; ship gate green **on local venv Python 3.12.13** (aligned) |
| Deployed | **live on Render** — service **`DRONAv2`** (`srv-dajkh37qj5pc73e038i0`), deploy `dep-dapvtv4s728c73fh3g40` (2026-09-23, commit `f8d12c0`) |
| Health | `https://dronav2.onrender.com/health/` → `200 ok`; `/` → `302`; HTTP → HTTPS `301` |
| Keep-alive | 3 layers: GH Actions `/health/` ping every 5m · local crontab every 6m (`scripts/keep_awake.sh`) · landing-page beacon. Fast boot via `manage.py boot` (69s → 44s cold). |

The 9 defect classes found in the audit are fixed, committed, pushed, and CI-verified.
The 3 findings from the security review (2026-09-23: Clerk fail-closed binding,
`frame-ancestors 'none'`, `list_users` email masking) are fixed the same way — commits
`e5226a2` + `b4e019d`, covered by 3 new regression tests. Nothing is half-finished.
The items below are *follow-ups*, not incomplete work.

---

## 1a. Production verification (2026-09-14, session 2)

The security fixes were verified **against the running service**, not just in tests. All
read-only probes:

| Probe | Result | Verdict |
|---|---|---|
| `GET /media/certificates/<file>.pdf` (anonymous) | `302` → `/login/?next=...` | ✅ never `200` |
| `GET /media/sop_documents/sop.pdf` (anonymous) | `302` → `/login/` | ✅ never `200` |
| `GET /media/../srms_drona/settings.py` | `404` | ✅ traversal rejected |
| `GET /media/....//srms_drona/settings.py` | `302` → login (404 once authed) | ✅ no leak |
| `GET /` `/certificates/` `/analytics/` `/manage/` | `302` → `/login/` | ✅ auth enforced |
| `GET /verify/<bogus>/` | `200`, renders "Certificate Not Found" | ✅ no data leak |
| `GET /verify/<img src=x onerror=...>` | reflected **HTML-escaped** | ✅ no XSS |
| `Host: evil.com` | `403` | ✅ `ALLOWED_HOSTS` not `*` |
| HTTP → HTTPS | `301` | ✅ `SECURE_SSL_REDIRECT` |
| Security headers | CSP+nonce, HSTS `preload`, `Secure` cookie, `nosniff`, `DENY` | ✅ all present |
| `/health/` | `200 ok` | ✅ |

Boot sequence on the live service confirms all four start steps run:
`migrate` → `createcachetable` → `set_admin_password` (`ADMIN001 password rotated.`) → `gunicorn`.

> Minor, non-security nit: `/verify/<bogus>/` returns `200` rather than `404`. Defensible for a
> "query result" page; left alone deliberately.

---

## 2. ⚠️ CRITICAL: `render.yaml` is NOT authoritative

**This is the most important thing in this document.**

`render.yaml` in this repo **does not control the live service**. The `dronav2` service was
created **manually** in the Render dashboard, not via Blueprint. It has **no blueprint
linkage** (verified: zero `blueprint` keys in the service JSON).

Consequence: **editing `render.yaml` changes nothing in production.** The 2026-09-14 fix to
`startCommand` sat inert in the repo while production kept running the old command. This was
only caught by reading the live boot logs, which still showed the old form:

```
==> Running 'python manage.py migrate --noinput && (python manage.py createcachetable rate_limit_cache || true); gunicorn ...'
```

— note the `&&`, the `|| true`, no `set -e`, and no `set_admin_password`.

**Resolved for now** by setting the start command directly on the service
(`render services update srv-dajkh37qj5pc73e038i0 --start-command ...`, 2026-09-14 13:56Z).
Verified live in the boot logs:

```
13:58:26  No migrations to apply.              <- migrate
13:58:34  Cache table 'rate_limit_cache' already exists.   <- createcachetable
13:58:50  ADMIN001 password rotated.           <- set_admin_password  (NEVER ran before)
13:58:57  [INFO] Starting gunicorn 26.0.0      <- gunicorn
```

### The permanent fix: make `render.yaml` authoritative

There are two ways. **Option A works today and needs no dashboard.**

#### Option A — apply `render.yaml` via the CLI (available now)

`scripts/apply_render_config.py` reads `render.yaml` and pushes it onto the live service with
`render services update`. After this, **`render.yaml` is the source of truth**: edit it, run the
script, done.

```bash
python scripts/apply_render_config.py              # dry run -- shows the exact command
python scripts/apply_render_config.py --apply      # update the service
python scripts/apply_render_config.py --apply --deploy   # and trigger a deploy
```

It verifies against the running service afterwards (never trusts the file), and **reports anything
it cannot apply rather than skipping it silently**:

| Field | Why it can't be applied |
|---|---|
| `runtime` | The CLI refuses outright: *"cannot switch runtimes via the CLI"* |
| `region` | Immutable after creation |
| `numInstances` | No CLI flag exists |
| `envVars` | `services update` has no env-var flag; secrets live in the dashboard |
| `autoDeployTrigger: off` | Only `--auto-deploy` (enable) exists; disable in the dashboard |

Note a config change never auto-deploys — use `--deploy` or run `render deploys create`.

#### Option B — adopt a Blueprint (the "proper" IaC route)

`render.yaml` has been **rebuilt to mirror the live service field-by-field**, so adopting it is a
no-op. This is a dashboard step — the CLI cannot create a Blueprint.

**Pre-flight (already passing).** `render blueprints validate` reveals whether a Blueprint would
*adopt* the existing service or *create a duplicate*: the `plan.services` list names services that
would be **created**, so an **absent/empty list means adoption**.

```bash
render blueprints validate render.yaml
# -> {"plan": {"totalActions": 1}, "valid": true}     # no "services" key = ADOPTS. Good.
```

> ⚠️ **The name must be the display name `DRONAv2`, not the slug `dronav2`.** Matching is
> case-sensitive and uses the service's *name*. Verified empirically against all five services in
> the account: every existing name adopts; `dronav2` (lowercase) and any invented name are listed
> under `services`, i.e. they would **create a second, duplicate service**.

**Migration steps:**
1. Dashboard → **New > Blueprint** → connect `dgexplores/DRONAv2`, branch `main`.
2. Read the change preview. It must show the **existing** `DRONAv2` service being updated.
3. Set the Blueprint's **Auto Sync to No** before the first sync.
4. Deploy, then verify against the running service (never against the file):
   `render services -o json` and `render logs -r srv-dajkh37qj5pc73e038i0 --limit 200 -o text`.

**Before step 1 — close the env-var unknown.** `render.yaml` cannot be checked against the live
env vars from the CLI (secrets are write-only). `scripts/verify_render_env.py` does it over the
API and prints **names only, never values**:

```bash
export RENDER_API_KEY=rnd_...    # Dashboard > Account Settings > API Keys
python scripts/verify_render_env.py
# exit 0 = exact match; 1 = mismatch (see report); 2 = could not run
```

This matters because Render's docs warn that any option omitted from the Blueprint gets a
default that "almost definitely differs". An undeclared env var is *preserved* on adoption, so it
is not dangerous — but the file would then be incomplete.

**Known limitation:** creating a Blueprint is **not** possible via the API or CLI. The public API
exposes only `GET /blueprints`, `POST /blueprints/validate`, `GET|PATCH|DELETE
/blueprints/{id}` and `GET /blueprints/{id}/syncs` — there is no create endpoint (verified
against Render's OpenAPI spec, 131 paths). Creation is dashboard-only by design.

**Why the risk is low** (from Render's own docs, checked 2026-09-14):
- `name` matching an existing service **applies config to that service** — it does not recreate it.
- **Syncing a Blueprint never deletes an existing resource**, even if you remove it from the file
  or disconnect the Blueprint.
- `generateValue: true` generates a value **only if none exists**, so the live `DJANGO_SECRET_KEY`
  is **not** rotated (this was my first worry — the docs disproved it).
- `sync: false` env vars are **ignored on update**, so no secret can be overwritten by a sync.
- Omitted env vars are **preserved**; omitted `plan` / `numInstances` / `previews` **retain** the
  current values or default to a matching state.

**Rollback:** set Auto Sync to No (or disconnect the Blueprint). The service and its URL survive.
Re-apply any setting you want changed via the dashboard or `render services update`. Nothing is
destroyed by this process.

> Side finding: `set_admin_password` printed "ADMIN001 password rotated.", which proves
> `DJANGO_ADMIN_PASSWORD` **is** set on Render. That rotation had never once executed before.

---

## 3. Outstanding items

### ✅ RESOLVED — Gemini model names verified
Previously the top unknown. All four entries in `DEFAULT_GEMINI_MODELS`
(`apps/quizzes/gemini_services.py`) were checked against Google's live model list on
2026-09-14:

| Model in code | Status |
|---|---|
| `gemini-3.5-flash` | Stable |
| `gemini-3.1-flash-lite` | Stable |
| `gemini-3-flash-preview` | Preview |
| `gemini-2.5-flash` | Exists (2.5 family) |

**No fix required.** The app is *not* silently serving fallback questions.

> Optional hardening (low priority, not a defect): `gemini-3-flash-preview` sits third in
> the preference order. Preview models can be retired with short notice — indeed
> `gemini-3.1-flash-lite-preview` and `gemini-3-pro-preview` are already shut down. Newer
> **stable** models exist (`gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.8-flash`).
> Consider reordering so stable models always precede preview ones, or pin a specific model
> with the `GEMINI_MODEL` env var. Changing this is a one-line edit; it was deliberately
> **not** made, to avoid unrequested churn in a green build.

**One live check still worth doing** (cheap, definitive): generate a quiz on the deployed app
and check the logs. As of `ac34e32` the app now logs which path it took, so this is
self-answering:

```bash
render logs -r srv-dajkh37qj5pc73e038i0 --limit 500 -o text | grep -iE "GEMINI_API_KEY|fell back"
```

- `GEMINI_API_KEY is not set; quiz N will use the rule-based fallback.` → key missing on Render
- `Quiz N fell back to rule-based questions (...)` → key present but the API call failed
- neither line, with questions generated → the key is set and Gemini worked

> This logging was **added in session 2** (`ac34e32`). Previously an unset key degraded every
> quiz with **no log line at all**, which is why the key's status could not be determined from
> outside.

**✅ ANSWERED (2026-09-16): `GEMINI_API_KEY` IS set.** Read from the Render API (names only,
values never printed) — see §3a for the method. AI quiz generation is live; it is not serving
fallback questions.

---

## 3a. 🚨 FINDING — email delivery is still disabled (scheduler since enabled)

Reading the live env vars (method below) revealed that several variables the app expects are
simply **absent**. Nothing reports this, because each one has a harmless-looking default.

| Variable | Status | Consequence |
|---|---|---|
| `DJANGO_EMAIL_BACKEND` | **absent** → `console.EmailBackend` | **No email is ever delivered.** Password-reset and staff setup links are printed to stdout (Render logs) instead of sent. `send_mail()` still returns `1`, so the UI reports success. |
| `SMTP_USER` / `SMTP_PASSWORD` | **absent** | Same as above — no SMTP credentials configured. |
| `SRMS_RUN_SCHEDULER` | **present = `1`** (set 2026-09-23) | **APScheduler starts.** Reminders generate and are sent through the console backend, i.e. they land in Render logs until SMTP delivery is configured below. |
| `GEMINI_MODEL` | **present = `gemini-3.5-flash`** (set 2026-09-23) | Quiz generation pinned to a stable model; the fallback pool also reorders stable-before-preview (`f8d12c0`). |
| `CLERK_PUBLISHABLE_KEY` / `CLERK_SECRET_KEY` / `CLERK_AUTHORIZED_PARTIES` | **present** (set via Render API 2026-09-23) — Clerk SSO is **ON**; `/login/` renders `clerk.browser.js` on the live site. Binding is the JWT `azp` claim via `CLERK_AUTHORIZED_PARTIES`; `CLERK_JWT_AUDIENCE` is unset (optional alternative, deliberately not used — plain session tokens carry no `aud`). |

Present and correct: `DATABASE_URL`, `DJANGO_ADMIN_PASSWORD`, `DJANGO_ALLOWED_HOSTS`,
`DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`,
`DJANGO_SECURE_SSL_REDIRECT`, `GEMINI_API_KEY`, `SRMS_BASE_URL` — plus, since 2026-09-23,
the three `CLERK_*` vars, `GEMINI_MODEL`, and `SRMS_RUN_SCHEDULER=1` (table above).
Still absent (the remaining gap): `DJANGO_EMAIL_BACKEND`, `SMTP_*`, `SMTP_USER`,
`SMTP_PASSWORD`.

**Why this matters:** staff onboarding depends on emailed setup links. If email is not
delivered, **new users can never set a password** and the only way in is an admin manually
resetting it. This is the same silent-degradation class as the old `GEMINI_API_KEY` defect
(`ENGINEERING.md` trap 4.12).

**To fix (needs a decision + credentials — not doable from the repo alone):**
1. Choose an SMTP provider and set `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_HOST`, `SMTP_PORT`,
   `SMTP_USE_TLS` on the Render service.
2. Set `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` — **without this the
   console backend stays active even once credentials exist.** This is the step that is easy
   to miss.
3. Set `SRMS_RUN_SCHEDULER=1` if reminders should run.
4. Prove it: `python manage.py send_test_email <address>` (the command already exists), then
   confirm delivery rather than trusting the exit code.

---

### 3b. How the live env vars were read (names only)

The CLI has no read command, but the REST API does — and the CLI's own token works for it:

```bash
# strip the trailing slash or you get a bare "404 page not found"
KEY=$(python3 -c "import yaml,pathlib;print(yaml.safe_load((pathlib.Path.home()/'.render'/'cli.yaml').read_text())['api']['key'])")
curl -s -H "Authorization: Bearer $KEY" \
  "https://api.render.com/v1/services/srv-dajkh37qj5pc73e038i0/env-vars?limit=100"
```

⚠️ **The response contains secret values in plaintext.** Never pipe this to a file, a log, or a
commit. Prefer `scripts/verify_render_env.py`, which prints names only.

> This corrects `ENGINEERING.md` trap 4.11, which said secrets are write-only. That is true of
> the CLI commands, **not** of the API. `~/.render/cli.yaml` (mode 600) is therefore as
> sensitive as the secrets themselves.

---

### 4. ✅ DONE — stray local media artifacts
Deleted 2026-09-23 (37 leftover test PDFs). `media/` now holds **0 files**. The directory stays
gitignored for runtime uploads.

### 5. ✅ DONE — Python version drift
Resolved 2026-09-23: local venv rebuilt on **Python 3.12.13** (via `uv python install 3.12`),
matching `runtime.txt` and CI. Full ship gate re-run green on 3.12 (120 tests).

### 6. ✅ DONE — Render redeploy (with a catch)
Applied and verified on 2026-09-14. Production now runs the `set -e` start command and
`set_admin_password` executes. **See §2** — the redeploy alone would *not* have applied the
fix, because `render.yaml` is not wired to the service. The start command was set via the CLI.

### 7. ✅ DONE — GitHub Actions Node.js deprecation
Bumped `actions/checkout` v4 → **v7** and `actions/setup-python` v5 → **v7** (current majors,
verified against upstream tags). CI run `34854209674` passed with **zero annotations** — the
Node 20 deprecation warning is gone. The Railway workflow's stale "Render deploys via Blueprint"
comment was corrected at the same time.

---

## 3. What was actually fixed (context for the follow-ups)

Nine defect classes, verified — not just claimed:

1. **Certificate forgery** — video completion is now *derived* server-side from
   `LessonProgress.watched_seconds` (90% of duration). The client `completed` flag is
   ignored for video lessons.
2. **`/media/` leak** — `srms_drona.views.protected_media` authorises per file
   (certificate = owner or manager; SOP = enrolled), replacing a blanket `login_required`.
3. **Timing oracle** — login now goes through `authenticate()`.
4. **Password display** — provisioning no longer renders passwords into Django messages.
5. **Unusable accounts** — imported staff now receive a setup link
   (`apps/users/services.py`).
6. **`render.yaml` shell bug** — `A && B || true; C` swallowed failed migrations; now
   `set -e`.
7. **`set_admin_password` never invoked** on Render — now in the start command.
8. **Silent AI degradation** — `GenerationReport` surfaces fallback; pool 5 → 10.
9. **Public verify page** — masks surname, hides Employee ID and department.

Plus: production settings guards (refuses to boot with default `SECRET_KEY` or
`ALLOWED_HOSTS=['*']`), quiz enrollment gate, test isolation, dead-import removal.

---

## 5. How to verify the current state yourself

```bash
cd /Users/dgsmacbook/DRONAv2

# tree clean and in sync?
git status --porcelain
git rev-list --left-right --count origin/main...HEAD   # expect: 0   0

# CI green?
gh run list --limit 3

# full ship gate (expect all green, twice)
./venv/bin/python manage.py check --settings=srms_drona.test_settings
./venv/bin/python manage.py makemigrations --check --dry-run --settings=srms_drona.test_settings
./venv/bin/python manage.py test --settings=srms_drona.test_settings
./venv/bin/python manage.py collectstatic --noinput --settings=srms_drona.test_settings
./venv/bin/python -m compileall -q apps srms_drona

# is production actually running the intended start command? (§2 — do not skip)
render services -o json | python3 -c "import json,sys; [print(e['service']['serviceDetails']['envSpecificDetails']['startCommand']) for e in json.load(sys.stdin) if e['service']['id']=='srv-dajkh37qj5pc73e038i0']"
```

Read `ENGINEERING.md` before changing anything — it holds the invariants, the change loop,
the ship gate, the 9 known traps, and the review checklist.

---

## 6. Working with a limited context window

The context limit is a real constraint. The strategy that keeps this project safe:

1. **State lives in files, not in the conversation.** `HANDOFF.md` (this file),
   `ENGINEERING.md`, `README.md`, and `.workbuddy-ai/memory/` are committed or on disk.
   A fresh session reads them and is instantly current. Do not rely on chat history.
2. **Start a new session per task.** The change loop in `ENGINEERING.md` is self-contained;
   you do not need the history of the last session to fix the next bug.
3. **Record decisions where they will be found.** When you change a rule, update
   `ENGINEERING.md` in the same commit. When you finish a work block, append to
   `.workbuddy-ai/memory/YYYY-MM-DD.md`.
4. **Let git carry the history.** `git log --oneline` plus the memory log tells you what
   happened and why, without burning context on transcripts.
5. **Verify from the repo, not from memory.** Before acting, run the checks in §5. The
   repository is the source of truth; any summary — including this one — can be stale.
   **And verify against production, not against `render.yaml`** (§2).

---

## 7. Suggested next actions, in priority order

1. ✅ ~~Trigger a Render redeploy~~ — **done**, fix verified live in the boot logs. *(item 6)*
2. ✅ ~~Bump the GitHub Actions versions~~ — **done**, CI green with zero annotations. *(item 7)*
3. ✅ ~~Make `render.yaml` authoritative~~ — **done via Option A**, `scripts/apply_render_config.py`
   now pushes `render.yaml` to the live service and verifies the result. Blueprint adoption is
   therefore **optional**, not blocking. *(§2)*
4. ✅ ~~Correct the README and push everything~~ — **done**, `df6ec43`, CI green, deploy live.
   The README now states plainly that `render.yaml` is inert and documents the Render env vars.
5. **Convert `DRONAv2` to a Blueprint-managed service** — nice-to-have; needs a **dashboard**
   action (the API cannot create Blueprints), and the `name` must be the display name `DRONAv2`
   or Render creates a duplicate. *(§2)*
6. 🚨 **Enable email delivery** — the only high-impact gap left. Scheduler now runs, but
   `DJANGO_EMAIL_BACKEND` and `SMTP_USER`/`SMTP_PASSWORD` are still absent, so mail only logs.
   Needs SMTP credentials — blocks onboarding/setup links. *(§3a)*
7. ✅ ~~Enable the reminder scheduler~~ — **done** 2026-09-23: `SRMS_RUN_SCHEDULER=1` live.
   Reminders generate now; delivery starts the moment item 6 lands. *(§3a)*
8. ✅ ~~Confirm `GEMINI_API_KEY`~~ — **done, it is set.** *(§3)*
9. ✅ ~~Align the local Python venv to 3.12~~ — **done**: 3.12.13, gate green. *(item 5)*
10. ✅ ~~Reorder `DEFAULT_GEMINI_MODELS`~~ — **done** (`f8d12c0`): stable first, preview last;
    `GEMINI_MODEL=gemini-3.5-flash` pinned live. *(§3 note)*
11. ✅ ~~Delete the 37 local media artifacts~~ — **done**: `media/` empty. *(item 4)*
12. ✅ ~~Security-review findings~~ — **done**, `e5226a2` + `b4e019d`, 3 new tests.
13. ✅ ~~Enable Clerk SSO on Render~~ — **done** 2026-09-23, verified live.
14. ✅ ~~Tailor README + HANDOFF to current state~~ — **done**, then re-synced in session 6.
