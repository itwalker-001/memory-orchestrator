#!/bin/sh
find /opt/memory-orchestrator/scripts -name "*.sh" | while read f; do
  sed -i 's/\r//' "$f"
  chmod +x "$f"
done
echo "done"
