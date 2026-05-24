## App Brief

**Name:** habit-tracker
**Target user:** single user
**Tech stack:** Flask + SQLite + Jinja2 (sandbox standard)
**Core features:**
- Create and manage daily habits
- Mark habits as complete each day
- View a weekly streak calendar
- Simple dashboard showing current streaks

**Explicitly out of scope for MVP:**
- Multi-user / auth
- Mobile app
- Notifications / reminders
- Analytics beyond streak count

## Roadmap

**Phase 1 (MVP -- this build):**
- Habit CRUD (create, edit, delete)
- Daily completion toggle
- Weekly calendar view with streak visualization

**Phase 2 (future):**
- Monthly/yearly views
- Habit categories and tags

**Phase 3 (if needed):**
- Export to CSV

## Lessons Applied from Prior Builds

- CSRF protection required on all POST forms (from: autopilot-swarm-orchestration)
- SECRET_KEY must read from environment (from: autopilot-swarm-orchestration)
