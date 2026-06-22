# Claude Code Handoff: App Store Submission Cleanup

Claude Code,

This is the cleanup pass completed for FriedSports App Store review readiness on
branch `codex/app-review-readiness`. The main commit is:

`ac19be4 Harden FriedSports app review readiness`

## What Changed

### 1. Reduced Guideline 4.2 WebView-wrapper risk

- Removed `server.url` from `capacitor.config.json`.
- The iOS app now ships bundled React assets from `frontend/dist` via
  Capacitor `webDir` instead of loading `https://www.friedsports.com` as the
  entire app.
- Added `npm run ios:sync` in `package.json`:
  - runs `npm --prefix frontend run build`
  - then runs `npx cap sync ios`
- Updated `README.md` and `APP_STORE_SUBMISSION.md` to make `npm run ios:sync`
  the documented Xcode handoff step.

Important operational note: `ios/App/App/public` and
`ios/App/App/capacitor.config.json` are generated and ignored by Git. Run
`npm run ios:sync` before opening/archive-building in Xcode.

### 2. Made native iOS API auth work with bundled assets

- Updated `frontend/src/api/client.js`:
  - Web/dev keeps same-origin `/api`.
  - Capacitor native uses `https://www.friedsports.com/api`.
  - `VITE_API_ORIGIN` can override the API origin if needed.
- Updated CORS in `app/__init__.py` to allow:
  - local dev origins
  - `capacitor://localhost`
  - `ionic://localhost`
  - `https://friedsports.com`
  - `https://www.friedsports.com`
- Updated production cookies in `config.py`:
  - `SESSION_COOKIE_SAMESITE = "None"`
  - `REMEMBER_COOKIE_SAMESITE = "None"`
  - both remain `Secure`
- Fixed JSON API login in `app/routes/api_react.py` so email/password signs in
  directly and returns the serialized user. Previously the React API still sent
  users to `verify-code`, which contradicted the reviewer notes.

### 3. Fixed database migration drift for Railway/fresh installs

- Patched `migrations/versions/2596338ae9ea_add_email_verified_and_notifications.py`
  so non-Postgres dialects do not fail on Postgres-specific SQL.
- Added `migrations/versions/6b4f31d2a9c0_app_review_schema_sync.py`.
- The new migration fills drift between current SQLAlchemy models and a clean
  migrated database:
  - `users.role`
  - `group_members.reporter_score`
  - `incident_reports`
  - `game_events.incident_report_id`
  - nullable `game_events.game_id`
  - all `lab_*` analytics tables
- Confirmed Railway should pick this up automatically because both `Procfile`
  and `nixpacks.toml` run `flask db upgrade` before Gunicorn starts.

### 4. Fixed Xcode/App Store packaging issues

- Added `ios/App/App/PrivacyInfo.xcprivacy` to the App target resources in
  `ios/App/App.xcodeproj/project.pbxproj`.
- Confirmed the built `.app` contains the app-root privacy manifest, not only
  SDK framework manifests.
- Changed the App target deployment target from `26.0` to `13.0`.

### 5. Cleaned App Store submission docs and privacy copy

- Updated `APP_STORE_SUBMISSION.md`:
  - reviewer notes now match the long-press report flow
  - checklist includes app-root privacy manifest verification
  - checklist includes `npm run ios:sync`
  - 4.2 section now describes bundled assets plus native capabilities
- Updated `app/templates/legal/privacy.html` to remove stale push/device-token
  language.
- Updated README dev account emails to `@friedsports.dev`.

## Verification Already Run

- `rm -f /tmp/friedsports_migration_check.db && FLASK_ENV=development SECRET_KEY=dev-review DATABASE_URL=sqlite:////tmp/friedsports_migration_check.db venv/bin/flask --app wsgi.py db upgrade && FLASK_ENV=development SECRET_KEY=dev-review DATABASE_URL=sqlite:////tmp/friedsports_migration_check.db venv/bin/flask --app wsgi.py seed`
- SQLAlchemy metadata vs migrated SQLite schema check:
  - columns match
  - nullability matches
- Production-style native auth smoke:
  - `Origin: capacitor://localhost`
  - CORS preflight returns allowed origin and credentials
  - login returns user
  - `remember_token` and `session` cookies are `Secure; SameSite=None`
  - subsequent `/api/auth/me` succeeds
- `venv/bin/python -m compileall app migrations`
- `npm run ios:sync`
- `xcodebuild -workspace ios/App/App.xcworkspace -scheme App -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' CODE_SIGNING_ALLOWED=NO build`
- Built app bundle inspection confirmed:
  - `App.app/PrivacyInfo.xcprivacy` exists
  - `App.app/public/index.html` exists
  - built `capacitor.config.json` has no `server.url`

## Remaining Review Readiness Notes

- Create a real non-admin production reviewer account:
  - profile complete
  - in at least one group
  - with an active thread containing another user's message
  - able to long-press another user's message and report/block
- Before archive/submission, run:

```bash
npm install
npm run ios:sync
```

- Then open Xcode and confirm:
  - no Push Notifications capability
  - `PrivacyInfo.xcprivacy` is in App target resources
  - built app root contains `PrivacyInfo.xcprivacy`
  - version/build are set for submission

## Files Most Relevant To Review

- `APP_STORE_SUBMISSION.md`
- `capacitor.config.json`
- `frontend/src/api/client.js`
- `app/__init__.py`
- `config.py`
- `app/routes/api_react.py`
- `ios/App/App.xcodeproj/project.pbxproj`
- `ios/App/App/PrivacyInfo.xcprivacy`
- `migrations/versions/6b4f31d2a9c0_app_review_schema_sync.py`
- `migrations/versions/2596338ae9ea_add_email_verified_and_notifications.py`
- `package.json`

