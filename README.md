# SRMS Drona — Learning & HR Analytics Platform

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
- **Hindi / English UI toggle**.
- **PWA** — manifest + service worker, installable to home screen, works as an app.
- **Email reminders** — APScheduler nudges staff with pending training (single-worker safe).
- **Hardened** — per-IP rate limiting on login/register/password-reset, CSP + security headers,
  approval-notification emails, background email delivery so admin actions never hang.

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12 · Django 6 · custom `StaffUser` model |
| **Database** | PostgreSQL (Railway-managed; SQLite fallback for local) |
| **Frontend** | Server-rendered HTML · custom design-system CSS · vanilla JS · mobile-first |
| **AI** | Google Gemini — MCQ generation from SOP PDF/text (candidates in `GEMINI_MODELS`; pin one with `GEMINI_MODEL`) |
| **PDF / QR** | ReportLab + qrcode — verifiable certificates |
| **Scheduler** | APScheduler — email reminders |
| **Auth** | Django auth + optional Clerk SSO (JWT) |
| **Hosting** | Render (app) + external Postgres. `Procfile` / `railway.toml` are kept in sync but Railway is no longer the live target |
| **CI/CD** | GitHub Actions — CI on every push and PR; backend deploy is `workflow_dispatch` only |

---

## 🚀 Live Deployment

| Service | Where it comes from |
|---|---|
| **App (Django backend)** | `render.yaml` — service `dronav2`, configured for `https://dronav2.onrender.com` |
| **Landing page (static)** | Deployed separately from `landing/` (Vercel — see `landing/vercel.json`) |

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
- **CSP + security headers** via `srms_drona.middleware.SecurityHeadersMiddleware`
  (per-request nonce for inline scripts, Referrer-Policy, Permissions-Policy, nosniff,
  frame-ancestors, `object-src 'none'`). Inline `<script>` tags must carry
  `nonce="{{ request.csp_nonce }}"` or the browser will block them.
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

> ⚠️ If you ever share an admin password in a chat/log, rotate it: update the `DJANGO_ADMIN_PASSWORD`
> env var in Railway, then redeploy. The `set_admin_password` command applies it automatically.

---

## 🚀 Quick Start (Local) — step by step

> **What you're doing:** clone the repo, create an isolated Python virtual environment, install
> the dependencies, create the database schema, load demo data, and run the dev server. You end
> up with a fully working app at `http://127.0.0.1:8000/`.

Prereqs: **Python 3.12+** and **Git**.

### 1. Get the code

```bash
git clone git@github.com:dgexplores/DRONAv2.git
cd DRONAv2
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
- **Clerk SSO** (optional) — renders when `CLERK_PUBLISHABLE_KEY` / `CLERK_SECRET_KEY` are set.
  Set the Clerk Dashboard **Homepage URL** to the live app URL for SSO signups to work.

---

## ☁️ Production deployment on Render (backend) — the live target

> **What's happening:** Render builds the repo from `render.yaml`, installs Django on a Python
> runtime, connects to your external Postgres via `DATABASE_URL`, runs migrations, rotates the
> admin password, and serves behind HTTPS with the single-worker gunicorn command.
>
> **To deploy:** Render Dashboard → **New → Blueprint** → select this repo. Then set the
> `sync: false` secrets (`DATABASE_URL`, `GEMINI_API_KEY`, `SRMS_BASE_URL`,
> `DJANGO_ADMIN_PASSWORD`, `SMTP_USER`, `SMTP_PASSWORD`) under Dashboard → Environment.

The start command runs under `set -e`, so a failed migration **aborts the boot** instead of
starting against a broken schema. Do not reintroduce the `A && B || true; gunicorn …` form — the
`|| true` swallows the failure and the app reports healthy while every query fails.

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
| `CLERK_PUBLISHABLE_KEY` / `CLERK_SECRET_KEY` / `CLERK_JWT_AUDIENCE` | Optional Clerk SSO |

> **Scheduler note:** keep exactly one worker running the scheduler (`SRMS_RUN_SCHEDULER=1`)
> to avoid duplicate reminder emails. The Procfile runs a single `web` worker by default.

---

## 🚦 CI/CD (GitHub Actions)

Two workflows in `.github/workflows/`:

| Workflow | File | Trigger | Job |
|---|---|---|---|
| **CI** | `.github/workflows/ci.yml` | push to `main`, every PR | Django system check · missing-migration check · full test suite · `collectstatic` · `compileall` |
| **Deploy backend** | `.github/workflows/deploy-backend.yml` | **manual** (`workflow_dispatch`) | Deploys Django to Railway (`railway up`) |

> **Railway CD is manual-only.** The Railway trial expired and Render is now the live target, so
> the push trigger was removed. Render deploys from `render.yaml` on its own. Re-add the push
> trigger only if Railway is reactivated.

### Required GitHub Secrets

| Secret | Where to get it | Used by |
|---|---|---|
| `RAILWAY_TOKEN` | Railway Dashboard → Account → Tokens | Backend CD |
| `RAILWAY_SERVICE_ID` | Railway service → Settings → Service ID | Backend CD |
| `RAILWAY_PROJECT_ID` | Railway project → Settings → Project ID | Backend CD |

---

## 🧪 Running Tests

```bash
./venv/bin/python manage.py test apps --settings=srms_drona.test_settings
```

`test_settings.py` forces an in-memory DB, disables the scheduler, and clears the Gemini key so
AI tests use the offline rule-based generator. It also swaps in `LocMemCache` (an in-memory DB
cannot host the `DatabaseCache` backend) and MD5 password hashing for speed.

**The suite is 107 tests and must stay green.** Coverage includes auth, RBAC, approval flow,
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
| `test_insecure_default_secret_key_is_rejected` | Booting production on dev defaults |

Tests write generated PDFs to a temporary `MEDIA_ROOT` (not the repo's `media/`), so a test run
leaves the working tree untouched.

---

## 📁 Project Structure

```
DRONAv2/
├── apps/
│   ├── users/          # StaffUser, Department, auth, approval views, rate limiting,
│   │                   #   services.py (post-commit hooks + password-setup email)
│   ├── courses/        # Category, Course, Module, Lesson, Enrollment, LessonProgress
│   ├── quizzes/        # Quiz, Question, Choice, Attempt + Gemini service
│   ├── certificates/   # Certificate model + PDF/QR builder
│   ├── analytics/      # HR dashboard + CSV export
│   ├── management/     # Admin management console + AuditLog
│   └── notifications/  # APScheduler email reminders
├── srms_drona/         # Settings, URLs, middleware, protected_media, test_settings
├── static/             # CSS (design system), JS, manifest.json, sw.js, icons, videos/
├── templates/          # Server-rendered HTML templates
├── landing/            # Static marketing site (deployed separately via Vercel)
├── media/              # Runtime uploads (cert PDFs, SOP PDFs) — git-ignored
├── .github/workflows/  # ci.yml + deploy-backend.yml (manual)
├── ENGINEERING.md      # Invariants, review checklist, known traps — read before changing
├── render.yaml         # Active deployment (Render blueprint)
├── Procfile            # Railway web command (kept in sync, currently unused)
├── railway.toml        # Railway config (kept in sync, currently unused)
├── seed.py             # Demo data loader
└── requirements.txt
```

---

## 📄 License & Usage

Internal educational project for SRMS Group of Institutions. Not for redistribution without permission.
