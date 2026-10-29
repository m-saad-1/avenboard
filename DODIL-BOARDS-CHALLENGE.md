# Dodil Boards Challenge: build the Trello replacement

> **How to use this file:** download it, put it in an empty project folder, and
> give it to your AI assistant (Claude Code, Claude, ChatGPT or Cursor) with
> *"Read DODIL-BOARDS-CHALLENGE.md and help me build this, step by step."*
> It is written for you **and** for your assistant.

Prize: **$100** to the winner, plus a paid follow-up project. The winning board
becomes the official Dodil template, credited to you.

---

## 1. What you are building

A team task board that anyone can **remix** (copy into their own Dodil
organization with one command) and have running in minutes. Someone says
*"I need a Trello"*, and the answer is *"here's one, remix it, it's yours."*

### Required core

| Area | What it must do |
|---|---|
| People | An owner invites members. Roles: `owner`, `member`, `viewer`. A viewer can't edit. Only the owner manages members. |
| Boards | Boards → lists → cards. A card has a title, description, assignee, due date and labels. Cards move between lists (drag and drop on the web page). |
| History | Every change to a card is recorded: who, when, what changed. |
| MCP | Claude or ChatGPT can use the board through MCP, with real actions: *"what's on my plate this week?"*, *"add a card 'Send invoice' to Doing on the Ops board"*, *"move card 12 to Done"*, *"what's overdue?"*. The AI only sees boards the signed-in person can see. |
| Web | A simple web page that does the same things. |

### Extras (scored, not required)

- AI: *"turn this card into a checklist"*, *"find cards like this one"* (search
  by meaning), a short daily summary of a board.
- Card dependencies: *"blocked by"* links, and *"what is blocking the launch?"*
- Overdue cards flagged automatically.

---

## 2. The rules (an entry that breaks one is not judged)

1. **Public repo on Dodil Git** (git.dodil.io) in your own Dodil organization,
   MIT licence, tagged `dodil-challenge` and `dodil-challenge-boards`.
2. **Dodil cloud services only:**
   - **DataK3** for all data. No outside database.
   - **appid** user pool for sign-in. No home-made login, Auth0, Firebase or similar.
   - **Ignite** runs the app.
   - **Dodil Models** for AI. No OpenAI, Anthropic or other API keys.
3. **Deployed by Dodil Git CI** (push → build → deploy) to a live Ignite URL.
4. **One MCP endpoint** whose tools are actions (`move_card`, `assign_card`),
   never raw table access.
5. **Remixable:** a valid `.dodil/remix.yaml`. We remix your repo into a fresh
   organization ourselves, and it must come up live, with its tables and sign-in.
6. **Your own name and design.** No Trello name, logo or artwork in the app.

---

## 3. How to build it

### Fastest start: remix the starter

This repository (https://git.dodil.io/dodil/boards-challenge) is a small,
working, remixable app with sign-in, DataK3, Dodil Models and MCP already wired,
in the structure below. Remix it into your org and build your board on top:

```bash
dodil update                     # CLI 0.1.89 or later
dodil git remix dodil/boards-challenge --to-org <your-org> --name <your-repo>
```

Your remix is your entry: make it public and tag it when you're ready (see
"Publish your entry"). Starting from scratch is fine too, as long as you follow
the rules.

### Stack and structure

- **Python** backend, **FastAPI** recommended.
- **Light Domain-Driven Design.** The web routes and the MCP tools are two thin
  doors onto the **same use cases**, so every rule lives in one place:

```
app/
  domain/          Board, BoardList, Card, Membership, the rules
                   (a viewer can't move a card, only the owner invites)
  application/     use cases: create_board, add_card, move_card,
                   assign_card, list_my_cards, list_overdue
  infrastructure/  DataK3 repositories, appid identity, Dodil Models client
  web/             FastAPI routes  -> call application/
  mcp/             MCP tools       -> call application/
tests/             the main rules: roles, moving cards, visibility
schema.sql         the tables (created by the remix)
.dodil/remix.yaml  what a remix creates
.dodil/deploy.yaml how CI deploys it
README.md
```

- **Tests** for the main rules.
- **Documentation:** a README (what it is, how to run it, how to remix it, what
  you'd improve) and short notes on your main design decisions.

### Your best guide: the Dodil MCP connection

Connect Dodil to your assistant, and it can read Dodil's guides and run every
Dodil command for you.

```bash
# 1. Sign up free at https://dodil.io
# 2. Install the CLI and sign in
curl -fsSL https://cli.dodil.io | bash
dodil auth login
# 3. Connect your assistant (Claude Code shown)
claude mcp add dodil -- dodil mcp
```

Then ask your assistant to read these three guides **before writing code**:

| Guide | CLI | MCP resource | What it covers |
|---|---|---|---|
| Build | `dodil guide` | `dodil://build` | Sign-in through the gateway, one `/mcp` beside the routes, deploy via Git CI, the rules to copy |
| Remix | `dodil guide remix` | `dodil://git/remix` | Every `remix.yaml` field, a complete minimal template, how sign-in is set up after a remix |
| Data | — | `dodil://k3/sql` | DataK3's SQL, vector search and graph over the same rows |

### Facts to build on

- **Data:** DataK3 speaks the Postgres wire protocol at `pg.uk-lon-1.dodil.io:5432`
  (`sslmode=require`). The database name is your bucket. Every table needs a
  **primary key**, and you should choose the key yourself (no `SERIAL`).
- **AI:** Dodil Models is OpenAI-compatible at `https://api.dodil.io/v1`
  (`POST /chat/completions`, `/embeddings`) with a service-account token as the
  bearer. Chat model `kimi-k2.6`; embeddings `jina-embeddings-v4`. The gateway
  wraps the OpenAI body as `{"status": ..., "data": {...}}`, so unwrap `data`
  before reading `choices` (the starter's `infrastructure/dodil.py` shows how).
- **Who is signed in:** with a user pool attached, the Dodil gateway signs the
  person in and passes their identity to your app. **Don't write login code.**
  See `dodil://build`.
- **Credentials:** the remix generates the app's service account and puts its
  ID and secret into the repo's CI secrets. `deploy.yaml` hands them to the app
  as `DODIL_SERVICE_ACCOUNT_ID` / `DODIL_SERVICE_ACCOUNT_SECRET`. Never commit a
  secret.

### Make it remixable

The remix guide (`dodil guide remix`) has a complete minimal `remix.yaml` +
`deploy.yaml` + `schema.sql` for exactly this shape of app (one bucket, one
user pool, one service account with data and AI access). Start from it. Three
things that catch people:

1. **Name budget:** the bucket `<repo>-data` must be at most 25 characters,
   so keep your repo name to **18 characters or less** (e.g. `team-boards`).
2. Keep `on_conflict: fail` (the default) for the bucket and pool your
   `deploy.yaml` names.
3. After a remix, sign-in needs one documented step: add the app's callback URL
   to the pool (the remix guide, "After the remix"). **Say this in your README.**

Check your template as often as you like:

```bash
dodil git remix check <your-org>/<repo>          # valid / invalid + every error
dodil git remix plan <your-org>/<repo> --to-org <a test org>   # creates nothing
```

### Publish your entry

```bash
# Started from the starter? Your repo already exists in your org:
dodil git repo visibility <your-repo> public
# Started from scratch? Create it public instead, then push:
#   dodil git repo create <your-repo> --visibility public
dodil git repo topics <your-repo> set dodil-challenge,dodil-challenge-boards
dodil git remix check <your-org>/<your-repo>
```

### Become a Dodil partner (recommended, do it at the start)

Apply to the Dodil partner programme with the same organization you build in.
Partners earn from the clients they bring to Dodil, and the winner's paid
follow-up project runs through the partner deal tools.

| What partners get | Number |
|---|---|
| Referral commission | 15% of each invoice your referred clients pay, for 12 months (24 at Premier) |
| Managed clients | Up to 25% off what your managed clients use |
| Delivering projects for clients | 93.5% of the client price, by default |

All numbers and rules: https://partner.dodil.io/docs/programme-numbers

How to apply (you must be the account holder of your organization, which by
default is whoever created it):

- **Web:** sign in at https://partner.dodil.io with your organization, open
  **Apply**, fill in the form and accept the Partner Programme Agreement.
- **CLI:**

```bash
dodil partner terms show --kind programme      # read the agreement first
dodil partner apply --company "Your Studio" --country SG --website https://you.example \
  --expected-clients 3 --message "Dodil Boards Challenge entrant" --accept-terms
dodil partner status                            # follow the review
```

Dodil reviews every application. Applying is free, and it's not required to
enter the contest.

---

## 4. How to enter

Submit on Freelancer. **The only requirement is the link to your public repo on
Dodil Git.** We remix it ourselves to judge it.

- [ ] **required:** your public repo link (`https://git.dodil.io/<your-org>/<your-repo>`)
- [ ] optional: the live link, with test logins for an owner and a member
- [ ] optional: a short screen recording of it working from Claude or ChatGPT
- [ ] optional: 5 honest lines on what was hard (we read every one)
- [ ] optional: say if you applied to the partner programme

Images, mockups and documents without a repo link can't be judged.

## 5. How we judge

**The gate:** we remix your repo into a fresh organization, follow your README's
post-remix step, and sign in. If it doesn't come up, the entry stops there.

| Points | What |
|---|---|
| 30 | The core works and roles hold: a viewer can't edit, nobody sees boards they're not on |
| 25 | The MCP actions are real and useful from Claude or ChatGPT |
| 20 | Code quality: clear DDD layers, use cases shared by web and MCP, tests, documentation |
| 15 | The extras |
| 10 | Simplicity and polish |

A clean, working core beats a big broken board.

## 6. After the contest

The winner's board is published as the official Dodil template, credited to
you, and the winner gets a paid follow-up project to harden it. Strong entrants
are invited to the Dodil partner programme.

Questions: ask on the contest's Freelancer page. Stuck on Dodil itself? Put it
in your honest notes. That feedback is part of why we run this.
