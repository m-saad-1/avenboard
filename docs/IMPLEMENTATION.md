# Avenboard implementation record

Approved source: the parent workspace's docs/content.md and conversation implementation plan.
Starter: 2815f0bbc39ae589ff78be4dfcd87757e7cfe268. Brand/repository: Avenboard/avenboard.

## Checklist
- [x] Inspect official starter and all 14 brief phases.
- [x] Install/checksum-check Dodil CLI 0.1.91.
- [x] Read both CLI guides and all three mandatory MCP resources (snapshots in platform/).
- [ ] Authenticate CLI; confirm destination/test organizations; create official cloud remix.
- [x] Baseline tests: six original starter tests passed in an isolated checkout.
- [x] Domain, transactional DataK3 repository, nineteen-table schema and shared use cases implemented.
- [x] Membership, privacy, concurrency, invitations, ownership and activity covered by local tests.
- [x] Responsive light/dark React application, typed contracts and working management controls implemented.
- [x] Card/list drag-and-drop, keyboard alternatives, rollback and stale-session protection implemented; local browser evidence recorded.
- [x] Twelve required MCP tools plus four supporting tools; all eight scenario tool sequences exercised over real MCP transport with fixtures.
- [x] Four Models adapters/features and durable semantic indexing recovery implemented and fake-tested. Live model/vector verification remains pending; semantic deployment flag is off.
- [x] Dependencies, overdue indicators, activity, quick creation and filters implemented.
- [x] Authenticated opt-in, idempotent Acme Studio sample workflow implemented.
- [x] README, DESIGN, migration instructions, submission worksheet and twelve real local browser screenshots prepared.
- [x] Complete local browser suite: 28 passed across three viewports; five device-specific cases skipped. Backend: 56 passed, three live checks skipped. Frontend production build passes.
- [x] Local CI configuration verification: zero errors, one missing-authentication warning; live checks skipped.
- [ ] Authenticated remix check returns VALID and fresh-test-organization plan succeeds.
- [ ] Live appid/MCP/DataK3/Models contracts and deployment.
- [x] Final local coverage audit, 24-gate checklist and provisional scorecard recorded, with cloud gaps explicit.
- [ ] Actual fresh-org remix and cloud release gates completed; scorecard reassessed using live evidence.

The detailed gate audit and provisional scorecard are in [VERIFICATION.md](VERIFICATION.md). Checkmarks above describe implementation and local evidence, not deployed certification. Cloud-dependent work is not complete.

## Phase reports

| Work phase | Main files changed | Verification and remaining issues |
|---|---|---|
| Starter/platform | platform documentation snapshots, original starter checkout | CLI 0.1.91 verified; mandatory guides read; six baseline tests passed. Cloud remix requires account access. |
| Backend/data | domain/model.py, domain/commands.py, application/use_cases.py, infrastructure/repository.py, infrastructure/schema.py, schema.sql, migrations/001_avenboard.sql | 56 local backend tests pass, three live tests skip. Transactions, ordering, receipts, date boundaries and permissions covered; DataK3 execution still pending. |
| Web product | frontend/src, generated OpenAPI types, static build pipeline | TypeScript and Vite build pass. Actual browser suites cover desktop, tablet and mobile; screenshots are genuine local fixture captures. |
| MCP/AI/extras | doors/mcp.py, infrastructure/dodil.py, shared use cases, AI UI | Sixteen registrations and eight tool sequences tested. Checklist preview/save, authorization and indexing recovery covered. Actual Models and Claude/ChatGPT approval/session remain pending. |
| Delivery/docs | .dodil, .github/workflows, app/Dockerfile, README, DESIGN, docs | Local CLI config validation passes with the authentication warning. Container build, publication, live sign-in and actual fresh remix remain open. |

## Corrections found during verification

- Replaced the starter's vulnerable FastAPI/Starlette runtime pins; the current Python and npm audits report no known vulnerabilities.
- Made archive/delete retries reauthorize while retaining auditable tombstones; label deletion carries its board context so its receipt survives label removal.
- Compacted ordering after archival/deletion and appended restored cards without corrupting existing positions.
- Fixed nested drag collisions and synchronized keyboard checks with announced targets; added readable screen-reader instructions and announcements.
- Rendered feedback within the active native dialog so its backdrop cannot hide errors or block dismissal.
- Distinguished a successful mutation followed by a failed refresh from an unsaved mutation.
- Added browser evidence for failed-drag rollback and conflicting moves by two separate user sessions.
- Improved secondary/status text contrast in both themes (38 token pairs, minimum 4.64:1) and increased the smallest labels to 10px.

## Platform notes
Keep the starter DDD shape and Dodil adapters. All durable app state is in DataK3.
The build guide's old pending-read advice conflicts with the newer SQL resource; use a
transaction identity map and buffer writes, then verify deployed engine behavior explicitly.
Guard parent revision rows for empty-list races. Plain INSERT claims idempotency keys.
Git 1.6.11+ may register callbacks automatically: inspect deploy logs, retaining the manual
callback fallback and preserving existing pool settings. MCP client approval is separate.
Account-dependent checks remain pending; a local test is not evidence of live success.
