#!/usr/bin/env bash
# Keep the Render free instance awake (it sleeps after ~15 idle minutes).
# Layer 2 of 3: GitHub Actions pings every 5m, this cron every 6m, and the
# landing page pings on every visitor. Two independent schedulers mean one
# can be late or die without the instance ever sleeping.
LOG="$HOME/Library/Logs/DRONA_keep_awake.log"
mkdir -p "$(dirname "$LOG")"
# cap the log at 1MB so it can never grow unbounded
[ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 1048576 ] && : > "$LOG"
for attempt in 1 2 3; do
  code=$(/usr/bin/curl -sS -o /dev/null -w '%{http_code}' --max-time 90 \
    "https://dronav2.onrender.com/health/") || code=000
  printf '%s attempt=%s code=%s\n' "$(date '+%F %T')" "$attempt" "$code" >> "$LOG"
  [ "$code" = "200" ] && exit 0
  sleep 20
done
exit 1
