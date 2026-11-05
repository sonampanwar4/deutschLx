#!/bin/bash
# Creates a virtual environment on first run, then starts deutschlx.
cd "$(dirname "$0")" || exit 1
if [ ! -d .venv ]; then
  python3 -m venv .venv || { echo "Python 3.10+ is required."; exit 1; }
fi
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt
exec .venv/bin/python main.py
