# ConsentX

ConsentX is our PS-002 prototype: a synthetic service that records purpose-specific consent and enforces the latest consent state before a mock downstream API releases data.

Current development version: **v1.7.0-dev4**. The v1.6.0 field-scoped simulator remains the current feature baseline; this is a local demo prototype, not a claim that PS-002 evidence and submission steps are complete.

## Project boundary

- **This folder is the project root:** `consentx/`.
- The attached PS-002 brief is the product specification for this project.
- ConsentX has its own implementation, tests and evidence. Do not treat files outside this folder as part of this project.
- Use only synthetic users and data. This prototype is technical evidence, not legal certification or a claim of universal DPDP/GDPR compliance.

## Current status

**v1.6.0 field-scoped access and the first v1.7 revocation flow are implemented.** Requests identify the consumer, purpose, operation and requested fields. Withdrawal blocks new access, cancels matching queued synthetic work, and creates an auditable pending instruction for the associated service. Demo identities are session-pinned, and notice publishing requires a configured operator token. Delivery, acknowledgement, and retries are still roadmap work. The isolated suite now has 37 passing tests. Saved screen captures, a recorded clean-start demo, and submission proof remain tracked in [progress](docs/PROGRESS.md) and [evidence](docs/EVIDENCE.md).

## Documents

- [Requirements and acceptance criteria](docs/REQUIREMENTS.md)
- [Task plan](docs/TASKS.md)
- [v1.7 product direction and implementation roadmap](docs/ROADMAP_v1.7.md)
- [Feature-by-feature test plan](docs/TEST_PLAN.md)
- [Personal walkthrough, feature checks and demo script](docs/WALKTHROUGH.md)
- [Judge brief and honest prototype framing](docs/JUDGE_BRIEF.md)
- [Live review notes for the two reference apps](docs/COMPETITOR_REVIEW.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Technology choices and alternatives](docs/TECH_STACK.md)
- [Release notes](docs/RELEASES.md)
- [Evidence and demo plan](docs/EVIDENCE.md)
- [Progress tracker](docs/PROGRESS.md)
- [PS-002 major task tracker](docs/TASKS.md#ps-002-major-task-tracker)
- [Decision log](docs/DECISIONS.md)

## Definition of done

The PS-002 prototype is ready to present when all mandatory requirements in `docs/REQUIREMENTS.md` are implemented, the lifecycle suite has at least 12 passing tests, every evidence item in `docs/EVIDENCE.md` is captured, and the complete grant → allow → withdraw → deny → notice change → re-consent walkthrough works from a clean start.

To enable notice publishing in the local demo, set `CONSENTX_OPERATOR_TOKEN` when starting Flask. The token has no default; do not commit it. The browser's operator access field unlocks publishing for that session. The synthetic identity picker is a demo boundary, not account authentication.
