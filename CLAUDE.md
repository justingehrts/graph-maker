## Project manager (log items for Justin)
Justin tracks work in his project manager at https://justin-project-manager.fly.dev. Use its API
to log things he should see, instead of only mentioning them in chat.

- **Auth:** requests need `Authorization: Bearer <token>`. In a cloud session the network proxy adds it
  for you once a credential is saved for host `justin-project-manager.fly.dev`; if a request comes
  back 401, ask for that credential (the request_credential tool, Bearer). Locally, use
  `-H "Authorization: Bearer $PM_API_TOKEN"`. Never print, log or commit the token.
- **Repo name:** use this repo's GitHub name (e.g. `owner/name`). Items land in a project named
  after it, created the first time.
- **At the start of a session:** read open follow-ups and act on them if they're in scope:
  `curl -s "https://justin-project-manager.fly.dev/api/v1/items?repo=OWNER/NAME&open=1&kind=followup"`
- **Log an item** (check the open list first; an identical open title is returned, not duplicated):
  ```
  curl -s -X POST https://justin-project-manager.fly.dev/api/v1/items \
    -H "Content-Type: application/json" \
    -d '{"repo":"OWNER/NAME","kind":"todo","title":"…","notes":"…","due":"fri",
         "session_url":"<this session's link>","file":"path/to/file.py","line":42}'
  ```
  Kinds: `todo` = something only Justin can do (a secret, an approval, a sign-up, a test on his
  phone) · `idea` = an improvement noticed but not asked for · `bug` = a problem spotted but not
  fixed · `followup` = work a later session should pick up. `due` and `priority` are optional.
- **Close or update your own items:** `PATCH /api/v1/items/ID` with `{"done": true}`, `{"status":
  "In progress"}`, or `{"notes_append": "…"}`. Only items sessions created can be changed; there is
  no delete.
- **Judgment:** log things Justin would want to find later, not routine progress. One item per
  thing, short titles, details in notes. No secrets, personal data or large pastes in notes.
  Before ending a session with loose ends, log them as `followup` or `todo` and say so in chat.
- Full reference: `GET https://justin-project-manager.fly.dev/api/v1`.
