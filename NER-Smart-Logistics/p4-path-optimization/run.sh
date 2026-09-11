#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -x venv/bin/python ]; then
  python3 -m venv venv
  source venv/bin/activate
  python -m pip install --upgrade pip
  pip install -r requirements.txt
else
  source venv/bin/activate
fi
uvicorn src.main:app --reload --port 8000
