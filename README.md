# Pelosi Tracker — Setup Guide

This gets you a phone app that shows Nancy & Paul Pelosi's stock trades, and
**emails you** whenever a new one is disclosed. Everything is free and lives in
your GitHub account. No coding. About 20 minutes, once.

There are two halves:
- **The app** — a web page GitHub hosts for you, that you add to your iPhone.
- **The checker** — a little robot GitHub runs every 4 hours that emails you on
  any new filing and refreshes the app.

Do the steps in order. Don't worry about understanding the code.

---

## Part 1 — Put the project on GitHub

Already done if you're reading this in your repo!

---

## Part 2 — Turn on the app (GitHub Pages)

1. In your repository, click **Settings** (top menu) → **Pages** (left menu).
2. Under **Branch**, pick **main**, and for the folder pick **/docs**. Click
   **Save**.
3. Wait about a minute, then refresh. GitHub shows a green box with your live
   link — something like `https://yourname.github.io/pelosi-tracker/`.
   **That link is your app.** Open it on your iPhone in Safari.
4. In Safari: tap the **Share** icon → **Add to Home Screen**. Now it has its
   own icon and opens like a real app.

The app works now. Part 3 is what makes it email you.

---

## Part 3 — Make a Gmail "App Password"

(Gmail won't let a script use your normal password, so you make a special one
just for this. If you don't use Gmail, tell me your provider and I'll adjust.)

1. Your Google account needs **2-Step Verification** on. Check at
   **myaccount.google.com/security**. Turn it on if it isn't.
2. Then go to **myaccount.google.com/apppasswords**.
3. Type a name like `pelosi` and click **Create**.
4. Google shows a **16-character password**. Copy it (ignore the spaces).
   You'll paste it in the next part. You won't see it again, so keep the tab
   open for a moment.

---

## Part 4 — Give GitHub your email details (safely)

These are stored as encrypted "secrets" — the code never sees your actual
password text, and no one looking at your repo can read them.

1. In your repo: **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret** and add these three, one at a time:

   | Name | Value |
   |------|-------|
   | `SMTP_USER` | your full Gmail address |
   | `SMTP_PASS` | the 16-character app password from Part 3 |
   | `EMAIL_TO` | where you want alerts (your Gmail is fine) |

   (Type the **Name** exactly as shown, in capitals. Paste the value. Click
   **Add secret**. Repeat for all three.)

---

## Part 5 — Start the robot

1. In your repo, click the **Actions** tab.
2. If it asks you to enable workflows, click the green **I understand /
   Enable** button.
3. Click **Check for new Pelosi filings** on the left, then the **Run
   workflow** button on the right → **Run workflow**.
4. This first run sets the baseline. After it finishes (about a minute), run it
   **once more** the same way — that second run is the real test. From now on
   it runs itself every 4 hours.

To avoid getting emailed about every *old* filing on the very first run, the
robot treats whatever exists today as "already seen" and only emails you about
filings that appear **after** setup. So a quiet inbox at first is correct — it
means it's working and waiting.

---

## You're done

- **See trades:** open the app from your home-screen icon. It refreshes itself.
- **Get alerted:** when a new filing is disclosed, you get an email listing the
  trades, and the app updates automatically.

### Good to know
- Filings are legally allowed to be up to **45 days** late. No tracker can beat
  that — you're getting trades the instant they're public.
- Want to **check right now** instead of waiting? Actions tab → Run workflow.
  Or tap **Check for new filings** in the app's Alerts tab.
- Want to **also track another member of Congress**? Open `check.py`, find the
  line `WATCH = [("Nancy", "Pelosi")]`, and add another name. Ask me if unsure.
- This uses public government records, for transparency and education. Not
  investment advice.

If any step looks different from what's written, screenshot it and I'll tell you
exactly what to click.
