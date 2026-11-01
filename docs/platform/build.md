# Building on Dodil — the model

People ask for "an app", "a system", "a portal", "something to replace the
spreadsheet". Whatever the word, understand the person's need before you build:
who uses it, what they do, what it must remember. Write that down and get a yes
before any code.

**Business software (HR, CRM, contracts, invoicing, the books...)? Read
dodil://erp/build first** (or `dodil guide erp`): most modules already exist as
public, tested bricks to compose, and that method — phase cards, sign-off,
change requests — is maintained in git.dodil.io/dodil/erp-method. Never rebuild a
module from a tutorial or a recipe.

## The lifecycle

    UNDERSTAND  who, what, which records; written down and confirmed
    BUILD       code against the test copy; natural keys; one /mcp beside the routes
    TEST        a test per story and role, in process and against the test copy
    PROVISION   test copy + live copy; MERGE role catalogs, never replace them
    DEPLOY      git push -> the forge's own CI -> registry -> CD (.dodil/deploy.yaml)
    VERIFY      the app reaches its own data; the gateway strips forged headers;
                a real person signs in, and their agent connects
    OPERATE     changes: restate, show the impact, a yes, then the work

**Deploy: dodil git runs the CI itself.** Commit .github/workflows/*.yml and the
forge executes it on push — .github is the workflow FORMAT, not GitHub. Registry
credentials are injected into every job (secrets.DODIL_REGISTRY_URL / _TOKEN —
never create them); jobs show up as checks (`dodil git check list <repo> <sha>`).
Details: dodil://recipes (Git CI).
**Before every push of CI/CD config, run `dodil git ci verify`.** It reads the
workflows and .dodil/deploy.yaml against the repo and the live org and lists every
problem at once. What it catches, because each one cost a day:
  - paths are relative to THIS repo's root: code developed in a monorepo and pushed
    as a subtree split keeps no prefix (paths:, working-directory:,
    cache-dependency-path:)
  - a bucket named in env must exist — create it first
  - PG_HOST/PG_PORT come from `dodil data connect <bucket>`, never from memory: the
    pg wire is 5432; 8443 answers TCP and drops a Postgres client
  - DODIL_SERVICE_ACCOUNT_ID is the FULL id and always travels with its secret
  - ${{ secrets.X }} in deploy.yaml resolves from the REPO's CI secrets
    (`dodil git secret set`), not from ignite secrets
  - deploys ship from when.branches, or the default branch — which must exist
**When it fails anyway, diff before you theorize.** If the org has an app that works,
`dodil ignite app diff <failing> <working>` shows the difference in config and env
(secrets masked). A wrong port found that way takes a minute; found by theory, it
took a rewritten grant, a rebuilt service account and a brief against a platform
that was fine.
**Verify needs a route.** `dodil ignite invoke <app>` always hits POST /,
so give every app a self-check there that opens the bucket with its OWN credential
and reports a row count per table. /healthz deliberately makes no database round
trip — a pod holding a broken credential passes it and looks deployed — and the
public URL answers 401 whether your app is healthy, crash-looping or absent.
**Verify includes their agent.** Claude.ai registers itself (DCR) and arrives
PENDING: it authorizes nobody until you approve it —
`dodil appid client list <pool>`, then `approve <pool> <id>` (appid 0.14, 2026-10-16).

### Rules for every phase
1. **Interactive by default.** One topic per turn, one to three questions, each
   with choices and a recommended default. Say back what you recorded.
2. **The repo remembers, not you.** Keep the decisions and the state in the repo;
   start every session by reading them.
3. **Test copy first; live only on an explicit "go live".** <customer>-dev (bucket,
   pool, app) and <customer>. Local .env points at the test copy ONLY; live
   credentials exist only as secret references in .dodil/deploy.yaml. Say which
   one you are touching in every message.
4. **Show it on localhost** before anything goes live.
5. **Migrations are additive**: ADD COLUMN is cheap; a rename or type change is
   add -> backfill -> switch -> drop later, which is also what keeps
   `ignite version rollback` an actual rollback. VERIFY a migration: CREATE
   TABLE IF NOT EXISTS SKIPS a table it finds, so add a new column as an explicit
   ALTER too, then read the bucket back.

## One customer = one topology

    appid pool <customer>     ONE pool, all their modules -> staff sign in once
      roles = their org chart; permissions <module>:<object>:<verb>
    Ignite group <customer>   ONE staff app serving every module under /<module>
                              and ONE /mcp; split only for a stated reason
                              (independent scaling, a distinct trust boundary)
      staff app:  --user-pool <customer> WITH --allow-unauthenticated: the gateway
                  logs in optionally, strips forged identity headers and injects
                  them when a session or bearer is present; the app's sign-in gate
                  refuses every route without identity except /healthz and
                  /.well-known/oauth-protected-resource (RFC 9728 — connector
                  discovery and the browser redirect need it anonymously; crm-demo
                  v4-v7: anonymous /lead/leads 401 from the app, metadata 200).
                  public_invoke=false is right only for an app with no MCP and
                  no browser sign-in redirect
      public app: ONLY if the app issues links (signing pages, a public form,
                  open/click tracking): a separate app, no pool,
                  public_invoke=true, token links only; it never migrates
    bucket <customer>         ONE bucket = their database. Cross-module JOINs with
                              no ETL is the reason this is on Dodil at all.
    SA <customer>-app         k3.editor on that bucket (+ ignite.model-user if the
                              app calls Models)
    SA <customer>-public      the public app's OWN, narrower one: k3.editor only

MODULES IN ONE APP CALL EACH OTHER IN PROCESS, as the caller: no service client,
no header. Only SEPARATE apps need a machine identity for a
call — a dodil-appid service client, never a forged header: the gateway strips
inbound identity headers, so a fabricated X-Dodil-User passes a local uvicorn and
is a 401 in production:
`dodil appid service-client create <pool> --client-id <id> --role <r>`, a role
holding ONLY what that call needs, its client_credentials token as
`Authorization: Bearer`. A test suite cannot catch this: it fakes the
header and agrees with itself.

Scope each SA to ITS bucket: `--on resource=drn:dodil:k3:<region>:<org>:bucket/<b>`
(also …/dir/<prefix>/ and …/table/<t>, dodil-iam >= v1.5.0; a table grant holds
over gRPC/HTTP only). Then "this app only touches its own data" is enforced by
the doors, not by the app's discipline.

Adding a module = same pool, same bucket, its
roles MERGED into the pool catalog (roles set replaces it: get -> merge -> set).

A POOL WITH NO redirect_uris LOGS NOBODY IN. Every app behind the pool needs
    https://<public_url>/.dodil/auth/callback
on that list (appid settings set REPLACES it: read first). <public_url> is the
host from `ignite app get <app>`'s public_urls — copy it, never assemble it:
the host escapes characters (an org named acme-co appears as acme--co), and a
hand-built URL fails at the sign-in screen ("redirect_uri is not in the pool's
allowlist" — to the person signing in, not to you). And with allow_signup false
(right for a business system) nobody can create their own account: invite at least one user, or a
correct allowlist still admits no one. This is the step most easily skipped:
invoke and a service-client token both go round the browser login. Five modules
were deployed, self-checked and exercised end to end through their APIs before
anyone found the pool had neither redirect_uris nor users. If you cannot hand
someone a URL they can sign into, the module is not verified.

## Invariants — depend on these, never re-derive them

- **No auth code in the app.** The gateway does PKCE and injects X-Dodil-User;
  the app trusts that header and gates by role. See
  dodil://auth/service-accounts for the machine-to-machine half.
- **Every app exposes ONE /mcp calling the same use cases as its routes** —
  tools are use cases (accept_quote), never table CRUD. Machines connect with a
  dodil-appid service client; a PERSON connecting Claude.ai or ChatGPT signs in
  (authorization_code + PKCE) — never a service token, which carries no person
  to scope rows by, so every user's agent would see every row.
- **Natural primary keys; never SERIAL.** DataK3 mints an id when a write omits
  one, so a missing id fails silently.
- **A CLAIM is a PLAIN INSERT** (a number, a one-time action, a retry key): under
  concurrency one writer is acknowledged, the rest get 23505. Never an upsert,
  which lets every writer win (measured 2026-10-17, DataK3 0.2.1).
- **An upsert overwrites EVERY column in VALUES**, whatever SET says (tables#417,
  fixed in 0.2.2, not yet in production): leave insert-only columns out of it,
  and use the repository's upsert, never a hand-written one.
- **64-bit ids travel as JSON strings** (Brick(ids_as_strings=True)). JavaScript
  reads 45665172796086509 as another customer's id (CRM audit, 2026-10-16).
- **No lost updates.** A record two people edit carries a version; an edit sends
  it (If-Match), and a stale one is 409 "changed since you opened it" with nothing
  written (hr SC-HR-08).
- **Retries are safe.** Every non-idempotent command takes an Idempotency-Key (the
  doors add it; claimed by plain INSERT): a client that lost the reply gets the
  first answer, not a second record.
- **sslmode=require (verify-full + sslrootcert in production) and bolt+s://**,
  never prefer (plaintext fallback of an SA secret) or neo4j+s:// (refused).
- **16 concurrent reads per bucket**: hold a client semaphore below it
  (DB_CONCURRENCY=8-10) and retry 40001 / 08006 / 58030 / XX000.
- **DELETE requires a WHERE** (WHERE TRUE for a deliberate clear). **No
  read-your-writes inside an open transaction** — commit, then read.
- **Numeric non-root USER in the Dockerfile** — runAsNonRoot rejects a username and
  fails after a successful image pull. Install every dependency from its pin and copy
  your own code with a glob, never a hand-maintained file list — a dropped module
  crash-loops the pod behind a healthy gateway.
- **Secrets by reference**, never as values: ${{ secrets.NAME }} in
  .dodil/deploy.yaml, and an app env value of secret://<name> (an
  `ignite secret create <name> --type env --from-stdin` secret) when deploying
  by hand. A credential never goes in a command line or a tool argument.
- **Scope every owned read by the caller's identity**, inside the use case — so an
  agent sees exactly what its person sees. A row the caller may not see is 404.
- **Validate the modules TOGETHER**: one app, one bucket, its tests in process
  and live. Modules verified separately are internally consistent and still
  wrong together.

Rule of thumb: if the platform already does it (sign-in, secrets, CI, the three
data pillars), DEPEND on it — never re-implement it. When unsure, ask.

## Then go read

- Business software: dodil://erp/build (the ERP method, from git.dodil.io/dodil/erp-method);
  its phase cards are dodil://erp/phase/<name>, and the rest of the method is
  dodil://erp/file/<path> (dodil://erp/file/modules/lifecycle.md,
  dodil://erp/file/modules/pattern.md, dodil://erp/file/modules/template.md)
- Service accounts and app-to-API auth: dodil://auth/service-accounts
- Making the app remixable (one command gives another org its own copy: bucket,
  user pool, service account, deploy): dodil://git/remix (`dodil guide remix`)
- Worked examples end to end: dodil://blog/recipes (no web access needed) or
  https://blog.dodil.io/llms.txt
