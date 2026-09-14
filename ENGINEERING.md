# Engineering Standards — SRMS Drona

Read this before changing anything. It records the invariants this codebase depends on, the
review process we hold each other to, and the traps that have already cost us time.

It is deliberately short. If a rule here is wrong, change the rule in a PR and say why — don't
quietly work around it.

---

## 1. Invariants

These are load-bearing. Breaking one is a bug even if every test still passes.

**1.1 Completion is derived, never declared.**
`LessonProgress.is_completed` for a video lesson is computed from server-accumulated
`watched_seconds`, never from a client-supplied flag. The player sends ~10s `watched` deltas;
`register_watch()` clamps each delta and caps the running total at the lesson duration.
`COMPLETION_RATIO = 0.9` because the final heartbeat is partial — do not raise it to 1.0 or
legitimately-watched lessons will never complete.

**1.2 Lessons that cannot be watch-verified say so.**
PDF lessons and lessons with a zero duration fall back to an explicit acknowledgement
(`acknowledge()`). That is the honest floor, not a loophole. If you add a new lesson type,
decide explicitly which side of this line it sits on.

**1.3 A certificate means something.**
`Certificate` is issued only when the assessment passes **and** `Enrollment.progress_percent`
has reached 100%. Never issue one from a code path that skips either check.

**1.4 Passwords are never displayed.**
Not in a response, not in a Django message, not in a log. Provisioning either uses the password
the admin typed, or generates one that nobody ever sees and emails a setup link
(`apps/users/services.py`). The generated password stays *usable* on purpose — see trap 4.1.

**1.5 Media is authorised per file.**
`srms_drona.views.protected_media` is the only production `/media/` route. `certificates/`
requires ownership or a manager role; `sop_documents/` requires enrollment. A blanket
`login_required` is **not** sufficient — filenames are guessable and certificate IDs are printed
on the credential itself.

**1.6 Login goes through `authenticate()`.**
Never hand-roll a user lookup plus `check_password()`. Django's `ModelBackend` hashes a dummy
value when the account does not exist, which equalises response time. Skipping it turns response
latency into an Employee-ID oracle, no matter how generic the error message is.

**1.7 Production config fails fast.**
With `DJANGO_DEBUG=False`, `srms_drona/settings.py` raises on an empty/default `DJANGO_SECRET_KEY`
and on `DJANGO_ALLOWED_HOSTS=*`. Keep it that way. A misconfigured deploy must not boot.

**1.8 The AI fallback is never silent.**
`generate_quiz_from_text()` returns `(quiz, GenerationReport)`. If `report.used_fallback` is
true, the admin is told. Template questions must never be presented as AI-generated assessment.

**1.9 Inline `<script>` needs the CSP nonce.**
The CSP has no `'unsafe-inline'` for scripts. Any inline script must carry
`nonce="{{ request.csp_nonce }}"` or the browser silently blocks it.

---

## 2. The change loop

Run this for every change. It is not ceremony — step 4 is where the real bugs are found.

1. **Red.** Write a test that fails *because of the defect*. Confirm it fails for the right
   reason, not an import error.
2. **Fix.** Smallest change that turns it green.
3. **Green.** Run that test, then the whole suite.
4. **Adversarial re-read.** Ask what this broke. Does it need a migration? Does it change a URL
   or a template variable? Does it contradict a Django behaviour (see §4)? Does it touch a call
   site you haven't grepped?
5. **Regression sweep.** `grep` every caller of everything you changed.
6. Any failure → back to step 2.

**Exit condition: steps 1–5 pass twice in a row with no edits between runs.**

A regression test that was never red is worthless. Prove it fails against the old code — for
example `git stash push -- <file>`, run the test, confirm the failure, then `git stash pop`.

---

## 3. Ship gate

```bash
./venv/bin/python manage.py check --settings=srms_drona.test_settings
./venv/bin/python manage.py makemigrations --check --dry-run --settings=srms_drona.test_settings
./venv/bin/python manage.py test apps --settings=srms_drona.test_settings
./venv/bin/python manage.py collectstatic --noinput --settings=srms_drona.test_settings
./venv/bin/python -m compileall -q apps srms_drona seed.py manage.py
```

`makemigrations --check` must report **no changes** — if it doesn't, you forgot to commit a
migration and production will drift from the model layer.

Also confirm the test run leaves `media/` untouched:

```bash
ls media/certificates | wc -l   # before
# run the suite
ls media/certificates | wc -l   # must be identical
```

---

## 4. Known traps

Each of these has already caused a real defect or a real false-confidence moment.

**4.1 `PasswordResetForm` skips accounts without a usable password.**
`get_users()` filters on `has_usable_password()`. The intuitive "set an unusable password for a
new account" fix silently stops the setup email from sending, and nobody notices until a user
can't sign in.

**4.2 `transaction.on_commit` never fires inside `TestCase`.**
`TestCase` wraps each test in a transaction that is rolled back, so commit callbacks are
discarded. Any test of post-commit work must either use
`self.captureOnCommitCallbacks(execute=True)` or — better — test the synchronous function
directly and mock the scheduler to assert it was called. See §5.

**4.3 `A && B || true; C` swallows a failure.**
Shell parses this as `(A && B) || true; C`. If `A` fails, `B` is skipped, `|| true` succeeds, and
`C` still runs. That is how a failed migration once booted the app against a broken schema. Use
`set -e` and separate statements.

**4.4 Tests that write to the real `MEDIA_ROOT`.**
Anything calling `generate_certificate_pdf()` or attaching a `FileField` writes to disk. Decorate
the test class with `@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)` (a `tempfile.mkdtemp()`) or
the suite dirties the working tree and leaks state between runs.

**4.5 `[:n]` on a fixed-size pool.**
The fallback question pool had 5 entries while callers could request 10, so requests for 6–10
silently returned 5. Slice a constant against a request and you get a silent ceiling. Assert the
count you promised.

**4.6 Hardcoded model lists rot.**
`DEFAULT_GEMINI_MODELS` degrades to the fallback as Google retires versions, with no signal. Pin
with the `GEMINI_MODEL` env var when a version disappears rather than editing code under
pressure. An unset `GEMINI_API_KEY` is also logged as a warning — never let a fallback be silent.

**4.7 `django.conf.urls.static.static()` only exists when `DEBUG=True`.**
Routes added in that block cannot be exercised by a normal test run. Test the view function
directly with `RequestFactory` instead of going through the URL resolver.

**4.8 Django messages are persisted.**
`messages.success(request, ...)` is stored in the session/cookie store and rendered on the next
page. Anything you put there outlives the request — which is why a password in a message is worse
than a password in a template.

**4.9 Test the tests.**
`test_save_progress_updates_enrollment` originally asserted that POSTing `completed: true` yields
100% — it encoded the vulnerability as the specification. When a test looks like it is describing
what the code does rather than what the product promises, stop and check the product promise.

**4.10 `render.yaml` does not control the live service.**
The `dronav2` service was created **manually** in the Render dashboard and has **no blueprint
linkage**. Editing `render.yaml` therefore changes **nothing** in production — it is documentation
that looks like configuration. This already bit us: the `set -e` / `set_admin_password` fix sat
inert in the repo while production kept running `A && B || true; C`, and only reading the live
boot logs revealed it.

Apply service-config changes with the CLI, and verify against the running service:

```bash
render services update srv-dajkh37qj5pc73e038i0 --start-command '...' --confirm
render services -o json | python3 -c "import json,sys; [print(e['service']['serviceDetails']['envSpecificDetails']['startCommand']) for e in json.load(sys.stdin) if e['service']['id']=='srv-dajkh37qj5pc73e038i0']"
render logs -r srv-dajkh37qj5pc73e038i0 --limit 200 -o text | grep -E "Running '|gunicorn"
```

A config change does **not** auto-deploy; run `render deploys create <service-id> --confirm`.
The right long-term fix is to convert the service to Blueprint-managed so the file is truthful.

**Before adopting a Blueprint, pre-flight it.** `render blueprints validate` reports the services
it would **create** under `plan.services`. An absent/empty list means it will **adopt** the
existing service instead — which is what you want.

```bash
render blueprints validate render.yaml
# {"plan": {"totalActions": 1}, "valid": true}   <- no "services" key = ADOPTS. Safe.
# {"plan": {"services": ["dronav2"], ...}}       <- would CREATE a duplicate. STOP.
```

⚠️ The `name` must match the service's **display name** (`DRONAv2`), and matching is
**case-sensitive**. The lowercase slug (`dronav2`) does *not* match and would create a **second,
duplicate service**. Verified empirically across all five services in the account: every real
name adopts; the slug and invented names are listed as to-be-created.

Also note a service-config change never triggers a deploy on its own.

**4.11 Secrets are write-only through the CLI.**
There is no command to read a service's env vars, and `render ssh` needs a key registered on the
account. Do not assume a variable is set because it appears in `render.yaml` — that file is inert
(trap 4.10). Prove it from behaviour and logs instead.

---

## 5. Testing conventions

- **One behaviour per test**, named as the behaviour: `test_forged_completion_flag_is_ignored_for_video`.
- **Regression guards carry a docstring** explaining the defect they prevent. Future readers need
  to know why the test exists before they decide it's redundant.
- **Isolate side effects.** Temp `MEDIA_ROOT`; `mail.outbox = []` before asserting on email.
- **Don't test through threads.** Post-commit work is tested by calling the synchronous function
  and separately asserting the scheduler was invoked with the right arguments.
- **Prefer asserting on observable outcomes** (DB state, status codes, response body) over
  internals. `assertContains(resp, "Invalid")` survives a refactor; asserting on a private
  variable does not.
- **Subprocess for import-time behaviour.** Settings guards run at import, so they can't be
  triggered by re-importing in a live interpreter — shell out (see
  `ProductionSettingsGuardTests`).

---

## 6. Review checklist

Copy this into the PR description.

- [ ] Does the change touch one of the §1 invariants? If so, is the invariant still true?
- [ ] New migration committed, and `makemigrations --check` is clean?
- [ ] New test proven red against the old code?
- [ ] Every caller of every changed function grepped and updated?
- [ ] Any user input reaching the DB bounded (size, range, count)?
- [ ] Any new response path checked for leaked exception text or secrets?
- [ ] Any new inline `<script>` carrying the CSP nonce?
- [ ] Does the README still describe reality? (Counts, workflow triggers, deploy target.)
- [ ] If `render.yaml` was edited: was the change **also** applied to the service and verified
  in the live boot logs? (Trap 4.10 — the file alone is a no-op.)
- [ ] Does the test run leave the working tree clean?

---

## 7. Deployment rules

- **Render is the live target.** Service `dronav2` = `srv-dajkh37qj5pc73e038i0`.
  ⚠️ **`render.yaml` is inert** — the service is manually configured, not Blueprint-managed, so
  editing the file does not change production. See trap 4.10. Apply changes via the CLI and verify
  against the running service.
- Start commands run under `set -e`. Steps are separated by `;`, not chained with `&&`/`||`.
- Every start command must run, in order: `migrate` → `createcachetable` → `set_admin_password`
  → `gunicorn`. `createcachetable` is idempotent (exit 0 when the table exists), so it is safe on
  every boot. `set_admin_password` exits 0 when the password env var is unset or ADMIN001 is
  missing, so it cannot wedge a boot.
- `DJANGO_ADMIN_PASSWORD` is applied by `set_admin_password`; it is not enough to declare the env
  var. Confirmed set on Render 2026-09-14 (`ADMIN001 password rotated.` in the boot logs).
- A service-config change does **not** trigger a deploy. Run
  `render deploys create <service-id> --confirm` afterwards.
- The scheduler runs in exactly one worker (`SRMS_RUN_SCHEDULER=1`) or reminders are sent
  multiple times.
- Never commit a secret. `.env` is git-ignored; deploy secrets live in the platform.

---

## 8. Where things live

| Concern | File |
|---|---|
| Completion rules | `apps/courses/models.py` → `LessonProgress` |
| Progress endpoint | `apps/courses/views.py` → `save_lesson_progress` |
| Media authorisation | `srms_drona/views.py` → `protected_media` |
| Post-commit + setup email | `apps/users/services.py` |
| Login | `apps/users/views.py` → `login_view` |
| Provisioning | `apps/management/views.py` → `create_user`, `import_staff` |
| AI generation + report | `apps/quizzes/gemini_services.py` |
| Production guards | `srms_drona/settings.py` (bottom of the file) |
| CSP nonce | `srms_drona/middleware.py` |
| Player heartbeat | `static/js/app.js` (top of file) |
