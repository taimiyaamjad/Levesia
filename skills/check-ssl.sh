---
name: check-ssl
description: Check SSL certificate expiry for a domain (pass domain as arg)
safe: true
tags: [ssl, networking, monitoring]
---
#!/bin/bash
set -euo pipefail

DOMAIN="${1:-example.com}"
echo "=== SSL Check: $DOMAIN ==="
echo "Connecting..."
EXPIRY=$(echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN:443" 2>/dev/null \
  | openssl x509 -noout -dates 2>/dev/null | grep notAfter | cut -d= -f2)

if [ -z "$EXPIRY" ]; then
  echo "ERROR: Could not retrieve SSL certificate for $DOMAIN"
  exit 1
fi

echo "Expires : $EXPIRY"
EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s)
NOW_EPOCH=$(date +%s)
DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))

if [ "$DAYS_LEFT" -lt 14 ]; then
  echo "WARNING: Certificate expires in $DAYS_LEFT days!"
elif [ "$DAYS_LEFT" -lt 30 ]; then
  echo "NOTICE : Certificate expires in $DAYS_LEFT days"
else
  echo "OK     : $DAYS_LEFT days remaining"
fi
