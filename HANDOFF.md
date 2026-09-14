# HANDOFF — SRMS Drona (DRONAv2)

**Purpose:** durable state so that no remaining work depends on an agent's conversation
context. If you are a teammate or a fresh session, read this file plus `ENGINEERING.md`
and you are current.

**Last updated:** 2026-09-14

---

## 1. Where things stand

| Item | State |
|---|---|
| Working tree | clean (`git status --porcelain` empty) |
| Branch | `main`, in sync with `origin/main` |
| HEAD | `52252da` — *fix: close certificate-forgery, media-leak, and password-display defects* |
| CI | green — run `34850005290` on Python 3.12 (~29–33s) |
| Test suite | 107 tests, all passing; ship gate run twice consecutively |
| Deployed | **not redeployed** — see item 5 below |

The 9 defect classes found in the audit are fixed, committed, pushed, and CI-verified.
Nothing is half-finished. The items below are *follow-ups*, not incomplete work.

---

## 2. Outstanding items

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

**One live check still worth doing** (cheap, definitive): with a real `GEMINI_API_KEY` set,
generate a quiz and confirm `GenerationReport.source == 'gemini'` rather than `'fallback'`.
The docs list is authoritative but an actual call is proof.

---

### 3. Stray local media artifacts — cosmetic only
`media/` holds **37 untracked PDFs** (24 in `certificates/`, 13 in `sop_documents/`),
left over from test runs that predate the `MEDIA_ROOT` override.

- `media/` is **gitignored** (`.gitignore:14`) and **0 files are tracked** — these never
  reach the repo, CI, or Render.
- No action needed for shipping. Delete them locally only if you want a clean dev box.

### 4. Python version drift — environment hygiene
Local venv is **Python 3.14**; `runtime.txt` and CI pin **3.12**. CI passed, so this did not
cause a failure here — but it is a latent trap for anything version-sensitive.
**Action:** align the local venv to 3.12, or bump the pins deliberately and re-run CI.

### 5. Render redeploy — required for one fix to take effect
The corrected `startCommand` in `render.yaml` (`set -e` + `set_admin_password`) only applies
on the **next deploy**. Until then, production still runs the old shell-precedence command.
**Action:** trigger a Render deploy when you are ready.

### 6. GitHub Actions Node.js deprecation — low priority
`actions/checkout@v4` and `actions/setup-python@v5` target Node.js 20, which GitHub is
force-running on Node 24 with a warning. Harmless today.
**Action:** bump to the current major versions when convenient.

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

## 4. How to verify the current state yourself

```bash
cd /Users/dgsmacbook/DRONAv2

# tree clean and in sync?
git status --porcelain
git rev-list --left-right --count origin/main...HEAD   # expect: 0   0

# CI green?
gh run list --limit 3

# full ship gate (expect all green, twice)
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --settings=srms_drona.test_settings
python manage.py collectstatic --noinput --dry-run
python -m compileall -q apps srms_drona
```

Read `ENGINEERING.md` before changing anything — it holds the invariants, the change loop,
the ship gate, the 9 known traps, and the review checklist.

---

## 5. Working with a limited context window

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
5. **Verify from the repo, not from memory.** Before acting, run the checks in §4. The
   repository is the source of truth; any summary — including this one — can be stale.

---

## 6. Suggested next actions, in priority order

1. Trigger a Render redeploy so the `startCommand` fix goes live. *(item 5)*
2. Generate one real quiz with `GEMINI_API_KEY` set; confirm `source == 'gemini'`. *(§2)*
3. Align the local Python venv to 3.12. *(item 4)*
4. Optionally reorder `DEFAULT_GEMINI_MODELS` to prefer stable models. *(§2 note)*
5. Optionally bump the GitHub Actions versions. *(item 6)*
6. Optionally delete the 37 local media artifacts. *(item 3)*
