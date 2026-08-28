#!/usr/bin/env bash
set -e
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
chmod +x run.sh
echo "Setup complete. Put credentials/client_secret.json then run ./run.sh"
