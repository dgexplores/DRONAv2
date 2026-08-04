# SRMS Drona Learning App

Skill Learning & Performance Tracking Platform for **non-teaching staff** at SRMS Group of Institutions.

Built from the project spec documents (Project Plan + System Workflow).

## 🚀 Live Deployment
| Service | URL |
|---|---|
| **App (Django backend)** | https://dronav2-production.up.railway.app |
| **Landing page** | https://landing-two-phi-95.vercel.app |

**Demo accounts** (recreated on a fresh production DB):
| Role | Employee ID | Password |
|---|---|---|
| Super Admin | `ADMIN001` | `Admin12345` |
| HOD / Trainer | `EMP010` | `drona123` |
| Staff | `EMP001`–`EMP006` | `drona123` |

## Tech Stack
- **Backend:** Python 3.12 / Django 6 (custom `StaffUser`, RBAC, PostgreSQL-ready)
- **Frontend:** Server-rendered HTML + custom professional CSS + vanilla JS (mobile-first PWA)
- **AI:** Google Gemini API (`gemini-3.5-flash`) — auto MCQ generation from SOP PDF/text
- **PDF/QR:** ReportLab + qrcode — QR-verified certificates
- **Scheduler:** APScheduler — email reminders
- **Deploy:** Railway (backend) · Vercel (frontend/static, optional)

## Features
- ✅ Employee ID login + RBAC (staff / trainer-HOD / super admin)
- ✅ Split login page — **Staff/Trainee** and **Admin/Management** tabs (admin lands in the Management Console)
- ✅ **Password reset** via email (SMTP) — self-service "Forgot password?" link
- ✅ Optional **Clerk SSO** sign-in (auto-provisions accounts by email)
- ✅ Category → Course → Module → Lesson hierarchy
- ✅ Auto-enrollment in mandatory courses by department
- ✅ Video watch-position persistence (10s heartbeat) + progress calculation
- ✅ Gemini AI quiz generator (PDF/text → MCQs with answer keys)
- ✅ 70% passing threshold, retry logic
- ✅ Auto certificate generation with QR verification (`/verify/<id>/`)
- ✅ HR analytics dashboard (Chart.js) + CSV export
- ✅ Hindi / English UI toggle
- ✅ PWA (manifest + service worker) — Add to Home Screen
- ✅ APScheduler email reminders for pending training

## Quick Start (Local)
```bash
cd srms_drona
python3 -m venv venv
source venv/bin/activate          # or: .\venv\Scripts\activate (Windows)
pip install -r requirements.txt

# Optional: Gemini AI key + env config
cp .env.example .env              # then edit .env, add GEMINI_API_KEY

./venv/bin/python manage.py migrate
./venv/bin/python seed.py         # loads demo data
./venv/bin/python manage.py runserver
```
Open http://127.0.0.1:8000/

### Demo Accounts
| Role       | Employee ID | Password   |
|------------|-------------|------------|
| Super Admin| `ADMIN001`  | `Admin12345` |
| HOD/Trainer| `EMP010`    | `drona123` |
| Staff      | `EMP001`-`EMP006` | `drona123` |

> **Production admin password** is stored on the deployment machine at `~/.drona_admin_pw.txt`
> (permissions `600`). Change it after any shared-machine access.

## Authentication
- **Login** (`/login/`) has two tabs:
  - **Staff / Trainee** — for learners; lands on the dashboard.
  - **Admin / Management** — for admins & trainers; lands in the Management Console (`/manage/`).
- **Self-signup** (`/register/`) creates an *inactive* account that an **admin must approve** in the HR Dashboard (`/analytics/` → Pending Approvals).
- **Forgot password** (`/password-reset/`) emails a reset link. Emails are sent via SMTP
  (see env vars below) from the configured sender account.
- **Clerk SSO** renders on the login page when `CLERK_PUBLISHABLE_KEY` / `CLERK_SECRET_KEY` are set.
  Note: set the Clerk Dashboard **Homepage URL** to the live app URL so SSO signups work.

## Intro Videos
Welcome / platform-tour videos ship as git-tracked assets under `static/videos/`
(`intro_overview.mp4`, `intro_tour.mp4`) and are served by WhiteNoise at `/static/videos/`.
They seed the **Platform Introduction** course via a data migration (`apps/courses/migrations/0004_seed_intro_videos.py`).

## Deployment — Railway (backend)

1. Push this repo to GitHub.
2. In Railway, create **New Project → Deploy from GitHub repo**.
3. Add a **PostgreSQL** plugin (Railway auto-sets `DATABASE_URL`).
4. Set env vars in the service:
   - `DJANGO_DEBUG=False`
   - `DJANGO_ALLOWED_HOSTS=<your-app>.up.railway.app`
   - `DJANGO_SECRET_KEY=<long-random-string>`
   - `GEMINI_API_KEY=<your-key>`
   - `SRMS_BASE_URL=https://<your-app>.up.railway.app`
   - `SRMS_RUN_SCHEDULER=1` (enable reminder emails)
   - SMTP vars: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
5. Railway auto-detects `Procfile` (gunicorn) + `runtime.txt`.
6. Run migrations once:
   ```bash
   railway run python manage.py migrate
   railway run python seed.py      # optional demo data
   ```
7. Create/update a superuser:
   ```bash
   railway run python manage.py createsuperuser
   ```

> **Note:** Keep the scheduler to a single worker to avoid duplicate emails (`--workers 2` is fine; each worker runs the ready() scheduler — for production use `SRMS_RUN_SCHEDULER=1` on exactly one process, or set `--workers 1`).

## About Vercel
Django renders HTML templates server-side, so the **app itself runs on Railway**. Vercel hosts the static `landing/` marketing page (https://landing-two-phi-95.vercel.app) whose CTA links to the live app. The PWA + admin + API all live on Railway.

## Project Structure
```
srms_drona/
├── apps/
│   ├── users/          # StaffUser, Department, auth
│   ├── courses/        # Category, Course, Module, Lesson, Enrollment, Progress
│   ├── quizzes/        # Quiz, Question, Choice, Attempt + gemini_services
│   ├── certificates/   # Certificate model + pdf_builder (QR)
│   ├── analytics/      # HR dashboard + CSV export
│   └── notifications/  # APScheduler email reminders
├── static/             # CSS, JS, manifest.json, sw.js, icons, videos/
├── templates/          # PWA HTML templates (incl. password-reset pages)
├── media/              # runtime uploads (cert PDFs, SOP PDFs)
├── landing/            # Vercel static marketing site
├── .github/workflows/  # CI + CD pipelines
├── seed.py             # demo data loader
├── Procfile            # Railway web command (gunicorn)
└── requirements.txt
```

## Running Tests
```bash
./venv/bin/python manage.py test apps --settings=srms_drona.test_settings
```
`test_settings.py` forces an in-memory DB, disables the scheduler, and clears the Gemini
key so AI tests use the offline rule-based generator.

## CI/CD (GitHub Actions)
Three workflows run automatically on every push to `main`:

| Workflow | File | Job |
|---|---|---|
| **CI** | `.github/workflows/ci.yml` | Django system check + 31 tests + `collectstatic`, validates landing assets |
| **CD – Backend** | `.github/workflows/deploy-backend.yml` | Deploys Django to Railway via `railway up` |
| **CD – Frontend** | `.github/workflows/deploy-frontend.yml` | Deploys `landing/` to Vercel |

### Required GitHub Secrets
Set these in **Repo → Settings → Secrets and variables → Actions**:

| Secret | Where to get it | Used by |
|---|---|---|
| `RAILWAY_TOKEN` | Railway Dashboard → Account → Tokens | Backend CD |
| `RAILWAY_SERVICE_ID` | Railway service → Settings → Service ID | Backend CD |
| `VERCEL_TOKEN` | Vercel → Settings → Tokens (create new) | Frontend CD |

> The Vercel org/project IDs are already hardcoded in `deploy-frontend.yml`.
> Backend CD triggers only on backend path changes; frontend CD only on `landing/**`.
> Backend deploys run `python manage.py migrate --noinput` on every deployment
> (via `railway.toml` `predeploy`).

### Env Vars on Railway
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
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | Reminder + password-reset emails |
| `DEFAULT_FROM_EMAIL` | Sender shown on outgoing emails |
| `DJANGO_EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` (set this — default is console) |
| `CLERK_PUBLISHABLE_KEY` / `CLERK_SECRET_KEY` / `CLERK_JWT_AUDIENCE` | Optional Clerk SSO |

## Deployment Summary
- **Landing page** → Vercel — live at https://landing-two-phi-95.vercel.app (CTA opens the app)
- **Django app** → Railway — live at https://dronav2-production.up.railway.app
- **Database** → Railway-managed PostgreSQL (auto-attached via `DATABASE_URL`)
- **Scheduler** → APScheduler in the Django process (`SRMS_RUN_SCHEDULER=1`)
- **CI/CD** → GitHub Actions: CI + backend + frontend all green on every push
- **Data** → seeded with demo departments, staff, courses, quizzes, certificates

