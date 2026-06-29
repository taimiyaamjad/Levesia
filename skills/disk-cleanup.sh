---
name: disk-cleanup
description: Remove workspace dirs and output zips older than 7 days
safe: true
tags: [maintenance, disk]
---
#!/bin/bash
set -euo pipefail

WORKSPACE="/home/levesia/workspace"
OUTPUT="/home/levesia/output"
LOGS="/home/levesia/logs"

echo "=== Levesia Disk Cleanup ==="
echo "Removing workspace dirs older than 7 days..."
find "$WORKSPACE" -mindepth 1 -maxdepth 1 -type d -mtime +7 -exec rm -rf {} + 2>/dev/null && echo "Done."

echo "Removing output zips older than 7 days..."
find "$OUTPUT" -name "*.zip" -mtime +7 -delete 2>/dev/null && echo "Done."

echo "Removing logs older than 30 days..."
find "$LOGS" -name "*.log" -mtime +30 -delete 2>/dev/null && echo "Done."

echo ""
echo "=== Disk usage after cleanup ==="
df -h /
