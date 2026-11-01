# Implementation and release verification

This is an evidence audit of the local Avenboard implementation against the 1,129-line parent brief and the approved plan. It is not a claim that Dodil deployment or fresh remix has succeeded. The original brief is preserved outside this checkout.

## Evidence and its limits

| Check | Evidence | Meaning |
|---|---|---|
| Original starter baseline | Six original tests passed in an isolated starter checkout at `2815f0bbc39ae589ff78be4dfcd87757e7cfe268` | Existing integrations were inspected before replacement/expansion. |
| Backend | [JUnit results](evidence/backend-results.xml): 56 passed, three live checks skipped | Domain/use cases, authorization, atomic fake repository behavior, MCP transport, indexing and delivery structure tested. Does not prove actual DataK3 transactions. |
| Frontend | TypeScript check and Vite production build pass | Generated contract types compile and same-origin production assets build. |
| Browser | [Playwright results](evidence/browser-results.json): 28 passed, five device-specific cases skipped | Desktop 1440×1000, tablet 820×1180 and mobile Pixel 7; no failures. Pointer/keyboard cases run on desktop/tablet; the separate touch case runs on mobile. |
| Visuals | [Twelve screenshots](screenshots/) | Real Chromium captures of labeled, loopback-only QA fixtures. Light/dark overview, board and card views across three sizes. No simulated deployed screenshots. |
| Local performance | [Six samples](evidence/local-performance.json) | Chromium loopback navigation timings with no CPU/network throttle, fixture data and local assets; neither production measurements nor Lighthouse scores. |
| Python dependencies | [Audit JSON](evidence/python-audit.json) | No known advisories in the resolved runtime dependencies at audit time. |
| npm dependencies | [Audit JSON](evidence/npm-audit.json) | No known vulnerabilities at audit time; the exact dependency tree is locked. |
| Dodil configuration | [CLI output](evidence/ci-verification.txt) | Zero errors, one warning. Account-dependent resource/secret/branch checks skipped. This is not `remix check: VALID`. |
| Source hygiene | [Scoped audit](evidence/source-audit.json), `git diff --check`, Python compilation, Prettier | No matching credential patterns, broken local documentation links or whitespace errors. Pattern scanning is not a comprehensive security audit. |
| Theme text contrast | [Token-pair measurements](evidence/contrast.json) | All 38 checked foreground/background pairs exceed 4.5:1; smallest labels increased to 10px. This is not a complete rendered accessibility certification. |
| Production/live | Three opt-in tests in tests/test_live_contracts.py | Not run: genuine gateway identity, DataK3 rollback/vector/schema, Models envelopes/dimensions. |

Tests use injected identities and a transactional memory repository only in tests. The production application has neither a memory fallback nor DEV_USER authentication. The QA preview visibly identifies its fixture nature and is excluded from the container.

The browser run covers themes/navigation, safe literal content, viewer restrictions, task editing, labels, checklist review/save/edit, invitation creation/revocation, card archive/restore, guarded board deletion, pointer/touch/keyboard movement, list ordering, reload, filtered-reorder restriction, focus restoration, failed-request rollback and two-user stale-move rejection. Native-dialog errors remain visible and dismissible. This is a meaningful workflow sample, not exhaustive certification of every combination of controls or assistive technology.

The final six clean-fixture loopback samples measured LCP of 732–1,176 ms on the desktop viewport and 592–1,388 ms on mobile, CLS below 0.02, and nine resource requests with no external asset requests. These local results vary with workstation load and do not predict network/device/cloud performance. Initial JavaScript is approximately 83.4 kB gzip; board/card/action dialogs load separate chunks. No production performance score is claimed.

## Complete brief coverage

| Source phase | Implemented files/features | Remaining acceptance work |
|---|---|---|
| 0 — Platform/starter | CLI guides and build/remix/SQL snapshots; retained starter architecture; baseline tests | Authenticate, create official destination remix, validate live contracts. |
| 1 — Identity/design | Configurable Avenboard branding, original SVG mark, local Inter/icons, indigo tokens, light/dark layouts | Review actual deployed render and final judge-facing screenshots. |
| 2 — Core | Workspaces, members, invitations/approval, ownership; boards/private ACLs; lists/status; full cards/labels; atomic activity; typed commands | Exercise genuine owner/member/viewer accounts with DataK3. |
| 2.5 — Ordering | Card movement, within-list order, list order, empty targets, touch/pointer/keyboard, explicit controls, filtered-reorder restriction, rollback/conflicts | Verify live persistence/restarts and engine conflict behavior. |
| 3 — Dashboard/UX | Eight requested data areas, My Tasks groups, filters, all navigation, favorites, preferences, validation, native dialogs, refresh behavior | Production performance/capacity and broader assistive-technology review. |
| 4 — AI | Checklist preview/edit/append-save, authorized vector search/index leases, factual board snapshot plus generated summary, read-only recommendations | Confirm actual model names/envelopes/512 dimensions; enable semantic flag only afterward. |
| 5 — Advanced | Acyclic dependencies and blocker traversal/map, server overdue state, activity feed, quick creation, five requested smart filters | Live user demonstration. |
| 6 — MCP | One logical Streamable HTTP endpoint with slash compatibility, both discovery routes, 401 challenge, sixteen authorized tools | Approve real connector and execute eight natural-language conversations through Claude/ChatGPT. |
| 7 — Architecture | Domain/application/infrastructure/doors; shared use cases; parameterized SQL; structured errors; OpenAPI frontend types | Live SQL envelope/compatibility validation. |
| 8 — Platform compliance | Only DataK3 persistence, appid identity, Models AI, Ignite/Dodil Git delivery adapters | Actual deployment/account evidence. |
| 9 — Remixability | Destination-relative schema/pool/service grants/secrets/configuration, additive migration, callback guidance | Authenticated VALID check, fresh-org plan, real remix, deployment and sign-in. |
| 10 — Testing | Domain/permission/activity/MCP/indexing/concurrency/lifecycle tests; responsive browser suite; explicit live tests | Run all live checks and deployed browser role scenarios. |
| 11 — Demo | Opt-in idempotent Acme Studio, three named boards/five lists, all seven named tasks plus redesign/launch examples; relative dates and genuine-owner assignments | Genuine Sarah account and deployed sample demonstration. |
| 12 — Documentation | README's 18 topics, DESIGN's seven topics, MIT, third-party notices, screenshots, migration and submission guides | Fill verified public/live/MCP URLs and optional recording. |
| 13 — Competitive audit | This 24-gate audit and five-category provisional scorecard | Re-score against actual cloud evidence before submission. |

### Required detail inventories

- Three roles: OWNER, MEMBER, VIEWER. Private access, assignment eligibility, sole-owner protection, atomic transfer and membership revocation are enforced by shared use cases.
- Card fields: title, description, assignee, due date, labels, list, integer position, creation/update timestamps and creator; version and workspace card number extend these fields. Detail UI includes the seven requested sections plus checklists/dependencies.
- Eight overview areas: total boards, total tasks, completed tasks, in-progress tasks, overdue tasks, current-user assignments, upcoming deadlines and recent activity. Values derive from authorized records.
- Twelve required MCP tools: list_my_boards, show_board, list_my_cards, list_overdue, create_board, create_card, move_card, assign_card, update_card, add_label, generate_checklist, summarize_board. Supporting tools: list_board_members, search_cards, list_blockers, save_checklist.
- Eight scenario sequences: this-week assignments; overdue tasks; Send invoice in Doing on Operations; card 12 to Done; website redesign to Sarah; launch blockers; Operations progress summary; homepage redesign checklist. `test_mcp_scenarios.py` tests the tool sequences, not an actual conversational client.
- Four AI features and five advanced features are mapped in the phase table. Semantic search remains disabled in deployment until its live contract succeeds; this is an explicit unfinished release gate.
- Eighteen README topics: introduction, visual previews, features, architecture, stack, database, authentication, MCP instructions, command examples, local development, environment, testing, deployment, remixing, post-remix sign-in, security, limitations, future improvements.
- Seven DESIGN topics: architectural decisions, domain model, authorization, DataK3 design, MCP design, remixability and trade-offs; AI/background work and interface decisions are also documented.

## Mandatory 24-gate release checklist

“Local pass” is deliberately narrower than a production pass. Pending gates must be resolved before presenting this as a completed competition entry.

| # | Gate | Status and evidence |
|---|---|---|
| 1 | Public Dodil Git repository | Pending account/organization and publication. |
| 2 | Repository in user's organization | Pending account inspection and destination selection. |
| 3 | MIT license | Local pass: LICENSE preserves starter notice. |
| 4 | Exact repository topics | Configured correctly; live metadata pending. |
| 5 | All persistent application data in DataK3 | Production code/schema pass; live persistence and restart verification pending. |
| 6 | Dodil appid authentication | Gateway-only implementation and local negative tests pass; genuine sign-in pending. |
| 7 | Dodil Ignite deployment | Configuration prepared; actual deployment pending. |
| 8 | Dodil Models integration | Adapter and fake tests pass; actual model contracts pending. |
| 9 | One functional MCP endpoint | Local real-transport pass for /mcp and /mcp/ alias; deployed connector pending. |
| 10 | Shared web/MCP application use cases | Local pass: both doors call the same Boards service. |
| 11 | All required MCP operations work | Registration and local tool tests pass; live tool/client evidence pending. |
| 12 | Three-role permissions tested | Local role matrix, privacy and write denial pass; real-account checks pending. |
| 13 | Board/list/card functionality | Local backend and browser checks pass; live DataK3 acceptance pending. |
| 14 | Drag-and-drop works and persists | Browser reload/order/rollback/concurrent-session checks; actual persistent engine verification pending. |
| 15 | Activity logging | Atomic local tests and UI feed checks pass; live transaction verification pending. |
| 16 | Remix config exists and validates | File/structure pass; authenticated remix check must still return VALID. |
| 17 | Deployment config correct | Local CLI: zero errors, one auth warning; image/live resource checks pending. |
| 18 | README post-remix sign-in | Local pass: exact callback, read-before-merge settings and connector approval distinction documented. |
| 19 | Automated tests pass | Backend results and complete browser results attached; three live tests intentionally not run. |
| 20 | Live deployment works | Pending; no verified live URL claimed. |
| 21 | Works after actual fresh remix | Pending; configuration validation is insufficient. |
| 22 | No secrets committed | No credentials added; secret references only. Final publication diff/scan required again before push. |
| 23 | No prohibited external services | Local pass: production adapters use only Dodil; fonts/icons self-hosted. |
| 24 | No placeholder controls/fake functionality | Implemented controls checked locally; QA data/AI are explicitly isolated fixtures; unavailable semantic service displays its limitation. Full live acceptance remains pending. |

## Provisional competitive scorecard

These are conservative internal estimates, not judge scores or a release declaration. Unverified platform behavior may reduce them substantially.

| Category | Available | Estimate | Implemented / observed evidence | Missing evidence and risks |
|---|---:|---:|---|---|
| Core functionality and permissions | 30 | 23 | Shared transactional CRUD/lifecycle, roles/private access, activity, ordering; local backend/browser checks | Actual DataK3 concurrency, genuine identities and deployed persistence; large snapshots need capacity testing. |
| MCP functionality | 25 | 18 | Sixteen tools, transport auth/discovery, shared authorization, eight deterministic scenario sequences | Real connector approval, natural-language execution and live Models. |
| Architecture, tests and documentation | 20 | 18 | Four layers, typed contracts, local suites, additive schema, CI, full docs and actual screenshots | Container build and fresh-remix proof; release metadata still missing. |
| Extras | 15 | 8 | Dependencies/blockers, advanced filters/activity/quick-add, AI review/save and durable indexing logic | Semantic deployment deliberately disabled until live contract; AI quality unmeasured against real Models. |
| Simplicity and polish | 10 | 8 | Responsive themes, keyboard/touch movement, focus restoration, safe rendering, honest states and local performance samples | Real device/assistive-tech and deployed performance verification remain. |
| **Total** | **100** | **75** | **Local implementation estimate only** | **Cloud release is unfinished.** |

## Remaining work in execution order

1. Complete Dodil browser sign-in, inspect organizations and select the user's destination and a distinct disposable test organization. No credentials belong in source or evidence.
2. Make the official fresh cloud remix, attach its repository as origin without pushing the starter remote, and reconcile history while preserving the original parent brief.
3. Build the nonroot image, run authenticated CI/resource checks and the isolated live SQL/Models/gateway contracts; resolve any compatibility failures. Enable semantic search only after validation.
4. Publish and deploy through Dodil Git, verify actual URL/health/sign-in, all roles, persistence, AI and one approved MCP client. Add callback only after preserving existing appid settings.
5. Require VALID from remix check; execute a genuine fresh-org remix and repeat deployment/sign-in/MCP checks. Record sanitized evidence.
6. Fill the submission worksheet with actual verified URLs, re-audit every gate and update the scorecard. Freelancer submission and partner acceptance stay with the user.

Docker is not installed in this workstation, and an authenticated Dodil account/organizations were not available for the recorded local checks. No cloud resource, deployment, public submission or fabricated real user is claimed.
