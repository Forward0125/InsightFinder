# Deploy InsightFinder

Two services, deployed in this order:

1. **API → Render** (Docker) — gets a URL like `https://insightfinder-api.onrender.com`
2. **Web → Vercel** (Next.js) — gets a URL like `https://insightfinder-xxx.vercel.app`

The frontend's env points at the API URL; the API's CORS list points back at the frontend URL. The chicken-and-egg is broken with one redeploy.

---

## 1. Render — API

### A. Create the service

1. [render.com](https://render.com) → **+ New** → **Web Service**
2. Connect your GitHub account if you haven't, then pick the **`InsightFinder`** repo
3. Render auto-detects [`render.yaml`](../render.yaml). Confirm:
   - **Name:** `insightfinder-api`
   - **Region:** Oregon (closest to most US users)
   - **Branch:** `main`
   - **Root directory:** `api`
   - **Runtime:** Docker
   - **Plan:** Free
   - **Health check path:** `/health`

### B. Set the secret env vars

Render shows a list of env vars from `render.yaml`. The three with `sync: false` need values:

| Key | Value |
|---|---|
| `DATABASE_URL` | Paste your Neon pooled connection string (from `.env`) |
| `OPENAI_API_KEY` | Paste your `sk-...` key (from `.env`) |
| `API_CORS_ORIGINS` | `*` for now — we tighten this in step 4 |

Click **Create Web Service**.

### C. Wait for first deploy (~5 min)

Build runs `docker build` on the `api/` dir, then starts the container. Watch the **Logs** tab. You'll see:

```
INFO  [alembic.runtime.migration] Running upgrade ... -> 0001_initial
INFO     Started server process [1]
INFO     Application startup complete.
INFO     Uvicorn running on http://0.0.0.0:10000
```

(Render injects `PORT=10000` for free-tier services.)

### D. Verify

Once it's "Live", grab the URL from the top of the page (`https://insightfinder-api.onrender.com`) and:

```bash
curl https://insightfinder-api.onrender.com/health
# expect: {"status":"ok","db":"ok"}
```

If it returns `db:"unreachable"`, your `DATABASE_URL` is wrong — fix it in **Environment** and Render will redeploy.

---

## 2. Vercel — Web

### A. Create the project

1. [vercel.com/new](https://vercel.com/new) → import the **`InsightFinder`** repo
2. **Configure:**
   - **Framework Preset:** Next.js (auto-detected)
   - **Root Directory:** `web`  ← **set this manually**
   - Build / Output: leave defaults

### B. Set env vars

In the same screen, **Environment Variables**:

| Key | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://insightfinder-api.onrender.com` (no trailing slash) |

Click **Deploy**.

### C. Wait (~2 min)

You'll get a URL like `https://insightfinder-forward0125.vercel.app`. Copy it.

---

## 3. Tighten Render's CORS

Back in Render → your service → **Environment**:

- Edit `API_CORS_ORIGINS`
  - Old: `*`
  - New: `https://insightfinder-forward0125.vercel.app` (your actual Vercel URL)

Render redeploys. Your frontend now talks to the API but no other origin can.

---

## 4. Smoke-test the live site

Open your Vercel URL. You should see:

- **`/`** — Query page. Type "What was Apple iPhone revenue in fiscal Q1 2026?" — answer streams from the deployed API.
- **`/pipelines`** — Recent jobs from your Neon DB show up. Click "New Pipeline Run" → pick a filing → DAG animates live.
- **`/dashboard`** — KPIs + 7-day chart populated from the same DB.

The first request to the API after idleness will be slow (~30s) — Render's free tier sleeps after 15min. Subsequent requests are normal speed.

---

## Updating

Just push to `main`. Both Vercel and Render auto-redeploy.

```bash
git push
```

Render: ~3 min for Docker rebuild
Vercel: ~1 min for Next.js build

---

## Cost expectations

| Service | Free tier covers? |
|---|---|
| Render Web Service | 750 hrs/month free (sleeps when idle) — **yes** |
| Vercel Hobby | 100 GB-hours bandwidth — **yes** for personal portfolio |
| Neon | 3 GB storage, autoscale-to-zero — **yes** |
| OpenAI | $5/day cap enforced in code — keep eye on dashboard |

---

## Production differences from local

| | Local | Production |
|---|---|---|
| Cross-encoder rerank | available (~16 s/query on CPU) | disabled (`ENABLE_RERANK=false`); falls back to hybrid silently |
| Cold start | none | ~30 s on first request after 15min idle |
| Daily $ cap | $5 (configurable) | $5 (configurable) |
| Per-IP rate limit on `/search/answer` | 30/hr | 30/hr |
| Per-IP rate limit on `/pipelines/runs` | 5/hr | 5/hr |
