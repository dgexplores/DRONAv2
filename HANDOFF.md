# HANDOFF — SRMS Drona (DRONAv2)

**Purpose:** durable state so that no remaining work depends on an agent's conversation
context. If you are a teammate or a fresh session, read this file plus `ENGINEERING.md`
and you are current.

**Last updated:** 2026-09-14 (session 2)

---

## 1. Where things stand

| Item | State |
|---|---|
| Working tree | clean (`git status --porcelain` empty) |
| Branch | `main`, in sync with `origin/main` |
| HEAD | `1a5fa22` — *ci: bump actions to current majors, clear Node 20 deprecation* |
| CI | green — run `34854209674`, zero annotations (Node 20 warning cleared) |
| Test suite | 108 tests, all passing; ship gate run twice consecutively |
| Deployed | **live on Render** — service `dronav2`, deploy `dep-dajvqb0ae00c73bjjeug` (2026-09-14 13:59Z) |
| Health | `https://dronav2.onrender.com/health/` → `200 ok` |

The 9 defect classes found in the audit are fixed, committed, pushed, and CI-verified.
Nothing is half-finished. The items below are *follow-ups*, not incomplete work.

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

**Permanent fix (recommended):** convert the service to Blueprint-managed so `render.yaml`
becomes the source of truth. Until that happens, **any `render.yaml` edit must also be applied
via the CLI or dashboard**, or it is a no-op.

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
> outside. `GEMINI_API_KEY` remains the one env var whose presence is still unconfirmed.

---

### 4. Stray local media artifacts — cosmetic only
`media/` holds **37 untracked PDFs** (24 in `certificates/`, 13 in `sop_documents/`),
left over from test runs that predate the `MEDIA_ROOT` override.

- `media/` is **gitignored** (`.gitignore:14`) and **0 files are tracked** — these never
  reach the repo, CI, or Render.
- No action needed for shipping. Delete them locally only if you want a clean dev box.

### 5. Python version drift — environment hygiene
Local venv is **Python 3.14**; `runtime.txt` and CI pin **3.12**. CI passed, so this did not
cause a failure here — but it is a latent trap for anything version-sensitive.
**Action:** align the local venv to 3.12, or bump the pins deliberately and re-run CI.

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
3. **Convert `dronav2` to a Blueprint-managed service** so `render.yaml` stops being a lie.
   Until then, every `render.yaml` edit is a no-op. *(§2 — highest structural risk; needs a
   decision, because Render may not adopt a manually-created service cleanly)*
4. **Confirm `GEMINI_API_KEY`** by generating a quiz and reading the logs — now self-answering
   thanks to the new logging. *(§3)*
5. Align the local Python venv to 3.12. *(item 5)*
6. Optionally reorder `DEFAULT_GEMINI_MODELS` to prefer stable models. *(§3 note)*
7. Optionally delete the 37 local media artifacts. *(item 4)*
