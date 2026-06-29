---
name: update-system
description: Run apt update + upgrade and report what changed
safe: true
tags: [maintenance, system]
---
#!/bin/bash
set -euo pipefail

echo "=== Levesia System Update ==="
echo "Time: $(date)"
echo ""
echo "--- apt update ---"
apt-get update -qq 2>&1

echo ""
echo "--- Packages with upgrades ---"
apt list --upgradable 2>/dev/null | grep -v "Listing..."

echo ""
echo "--- Running upgrade ---"
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq 2>&1

echo ""
echo "=== Update complete ==="
uname -r
