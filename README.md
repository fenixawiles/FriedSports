# FraudWatch

Private-group sports trash-talk website. FraudWatch monitors live games and auto-triggers snarky alerts when someone in your group's team is getting embarrassed. Group threads, shame scoring, leaderboards, and public receipts.

**MVP leagues:** NBA and NFL.

---

## Local Setup

```bash
cd fraudwatch
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask db upgrade
flask seed
flask run
```

Visit `http://localhost:5000`

**Dev accounts** (all use password `password123`):
- `fenix@fraudwatch.dev` — Spurs + Cowboys fan
- `cody@fraudwatch.dev` — Lakers fan
- `aj@fraudwatch.dev` — Cowboys fan
- `lynn@fraudwatch.dev` — Celtics fan

---

## CLI Commands

```bash
flask seed          # Seed teams, users, groups, mock games
flask poll-scores   # Advance mock games one tick and fire triggers
flask simulate      # Run 3 poll ticks rapidly (for demos)
flask reset-db      # Wipe and recreate all tables (dev only)
```

**The main demo loop:**

```bash
flask seed
flask run           # In one terminal
# In another terminal:
flask poll-scores   # Run several times to advance game state
```

Log in as Fenix, visit the dashboard — active alert banners appear for the Spurs blowout and Cowboys choked lead. Click into a thread, post messages, react, watch leaderboards update.

---

## Project Structure

```
app/
  models.py               # All SQLAlchemy models
  routes/
    auth.py               # /signup /login /logout
    dashboard.py          # /dashboard /onboarding /settings
    groups.py             # /groups/*
    threads.py            # /threads/*
    public.py             # /public/receipts/<slug>
    api.py                # JSON endpoints for JS polling
  services/
    sports_provider.py    # Abstract base class
    mock_provider.py      # Local mock game simulation
    trigger_engine.py     # Detects game events, creates threads
    trash_templates.py    # Deterministic snarky message templates
    scoring.py            # Shame/brag/trash-talk point logic
  templates/              # Jinja2 HTML templates
  static/
    css/styles.css        # Dark-mode sports aesthetic
    js/main.js            # Flash auto-dismiss, alert polling
    js/threads.js         # Thread message polling + reactions
```

---

## Data Model (key relationships)

```
Game → GameEvent (objective trigger)
GameEvent → GroupTrigger (one per group/user pair)
GroupTrigger → GameThread
GameThread → GameThreadMessage
GameThreadMessage → MessageReaction / MessageReport
GameThread → Receipt (public shareable)
```

`UserFavoriteTeam` is the single source of truth for which team a user roots for.

---

## Trigger Types

| Type | When |
|---|---|
| BLOWOUT_ALERT | Team losing by 15/25/30+ |
| CHOKED_LEAD | Team blew a big lead |
| SHUTOUT_RISK | NFL team scoreless at halftime |
| DISASTER_QUARTER | Allowed 40+ in a quarter (NBA) |
| PLAYOFF_COLLAPSE | Lost after leading in Q4 |
| FINAL_LOSS | Game over, team lost |
| REDEMPTION_WIN | Team came back and won |
| RIVAL_WINNING | Rival is winning |
| ELIMINATION_RISK | Playoff elimination risk |
| UPSET_ALERT | Losing to inferior opponent |
| FRAUD_WATCH | General fraud detection |

Cooldown: same trigger_type / team / game won't re-fire within 15 minutes unless severity increases.

---

## Scoring

| Event | Points |
|---|---|
| Your team triggers embarrassing event | +5–30 shame |
| First reply in thread | +5 trash-talk |
| Reply before target responds | +3 trash-talk |
| Message gets a reaction | +1 trash-talk |
| Target user responds | +5 defense |
| Your team comes back and wins | +25 bragging, +10 shame to attackers |

**Leaderboard categories:** Biggest Loser · Best Hater · Most Delusional Fan · Bragging Rights Champion

---

## Deploying to Railway

1. Create a Railway project and add a Postgres database
2. Set environment variables:
   - `SECRET_KEY` — random secret string
   - `DATABASE_URL` — Railway provides this automatically
   - `FLASK_ENV=production`
3. Push code — Railway detects `Procfile` (`web: gunicorn wsgi:app`)
4. Run migrations: open the Railway shell and run `flask db upgrade`

The app auto-detects `DATABASE_URL` and switches from SQLite to Postgres.

---

## Adding a New League (e.g. MLB)

1. Add teams to `seed.py` with `league="MLB"`
2. Add trigger detection logic in `trigger_engine.py` under a new `elif game.league == "MLB"` block
3. `UserFavoriteTeam` and `Game` models already support any league string — no schema changes needed
