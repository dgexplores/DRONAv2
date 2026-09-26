# SRMS DRONA — Learning & HR Analytics Platform

A full-featured, production-ready skill-learning and performance-tracking platform for
**non-teaching staff** at SRMS Group of Institutions. Users learn from structured courses,
watch SOP videos, take AI-generated quizzes, earn QR-verified certificates, and are managed
through an HR analytics console — all under strict role-based access control (RBAC).

> Built to spec (Project Plan + System Workflow). Deployed on **Render** (Django) against a
> managed Postgres, with GitHub Actions CI and zero-cost single-worker hosting.
>
> **Before changing anything here, read [`ENGINEERING.md`](ENGINEERING.md)** — it records the
> invariants this project depends on and the traps that have already bitten us.

---

## ✨ Highlights (for a showcase)

- **Employee-ID auth + RBAC** — three roles: **Staff / Learner**, **HOD / Trainer**, **Super Admin**.
  The login page splits into a *Staff/Trainee* tab and an *Admin/Management* tab so each persona
  lands in the right workspace.
- **Self-signup with admin approval workflow** — new accounts are created *inactive*, an admin or
  trainer/HOD approves or rejects them in the HR Dashboard, and the user gets an email either way.
  No lockout, no enumeration leaks.
- **Admin provisions HR / HOD accounts** — super admin creates trainer accounts directly (no signup
  needed); those HR/HOD accounts get approval rights **and** the full management console.
- **Certificate directory** — super admin and HR/HOD see exactly who completed which certificate,
  with a search box (employee ID / name / email) plus filters by department and course.
- **Per-student course assignment** — assign a specific employee to a course, separate from the
  existing department-wide bulk-enroll.
- **Editable training calendar** — super admin and HR/HOD add/edit/delete sessions directly on the
  calendar grid (regular staff still only view it).
- **Category → Course → Module → Lesson** hierarchy with **auto-enrollment** into mandatory courses
  by department.
- **Video progress tracking** — watch position saved on a 10s heartbeat. Lesson completion is
  **derived server-side** from accumulated watch time (90% of the lesson duration), never from a
  client-supplied flag, so progress cannot be forged from the browser console.
- **AI quiz generator** — Google **Gemini** turns an SOP PDF/text into MCQs with answer keys.
  When the API is unavailable the offline rule-based generator runs, and the admin is **told** —
  template questions are never presented as AI-generated.
- **70% pass threshold + retries** — fair, measurable skill verification.
- **QR-verifiable certificates** — ReportLab renders the PDF; the QR code resolves to a public
  `/verify/<id>/` page that confirms authenticity while masking the holder's surname.
- **HR analytics dashboard** — Chart.js visualizations + **CSV export**.
- **Bilingual UI (English / हिन्दी)** — the whole interface is translated: navigation, buttons,
  form labels, validation messages, email subjects, the management console and every error page.
  347 catalogued strings. Content (course/module/lesson/quiz titles and descriptions) is
  bilingual via `_hi` model fields and switches with the UI. See
  [Localisation](#localisation--adding-or-changing-a-translation)..
- **PWA** — manifest + service worker, installable to home screen, works as an app.
- **Email reminders** — APScheduler nudges staff with pending training (single-worker safe).
  The scheduler is **on** in production; actual delivery awaits SMTP credentials (see
  Capabilities). Until then, outgoing mail logs a WARNING instead of pretending to send.
- **Always-on free plan** — triple keep-alive keeps Render from sleeping the instance:
  GitHub Actions pings `/health/` every 5 minutes, an optional local crontab job
  (`scripts/keep_awake.sh`, every 6 minutes), and a tiny beacon on the landing page. Fast boot
  via `manage.py boot` (migrate + cache + admin password in **one** process — cold start 69s → 44s).
- **Hardened** — per-IP rate limiting on login/register/password-reset, CSP + security headers
  (incl. `frame-ancestors 'none'`), masked staff emails in `list_users` output, approval-notification
  emails, background email delivery so admin actions never hang.

---

## ✅ Capabilities vs 🗺️ mapped to be made

**Live in production** (`https://dronav2.onrender.com`, last probed 2026-09-26):
Employee-ID auth + RBAC · approval workflow · admin provisioning · course hierarchy with
auto-enrollment · server-derived video progress · AI quiz generation (`GEMINI_API_KEY` confirmed
set, not serving fallback; model pinned via `GEMINI_MODEL=gemini-3.5-flash`) · 70% pass
threshold · QR-verifiable certificates · certificate directory with search/filters · per-student
assignment · editable training calendar · HR analytics + CSV export · Hindi/English toggle ·
PWA · rate limiting + CSP + anti-enumeration login ·
**reminder scheduler running** (delivery pending SMTP) ·
**Blueprint-managed config** (`render.yaml` authoritative, Auto Sync off) ·
**triple keep-alive** (free plan stays warm).

**Removed:** Clerk SSO (2026-09-26). Employee-ID + password is the only sign-in path. See
[Clerk SSO — removed](#clerk-sso--removed-future-scope).

**Partially live** (`HANDOFF.md` §3a): the reminder **scheduler is on** (`SRMS_RUN_SCHEDULER=1`,
set 2026-09-23 — reminders generate and log), but **email delivery is still off**: the live
service has no `DJANGO_EMAIL_BACKEND`/SMTP credentials, so mail prints to logs and never
delivers. The repo logs a **WARNING** on both paths instead of failing silently — delivery stays
off until the SMTP env vars below are set.

**Mapped to be made** (ordered):
1. **Go-live for email delivery** — scheduler already on; still needs `SMTP_USER`/`SMTP_PASSWORD`
   (+ host/port/TLS) and `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` on
   the Render service, redeploy, prove with `send_test_email`. Needs SMTP credentials — not doable
   from the repo alone. (`render.yaml` defers these declarations until the creds exist —
   adoption must not flip the backend unconfigured; see `HANDOFF.md` §3a.)
2. ✅ ~~Adopt the Blueprint~~ — **done 2026-09-23**: `DRONAv2` = `exs-daq0qoek1f9s73dhte70`,
   associated with the existing service (no duplicate), **Auto Sync off**, status `in_sync` at
   `7168f1a`. `render.yaml` is now authoritative; syncs are manual (`HANDOFF.md` §2).
3. ✅ ~~Pin/reorder Gemini models~~ — done 2026-09-23: stable models now precede the preview entry
   in `DEFAULT_GEMINI_MODELS`, and `GEMINI_MODEL=gemini-3.5-flash` is pinned on the live service.
4. Deliberately **not** planned: `/verify/<bogus>/` returns `200` not `404` (a "query result" page,
   left alone on purpose).

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12 · Django 6 · custom `StaffUser` model |
| **Database** | PostgreSQL (external, e.g. Neon, via `DATABASE_URL`; SQLite fallback for local) |
| **Frontend** | Server-rendered HTML · custom design-system CSS · vanilla JS · mobile-first |
| **AI** | Google Gemini — MCQ generation from SOP PDF/text (candidates in `DEFAULT_GEMINI_MODELS`; pin one with `GEMINI_MODEL`) |
| **PDF / QR** | ReportLab + qrcode — verifiable certificates |
| **Scheduler** | APScheduler — email reminders |
| **Auth** | Django auth only — employee ID + password. No third-party identity provider |
| **Hosting** | Render (app) + external Postgres. `Procfile` / `railway.toml` are kept in sync but Railway is no longer the live target |
| **CI/CD** | GitHub Actions — CI on every push and PR; backend deploy is `workflow_dispatch` only |

---

## 🚀 Live Deployment

**https://dronav2.onrender.com**

| Service | Where it comes from |
|---|---|
| **App (Django backend)** | Render service **`DRONAv2`** (`srv-dajkh37qj5pc73e038i0`) at `https://dronav2.onrender.com` |
| **Landing page (static)** | Deployed separately from `landing/` (Vercel — see `landing/vercel.json`) |

> ### `render.yaml` is Blueprint-authoritative — but **Auto Sync is OFF**
>
> The service was created manually, then **adopted as Blueprint-managed on 2026-09-23**
> (`exs-daq0qoek1f9s73dhte70`, associated with the existing service — no duplicate). Syncs are
> **manual**: editing `render.yaml` changes nothing until you press **Sync** in the Render
> dashboard (or run `scripts/apply_render_config.py --apply` to push immediately). Before
> adoption this file was fully inert, which caused one incident: the `set -e` start-command fix
> sat in the file while production kept running `A && B || true; C`, revealed only by live boot
> logs. Verify against the running service after any change.
>
> See `ENGINEERING.md` trap 4.10 and `HANDOFF.md` §2.

> **Railway is no longer the live target** — its trial expired. `Procfile` and `railway.toml` are
> still valid and are kept in sync, but the active deployment path is Render. The Railway deploy
> workflow (`.github/workflows/deploy-backend.yml`) is manual-only for this reason.

---

## 🔐 Security model

- **Secrets never committed.** `.env`/`.env.local` are git-ignored. Deploy secrets
  (`DJANGO_SECRET_KEY`, SMTP creds, `GEMINI_API_KEY`, tokens) live only in Render/Railway env
  vars and GitHub Actions secrets.
- **Production config fails fast.** With `DJANGO_DEBUG=False`, the settings module raises on an
  empty or default `DJANGO_SECRET_KEY` **and** on `DJANGO_ALLOWED_HOSTS=*`, so a misconfigured
  deploy refuses to boot instead of serving wide open. Covered by tests.
- **Admin password is environment-managed**, not hardcoded: `set_admin_password` reads
  `DJANGO_ADMIN_PASSWORD` and rotates the super-admin password. It is wired into **all three**
  start commands (`Procfile`, `railway.toml`, `render.yaml`). No plaintext credentials are
  stored in this repo.
- **No plaintext passwords are ever displayed.** Provisioning either uses the password the admin
  typed, or generates one that is never rendered, logged, or stored in the session-backed message
  store — the user sets their own via an emailed setup link (`apps/users/services.py`).
- **Media is authorised per file.** The production `/media/` route is not a blanket
  `login_required`: certificate PDFs require ownership (or a manager role) and SOP documents
  require enrollment, so guessing a filename gets a 404.
- **Rate limiting** (`django-ratelimit`) on login, registration, and password reset — per IP —
  mitigates brute force and email bombing.
- **CSP + security headers** via `srms_dorna.middleware.SecurityHeadersMiddleware`
  (per-request nonce for inline scripts, Referrer-Policy, Permissions-Policy, nosniff,
  `frame-ancestors 'none'`, `object-src 'none'`). Inline `<script>` tags must carry
  `nonce="{{ request.csp_nonce }}"` or the browser will block them.
- **Management CLI masks PII** — `list_users` prints `***@domain` unless `--include-email`
  is passed, so staff addresses never land in logs by default.
- **Anti-enumeration** login: pending/inactive accounts return a generic error message, and login
  goes through `authenticate()` so an unknown Employee ID costs the same as a wrong password
  (Django hashes a dummy value) — the message and the timing both stay generic.
- **Role-gated manager views** — certificate directory, course assignment, and calendar editing
  honor the same single `_can_manage`/`_is_manager` check (super admin + HR/HOD), so there is no
  divergent role logic to bypass.
- **Background email** — approval/reminder/setup emails send on a daemon thread after commit with
  `EMAIL_TIMEOUT`, so SMTP stalls never block a request.
- **Demo credentials below are for a fresh seed only** — production override them with strong
  passwords via env vars. Never publish a password that matches a live account.

> ⚠️ If you ever share an admin password in a chat/log, rotate it: update the
> `DJANGO_ADMIN_PASSWORD` env var **on Render** (Dashboard → `DRONAv2` → Environment), then
> redeploy. The `set_admin_password` command applies it automatically on boot:
>
> ```bash
> render deploys create srv-dajkh37qj5pc73e038i0 --confirm
> ```
>
> You do not need the old password — rotation overwrites it. The value is a **secret** and cannot
> be read back: Render env vars are write-only, so keep it in a password manager.

---

## 🚀 Quick Start (Local) — step by step

> **What you're doing:** clone the repo, create an isolated Python virtual environment, install
> the dependencies, create the database schema, load demo data, and run the dev server. You end
> up with a fully working app at `http://127.0.0.1:8000/`.

Prereqs: **Python 3.12+** and **Git**.

### 1. Get the code

```bash
git clone git@github.com:dgexplores/DRONA.git
cd DRONA
```

### 2. Create and activate a virtual environment

A virtual environment keeps this project's dependencies isolated from your system Python —
so installing them here won't affect other projects or require admin rights.

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure local environment (optional)

Copy the example env file and edit it. Only `GEMINI_API_KEY` is needed for AI quiz generation;
everything else has safe defaults for local development.

```bash
cp .env.example .env            # then edit settings as needed
```

### 5. Set up the database

`migrate` builds the tables (Postgres schema when `DATABASE_URL` is set, otherwise SQLite).

```bash
./venv/bin/python manage.py migrate
```

### 6. Load demo data

`seed.py` creates departments, demo staff accounts, courses/quizzes, and the super admin.

```bash
./venv/bin/python seed.py
```

### 7. Run the dev server

```bash
./venv/bin/python manage.py runserver
```

Open **http://127.0.0.1:8000/** in your browser.

### Demo accounts (seed only — local / fresh environments)

> This repository is **public**: treat these as published constants, not secrets. They only
> exist where you deliberately run `seed.py`. Any instance you expose must override them —
> production uses `DJANGO_ADMIN_PASSWORD` (env-managed, never stored here).

| Role | Employee ID | Password |
|---|---|---|
| Super Admin | `ADMIN001` | `Admin12345` |
| HOD / Trainer | `EMP010` | `drona123` |
| Staff | `EMP001`–`EMP006` | `drona123` |

Seed password values come from `SEED_ADMIN_PASSWORD` (env, default `Admin12345`) and `drona123`
for staff. Override `SEED_ADMIN_PASSWORD` for your own seed. The live deployment uses a rotated
admin password from `DJANGO_ADMIN_PASSWORD` (see Production below) — never reuse the seed admin
password in production.

---

## 🌐 Localisation — adding or changing a translation

The UI is bilingual. **English → Hindi** is wired through Django's own i18n, not ad-hoc
conditionals.

| Piece | Where | Notes |
|---|---|---|
| Enabled languages | `LANGUAGES` in `settings.py` | `en` + `hi` |
| Catalog location | `LOCALE_PATHS` → `locale/hi/LC_MESSAGES/` | `django.po` is the source, `django.mo` is the compiled binary |
| Markup | `{% trans "…" %}` / `{% blocktranslate %}` for text with `{{ variables }}` | every template does `{% load i18n %}` |
| Backend strings | `gettext_lazy as _` in Python | module-level constants must use the lazy form |
| Which language | `UserLanguageMiddleware` | session `django_language` first, then `StaffUser.preferred_language` |

**`django.mo` is committed on purpose.** Render's Python image has no `msgfmt`, so a
build-time `compilemessages` would fail or be skipped. If you edit `django.po`, recompile
and commit both:

```bash
python manage.py makemessages -l hi -a --ignore=venv --ignore=staticfiles --ignore=media
msgfmt -o locale/hi/LC_MESSAGES/django.mo locale/hi/LC_MESSAGES/django.po
```

`msgfmt --check` is worth running — a malformed catalog fails at runtime, not at build.

**Two things never to translate**, both of which caused real breakage here:

1. **A language code inside a URL.** The toggle is `?lang={% if is_hindi %}en{% else %}hi{% endif %}`.
   Wrapping `hi` in `{% trans %}` sends the translated *word* as the code and silently breaks the switch.
2. **A value, not display text** — Employee IDs, passwords, department codes, `pk_test_…` keys.

**Bilingual content** is separate and pre-existing: `Category.name_hi`, `Course.title_hi`,
`Lesson.title_hi`, `Quiz.title_hi` etc. Templates pick the `_hi` field when `is_hindi` is set
and fall back to the English one. Anything typed into a `_hi` field in the admin shows only
in Hindi mode.

`HindiCatalogTests` (in `apps/users/tests.py`) fails if `LOCALE_PATHS` is empty, if `django.mo`
is missing, if a known string stops translating, or if the session/user preference stops
reaching `{% trans %}`.

---

## 🧭 Authentication & Approval flow

- **Login** (`/login/`) — two tabs:
  - **Staff / Trainee** → learner dashboard.
  - **Admin / Management** → Management Console (`/manage/`).
- **Self-signup** (`/register/`) creates an **inactive** account. An admin **or trainer/HOD** approves
  it in the HR Dashboard (`/analytics/` → Pending Approvals). Approved users can then sign in and, if
  needed, reset their password via email.
- **Admin-provisioned accounts** — the super admin can create HR / HOD / staff accounts directly from
  the Management Console (`➕ Create HR/HOD Account`, `/manage/users/create/`). The new account is
  active immediately. HR/HOD (trainer) accounts get approval rights plus the full management console,
  so they can operate independently.
- **Password reset** (`/password-reset/`) — emails a reset link via SMTP.

### Clerk SSO — removed (future scope)

Clerk (a hosted third-party identity provider) was integrated until 2026-09-26 and has been
**removed from the codebase**. Sign-in is **employee ID + password only**.

Removed: `apps/users/clerk_auth.py` (the `ClerkAuthenticationBackend`), the `/clerk/login/`
token-exchange view and its URL, the `CLERK_*` settings, the `ClerkAuthenticationBackend` entry in
`AUTHENTICATION_BACKENDS`, the login-page widget markup and scripts, its 5 regression tests, and the
`clerk-backend-api` / `pyjwt` dependencies. Net effect: `/login/` no longer loads
`clerk.browser.js`, so the console is clean and the page loads one script lighter.

**If SSO is ever wanted**, it is a deliberate re-adding, not a config flip. Two things to get right
that the old integration got wrong:

1. **The key was being handed to Clerk the wrong way.** The page loaded the CDN *global* build and
   called `window.Clerk.load({ publishableKey: key })` — but that options-object signature belongs to
   the npm/ESM build. The global build reads the key from a `data-clerk-publishable-key` script
   attribute or `window.__clerk_publishable_key`, so it threw `Missing publishableKey` and rendered
   an empty widget even though the key *was* set and correctly rendered into the page.
2. **The gate didn't check the key it needed.** `clerk_enabled()` tested `CLERK_SECRET_KEY` plus a
   token-binding claim but never `CLERK_PUBLISHABLE_KEY`, so a missing key rendered a broken button
   instead of disabling SSO.

Also required: a **production** publishable key (the old one was `pk_test_…`, test mode only), and
`CLERK_AUTHORIZED_PARTIES` matching the Clerk Frontend API origin, since plain Clerk session tokens
carry no `aud` claim and bind on `azp` instead.

**Housekeeping:** the `CLERK_*` env vars are still set on the Render service. They are now inert —
nothing reads them. Clearing them in the dashboard is optional cleanup; a Blueprint sync will not
remove them, because `render.yaml` only declares what it declares.

---

## ☁️ Production deployment on Render (backend) — the live target

> **What's happening:** Render builds the repo on a Python runtime, installs the dependencies,
> connects to external Postgres via `DATABASE_URL`, then runs `python manage.py boot`
> (migrate → cache table → admin-password rotation **in one process**, ~44s cold) followed by a
> single-worker gunicorn under `set -e` — a failed boot step aborts before the app listens.

> ⚠️ The service is **already Blueprint-managed** (`exs-daq0qoek1f9s73dhte70`, adopted 2026-09-23).
> **Do not run "New → Blueprint" against this repo again** — a second blueprint or a mismatched
> `name` creates a duplicate service. Auto Sync is **off**: config changes land only via the
> dashboard **Sync** button or `scripts/apply_render_config.py --apply`. Read `HANDOFF.md` §2
> first. For a genuinely fresh environment, `render.yaml` is ready to use as-is.

**Deploy** — push to `main` (code auto-deploys via the service's `autoDeployTrigger: commit`;
config does **not** — that needs a Blueprint sync), or trigger one explicitly:

```bash
render deploys create srv-dajkh37qj5pc73e038i0 --confirm
```

**Change service config** — edit `render.yaml`, then apply it (Auto Sync is off, so a commit alone
won't sync):

```bash
python scripts/apply_render_config.py                    # dry run: shows the exact command
python scripts/apply_render_config.py --apply            # push it to the service
python scripts/apply_render_config.py --apply --deploy   # and deploy
```

Or click **Sync** on the Blueprint in the Render dashboard (renders the same `render.yaml`).

It applies `buildCommand`, `startCommand`, `healthCheckPath`, `plan`, `branch`, `repo`,
`rootDir`, `previews` and `autoDeployTrigger`, then **verifies against the running service**.
Anything it cannot set is reported, never silently skipped:

| Field | Why |
|---|---|
| `runtime` | The CLI refuses it — "cannot switch runtimes via the CLI" |
| `region` | Immutable after creation |
| `numInstances` | No CLI flag exists |
| `envVars` | `services update` has no env-var flag — set secrets in the dashboard |
| `autoDeployTrigger: off` | Only `--auto-deploy` (enable) exists |

The start command runs under `set -e`, so a failed migration **aborts the boot** instead of
starting against a broken schema. Do not reintroduce the `A && B || true; gunicorn …` form — the
`|| true` swallows the failure and the app reports healthy while every query fails.

### Env vars (Render)

Set these under **Dashboard → `DRONAv2` → Environment**. They are secrets and cannot be read
back through the CLI, so treat a password manager as the source of truth.

| Variable | Notes |
|---|---|
| `DATABASE_URL` | External Postgres (e.g. Neon) connection string |
| `DJANGO_SECRET_KEY` | Long random string |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `dronav2.onrender.com` (exact host — matches live and `render.yaml`) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://dronav2.onrender.com` |
| `DJANGO_SECURE_SSL_REDIRECT` | `True` |
| `GEMINI_API_KEY` | Live AI quiz generation; if unset, quizzes fall back to rule-based questions and **a warning is logged** |
| `GEMINI_MODEL` | `gemini-3.5-flash` — pins the stable model (fallback pool can drift through retired previews) |
| `SRMS_BASE_URL` | `https://dronav2.onrender.com` |
| `SRMS_RUN_SCHEDULER` | `1` — APScheduler reminder loop **on** (delivery still needs SMTP rows below) |
| `DJANGO_ADMIN_PASSWORD` | Super-admin password; applied on every boot by `set_admin_password` |
| `DJANGO_EMAIL_BACKEND` | **Not set yet** — when set: `django.core.mail.backends.smtp.EmailBackend` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USE_TLS` | **Not set yet** — e.g. `smtp.gmail.com` / `587` / `True` |
| `SMTP_USER` / `SMTP_PASSWORD` | **Not set yet** — reminder + password-reset emails stay off until these land |

To check whether `render.yaml` declares every env var the live service actually has:

```bash
export RENDER_API_KEY=rnd_...    # Dashboard → Account Settings → API Keys
python scripts/verify_render_env.py        # prints NAMES only, never values
```

**Keep-alive (free plan).** The instance sleeps after ~15 idle minutes; three layers prevent it:

1. `.github/workflows/keep-alive.yml` — GitHub Actions cron every 5 minutes hits `/health/`
   (free for public repos).
2. `scripts/keep_awake.sh` — optional local crontab entry (`*/6 * * * *`), logs to
   `~/Library/Logs/DRONA_keep_awake.log`.
3. A `fetch('/health/', {mode:'no-cors'})` beacon on the Vercel landing page.

---

## ☁️ Production deployment on Railway (legacy — no longer the live target)

> The Railway trial expired. `Procfile` and `railway.toml` are kept in sync and remain valid, but
> the CD workflow is now manual-only. Use the Render section above for the active path.

### 1. Push to GitHub

```bash
git add .
git commit -m "feat: your change"
git push origin main
```

### 2. Create the project and service on Railway

1. **Railway → New Project → Deploy from GitHub repo**, select this repo.
2. Add a **PostgreSQL** plugin — Railway auto-sets `DATABASE_URL`.

### 3. Set environment variables

Railway → your service → **Variables**. See the table below. **Debug** must be off and
`ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` must include the app URL, or HTTPS form posts (login,
enroll, approval) will be rejected.

### 4. Deploy

Railway auto-detects the **Procfile** (gunicorn) + `runtime.txt`. If the plugin didn't run them,
migrate + seed once:

```bash
railway run python manage.py migrate
railway run python seed.py            # optional demo data
```

### 5. Rotate the admin password

Set `DJANGO_ADMIN_PASSWORD` and redeploy. The `set_admin_password` management command applies it
on startup, so the live super-admin password is always environment-managed, never a seed default.

### Env vars (Railway)

| Variable | Notes |
|---|---|
| `DATABASE_URL` | Auto-provided by the Railway Postgres plugin |
| `DJANGO_SECRET_KEY` | Long random string |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `<app>.up.railway.app` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://<app>.up.railway.app` (comma-separated; required for HTTPS form POSTs) |
| `GEMINI_API_KEY` | Live AI quiz generation |
| `SRMS_BASE_URL` | `https://<app>.up.railway.app` |
| `SRMS_RUN_SCHEDULER` | `1` to enable email reminders |
| `DJANGO_ADMIN_PASSWORD` | Super-admin password; rotated on each deploy by `set_admin_password` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | Reminder + password-reset emails |
| `EMAIL_TIMEOUT` | SMTP connect timeout in seconds (default `10`) |
| `DEFAULT_FROM_EMAIL` | Sender shown on outgoing emails |
| `DJANGO_EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` (default is console) |

> **Scheduler note:** keep exactly one worker running the scheduler (`SRMS_RUN_SCHEDULER=1`)
> to avoid duplicate reminder emails. The Procfile runs a single `web` worker by default.

---

## 🚦 CI/CD (GitHub Actions)

Three workflows in `.github/workflows/`:

| Workflow | File | Trigger | Job |
|---|---|---|---|
| **CI** | `.github/workflows/ci.yml` | push to `main`, every PR | Django system check · missing-migration check · full test suite (120) · `collectstatic` · `compileall` |
| **Deploy backend** | `.github/workflows/deploy-backend.yml` | **manual** (`workflow_dispatch`) | Deploys Django to Railway (`railway up`) — legacy, manual only |
| **Keep-alive** | `.github/workflows/keep-alive.yml` | cron every 5 min + manual | GET `/health/` so the free Render instance never sleeps |

> **Railway CD is manual-only.** The Railway trial expired and Render is now the live target, so
> the push trigger was removed. Render auto-deploys *code* on push to `main` because the *service*
> has `autoDeployTrigger: commit`; `render.yaml` *config* applies only on a manual Blueprint sync
> (Auto Sync off — see Live Deployment). Re-add the push trigger only if Railway is reactivated.

### Required GitHub Secrets

| Secret | Where to get it | Used by |
|---|---|---|
| `RAILWAY_TOKEN` | Railway Dashboard → Account → Tokens | Backend CD |
| `RAILWAY_SERVICE_ID` | Railway service → Settings → Service ID | Backend CD |
| `RAILWAY_PROJECT_ID` | Railway project → Settings → Project ID | Backend CD |

---

## 🧪 Running Tests

```bash
./venv/bin/python manage.py test apps --settings=srms_dorna.test_settings
```

`test_settings.py` forces an in-memory DB, disables the scheduler, and clears the Gemini key so
AI tests use the offline rule-based generator. It also swaps in `LocMemCache` (an in-memory DB
cannot host the `DatabaseCache` backend) and MD5 password hashing for speed.

**The suite is 120 tests and must stay green.** Coverage includes auth, RBAC, approval flow,
rate limiting, quizzes, certificates, the certificate directory + filters, per-student
assignment, calendar manager gating, and analytics — plus the regression guards added for the
defects fixed in `ENGINEERING.md`:

| Guard | What it prevents |
|---|---|
| `test_forged_completion_flag_is_ignored_for_video` | Earning a certificate by POSTing `completed: true` |
| `test_single_heartbeat_cannot_credit_whole_video` | Inflating watch time in one request |
| `test_other_staff_cannot_fetch_someone_elses_certificate` | Reading another staff member's certificate PDF from `/media/` |
| `test_media_route_blocks_unenrolled_sop` | Bypassing the enrollment check on SOP documents |
| `test_unknown_employee_id_still_runs_the_password_hasher` | Timing-based Employee ID enumeration |
| `test_supplied_password_is_never_echoed_back` | Plaintext passwords reaching the page or session |
| `test_import_schedules_one_batched_setup_job` | Imported staff who can never sign in |
| `test_fallback_honours_the_requested_count` | Silently returning 5 questions when 10 were asked |
| `test_missing_api_key_is_logged_not_silent` | An unset `GEMINI_API_KEY` degrading to fallback with no log line |
| `test_password_setup_email_warns_when_console_backend` | Setup links printed instead of delivered with no log line |
| `test_disabled_scheduler_warns` | Scheduler off with only an INFO trace |
| `test_insecure_default_secret_key_is_rejected` | Booting production on dev defaults |
| `test_emails_masked_by_default` | `list_users` printing staff emails into logs |

Tests write generated PDFs to a temporary `MEDIA_ROOT` (not the repo's `media/`), so a test run
leaves the working tree untouched.

---

## 📁 Project Structure

```
DRONA/
├── apps/
│   ├── users/          # StaffUser, Department, auth, approval views, rate limiting,
│   │                   #   services.py (post-commit hooks + password-setup email)
│   ├── courses/        # Category, Course, Module, Lesson, Enrollment, LessonProgress
│   ├── quizzes/        # Quiz, Question, Choice, Attempt + Gemini service
│   ├── certificates/   # Certificate model + PDF/QR builder
│   ├── analytics/      # HR dashboard + CSV export
│   ├── management/     # Admin management console, AuditLog, and `boot` (single-process
│   │                   #   migrate + createcacheetable + set_admin_password for fast cold start)
│   └── notifications/  # APScheduler email reminders
├── srms_dorna/         # Settings, URLs, middleware, protected_media, test_settings
├── static/             # CSS (design system), JS, manifest.json, sw.js, icons, videos/
├── templates/          # Server-rendered HTML templates
├── landing/            # Static marketing site (deployed separately via Vercel)
├── media/              # Runtime uploads (cert PDFs, SOP PDFs) — git-ignored
├── .github/workflows/  # ci.yml · deploy-backend.yml (manual, legacy) · keep-alive.yml (5m /health/)
├── scripts/            # apply_render_config.py (push render.yaml to Render, then verify)
│                       #   verify_render_env.py (compare live env vars, names only)
│                       #   keep_awake.sh (optional local crontab keep-alive)
├── ENGINEERING.md      # Invariants, review checklist, known traps — read before changing
├── HANDOFF.md          # Outstanding work, deploy state, how to verify from the repo
├── render.yaml         # Render config — Blueprint-authoritative (Auto Sync off since 2026-09-23).
│                       #   Apply via dashboard Sync or scripts/apply_render_config.py (see Live Deployment)
├── Procfile            # Railway web command (kept in sync, currently unused)
├── railway.toml        # Railway config (kept in sync, currently unused)
├── seed.py             # Demo data loader
└── requirements.txt
```

---

## 📄 License & Usage

Internal educational project for SRMS Group of Institutions. Not for redistribution without permission.
