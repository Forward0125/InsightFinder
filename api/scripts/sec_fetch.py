"""Fetch latest 10-K + 10-Q filings from SEC EDGAR for our 8 demo companies.

SEC EDGAR serves filings as HTML (no native PDF). The "primary document"
of each filing is the company's submitted iXBRL-tagged HTML. We save it
verbatim to data/raw/<TICKER>/<FILING_TYPE>_<PERIOD>_<ACCESSION>.htm
and write an index CSV mapping every file to its metadata.

SEC requires:
  - A meaningful User-Agent (preferably with contact info or a project URL)
  - <= 10 requests per second; we use ~150ms between requests to stay polite

Re-running is idempotent: existing files are skipped.

Usage:
    cd api
    uv run python scripts/sec_fetch.py                 # latest 2 each
    uv run python scripts/sec_fetch.py --max 4         # latest 4 each
    uv run python scripts/sec_fetch.py --tickers AAPL,MSFT
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx


# Repo root: api/scripts/sec_fetch.py -> api/scripts -> api -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "raw"
INDEX_CSV = DATA_DIR / "_index.csv"

# SEC requires a contact-info User-Agent, format: "Name email@domain.com".
# Their sample: "Sample Company Name AdminContact@samplecompany.com".
# Override via SEC_USER_AGENT env var to use your real email.
DEFAULT_USER_AGENT = "InsightFinder Demo demo@insightfinder.dev"
USER_AGENT = os.environ.get("SEC_USER_AGENT", DEFAULT_USER_AGENT)

# (ticker, name, CIK left-padded to 10 digits)
COMPANIES: list[tuple[str, str, str]] = [
    ("AAPL",  "Apple Inc.",            "0000320193"),
    ("MSFT",  "Microsoft Corporation", "0000789019"),
    ("GOOGL", "Alphabet Inc.",         "0001652044"),
    ("AMZN",  "Amazon.com, Inc.",      "0001018724"),
    ("TSLA",  "Tesla, Inc.",           "0001318605"),
    ("NVDA",  "NVIDIA Corporation",    "0001045810"),
    ("META",  "Meta Platforms, Inc.",  "0001326801"),
    ("NFLX",  "Netflix, Inc.",         "0001065280"),
]

FILING_TYPES = ["10-K", "10-Q"]
RATE_LIMIT_SLEEP = 0.15  # ~6.6 req/sec, safely under SEC's 10/sec hard limit
TIMEOUT = 60.0


# ─── Filing record ───────────────────────────────────────────────


@dataclass
class Filing:
    ticker: str
    company_name: str
    cik: str
    filing_type: str
    accession_number: str
    filing_date: str
    period_of_report: str
    primary_document: str
    document_url: str
    local_path: Path


# ─── EDGAR API ────────────────────────────────────────────────────


def list_company_filings(
    client: httpx.Client, ticker: str, name: str, cik: str
) -> list[Filing]:
    """Fetch /submissions/CIK{cik}.json and return Filing rows for our types."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    r = client.get(url)
    r.raise_for_status()
    data = r.json()

    recent = data["filings"]["recent"]
    n = len(recent["accessionNumber"])

    filings: list[Filing] = []
    for i in range(n):
        ftype = recent["form"][i]
        if ftype not in FILING_TYPES:
            continue

        accession = recent["accessionNumber"][i]                         # e.g. "0000320193-24-000123"
        accession_no_dashes = accession.replace("-", "")
        primary = recent["primaryDocument"][i]                            # e.g. "aapl-20240928.htm"
        filing_date = recent["filingDate"][i]
        period = recent["reportDate"][i]

        archive_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{int(cik)}/{accession_no_dashes}/{primary}"
        )

        local_filename = f"{ftype}_{period}_{accession}.htm"
        filings.append(
            Filing(
                ticker=ticker,
                company_name=name,
                cik=cik,
                filing_type=ftype,
                accession_number=accession,
                filing_date=filing_date,
                period_of_report=period,
                primary_document=primary,
                document_url=archive_url,
                local_path=DATA_DIR / ticker / local_filename,
            )
        )
    return filings


def download_filing(client: httpx.Client, f: Filing) -> tuple[bool, int]:
    """Download primary document. Returns (downloaded_now, size_bytes)."""
    if f.local_path.exists():
        return False, f.local_path.stat().st_size

    f.local_path.parent.mkdir(parents=True, exist_ok=True)
    r = client.get(f.document_url)
    r.raise_for_status()
    f.local_path.write_bytes(r.content)
    return True, len(r.content)


# ─── Main ────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--max", type=int, default=2,
        help="Most recent N of each filing type per company (default: 2).",
    )
    parser.add_argument(
        "--tickers", default="",
        help="Comma-separated subset of tickers (default: all 8).",
    )
    args = parser.parse_args()

    wanted_tickers = (
        {t.strip().upper() for t in args.tickers.split(",") if t.strip()}
        if args.tickers else None
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"User-Agent: {USER_AGENT}")
    print(f"Max per type per company: {args.max}")
    print(f"Output: {DATA_DIR.relative_to(PROJECT_ROOT)}\n")

    # httpx sets the Host header automatically based on each request URL,
    # so we just need a User-Agent and Accept-Encoding.
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
    }

    rows: list[dict] = []
    total_bytes = 0
    new_count = 0
    skipped_count = 0

    with httpx.Client(headers=headers, timeout=TIMEOUT, follow_redirects=True) as client:
        for ticker, name, cik in COMPANIES:
            if wanted_tickers and ticker not in wanted_tickers:
                continue

            print(f"[{ticker}] {name}")
            try:
                all_filings = list_company_filings(client, ticker, name, cik)
            except httpx.HTTPError as e:
                print(f"  -> failed to list filings: {e}")
                continue
            time.sleep(RATE_LIMIT_SLEEP)

            # Pick the most recent N of each filing type.
            by_type: dict[str, list[Filing]] = {}
            for f in all_filings:
                by_type.setdefault(f.filing_type, []).append(f)

            picks: list[Filing] = []
            for ftype in FILING_TYPES:
                picks.extend(by_type.get(ftype, [])[: args.max])

            for f in picks:
                try:
                    new, size = download_filing(client, f)
                except httpx.HTTPError as e:
                    print(f"  -> {f.filing_type} {f.period_of_report} FAILED: {e}")
                    continue

                marker = "NEW" if new else "..."
                print(
                    f"  {marker} {f.filing_type:<5} period={f.period_of_report}  "
                    f"{size / 1024:>6.0f} KB  {f.local_path.name}"
                )
                rows.append({
                    "ticker": f.ticker,
                    "company_name": f.company_name,
                    "cik": f.cik,
                    "filing_type": f.filing_type,
                    "accession_number": f.accession_number,
                    "filing_date": f.filing_date,
                    "period_of_report": f.period_of_report,
                    "primary_document": f.primary_document,
                    "source_url": f.document_url,
                    "local_path": str(f.local_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                    "size_bytes": size,
                })

                if new:
                    new_count += 1
                else:
                    skipped_count += 1
                total_bytes += size
                time.sleep(RATE_LIMIT_SLEEP)

    if not rows:
        print("\nNo filings collected.")
        return 1

    INDEX_CSV.parent.mkdir(parents=True, exist_ok=True)
    with INDEX_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print()
    print("-" * 60)
    print(f"Index:        {INDEX_CSV.relative_to(PROJECT_ROOT)}")
    print(f"Total:        {len(rows)} filings  ({total_bytes / 1e6:.1f} MB)")
    print(f"Newly fetched: {new_count}    skipped (already cached): {skipped_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
