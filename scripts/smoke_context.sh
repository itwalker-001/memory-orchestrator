#!/usr/bin/env bash
# scripts/smoke_context.sh
# Verify UserPromptSubmit hook outputs context markdown
set -e

export CLAUDE_PROJECT_DIR="$(pwd)"
output=$(python hooks/user_prompt_submit.py)

if [ -z "$output" ]; then
  echo "hook produced no output — did you save any memory first?"
  exit 1
fi

if echo "$output" | grep -q "Remembered context"; then
  echo "context smoke OK"
else
  echo "FAIL: output did not contain marker"
  echo "$output"
  exit 1
fi
