# Service accounts & roles

A service account (SA) is a machine identity — a client id + secret — for
headless auth and for code that runs on Ignite (or any remote environment) and
needs to call K3 / models / scriptum on its own behalf.

There are two distinct auth needs:
- **Deploy-time** (who deploys the app): a human/agent, via user login or an SA.
- **Runtime / workload** (the deployed app calling a service): the app itself,
  which MUST use an SA — it cannot borrow the deployer's user token.

## The workload pattern (app on Ignite -> calls K3)
1. Create an SA:            auth_service-account_create args:["<name>"]   # a NAME; store the id it returns
   -> returns id + uuid + SECRET (shown once — save it).
2. Grant it a role for each service it will call (see the catalog below). Roles
   are ADDITIVE — grant-role keeps the roles the SA already has:
   auth_service-account_grant-role args:["<sa-id>","<service-id>","<role>"]
   e.g. args:["<sa-id>","k3-authorization-service","k3.editor"]
   Also: auth_service-account_revoke-role (remove one) and
   auth_service-account_set-roles args:["<sa-id>","<svc>:<role>","<svc>:<role>"]
   to set several at once. (The IAM permissions API is a declarative SET; the CLI
   does read-modify-write so grant/revoke don't clobber other roles. Each service
   role also lands in the token's audience, so a bare client_credentials exchange
   then reaches every granted service — no scope/audience params needed.)
3. Give the app the SA creds as RUNTIME ENV, the secret BY REFERENCE (never
   hardcoded, never a literal in a tool argument):
     printf %s "<secret>" | dodil ignite secret create <app>-sa-secret --type env --from-stdin
     ignite_app_* env:["DODIL_SERVICE_ACCOUNT_ID=<full id: name@<org>.sa>",
                       "DODIL_SERVICE_ACCOUNT_SECRET=secret://<app>-sa-secret"]
   The app's config holds only the reference; the value is resolved into the pod
   at deploy, and a missing secret fails the deploy naming it. NOT
   ignite_build_secrets_set — build secrets never reach the running app.
4. In the app, exchange the SA creds for a token and call the service:
   POST https://id.dodil.io/realms/dodil/protocol/openid-connect/token
     grant_type=client_credentials, client_id=<FULL serviceAccountId>, client_secret=<secret>
   -> access_token ; then call the service with Authorization: Bearer <token>.
   (This is the same client_credentials grant the CLI uses to refresh.)

Concrete example — call a dodil model from a deployed app (OpenAI-compatible):
    import os, requests
    from openai import OpenAI
    token = requests.post(
        "https://id.dodil.io/realms/dodil/protocol/openid-connect/token",
        data={"grant_type": "client_credentials",
              "client_id": os.environ["DODIL_SERVICE_ACCOUNT_ID"],
              "client_secret": os.environ["DODIL_SERVICE_ACCOUNT_SECRET"]},
    ).json()["access_token"]
    client = OpenAI(base_url="https://api.dodil.io/v1", api_key=token)
    resp = client.chat.completions.create(
        model="kimi-k2.5",
        messages=[{"role": "user", "content": "Hello!"}],
    )
The same token (Bearer) works against K3 and scriptum APIs too — grant
the SA the matching role for each service it calls (see the catalog below).

## Scoping a role to specific apps/resources (conditions on a DRN)
Only CONDITIONABLE roles can be scoped (list-roles marks them, e.g.
ignite.app-viewer / ignite.app-developer); org-wide-only
roles (e.g. ignite.model-user / ignite.admin) reject a condition. A conditionable
role with no "on" applies ORG-WIDE — to EVERY resource of that service (e.g. ALL
ignite apps). To limit it, attach a condition on the resource's DRN with "on":
   auth_service-account_grant-role args:["<sa-id>","ignite-authorization-service","ignite.app-developer"] on:["resource=<drn>"]
- on:["resource=<drn>"] is repeatable — multiple DRNs are OR-matched ("any of
  these apps"). Repeating grant-role adds DRNs to the role's allowlist.
- Get an app's DRN from ignite_app_get / ignite_app_list (the "drn" field:
  drn:dodil:ignite:<org>:app/<app>).
- ⚠️ Omitting "on" grants the role ORG-WIDE (all apps). Always scope a workload
  SA to only the app(s) it serves — least privilege.
- Enforced today for ignite apps and scriptum (more services coming).
  grant-role, revoke-role, and rotate PRESERVE conditions on the SA's other roles.
- Sub-resources (iam >= 1.5.0): the DRN may name an UNREGISTERED child of a
  registered resource — iam auto-registers it under its parent (no pre-step).
  K3 forms: …:bucket/<b>/dir/<prefix>/ (prefix MUST end '/'; iam appends it and
  stores the canonical DRN — without it dir/raw would also cover raw-secrets/)
  and …:bucket/<b>/table/<t> (one segment). A table grant covers RPCs that name
  the table on the wire (GetRow/Upsert/Delete); SQL Query/Execute are
  database-level and need a bucket grant today.
- Same model applies to USERS (the permissions API is shared). Manage humans with
  auth_user_*: auth_user_invite args:["<email>"] [role:["<svc>:<role>"] on:["resource=<drn>"]]
  to invite (optionally with scoped roles), auth_user_list / auth_user_list-invites /
  auth_user_revoke-invite args:["<code>"], and auth_user_grant-role /
  auth_user_revoke-role / auth_user_roles args:["<user-id>", ...] with the same
  on:["resource=<drn>"] scoping. A user role is org-wide unless conditioned on a DRN.
  auth_user_remove args:["<email>"] yes:true removes a member from THIS org only
  (their account and other orgs are untouched); the server refuses the org's creator.

## The client id is the FULL serviceAccountId — not the name you created
IAM assigns every SA id: create "my-sa" and its serviceAccountId is
"cli-my-sa@<org>.sa" (older ids end .svcacc.dodil.io). Omit the name and IAM
picks one. NEVER build an id from a name — use the one create returns. THAT full string is the client_id for the
token endpoint, --service-account-id and DODIL_SERVICE_ACCOUNT_ID — the bare
name is rejected (401 invalid_client). Copy it from the create output, or
refetch it with auth_service-account_get args:["my-sa"] / auth_service-account_list.
An app or CI job that stored a bare id must be updated to the full one.

## Identifier — pass the id OR the uuid, either works
Every SA has two handles: the serviceAccountId (the full client id above) and a
uuid (both shown by list/create/get). The underlying IAM endpoints are picky and
INCONSISTENT about which one they want — get/roles key off the name, delete keys
off the uuid — but you do NOT need to track that: the CLI/MCP resolves whatever
you pass (via list) to the identifier each endpoint needs. So pass EITHER the id
or the uuid to ANY tool below (get, roles, grant-role, revoke-role, set-roles,
rotate, delete) and it just works — e.g. take the uuid straight from list and
hand it to delete, or the name, either is fine. (A stale-listing race is the only
caveat — retry if a just-created SA isn't resolvable yet.)

## Commands
- auth_service-account_create args:["<name>"]            # IAM assigns + returns the id; secret shown once; no name = IAM picks one
- auth_service-account_list                              # id + uuid per SA
- auth_service-account_get args:["<id-or-uuid>"]         # either handle
- auth_service-account_delete args:["<id-or-uuid>"] yes:true   # either handle; refused without yes
- auth_service-account_rotate args:["<id-or-uuid>"]      # new secret, same id + roles
- auth_service-account_list-roles                        # the org's role catalog (live)
- auth_service-account_roles args:["<id-or-uuid>"]       # roles a SA currently has
- auth_service-account_grant-role args:["<id-or-uuid>","<service-id>","<role>"]

CLI/MCP-created accounts are name-prefixed (default "cli-") so they're
identifiable in the list; a bare id "foo" becomes "cli-foo" (override the prefix
with DODIL_SA_PREFIX, or pass a full id to bypass). There is no regenerate-secret
API, so rotate = delete + recreate-same-id + re-grant roles (brief existence gap;
update the consumer with the new secret afterward).

## Tie an SA to an app, and clean it up on teardown
Name an app's SA after the app (e.g. auth_service-account_create args:["<app>-sa"];
CLI-created ids are also prefixed "cli-", so it lists as cli-<app>-sa). There is
no automatic app->SA cleanup, so when you DELETE an app, delete its SA too:
  auth_service-account_list filter:"<app>"      # find the app's SA(s) + uuid
  auth_service-account_delete args:["<uuid>"] yes:true   # remove each
Leaving the SA behind is a dangling credential — always tear it down with the app.

## Roles (grant the least privilege the app needs) — fetch the live set
Roles are per service and change per org, so ALWAYS get the current set from
auth_service-account_list-roles rather than a hardcoded list — it returns each
serviceId / role / description AND whether the role is conditionable. Grant one
role per service the app calls (e.g. k3-authorization-service, ignite-,
scriptum-, iam- (org.member|org.admin|org.owner)).

Conditionable roles can be scoped to a specific resource with on:["resource=<drn>"]
(list-roles marks them, e.g. ignite.app-viewer / ignite.app-developer, and the
three k3 roles at bucket, dir-prefix or table granularity); the rest are
org-wide only. See "Scoping …" above.

### Least privilege first — but don't get stuck
Grant the NARROWEST role that fits what the app does (list-roles descriptions say
what each covers — e.g. a read-only viewer if it only reads, a writer/developer if
it writes). Prefer a CONDITIONABLE role scoped to the specific resource(s) it
touches (on:["resource=<drn>"]) over an org-wide grant. Do NOT default to admin.
BUT don't spin on permission errors: if a call still 403s after a reasonable role,
grant a broader role for that service (e.g. the domain's admin) to UNBLOCK, confirm
the flow works, then NARROW back down to the least role that still works (grant the
smaller role, revoke-role the admin). Getting unblocked then tightening beats
guessing role-by-role — and beats leaving admin in place.

Managing service accounts is high-privilege (it mints credentials). It requires
the caller to have IAM admin rights in the org; the secret is returned only once.