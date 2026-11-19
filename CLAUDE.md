## Project manager (log items for Justin)
Justin tracks work in his project manager at https://justin-project-manager.fly.dev. Log things he
should see there, instead of only mentioning them in chat. This repo is `justingehrts/graph-maker`.

- **At the start of a session,** read the API guide (current fields, kinds and examples), then this
  repo's open follow-ups, and act on those that are in scope:
  `curl -s https://justin-project-manager.fly.dev/api/v1`
  `curl -s "https://justin-project-manager.fly.dev/api/v1/items?repo=justingehrts/graph-maker&open=1&kind=followup"`
- **What to log:** `todo` = something only Justin can do · `idea` = an improvement noticed but not
  asked for · `bug` = a problem spotted but not fixed · `followup` = work a later session should
  pick up. Check the open list first. One item per thing, short titles, details in notes. If you
  made an artifact, PR or doc for an item, attach its link (see the guide).
- **Judgment:** log what Justin would want to find later, not routine progress. No secrets,
  personal data or large pastes. Before ending a session with loose ends, log them as `followup`
  or `todo` and say so in chat.
- **Auth:** the network proxy adds the token for host `justin-project-manager.fly.dev`. If a request
  comes back 401, ask for that credential (request_credential tool, Bearer). Never print, log or
  commit the token.
- **Command shape (so this repo's permission rules allow it):** one line per call, with the full
  `https://justin-project-manager.fly.dev/api/v1...` address written right after `curl -s` (GET,
  quoted when it has `?` or `&`), `curl -s -X POST`, or `curl -s -X PATCH`. No variables for the
  address, no line continuations, nothing chained with `&&` or `;`.
- Sessions can update or finish only items they created; Justin's tasks are read-only and nothing
  can be deleted.
