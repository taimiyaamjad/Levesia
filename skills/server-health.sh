---
name: server-health
description: Full VPS health snapshot — CPU, memory, disk, network, top processes
safe: true
tags: [monitoring, system]
---
#!/bin/bash
echo "=== Levesia Server Health ==="
echo "Time   : $(date)"
echo "Host   : $(hostname)"
echo ""
echo "--- Uptime & Load ---"
uptime
echo ""
echo "--- Memory ---"
free -h
echo ""
echo "--- Disk ---"
df -h --output=target,used,avail,pcent
echo ""
echo "--- Top 10 Processes (CPU) ---"
ps aux --sort=-%cpu | head -11 | awk '{printf "%-25s %5s%% CPU  %5s%% MEM\n", $11, $3, $4}'
echo ""
echo "--- Open Ports ---"
ss -tuln | grep LISTEN | awk '{print $1, $5}' | column -t
