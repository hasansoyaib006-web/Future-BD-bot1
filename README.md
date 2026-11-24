# FUTURE EARN BD — Telegram task & referral bot

## Included
- User registration and referral links
- Admin-created tasks and proof submissions
- Manual admin approval; task rewards credited only after approval
- Referral reward after a referred user gets their first task approved
- Advertisement text controlled by admin
- Withdrawal requests to bKash/Nagad; admin marks paid or rejects/refunds
- SQLite ledger and basic statistics

## Important safety limits
This starter is for a small demo/test only. It does not accept deposits, collect investment money, promise income, connect to Binance, or automatically pay users. Only credit rewards that are genuinely funded by your own verified task/advertising revenue. Get permission from advertisers before posting ads and disclose task conditions clearly. Review Bangladesh's applicable laws and payment-provider terms before any real-money operation.

## 1. Create the Telegram bot
1. Open Telegram and contact `@BotFather`.
2. Send `/newbot`, follow the prompts, and copy the token.
3. Never share the token publicly. If exposed, regenerate it using BotFather.

## 2. Find your Telegram numeric user ID
Use a trusted ID-check bot or a small Telegram bot utility, then set it as `ADMIN_ID`.
Do not use your phone number as ADMIN_ID.

## 3. Run locally
Install Python 3.10+.
```bash
pip install -r requirements.txt
```
Linux/macOS:
```bash
export BOT_TOKEN="YOUR_BOT_TOKEN"
export ADMIN_ID="YOUR_NUMERIC_TELEGRAM_ID"
python bot.py
```
Windows PowerShell:
```powershell
$env:BOT_TOKEN="YOUR_BOT_TOKEN"
$env:ADMIN_ID="YOUR_NUMERIC_TELEGRAM_ID"
python bot.py
```

## 4. Admin commands
- `/addtask 5|Subscribe to our channel|https://t.me/example`
- `/addad Sponsored: visit our partner page. Terms apply.`
- `/pending`
- `/approve 1` or `/reject 1` (submission ID)
- `/approvewd 1` or `/rejectwd 1` (withdrawal ID)
- `/stats`

The reward value in `/addtask` is in BDT. Update the sample task URL/title to a real, permitted task. Never ask users for passwords, OTPs, card details, or sensitive credentials.

## 5. Free hosting note
Render currently offers free services with limitations; free services may spin down/restart and local files can be lost. This bot uses SQLite on local disk, so do not rely on a free ephemeral host for real balances or payout records. Use it for testing only; before real deployment, move to durable managed storage and add backups, monitoring, abuse controls, and security review.
