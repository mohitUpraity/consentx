# ConsentX

ConsentX is our PS-002 prototype: a synthetic service that records purpose-specific consent and enforces the latest consent state before a mock downstream API releases data.

## Project boundary

- **This folder is the project root:** `consentx/`.
- The attached PS-002 brief is the product specification for this project.
- ConsentX has its own implementation, tests and evidence. Do not treat files outside this folder as part of this project.
- Use only synthetic users and data. This prototype is technical evidence, not legal certification or a claim of universal DPDP/GDPR compliance.

## Current status

**Planning — implementation not started.** See [progress](docs/PROGRESS.md) for the source of truth and [tasks](docs/TASKS.md) for the work queue.

## Documents

- [Requirements and acceptance criteria](docs/REQUIREMENTS.md)
- [Task plan](docs/TASKS.md)
- [Feature-by-feature test plan](docs/TEST_PLAN.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Evidence and demo plan](docs/EVIDENCE.md)
- [Progress tracker](docs/PROGRESS.md)
- [PS-002 major task tracker](docs/TASKS.md#ps-002-major-task-tracker)
- [Decision log](docs/DECISIONS.md)

## Definition of done

The PS-002 prototype is ready to present when all mandatory requirements in `docs/REQUIREMENTS.md` are implemented, the lifecycle suite has at least 12 passing tests, every evidence item in `docs/EVIDENCE.md` is captured, and the complete grant → allow → withdraw → deny → notice change → re-consent walkthrough works from a clean start.
