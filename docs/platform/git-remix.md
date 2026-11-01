# Making a repo remixable — `.dodil/remix.yaml`

A **remix** copies a template repo into another org and gives the copy what it
needs to run there: it forks the repo, creates the buckets, user pools and
service accounts the template declares, writes the generated credentials into
the new repo's CI secrets (never shown to anyone), and deploys it. One file
makes a repo a template: `.dodil/remix.yaml` at the root of the default branch.
`.dodil/deploy.yaml` then deploys the copy like any other repo.

Remixing (the other side): `dodil git remix <org>/<repo> --to-org <org>`, which
shows the plan, asks you to confirm and follows the run. This page is for the
AUTHOR.

## The feedback loop

1. Write `.dodil/remix.yaml` (and the schema file it names), commit, push.
2. `dodil git remix check <repo>` prints `none` (no file: forkable, not
   remixable), `valid` (with what it would create) or `invalid` with every
   error. The commit also gets a `dodil-ci/remix` check, red when invalid.
3. `dodil git remix plan <repo> --to-org <a test org>` shows exactly what a
   remix would create, reuse or be blocked by, in a real org, and creates
   nothing. Then remix it into that org for real, and fix what fails.

Every key is checked strictly: an unknown key (a typo) fails the file. Secret
VALUES never go in it, only names.

## Every field

```yaml
version: 1                       # required; the only version

description: Boards for small teams          # optional; shown on the Remix button and in explore
topics: [boards, starter]        # optional; ≤ 20, each a-z 0-9 '-', not starting with '-';
                                 # keep each ≤ 35 chars (the limit for a repo's own topics)
                                 # (the repo's own topics win; these are the fallback)

fork:
  on_conflict: suffix            # the new repo's name if taken: suffix (DEFAULT here) | fail
                                 # (suffix makes it board-2 … board-9, then blocks)

required_secrets:                # values the REMIXER supplies (their own API keys) — names only
  - name: STRIPE_API_KEY         # [A-Za-z0-9_], not starting with a digit, ≤ 128
    description: Payments        # optional; shown in the plan
    url: https://dashboard.stripe.com/apikeys   # optional; where to get one
                                 # The run waits (waiting_for_secrets) until each is set on the
                                 # new repo (dodil git secret set <repo> NAME) or in the org.

provision:                       # what the remix CREATES in the target org (≤ 16 in total)
  buckets:                       # K3 buckets (SQL tables, vectors, objects)
    - name: "${{ dodil.repo }}-data"
      on_conflict: fail          # fail (DEFAULT) | reuse | suffix
      schema: schema.sql         # optional; a SQL file in the repo (relative, no '..'),
                                 # applied once, only to a bucket THIS run creates.
                                 # On reuse, its CREATE TABLEs must already exist there.
  user_pools:                    # AppID user pools (sign-in for the app's users)
    - name: "${{ dodil.repo }}-users"
      on_conflict: fail          # fail (DEFAULT) | reuse | suffix
      roles: [admin, member]     # the roles the pool defines (a-z 0-9 '-')
  service_accounts:              # credentials the PLATFORM generates for the app
    - name: "${{ dodil.repo }}-app"
      grants:                    # at least one; only these:
        - { role: k3.editor, bucket: "${{ dodil.repo }}-data" }   # k3.editor | k3.viewer, on a bucket
                                 # declared ABOVE, written exactly as declared
        - { role: ignite.model-user }   # org-wide, no bucket: the app may call Models,
                                 # token-billed to the remixer's org (shown in the plan)
      secrets:                   # the CI secrets on the new repo that receive the credential
        client_id: DODIL_SERVICE_ACCOUNT_ID
        client_secret: DODIL_SERVICE_ACCOUNT_SECRET
```

Rules the file is checked against:
- **Names** may contain only `${{ dodil.repo }}` (the new repo's FINAL name,
  after its own suffix) and `${{ dodil.org }}` (the target org). They render
  lowercase `a-z 0-9 -`, at most 63 characters, never `org/…`: a remix only
  creates in the org it goes into.
- **Bucket names are at most 25 characters once rendered** (k3 stores a bucket
  as `<org id>--<name>` under S3's 63). A longer one blocks the plan with
  `too_long`, whatever `on_conflict` says.
- A grant names a bucket this file declares, never an existing one. A generated
  credential on a REUSED bucket blocks (`grant_on_reused`).
- No bucket, pool, account or secret name twice. The remixer's secrets and the
  generated ones share the new repo's one secret store.

### The 25-character budget, worked out

`${{ dodil.repo }}-data` is the repo name plus 5 characters, so the repo name
gets at most **20**:

| new repo name | bucket | length | plan |
|---|---|---|---|
| `team-boards` | `team-boards-data` | 16 | ok |
| `team-boards-2` (name was taken; fork `suffix`) | `team-boards-2-data` | 18 | ok |
| `quick-kanban-for-teams` | `quick-kanban-for-teams-data` | 27 | blocked `too_long` (max 25) |

The remixer can pick another name (`--name`), and the fork's suffix adds 2
(`-2`), so keep a template's own name to **18** characters or less with a
`-data` bucket. Or use a shorter suffix: `${{ dodil.repo }}-db` leaves 22.

## How remix.yaml meets deploy.yaml

Each generated credential lands in the new repo's **CI secrets** under the
names in `secrets:`. The deploy reads CI secrets with `${{ secrets.NAME }}`, so
`.dodil/deploy.yaml` hands them to the app as env. `name`, `group`,
`user_pool` and env values also take `${{ dodil.repo }}` / `${{ dodil.org }}`,
so every copy points at its OWN bucket and pool:

```yaml
version: 1
create_if_missing: true                    # the copy's first deploy creates the app
apps:
  - name: "${{ dodil.repo }}"
    image: "{registry}/{org}/{repo}:{sha}" # where the build workflow pushes
    port: 8080
    health: { path: /healthz }
    user_pool: "${{ dodil.repo }}-users"   # AppID sign-in in front of the app
    env:
      DODIL_SERVICE_ACCOUNT_ID: "${{ secrets.DODIL_SERVICE_ACCOUNT_ID }}"
      DODIL_SERVICE_ACCOUNT_SECRET: "${{ secrets.DODIL_SERVICE_ACCOUNT_SECRET }}"
      K3_BUCKET: "${{ dodil.repo }}-data"
when:
  branches: [main]
  require_checks: [build/build]            # deploy only what built
```

The build workflow tags the image with the env the runner injects,
`$DODIL_GIT_ORG/$DODIL_GIT_REPO_NAME` (never `github.repository`):
`dodil git ci init <dir> --app <name>` writes both files, then edit them as
above. Full deploy.yaml reference: `dodil git ci init --help` and the CI
section of dodil://recipes.

**Keep `on_conflict: fail` for any bucket or pool the deploy names.** With
`suffix`, the remix may create `team-boards-data-2` while deploy.yaml still says
`${{ dodil.repo }}-data`. The fork's own name may suffix freely: everything
renders from its final name.

## A complete minimal template

An app with one bucket and its schema, one user pool, and one account that
reads and writes the bucket and calls Models. The repo holds:

```
.dodil/remix.yaml
.dodil/deploy.yaml
.github/workflows/build.yml    # dodil git ci init writes it
schema.sql
Dockerfile, the app …
```

`.dodil/remix.yaml`:

```yaml
version: 1
description: Kanban boards for small teams
topics: [boards, kanban, starter]
provision:
  buckets:
    - name: "${{ dodil.repo }}-data"
      schema: schema.sql
  user_pools:
    - name: "${{ dodil.repo }}-users"
      roles: [admin, member]
  service_accounts:
    - name: "${{ dodil.repo }}-app"
      grants:
        - { role: k3.editor, bucket: "${{ dodil.repo }}-data" }
        - { role: ignite.model-user }
      secrets:
        client_id: DODIL_SERVICE_ACCOUNT_ID
        client_secret: DODIL_SERVICE_ACCOUNT_SECRET
```

`.dodil/deploy.yaml`: the one in the previous section, as is.

`schema.sql`: plain `CREATE TABLE` statements (`IF NOT EXISTS` is fine); the
plan reads their table names to check a reused bucket. K3's SQL dialect and
types: dodil://k3/sql.

```sql
CREATE TABLE IF NOT EXISTS boards (id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT);
CREATE TABLE IF NOT EXISTS cards  (id TEXT PRIMARY KEY, board_id TEXT NOT NULL, title TEXT, status TEXT, position BIGINT);
```

In the app, sign in to Dodil as the service account with the two env vars (the
client-credentials flow of dodil://auth/service-accounts), then use K3 on
`K3_BUCKET` and Models with the same token.

## After the remix: let people sign in

The deploy registers the app's sign-in callback
(`https://<app host>/.dodil/auth/callback`) on its `user_pool` itself (from
git 1.6.11), keeping the pool's other entries; the deploy log says "already
lists the sign-in callback" on later deploys. Once the run has succeeded, in
the org it was remixed into:

1. If the deploy log says the callback was "not registered", run the command
   that line prints, once.
2. Let the first people in. A new pool allows public signup by default; if it
   is off (`--allow-signup=false`, admin-provisioned only), invite them:
   `dodil appid user create <repo>-users <email> --roles admin` (no
   `--password`: they set one through the forgot-password flow).
3. Signing in through Claude.ai or another MCP client: the client registers
   itself and arrives PENDING. Approve it once:
   `dodil appid client list <repo>-users`, then
   `dodil appid client approve <repo>-users <client-id>`.

## Publishing a template, and a challenge entry

The author:

```
dodil git repo create team-boards --visibility public
# push the app, remix.yaml, deploy.yaml, workflow
dodil git repo topics team-boards set dodil-challenge,dodil-challenge-boards
dodil git remix check team-boards
```

A remixer (the remix IS the submission: it goes public, with the topics, only
once its deploy succeeded, so a failed deploy is never public):

```
dodil git remix <org>/team-boards --to-org <their org> --visibility public --topics dodil-challenge,dodil-challenge-boards
```

Who may: anyone who can read the template (public = anyone signed in), with
`git.admin` in the target org.
