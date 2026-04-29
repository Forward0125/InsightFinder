# InsightFinder Web

Next.js 16 frontend for [InsightFinder](../README.md).

## Run

Make sure the API is running first (`api/` — see its README), then:

```bash
cd web
npm install
npm run dev          # http://localhost:3000
```

The dev server proxies `/api/*` to the FastAPI backend at
`NEXT_PUBLIC_API_URL` (default `http://localhost:8000`), so the browser
hits same-origin routes and there's no CORS preflight in dev.

## Routes

| Path | Becomes (in step) | Matches screenshot |
|---|---|---|
| `/`           | Query — search bar, streaming answer, sources, eval gates  | step 12 (`02_1.webp`) |
| `/pipelines`  | Pipelines — DAG viz, recent jobs, "New Pipeline" upload    | step 13 (`02_2.webp`) |
| `/dashboard`  | Dashboard — KPIs, performance trends, alerts               | step 14 (`02_3.webp`) |

All three currently render placeholder shells. The homepage hits
`/health` to prove the frontend ↔ backend wiring works.

## Layout

```
web/
├── package.json
├── tsconfig.json
├── next.config.ts            # /api/* rewrite to NEXT_PUBLIC_API_URL
├── tailwind.config.ts        # design tokens identical to TwilightCore portfolio
├── app/
│   ├── layout.tsx            # fonts, theme provider, sidebar shell
│   ├── globals.css           # CSS variables for dark + light themes
│   ├── page.tsx              # Query view (live /health probe)
│   ├── pipelines/page.tsx
│   └── dashboard/page.tsx
├── components/
│   ├── layout/Sidebar.tsx
│   └── ui/Container.tsx
├── lib/
│   ├── utils.ts              # cn() Tailwind merger
│   └── api.ts                # typed API client
└── providers/
    └── ThemeProvider.tsx     # next-themes wrapper
```

## Dev commands

```bash
npm run dev         # autoreload on http://localhost:3000
npm run build       # production build
npm run lint        # eslint
npm run typecheck   # tsc --noEmit
```
