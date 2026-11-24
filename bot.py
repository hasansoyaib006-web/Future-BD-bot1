import os
import sqlite3
import logging
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

TOKEN = os.getenv("BOT_TOKEN", "PASTE_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
REFERRAL_REWARD = float(os.getenv("REFERRAL_REWARD", "5"))
MIN_WITHDRAW = float(os.getenv("MIN_WITHDRAW", "50"))
DB_PATH = os.getenv("DB_PATH", "future_earn.db")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          user_id INTEGER PRIMARY KEY, username TEXT, balance REAL NOT NULL DEFAULT 0,
          referred_by INTEGER, referral_paid INTEGER NOT NULL DEFAULT 0,
          joined_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks(
          id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT,
          reward REAL NOT NULL, active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS submissions(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          task_id INTEGER NOT NULL, proof TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS withdrawals(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          amount REAL NOT NULL, method TEXT NOT NULL, account TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ledger(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          amount REAL NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ads(
          id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
        );
        """)

def now():
    return datetime.now(timezone.utc).isoformat()

def is_admin(update):
    return update.effective_user and update.effective_user.id == ADMIN_ID and ADMIN_ID != 0

def ensure_user(tg_user, referrer=None):
    with db() as c:
        row = c.execute("SELECT user_id FROM users WHERE user_id=?", (tg_user.id,)).fetchone()
        if not row:
            if referrer == tg_user.id:
                referrer = None
            c.execute("""INSERT INTO users(user_id,username,referred_by,joined_at)
                         VALUES(?,?,?,?)""",
                      (tg_user.id, tg_user.username or "", referrer, now()))
        else:
            c.execute("UPDATE users SET username=? WHERE user_id=?",
                      (tg_user.username or "", tg_user.id))

def add_credit(user_id, amount, note):
    with db() as c:
        c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))
        c.execute("INSERT INTO ledger(user_id,amount,note,created_at) VALUES(?,?,?,?)",
                  (user_id, amount, note, now()))

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Available Tasks", callback_data="tasks"),
         InlineKeyboardButton("💰 My Balance", callback_data="balance")],
        [InlineKeyboardButton("👥 Refer & Earn", callback_data="refer"),
         InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("📢 Latest Advertisement", callback_data="ad"),
         InlineKeyboardButton("📜 History", callback_data="history")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ref = None
    if context.args:
        try: ref = int(context.args[0])
        except ValueError: pass
    ensure_user(update.effective_user, ref)
    await update.message.reply_text(
        "স্বাগতম FUTURE EARN BD-তে!\n"
        "কাজ সম্পন্ন করে যাচাইয়ের পর রিওয়ার্ড পেতে পারো। "
        "কোনো আয়ের নিশ্চয়তা নেই; ভুয়া প্রমাণ দিলে অ্যাকাউন্ট বন্ধ হতে পারে।",
        reply_markup=main_keyboard()
    )

async def help_cmd(update, context):
    msg = ("ব্যবহার:\n/start — মেনু\n"
           "/addtask reward|title|url — অ্যাডমিন: নতুন টাস্ক\n"
           "/addad বিজ্ঞাপনের লেখা — অ্যাডমিন: বিজ্ঞাপন\n"
           "/pending — অ্যাডমিন: অপেক্ষমাণ কাজ/উইথড্র\n"
           "/approve ID — অ্যাডমিন: কাজ অনুমোদন\n"
           "/reject ID — অ্যাডমিন: কাজ বাতিল\n"
           "/approvewd ID — অ্যাডমিন: উইথড্র সম্পন্ন\n"
           "/rejectwd ID — অ্যাডমিন: উইথড্র বাতিল ও ব্যালেন্স ফেরত\n"
           "/stats — অ্যাডমিন: পরিসংখ্যান")
    await update.message.reply_text(msg)

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if q.data == "tasks":
        with db() as c:
            rows = c.execute("SELECT * FROM tasks WHERE active=1 ORDER BY id DESC").fetchall()
        if not rows:
            await q.message.reply_text("এখন কোনো টাস্ক নেই। পরে আবার দেখো।")
            return
        for r in rows:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Submit proof", callback_data=f"task_{r['id']}")]])
            await q.message.reply_text(
                f"Task #{r['id']}: {r['title']}\nReward: ৳{r['reward']:.2f}\n"
                f"Link: {r['url'] or 'No link'}\nকাজ শেষে Submit proof চাপো।", reply_markup=kb)
    elif q.data == "balance":
        with db() as c:
            r = c.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
        await q.message.reply_text(f"তোমার উপলভ্য ব্যালেন্স: ৳{(r['balance'] if r else 0):.2f}")
    elif q.data == "refer":
        me = await context.bot.get_me()
        with db() as c:
            count = c.execute("SELECT COUNT(*) n FROM users WHERE referred_by=?", (uid,)).fetchone()["n"]
        await q.message.reply_text(
            f"তোমার referral link:\nhttps://t.me/{me.username}?start={uid}\n"
            f"মোট invite: {count}\nরেফারেল রিওয়ার্ড কেবল আমন্ত্রিত ব্যক্তি প্রথম টাস্ক অনুমোদন পেলে যোগ হবে।")
    elif q.data == "withdraw":
        context.user_data["awaiting_withdraw_amount"] = True
        await q.message.reply_text(f"কত টাকা তুলতে চাও? সর্বনিম্ন ৳{MIN_WITHDRAW:.2f} লিখো।")
    elif q.data == "ad":
        with db() as c:
            r = c.execute("SELECT text FROM ads WHERE active=1 ORDER BY id DESC LIMIT 1").fetchone()
        await q.message.reply_text(r["text"] if r else "এখন কোনো বিজ্ঞাপন নেই।")
    elif q.data == "history":
        with db() as c:
            rows = c.execute("SELECT amount,note,created_at FROM ledger WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,)).fetchall()
        if not rows:
            await q.message.reply_text("এখনো কোনো লেনদেন নেই।")
        else:
            await q.message.reply_text("\n".join(
                f"{r['created_at'][:10]} | {'+' if r['amount']>=0 else ''}{r['amount']:.2f} | {r['note']}"
                for r in rows))

async def task_callback(update, context):
    q = update.callback_query
    await q.answer()
    task_id = int(q.data.split("_", 1)[1])
    with db() as c:
        exists = c.execute("SELECT id FROM tasks WHERE id=? AND active=1", (task_id,)).fetchone()
        prior = c.execute("SELECT id FROM submissions WHERE user_id=? AND task_id=? AND status IN ('pending','approved')",
                          (q.from_user.id, task_id)).fetchone()
    if not exists:
        await q.message.reply_text("এই টাস্কটি আর চালু নেই.")
    elif prior:
        await q.message.reply_text("এই টাস্কের জন্য তোমার আগের সাবমিশন আছে।")
    else:
        context.user_data["awaiting_proof_task"] = task_id
        await q.message.reply_text("কাজের প্রমাণ হিসেবে screenshot-এর বদলে আপাতত একটি public link বা সংক্ষিপ্ত বিবরণ পাঠাও।")

async def message_handler(update, context):
    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    # Handle a task proof first; keep the selected task ID until the proof arrives.
    if "awaiting_proof_task" in context.user_data:
        task_id = context.user_data.pop("awaiting_proof_task")
        with db() as c:
            c.execute("INSERT INTO submissions(user_id,task_id,proof,created_at) VALUES(?,?,?,?)",
                      (uid, task_id, text[:2000], now()))
            sid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        await update.message.reply_text(f"প্রমাণ জমা হয়েছে। Submission ID: {sid}\nঅ্যাডমিন যাচাই করবেন।")
        if ADMIN_ID:
            await context.bot.send_message(ADMIN_ID, f"নতুন Task submission #{sid}\nUser: {uid}\nTask: {task_id}\nProof: {text[:1000]}")
        return
    if context.user_data.get("awaiting_withdraw_amount"):
        try: amount = float(text)
        except ValueError:
            await update.message.reply_text("সঠিক অঙ্ক লিখো, যেমন 100")
            return
        if amount < MIN_WITHDRAW:
            await update.message.reply_text(f"সর্বনিম্ন উত্তোলন ৳{MIN_WITHDRAW:.2f}")
            return
        with db() as c:
            row = c.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
        if not row or row["balance"] < amount:
            await update.message.reply_text("পর্যাপ্ত ব্যালেন্স নেই।")
            return
        context.user_data["withdraw_amount"] = amount
        context.user_data["awaiting_withdraw_amount"] = False
        context.user_data["awaiting_withdraw_method"] = True
        await update.message.reply_text("পেমেন্ট মাধ্যম লিখো: bKash অথবা Nagad")
        return
    if context.user_data.get("awaiting_withdraw_method"):
        method = text.lower()
        if method not in ("bkash", "nagad", "বিকাশ", "নগদ"):
            await update.message.reply_text("শুধু bKash অথবা Nagad লিখো।")
            return
        context.user_data["withdraw_method"] = "bKash" if method in ("bkash","বিকাশ") else "Nagad"
        context.user_data["awaiting_withdraw_method"] = False
        context.user_data["awaiting_withdraw_account"] = True
        await update.message.reply_text("যে নম্বরে টাকা নিতে চাও সেই bKash/Nagad নম্বর পাঠাও।")
        return
    if context.user_data.get("awaiting_withdraw_account"):
        amount = context.user_data.pop("withdraw_amount")
        method = context.user_data.pop("withdraw_method")
        account = text[:40]
        with db() as c:
            row = c.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
            if not row or row["balance"] < amount:
                context.user_data["awaiting_withdraw_account"] = False
                await update.message.reply_text("ব্যালেন্স পরিবর্তিত হয়েছে; আবার চেষ্টা করো।")
                return
            c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, uid))
            c.execute("INSERT INTO ledger(user_id,amount,note,created_at) VALUES(?,?,?,?)",
                      (uid, -amount, "Withdrawal held", now()))
            c.execute("INSERT INTO withdrawals(user_id,amount,method,account,created_at) VALUES(?,?,?,?,?)",
                      (uid, amount, method, account, now()))
            wid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        context.user_data["awaiting_withdraw_account"] = False
        await update.message.reply_text(f"উত্তোলন অনুরোধ #{wid} জমা হয়েছে। যাচাই শেষে জানানো হবে।")
        if ADMIN_ID:
            await context.bot.send_message(ADMIN_ID, f"Withdrawal #{wid}\nUser {uid}\n৳{amount:.2f} via {method}\nAccount: {account}")
        return
    await update.message.reply_text("মেনু ব্যবহার করতে /start চাপো।", reply_markup=main_keyboard())

async def addtask(update, context):
    if not is_admin(update): return
    raw = " ".join(context.args)
    try:
        reward_s, title, url = raw.split("|", 2)
        reward = float(reward_s.strip())
        if reward <= 0: raise ValueError()
    except Exception:
        await update.message.reply_text("ব্যবহার: /addtask 5|ভিডিও দেখো|https://example.com")
        return
    with db() as c:
        c.execute("INSERT INTO tasks(title,url,reward) VALUES(?,?,?)", (title.strip(), url.strip(), reward))
    await update.message.reply_text("টাস্ক যোগ হয়েছে।")

async def addad(update, context):
    if not is_admin(update): return
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("ব্যবহার: /addad বিজ্ঞাপনের লেখা")
        return
    with db() as c:
        c.execute("UPDATE ads SET active=0")
        c.execute("INSERT INTO ads(text) VALUES(?)", (text[:3000],))
    await update.message.reply_text("বিজ্ঞাপন আপডেট হয়েছে।")

async def pending(update, context):
    if not is_admin(update): return
    with db() as c:
        subs = c.execute("SELECT * FROM submissions WHERE status='pending' ORDER BY id").fetchall()
        wds = c.execute("SELECT * FROM withdrawals WHERE status='pending' ORDER BY id").fetchall()
    lines = ["PENDING TASKS:"]
    lines += [f"#{r['id']} user={r['user_id']} task={r['task_id']} proof={r['proof'][:100]}" for r in subs] or ["None"]
    lines += ["PENDING WITHDRAWALS:"]
    lines += [f"#{r['id']} user={r['user_id']} amount={r['amount']} method={r['method']} account={r['account']}" for r in wds] or ["None"]
    await update.message.reply_text("\n".join(lines)[:4000])

async def approve(update, context):
    if not is_admin(update): return
    try: sid = int(context.args[0])
    except Exception:
        await update.message.reply_text("ব্যবহার: /approve SUBMISSION_ID"); return
    with db() as c:
        r = c.execute("""SELECT s.*,t.reward FROM submissions s JOIN tasks t ON t.id=s.task_id
                         WHERE s.id=? AND s.status='pending'""", (sid,)).fetchone()
        if not r:
            await update.message.reply_text("Pending submission পাওয়া যায়নি।"); return
        c.execute("UPDATE submissions SET status='approved' WHERE id=?", (sid,))
        c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (r["reward"], r["user_id"]))
        c.execute("INSERT INTO ledger(user_id,amount,note,created_at) VALUES(?,?,?,?)",
                  (r["user_id"], r["reward"], f"Task #{r['task_id']} reward", now()))
        u = c.execute("SELECT referred_by,referral_paid FROM users WHERE user_id=?", (r["user_id"],)).fetchone()
        referrer = u["referred_by"] if u else None
        if referrer and not u["referral_paid"]:
            c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (REFERRAL_REWARD, referrer))
            c.execute("INSERT INTO ledger(user_id,amount,note,created_at) VALUES(?,?,?,?)",
                      (referrer, REFERRAL_REWARD, "Referral reward", now()))
            c.execute("UPDATE users SET referral_paid=1 WHERE user_id=?", (r["user_id"],))
    await context.bot.send_message(r["user_id"], f"তোমার Task #{r['task_id']} অনুমোদিত। ৳{r['reward']:.2f} যোগ হয়েছে।")
    if referrer:
        await context.bot.send_message(referrer, f"Referral reward ৳{REFERRAL_REWARD:.2f} যোগ হয়েছে।")
    await update.message.reply_text("Submission approved; reward credited.")

async def reject(update, context):
    if not is_admin(update): return
    try: sid = int(context.args[0])
    except Exception:
        await update.message.reply_text("ব্যবহার: /reject SUBMISSION_ID"); return
    with db() as c:
        r = c.execute("SELECT * FROM submissions WHERE id=? AND status='pending'", (sid,)).fetchone()
        if not r:
            await update.message.reply_text("Pending submission পাওয়া যায়নি।"); return
        c.execute("UPDATE submissions SET status='rejected' WHERE id=?", (sid,))
    await context.bot.send_message(r["user_id"], f"তোমার Submission #{sid} অনুমোদিত হয়নি।")
    await update.message.reply_text("Submission rejected.")

async def approvewd(update, context):
    if not is_admin(update): return
    try: wid = int(context.args[0])
    except Exception:
        await update.message.reply_text("ব্যবহার: /approvewd ID"); return
    with db() as c:
        r = c.execute("SELECT * FROM withdrawals WHERE id=? AND status='pending'", (wid,)).fetchone()
        if not r:
            await update.message.reply_text("Pending withdrawal পাওয়া যায়নি।"); return
        c.execute("UPDATE withdrawals SET status='paid' WHERE id=?", (wid,))
    await context.bot.send_message(r["user_id"], f"Withdrawal #{wid} paid হিসেবে চিহ্নিত হয়েছে।")
    await update.message.reply_text("Withdrawal marked paid. টাকা ম্যানুয়ালি পাঠাতে হবে।")

async def rejectwd(update, context):
    if not is_admin(update): return
    try: wid = int(context.args[0])
    except Exception:
        await update.message.reply_text("ব্যবহার: /rejectwd ID"); return
    with db() as c:
        r = c.execute("SELECT * FROM withdrawals WHERE id=? AND status='pending'", (wid,)).fetchone()
        if not r:
            await update.message.reply_text("Pending withdrawal পাওয়া যায়নি।"); return
        c.execute("UPDATE withdrawals SET status='rejected' WHERE id=?", (wid,))
        c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (r["amount"], r["user_id"]))
        c.execute("INSERT INTO ledger(user_id,amount,note,created_at) VALUES(?,?,?,?)",
                  (r["user_id"], r["amount"], "Withdrawal rejected — refund", now()))
    await context.bot.send_message(r["user_id"], f"Withdrawal #{wid} বাতিল; ৳{r['amount']:.2f} ফেরত দেওয়া হয়েছে।")
    await update.message.reply_text("Withdrawal rejected and balance refunded.")

async def stats(update, context):
    if not is_admin(update): return
    with db() as c:
        users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        pending_w = c.execute("SELECT COUNT(*) n FROM withdrawals WHERE status='pending'").fetchone()["n"]
        pending_s = c.execute("SELECT COUNT(*) n FROM submissions WHERE status='pending'").fetchone()["n"]
        total = c.execute("SELECT COALESCE(SUM(balance),0) s FROM users").fetchone()["s"]
    await update.message.reply_text(f"Users: {users}\nPending tasks: {pending_s}\nPending withdrawals: {pending_w}\nTotal user balances: ৳{total:.2f}")

def main():
    if TOKEN == "PASTE_BOT_TOKEN_HERE" or ADMIN_ID == 0:
        raise SystemExit("Set BOT_TOKEN and ADMIN_ID environment variables first.")
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("addtask", addtask))
    app.add_handler(CommandHandler("addad", addad))
    app.add_handler(CommandHandler("pending", pending))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("reject", reject))
    app.add_handler(CommandHandler("approvewd", approvewd))
    app.add_handler(CommandHandler("rejectwd", rejectwd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(task_callback, pattern=r"^task_\d+$"))
    app.add_handler(CallbackQueryHandler(menu_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    log.info("FUTURE EARN BD started")
    app.run_polling()

if __name__ == "__main__":
    main()
