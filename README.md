# SRMS Drona Learning App

Skill Learning & Performance Tracking Platform for **non-teaching staff** at SRMS Group of Institutions.

Built from the project spec documents (Project Plan + System Workflow).

## Tech Stack
- **Backend:** Python 3.12 / Django 6 (custom `StaffUser`, RBAC, PostgreSQL-ready)
- **Frontend:** Server-rendered HTML + custom professional CSS + vanilla JS (mobile-first PWA)
- **AI:** Google Gemini API (`gemini-2.5-flash`) — auto MCQ generation from SOP PDF/text
- **PDF/QR:** ReportLab + qrcode — QR-verified certificates
- **Scheduler:** APScheduler — email reminders
- **Deploy:** Railway (backend) · Vercel (frontend/static, optional)

## Features
- ✅ Employee ID login + RBAC (staff / trainer-HOD / super admin)
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
| Super Admin| `ADMIN001`  | `drona123` |
| HOD/Trainer| `EMP010`    | `drona123` |
| Staff      | `EMP001`-`EMP006` | `drona123` |

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
Django renders HTML templates server-side, so the **app itself runs on Railway**. Vercel is **not** needed for the core app. If you want a static/landing page in front, point `vercel.json` at a `static/` build separately — but the PWA + admin + API all live on Railway.

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
├── static/             # CSS, JS, manifest.json, sw.js, icons
├── templates/          # PWA HTML templates
├── media/              # uploaded PDFs, certificates
├── seed.py             # demo data loader
├── Procfile            # Railway web command (gunicorn)
└── requirements.txt
```
