# ConsentX

ConsentX is our **PS-002** prototype: a synthetic CampusPulse consent, policy-enforcement, and downstream revocation orchestration system.

Current version: **v2.0.0**.

## Project boundary

- **This folder is the project root:** `consentx/`.
- The attached `../PS-002.pdf` brief is the specification for this project.
- Use only synthetic users and data. This prototype demonstrates technical enforcement and tamper-evident audit evidence, not legal certification or universal DPDP/GDPR compliance.

## What ConsentX v2.0.0 implements

1. **Purpose- & Field-Scoped PEP (`/api/data-access`)**: Checks session-pinned synthetic identity, exact purpose (`P1`–`P3`), consumer service (`notification-service`, `recommendation-service`, `analytics-service`), `READ`-only operation, requested field subset, latest consent event, and active notice SHA-256 hash before releasing any synthetic field. Returns a 6-step `decision_trace`.
2. **End-to-End Downstream Revocation Orchestration (`adapters.py`)**: Withdrawing consent blocks future requests immediately, cancels matching queued synthetic jobs (`pending_actions`), creates a `PENDING` revocation instruction, delivers it to the simulated consumer adapter (`PENDING → DELIVERED → ACKNOWLEDGED`), supports simulated consumer outages (`FAILED` + honest error tracking) and idempotent `RETRY` (`FAILED → ACKNOWLEDGED`).
3. **My Privacy & Downloadable Receipts (`/api/my-privacy`, `/api/privacy-receipt/<id>`)**: Data-subject view showing current permissions, connected services and authorized fields, unresolved vs. acknowledged withdrawals, and downloadable JSON + print-friendly HTML/PDF receipts with linked evidence IDs and an explicit scope disclaimer.
4. **Tamper-Evident SHA-256 Audit Ledger (`audit_chain.py`, `/api/audit/verify`)**: Unified append-only hash chain (`H_i = SHA256(H_{i-1} || CanonicalEvent_i)`) linking consent events, access decisions, notice publications, queued-work cancellations, deliveries, failures, retries, and acknowledgements, plus live verification and JSON/CSV exports.
5. **In-Browser Live Diagnostics (`/api/diagnostics`)**: Real-time verification checks inside the Audit & Verification view, plus **50 passing automated tests** on isolated temporary SQLite databases.

## Quick start (clean local demo)

```bash
cd consentx
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
rm -f instance/consentx.sqlite3
CONSENTX_OPERATOR_TOKEN=demo-operator-secret python app.py
```

Open `http://127.0.0.1:5001`. Notice publishing requires entering the configured `CONSENTX_OPERATOR_TOKEN` in the **Notice versions** tab (no default operator token is shipped in code).

## Run automated tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Production deployment (Render)

`render.yaml` configures Gunicorn (`gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4`), `/api/health`, a persistent SQLite disk at `/var/data/consentx.sqlite3`, and generated `CONSENTX_SECRET_KEY` / `CONSENTX_OPERATOR_TOKEN` environment variables.

## Documents

- [Requirements and acceptance criteria](docs/REQUIREMENTS.md)
- [Task plan](docs/TASKS.md)
- [v1.7/v2.0 product direction and roadmap](docs/ROADMAP_v1.7.md)
- [Feature-by-feature test plan](docs/TEST_PLAN.md)
- [Personal walkthrough and demo script](docs/WALKTHROUGH.md)
- [Judge brief](docs/JUDGE_BRIEF.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Mentor demo pseudocode](docs/DEMO_PSEUDOCODE.md)
- [Release notes](docs/RELEASES.md)
- [Evidence index](docs/EVIDENCE.md)
- [Progress tracker](docs/PROGRESS.md)
