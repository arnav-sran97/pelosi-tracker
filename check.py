#!/usr/bin/env python3
"""
check.py — runs on GitHub's servers every few hours.

What it does, top to bottom:
  1. Downloads the latest Pelosi filings from the official House Clerk website.
  2. Compares them to what it saw last time (remembered in seen.json).
  3. If there's a NEW filing: emails you the trades, and updates the data file
     the phone app reads (docs/latest.json) so the app shows it too.

No server, no website to keep alive. GitHub Actions wakes this up on a schedule,
runs it, and goes back to sleep. Totally free.

Your email login is read from "secrets" you set in GitHub (never written here).
"""

import io, os, re, json, zipfile, smtplib, pathlib, datetime as dt
import urllib.request
import xml.etree.ElementTree as ET
from email.mime.text import MIMEText

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

HERE = pathlib.Path(__file__).parent
DOCS = HERE / "docs"                 # GitHub Pages serves this folder
DOCS.mkdir(exist_ok=True)
SEEN = HERE / "seen.json"            # memory of filings already alerted

UA = {"User-Agent": "PelosiTracker/1.0 (personal transparency tool)"}
BASE = "https://disclosures-clerk.house.gov/public_disc"
WATCH = [("Nancy", "Pelosi")]        # add (first, last) tuples to track others

# ---- amount range -> short label + midpoint (for the portfolio view) --------
RANGE_MID = {
    "$1,001 - $15,000": 8000, "$15,001 - $50,000": 32500,
    "$50,001 - $100,000": 75000, "$100,001 - $250,000": 175000,
    "$250,001 - $500,000": 375000, "$500,001 - $1,000,000": 750000,
    "$1,000,001 - $5,000,000": 3000000, "$5,000,001 - $25,000,000": 15000000,
    "$25,000,001 - $50,000,000": 37500000,
}
def short_range(r):
    m = {"$1,001 - $15,000":"$1K–$15K","$15,001 - $50,000":"$15K–$50K",
         "$50,001 - $100,000":"$50K–$100K","$100,001 - $250,000":"$100K–$250K",
         "$250,001 - $500,000":"$250K–$500K","$500,001 - $1,000,000":"$500K–$1M",
         "$1,000,001 - $5,000,000":"$1M–$5M","$5,000,001 - $25,000,000":"$5M–$25M",
         "$25,000,001 - $50,000,000":"$25M–$50M"}
    return m.get(r.strip(), r.strip())

# ---------------------------------------------------------------- fetch
def _get(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read() if binary else r.read().decode("utf-8", "replace")

def get_year_index(year):
    raw = _get(f"{BASE}/financial-pdfs/{year}FD.zip", binary=True)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    xml_name = next(n for n in zf.namelist() if n.lower().endswith(".xml"))
    root = ET.fromstring(zf.read(xml_name))
    out = []
    for m in root.findall(".//Member"):
        g = lambda t: (m.findtext(t) or "").strip()
        out.append({"first": g("First"), "last": g("Last"),
                    "filing_type": g("FilingType"), "doc_id": g("DocID"),
                    "year": g("Year"), "filing_date": g("FilingDate")})
    return out

# ---------------------------------------------------------------- parse
TRADE_RX = re.compile(
    r"(?:(?P<owner>SP|JT|DC|Self)\b)?(?P<between>(?:(?!\b(?:SP|JT|DC|Self)\b).)*?)"
    r"\((?P<ticker>[A-Z]{1,6})\)\s*\[(?P<kind>[A-Z]{2})\]\s*"
    r"(?P<action>P|S\s*\(partial\)|S|E)\s+"
    r"(?P<traded>\d{2}/\d{2}/\d{4})\s+(?P<notif>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<amount>\$[\d,]+(?:\s*-\s*\$[\d,]+)?)", re.S)
ACTION = {"P":"Buy","S":"Sell","S (partial)":"Sell","E":"Other"}
KIND   = {"ST":"Stock","OP":"Options","AB":"Stock"}
OWNER  = {"SP":"Spouse","JT":"Joint","DC":"Dependent","Self":"Nancy Pelosi"}

def _iso(mdY):
    mo,d,y = mdY.split("/"); return f"{y}-{mo}-{d}"

def parse_ptr_text(text):
    trades=[]; last="Nancy Pelosi"
    for m in TRADE_RX.finditer(text):
        oc=(m["owner"] or "").strip(); owner=OWNER.get(oc,last); last=owner
        amt=re.sub(r"\s*-\s*"," - ",m["amount"]).strip()
        trades.append({"tk":m["ticker"],"owner":owner,
            "action":ACTION.get(re.sub(r"\s+"," ",m["action"]).strip(),"Other"),
            "kind":KIND.get(m["kind"],"Stock"),"amount":short_range(amt),
            "mid":RANGE_MID.get(amt,0),"traded":_iso(m["traded"])})
    return trades

def parse_ptr_pdf(year, doc_id):
    if PdfReader is None: raise RuntimeError("pip install pypdf")
    raw=_get(f"{BASE}/ptr-pdfs/{year}/{doc_id}.pdf", binary=True)
    text="\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages)
    return parse_ptr_text(text)

# ---------------------------------------------------------------- email
SUBS = HERE / "subscribers.json"   # list of subscriber emails

def get_recipients():
    """Return list of emails to alert. Combines EMAIL_TO secret + subscribers.json."""
    user = os.getenv("SMTP_USER")
    owner = os.getenv("EMAIL_TO") or user  # the repo owner always gets alerts
    subs = load(SUBS, {}).get("emails", [])
    all_to = list({owner} | set(subs)) if owner else list(set(subs))
    return [e for e in all_to if e]

def send_email(subject, body, recipients=None):
    user=os.getenv("SMTP_USER"); pw=os.getenv("SMTP_PASS")
    if not (user and pw):
        print("(no email secrets set — skipping email, just updating the app data)")
        return
    if recipients is None:
        recipients = get_recipients()
    if not recipients:
        print("(no recipients configured)")
        return
    for to in recipients:
        try:
            msg=MIMEText(body); msg["Subject"]=subject; msg["From"]=user; msg["To"]=to
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
                s.login(user, pw); s.send_message(msg)
            print(f"Emailed {to}")
        except Exception as e:
            print(f"Failed to email {to}: {e}")

# ---------------------------------------------------------------- main
def load(p,d):
    try: return json.loads(p.read_text())
    except Exception: return d

def run():
    year=dt.date.today().year
    seen=set(load(SEEN,{}).get("seen",[]))
    watch={(f.lower(),l.lower()) for f,l in WATCH}

    filings=[f for f in get_year_index(year)
             if f["filing_type"]=="P" and (f["first"].lower(),f["last"].lower()) in watch]
    filings.sort(key=lambda f:f["doc_id"], reverse=True)
    if not filings:
        print("No filings found this year."); return

    all_trades=[]; fresh=[]
    for f in filings:
        try: tr=parse_ptr_pdf(f["year"], f["doc_id"])
        except Exception as e: print("parse error",f["doc_id"],e); continue
        fd=_iso(f["filing_date"]) if "/" in f["filing_date"] else f["filing_date"]
        for t in tr: t["filed"]=fd; t["docId"]=f["doc_id"]
        all_trades.extend(tr)
        if f["doc_id"] not in seen: fresh.append((f,tr,fd))

    newest=filings[0]
    nd=_iso(newest["filing_date"]) if "/" in newest["filing_date"] else newest["filing_date"]
    (DOCS/"latest.json").write_text(json.dumps({
        "latestFilingId":newest["doc_id"],"latestFilingDate":nd,
        "updated":dt.datetime.utcnow().isoformat()+"Z","trades":all_trades}, indent=2))
    print(f"Updated app data — {len(all_trades)} trades, latest #{newest['doc_id']}")

    if fresh:
        recipients = get_recipients()
        print(f"Sending alerts to {len(recipients)} recipient(s): {recipients}")
        for f,tr,fd in fresh:
            lines=[f"{t['action'].upper():5} {t['tk']:6} {t['amount']:10} — {t['owner']} ({t['kind']})" for t in tr]
            body=(f"New Pelosi filing disclosed\n"
                  f"Filing #{f['doc_id']} • disclosed {fd} • {len(tr)} trades\n\n"
                  + "\n".join(lines) +
                  f"\n\nView the full filing:\n{BASE}/ptr-pdfs/{f['year']}/{f['doc_id']}.pdf\n"
                  f"\nSee all trades: https://arnav-sran97.github.io/pelosi-tracker/\n")
            print("ALERT:\n"+body)
            send_email(f"🏛️ New Pelosi filing — {len(tr)} trades (#{f['doc_id']})", body, recipients)
            seen.add(f["doc_id"])
        SEEN.write_text(json.dumps({"seen":sorted(seen)}, indent=2))
    else:
        print("No new filings since last check.")

if __name__=="__main__":
    import sys
    if "--backfill" in sys.argv:
        year=dt.date.today().year
        watch={(f.lower(),l.lower()) for f,l in WATCH}
        ids=[f["doc_id"] for f in get_year_index(year)
             if f["filing_type"]=="P" and (f["first"].lower(),f["last"].lower()) in watch]
        SEEN.write_text(json.dumps({"seen":sorted(set(ids))}, indent=2))
        print(f"Marked {len(ids)} existing filings as already-seen.")
    else:
        run()
