/**
 * Pelosi Tracker — Cloudflare Worker
 *
 * Endpoints:
 *   POST /subscribe   { "email": "user@example.com" }
 *   POST /unsubscribe { "email": "user@example.com" }
 *   GET  /health      → 200 OK
 *
 * Required secrets (set via `wrangler secret put`):
 *   GITHUB_TOKEN  — fine-grained PAT with Contents: read+write on the pelosi-tracker repo
 *
 * Required vars (set in wrangler.toml or dashboard):
 *   GITHUB_OWNER  — your GitHub username
 *   GITHUB_REPO   — "pelosi-tracker"
 *   ALLOWED_ORIGIN — "https://arnav-sran97.github.io" (or * for testing)
 */

const SUBS_PATH = "subscribers.json";

// ---------------------------------------------------------------- helpers

function corsHeaders(origin, env) {
  const allowed = env.ALLOWED_ORIGIN || "*";
  const ok = allowed === "*" || origin === allowed;
  return {
    "Access-Control-Allow-Origin": ok ? (allowed === "*" ? "*" : origin) : "",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...extraHeaders },
  });
}

function isValidEmail(e) {
  return typeof e === "string" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e.trim());
}

// ---------------------------------------------------------------- GitHub API

async function getFile(env) {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${SUBS_PATH}`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "pelosi-tracker-worker",
    },
  });
  if (!res.ok) {
    if (res.status === 404) return { emails: [], sha: null };
    throw new Error(`GitHub GET failed: ${res.status}`);
  }
  const data = await res.json();
  const content = JSON.parse(atob(data.content.replace(/\n/g, "")));
  return { emails: content.emails || [], sha: data.sha };
}

async function putFile(env, emails, sha) {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${SUBS_PATH}`;
  const body = {
    message: "Update subscribers",
    content: btoa(JSON.stringify({ emails }, null, 2) + "\n"),
  };
  if (sha) body.sha = sha;

  const res = await fetch(url, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      "User-Agent": "pelosi-tracker-worker",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`GitHub PUT failed: ${res.status} ${await res.text()}`);
  return res.json();
}

// ---------------------------------------------------------------- handlers

async function handleSubscribe(req, env, cors) {
  let body;
  try { body = await req.json(); } catch { return json({ error: "Invalid JSON" }, 400, cors); }

  const email = (body.email || "").trim().toLowerCase();
  if (!isValidEmail(email)) return json({ error: "Invalid email address" }, 400, cors);

  const { emails, sha } = await getFile(env);
  if (emails.includes(email)) return json({ ok: true, message: "Already subscribed" }, 200, cors);
  if (emails.length >= 5000) return json({ error: "Subscriber list full" }, 503, cors);

  emails.push(email);
  await putFile(env, emails, sha);
  return json({ ok: true, message: "Subscribed! You'll get an email on the next Pelosi filing." }, 200, cors);
}

async function handleUnsubscribe(req, env, cors) {
  let body;
  try { body = await req.json(); } catch { return json({ error: "Invalid JSON" }, 400, cors); }

  const email = (body.email || "").trim().toLowerCase();
  if (!isValidEmail(email)) return json({ error: "Invalid email address" }, 400, cors);

  const { emails, sha } = await getFile(env);
  const filtered = emails.filter(e => e !== email);
  if (filtered.length === emails.length) return json({ ok: true, message: "Email not found" }, 200, cors);

  await putFile(env, filtered, sha);
  return json({ ok: true, message: "Unsubscribed successfully." }, 200, cors);
}

// ---------------------------------------------------------------- main

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const origin = req.headers.get("Origin") || "";
    const cors = corsHeaders(origin, env);

    // CORS preflight
    if (req.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    // Health check
    if (url.pathname === "/health" && req.method === "GET") {
      return json({ ok: true }, 200, cors);
    }

    // Routes
    if (url.pathname === "/subscribe" && req.method === "POST") {
      return handleSubscribe(req, env, cors);
    }
    if (url.pathname === "/unsubscribe" && req.method === "POST") {
      return handleUnsubscribe(req, env, cors);
    }

    return json({ error: "Not found" }, 404, cors);
  },
};
