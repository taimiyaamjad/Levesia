---
name: backup-outputs
description: Archive all output zips into a dated backup tarball
safe: true
tags: [backup, maintenance]
---
#!/bin/bash
set -euo pipefail

OUTPUT="/home/levesia/output"
BACKUP_DIR="/home/levesia/backups"
DATE=$(date +%Y%m%d_%H%M%S)
ARCHIVE="$BACKUP_DIR/backup_$DATE.tar.gz"

mkdir -p "$BACKUP_DIR"
echo "=== Levesia Output Backup ==="
echo "Archiving $OUTPUT → $ARCHIVE"
tar -czf "$ARCHIVE" -C "$(dirname "$OUTPUT")" "$(basename "$OUTPUT")"
SIZE=$(du -sh "$ARCHIVE" | cut -f1)
echo "Created: $ARCHIVE ($SIZE)"
echo ""
echo "=== Existing Backups ==="
ls -lh "$BACKUP_DIR"
