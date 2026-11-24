# ConsentX

ConsentX is our PS-002 prototype: a synthetic service that records purpose-specific consent and enforces the latest consent state before a mock downstream API releases data.

Current code baseline: **v1.5.0**. This is a local demo prototype, not a claim that PS-002 evidence and submission steps are complete.

## Project boundary

- **This folder is the project root:** `consentx/`.
- The attached PS-002 brief is the product specification for this project.
- ConsentX has its own implementation, tests and evidence. Do not treat files outside this folder as part of this project.
- Use only synthetic users and data. This prototype is technical evidence, not legal certification or a claim of universal DPDP/GDPR compliance.

## Current status

**v1.5.0 judge-facing control center is implemented.** It presents the dashboard, consent controls, downstream request simulator, notice history, audit exports and a server-generated decision trace in separate views. The lifecycle suite currently has 28 passing tests. Saved screen captures, a recorded clean-start demo, and submission proof are still tracked separately in [progress](docs/PROGRESS.md) and [evidence](docs/EVIDENCE.md).

## Documents

- [Requirements and acceptance criteria](docs/REQUIREMENTS.md)
- [Task plan](docs/TASKS.md)
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
