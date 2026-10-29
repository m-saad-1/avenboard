# Dodil Boards Challenge

Build **the Trello replacement** on Dodil: a team task board anyone can remix
into their own Dodil organization and have running in minutes.

**Prize:** $100 to the winner, plus a paid follow-up project. The winning board
becomes the official Dodil template, credited to its builder.
Contest: https://www.freelancer.com/contest/contest-build-the-trello-replacement-on-dodil-run-it-from-claude-chatgpt-2799133

**All the rules and steps: [DODIL-BOARDS-CHALLENGE.md](DODIL-BOARDS-CHALLENGE.md).**
Give that file to your AI assistant: *"Read DODIL-BOARDS-CHALLENGE.md and help
me build this, step by step."*

## This repo is also the starter

It is a small, working, remixable app: sign-in, data, AI and MCP already wired.
Your job is to turn it into a great board. Remix it into your own organization:

```bash
dodil update                                   # CLI 0.1.89 or later
dodil git remix dodil/boards-challenge --to-org <your-org> --name <your-repo>
```

The remix creates, in your org: the repo, a DataK3 bucket `<repo>-data` with the
tables from `schema.sql`, a user pool `<repo>-users`, and a service account with
access to the bucket and to Dodil Models. Then CI tests, builds and deploys it.
Keep `<your-repo>` to **18 characters or less**.

After the remix, one step lets people sign in (until the platform does it for
you): add the app's callback URL to the pool. Run `dodil guide remix` and follow
"After the remix: let people sign in".

## What's inside

```
app/boards/
  domain/model.py            Board, Card, Role and the rules (a viewer can't edit,
                             only the owner manages members, lists are fixed)
  application/use_cases.py   every action: create_board, add_card, move_card,
                             add_member, show_board, suggest_checklist (AI)
  application/ports.py       what the use cases need (repository, AI assistant)
  infrastructure/dodil.py    service-account token, DataK3 connection, Dodil Models
  infrastructure/repository.py  boards, cards, members, activity in DataK3 tables
  doors/web.py               JSON routes + a tiny page   -> call the use cases
  doors/mcp.py               MCP tools for Claude/ChatGPT -> call the same use cases
  doors/identity.py          who is calling (the gateway's X-Dodil-User header)
  main.py                    wires it together, /mcp, sign-in metadata, /healthz
tests/test_boards.py         the rules, through the use cases and both doors
schema.sql                   the tables, created by the remix
.dodil/remix.yaml            what a remix creates
.dodil/deploy.yaml           how CI deploys every copy
.github/workflows/ci.yml     test -> build -> (deploy by Dodil Git CD)
```

## Run it locally

```bash
cd app
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest -q ../tests            # no Dodil account needed: fakes for data and AI
```

To run the server against your remixed bucket, set `BUCKET`,
`DODIL_SERVICE_ACCOUNT_ID`, `DODIL_SERVICE_ACCOUNT_SECRET` and
`DEV_USER=you@example.com` (acts as that person without the gateway; local only),
then `uvicorn boards.main:app --port 8080`.

## Connect Claude

The app serves MCP at `https://<your-app-host>/mcp`. Add it as a custom
connector in Claude (or ChatGPT): it asks you to sign in through your pool, then
approve the client once with `dodil appid client list <repo>-users` and
`dodil appid client approve <repo>-users <client-id>`.

## Licence

MIT. See [LICENSE](LICENSE).
