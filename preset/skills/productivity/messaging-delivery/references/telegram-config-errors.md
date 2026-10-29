# Telegram Configuration — Error Reference

## Error: `ValueError: invalid literal for int() with base 10: '<username>'`

### Full Traceback
```
ERROR gateway.platforms.telegram: [Telegram] Failed to send Telegram message:
  invalid literal for int() with base 10: 'igsergor'
Traceback (most recent call last):
  File ".../gateway/platforms/telegram.py", line 1908, in send
    chat_id=int(chat_id),
            ^^^^^^^^^^^^
ValueError: invalid literal for int() with base 10: 'igsergor'
```

### Root Cause
In `~/.hermes/.env`, the variable `TELEGRAM_ALLOWED_USERS` (or `TELEGRAM_HOME_CHANNEL`)
was set to a Telegram username string (e.g. `igsergor`) instead of a numeric user ID
(e.g. `252852450`).

Hermes calls `int(chat_id)` on these values when sending messages. Non-numeric strings throw `ValueError`.

### Affected Variables
| Variable in .env | Expected Format | Wrong Example |
|-------------------|-----------------|---------------|
| TELEGRAM_ALLOWED_USERS | Numeric ID(s), comma-separated | igsergor |
| TELEGRAM_HOME_CHANNEL | Numeric chat ID | igsergor |

Note: Telegram bot tokens (from @BotFather) are alphanumeric and are fine — the numeric-ID
requirement is only for user/chat IDs.

### Fix Steps

1. Get your numeric Telegram user ID:
   - Open @userinfobot in Telegram — it replies with your ID
   - Or grep gateway logs for incoming message events

2. Edit ~/.hermes/.env:
   Change TELEGRAM_ALLOWED_USERS=igsergor
   To     TELEGRAM_ALLOWED_USERS=<your_numeric_id>

3. Restart: hermes gateway restart

4. Verify: hermes gateway status && journalctl --user -u hermes-gateway --no-pager -n 30

### Temporary Workaround (to discover your ID)
Add GATEWAY_ALLOW_ALL_USERS=true to .env, restart, write to the bot, find your ID in logs,
then set TELEGRAM_ALLOWED_USERS and remove the allow-all line.

### Silent Gateway After Restart
After fixing config and restarting, the gateway may show as active (running) in systemd
but produce no journalctl output beyond "Started". This is normal for long-polling Telegram —
the adapter silently waits for incoming messages. Send a message to the bot; if it responds, everything works.
