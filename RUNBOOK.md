# Runbook — Client Onboarding Pipeline

Notes for anyone (including future me) who needs to operate this thing without having built it.

## Restarting a failed onboarding

Start the dashboard:

```bash
streamlit run dashboard/app.py
```

It opens on `http://localhost:8501`. Find the onboarding by its `crm_deal_id` — the status next to it will say `dead_letter` or `failed` if something's stuck. Expand it, and you'll see which of the 7 steps actually went through (green check) and which one is holding things up.

Click **Run / Retry**. That's it — you don't need to figure out which step failed and re-trigger just that one. The pipeline re-checks every step's status before doing anything, so anything already `completed` gets skipped automatically and it only actually retries from where it stopped. I tested this by forcing a failure on `invoice` mid-run (onboarding DEAL-DASH-002 in my test evidence) — after fixing the simulated outage and clicking Retry, `contract` through `kickoff_meeting` didn't re-run (attempt_count stayed at 1), only `invoice` and `welcome_email` executed.

If the dashboard itself won't load, it's usually because the API isn't up.
 Check with `docker compose ps` first before assuming the dashboard is broken.

## Figuring out why something failed

The Dead Letter Queue table in the dashboard shows the error message directly — no need to dig through logs for the common case.

If you need more detail, or the dashboard is down, query it straight from the database:

```bash
docker compose exec db psql -U onboarding_user -d onboarding_db -c "SELECT * FROM dead_letter_events WHERE resolved = false;"
```

There's also a log line for every failure, since a human should get pinged when something dies for good:

```bash
docker compose logs api
```

Grep for `SUPERVISOR ALERT` — each one has the step name, the deal ID, and the actual exception message. Right now this just goes to the container logs, not to Slack or email — that's the honest state of it. Swapping in a real Slack webhook later is a one-function change in `alerting.py`; nothing else in the pipeline needs to know.

## Rolling back a step manually

There's no automatic rollback — everything here is manual, and for one step there's genuinely nothing to roll back.

| Step | What to do |
|---|---|
| contract | Nothing automatic. If a contract went out and shouldn't have, that's a manual conversation with the client, not a database fix. |
| drive_folders | Delete or archive the folder from Drive directly. |
| project_board | Archive the board. |
| communication_channel | Archive the Slack/Teams channel. |
| kickoff_meeting | Cancel the calendar invite. |
| invoice | Cancel it, but only if it's still a draft — if it's already sent, same situation as the contract. |
| welcome_email | Can't unsend it. If it went out with wrong info, follow up with a correction email — that's outside what this system handles. |

## What this system actually is right now (don't oversell it)

All seven steps currently run against mock providers — `mock_provider.py` fakes the external call and hands back a fake `external_id`/`external_url` in the same shape a real API would. No real email gets sent, no real Drive folder gets created. This was a deliberate scope decision given the timeline, not an oversight — the point of this phase was proving the state machine (idempotency, locking, retry, dead-lettering) actually holds up under a forced mid-pipeline failure, which it does.

Swapping a mock for the real thing (Google Drive, Slack, an actual e-signature API) means writing one new function that returns `{"external_id": ..., "external_url": ...}` — `orchestrator.py` doesn't change. The contract step is the one I'd expect to take the longest to wire up for real, since it depends on an e-signature webhook completing asynchronously, possibly days later — the current mock completes it instantly, which the real flow won't.

One thing to watch for if this is ever run under real concurrent load: the row lock (`with_for_update`) blocks a second worker from touching the same step while the first is running, but it doesn't queue them nicely — the second request will just come back `busy`. Fine for a dashboard button, not fine if you're calling this from something that expects a guaranteed eventual result.