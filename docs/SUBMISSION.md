# Submission worksheet — Avenboard

Status: local implementation prepared; cloud release is not yet verified. Do not submit this worksheet as a completed live entry until the pending gates in [VERIFICATION.md](VERIFICATION.md) pass.

| Submission field | Verified value |
|---|---|
| Product | Avenboard |
| Destination Dodil organization | Pending authenticated account inspection |
| Public Dodil repository | Pending official cloud remix and publication |
| Live application URL | Pending deployment and sign-in verification |
| MCP endpoint | Pending; use the verified application's `/mcp` URL |
| License | MIT, original Dodil notice retained |
| Required topics | `dodil-challenge`, `dodil-challenge-boards` in remix configuration; verify actual repository metadata after publishing |
| Test evidence | [Verification report](VERIFICATION.md), [backend results](evidence/backend-results.xml), [browser results](evidence/browser-results.json) |
| Visual preview | [Desktop](screenshots/desktop-light.png), [dark](screenshots/desktop-dark.png), [mobile board](screenshots/mobile-board.png), [mobile card](screenshots/mobile-card.png) — explicitly local QA fixtures |
| Optional connector recording | Pending genuine Claude/ChatGPT connector session |

## Feature summary

Avenboard provides multiple team workspaces, private and workspace boards, dynamic lists, persistent card ordering, calendar-aware tasks, reusable labels, membership roles, invitations, activity, checklists and directed dependencies. The same authorized application operations serve a React web interface and sixteen authenticated MCP tools. Dodil Models adapters provide checklist drafts, summaries, recommendations and versioned semantic indexing; live model contracts must still be validated. The production repository persists state exclusively through DataK3 and deploys through Dodil Git/Ignite configuration.

## Demonstration sequence

1. Sign in through appid and opt in to Acme Studio sample content. Show that statistics derive from its records.
2. Create, edit and drag a card; reload and verify its persisted order from another browser session.
3. Demonstrate owner/member/viewer access and private-board isolation with genuine accounts.
4. Edit an AI checklist draft before saving; show activity, dependencies and an overdue task.
5. Connect an approved Claude or ChatGPT client to the verified MCP endpoint and execute all eight README scenarios, including genuine Sarah member resolution.
6. Show the successful fresh-organization remix, deployment and post-remix sign-in.

## Five honest lines about implementation difficulties

1. The starter's separate data/activity commits required a shared transactional mutation boundary.
2. Empty-list moves needed parent guards and conflict retries, beyond checking the moved card alone.
3. Private-board access had to constrain search, analytics, AI context and receipt replay as well as direct reads.
4. Nested card/list drag targets required explicit collision handling and keyboard announcements.
5. Local test success cannot establish Dodil remixability; authenticated live contracts and a fresh organization remain essential.

## Before submission

Fill URLs only after opening and verifying them. Confirm repository visibility, ownership, exact topics and MIT license. Attach actual fresh-remix and connector evidence, report any remaining limitations, and reassess the scorecard. Partner-programme acceptance and submission to Freelancer remain separate user actions.
