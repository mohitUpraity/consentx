#!/usr/bin/env bash
# ConsentX macOS & Linux One-Command Installer and Launcher (v2.0.0)
# Usage: ./start.sh [--clean] [--test] [--test-only] [--prod] [--port PORT] [--help]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CLEAN_DB=0
RUN_TESTS=0
TEST_ONLY=0
PROD_MODE=0
PORT="${PORT:-5001}"

usage() {
  cat <<'EOF'
ConsentX One-Command Installer & Launcher

Usage:
  ./start.sh [options]

Options:
  --clean, --reset   Delete instance/consentx.sqlite3 before starting (fresh Notice v1.0 demo)
  --test             Run the full automated unit test suite before starting the server
  --test-only        Install dependencies, run the automated test suite, and exit
  --prod             Start using Gunicorn WSGI server instead of Flask dev server
  --port <PORT>      Port to bind (default: 5001, or $PORT if set)
  -h, --help         Show this help message

Environment Variables (auto-defaulted for local demos if unset):
  CONSENTX_OPERATOR_TOKEN   Operator secret to unlock Notice publishing (default: demo-operator-secret)
  CONSENTX_SECRET_KEY       Flask session signing secret (default: local-demo-secret)
  CONSENTX_DB               SQLite database file path (default: instance/consentx.sqlite3)
  PORT                      HTTP server port (default: 5001)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clean|--reset)
      CLEAN_DB=1
      shift
      ;;
    --test)
      RUN_TESTS=1
      shift
      ;;
    --test-only)
      RUN_TESTS=1
      TEST_ONLY=1
      shift
      ;;
    --prod)
      PROD_MODE=1
      shift
      ;;
    --port)
      if [[ $# -lt 2 ]]; then
        echo "Error: --port requires a value." >&2
        exit 1
      fi
      PORT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

echo "============================================================"
echo "  ConsentX v2.0.0 — Purpose-Based Consent & Revocation Demo"
echo "============================================================"

# 1. Verify Python 3
if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required but was not found on PATH." >&2
  exit 1
fi
echo "[1/5] Python detected: $(python3 --version)"

# 2. Create virtual environment if missing
if [[ ! -d ".venv" || ! -x ".venv/bin/python" ]]; then
  echo "[2/5] Creating virtual environment in .venv..."
  python3 -m venv .venv
else
  echo "[2/5] Using existing virtual environment (.venv)"
fi

VENV_PY=".venv/bin/python"

# 3. Install/sync dependencies
echo "[3/5] Installing Python dependencies from requirements.txt..."
"$VENV_PY" -m pip install --disable-pip-version-check -q -r requirements.txt

# 4. Configure local demo environment defaults if not already exported
export CONSENTX_OPERATOR_TOKEN="${CONSENTX_OPERATOR_TOKEN:-demo-operator-secret}"
export CONSENTX_SECRET_KEY="${CONSENTX_SECRET_KEY:-local-demo-secret}"
export PORT="$PORT"

if [[ "$CLEAN_DB" -eq 1 ]]; then
  DB_TARGET="${CONSENTX_DB:-$SCRIPT_DIR/instance/consentx.sqlite3}"
  echo "[4/5] Cleaning local database for fresh Notice v1.0 baseline: $DB_TARGET"
  rm -f "$DB_TARGET"
else
  echo "[4/5] Database path: ${CONSENTX_DB:-$SCRIPT_DIR/instance/consentx.sqlite3}"
fi

# 5. Optional test suite run
if [[ "$RUN_TESTS" -eq 1 ]]; then
  echo "[5/5] Running automated lifecycle & security test suite..."
  "$VENV_PY" -m unittest discover -s tests -v
  if [[ "$TEST_ONLY" -eq 1 ]]; then
    echo "All tests completed. Exiting (--test-only)."
    exit 0
  fi
else
  echo "[5/5] Skipping test suite (run './start.sh --test' to verify all tests before launch)"
fi

echo ""
echo "Starting ConsentX server..."
echo "  App URL        : http://127.0.0.1:$PORT"
echo "  Synthetic Users: student-001 (Aarav Demo), student-002 (Mira Demo)"
echo "  Operator Token : $CONSENTX_OPERATOR_TOKEN  (unlocks Notice versions tab)"
echo "  Master Guide   : DEMO.md (and in-app 'Judge Tour' / 'Judge Guide')"
echo "  Press Ctrl+C to stop."
echo "------------------------------------------------------------"

if [[ "$PROD_MODE" -eq 1 ]]; then
  exec .venv/bin/gunicorn app:app --bind "0.0.0.0:$PORT" --workers 1 --threads 4
else
  exec "$VENV_PY" app.py
fi
