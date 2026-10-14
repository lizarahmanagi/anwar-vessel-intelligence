# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python automation project ("osiris") that scrapes the Chittagong Port Authority (CPA) daily vessel-information PDF, extracts the vessel table to CSV, runs a Groq LLM analysis over it, and emails an HTML report to the recipients in `.env`. Built for Anwar Group of Industries. There is no package manager manifest, no test suite, and no web app — the `Dockerfile` and `.next/` directory are leftovers from an unrelated Next.js project and are not used by anything here.

## Commands

```bash
# Full daily pipeline: download PDF -> CSV -> LLM -> markdown report -> email
python3 daily_analysis.py

# Weekly aggregate report (compares vs previous week, emails summary)
python3 weekly_report.py

# Individual stages (each module is runnable standalone via its main())
python3 extract_pdf_to_csv.py      # scrape + extract only, writes vessels_data.csv
python3 analyze_with_groq.py       # LLM analysis over vessels_data.csv
python3 send_report_email.py       # re-send the latest reports/*.md as HTML email

# Context-compression benchmark (unrelated to the vessel pipeline)
python3 benchmark_tooling.py       # writes benchmark_results.json
python3 generate_tooling_report.py # renders that JSON to tooling_benefits_report_osiris.pdf
```

Dependencies are installed globally (no venv, no requirements file): `requests`, `beautifulsoup4`, `PyPDF2`, `pandas`, `python-dotenv`, `langchain-groq`, plus `tiktoken` and `PyMuPDF` (`fitz`) for the benchmark scripts.

Scheduling is via crontab (see [SCHEDULE.md](SCHEDULE.md)): daily 6 AM `daily_analysis.py`, Sunday 8 AM `weekly_report.py`.

## Architecture

`daily_analysis.py` is the orchestrator; every other module exposes one class that it composes:

| Module | Class | Role |
|---|---|---|
| [extract_pdf_to_csv.py](extract_pdf_to_csv.py) | `PDFExtractor` | Scrapes cpa.gov.bd for the newest vessel PDF, downloads it to the project root (UUID filename), parses the table with PyPDF2 + regex, writes `vessels_data.csv` |
| [analyze_with_groq.py](analyze_with_groq.py) | `VesselAnalyzer` | LangChain `ChatGroq` (`meta-llama/llama-4-scout-17b-16e-instruct`) → business recommendations text, saved to `analysis_output.txt` |
| [generate_markdown_report.py](generate_markdown_report.py) | `MarkdownReportGenerator` | The live report generator → `reports/vessel_analysis_DD_MM_YYYY.md` |
| [generate_report.py](generate_report.py) | `ReportGenerator` | Older HTML variant; constructed by the pipeline but its output is not used downstream |
| [weekly_analysis.py](weekly_analysis.py) | `WeeklyAnalyzer` | Maintains `weekly_data/weekly_history.json` snapshots and computes week-over-week deltas |
| [send_report_email.py](send_report_email.py) | `EmailReportSender` | Converts the markdown report to styled HTML, sends via Gmail SMTP |

Pipeline failure semantics matter: PDF extraction failing is **fatal** (guards against emailing stale data), while a missing Groq key or missing email credentials only degrades — `VesselAnalyzer` and `EmailReportSender` are constructed in try/except and set to `None`, and LLM failure substitutes `_get_fallback_analysis()`.

The derived business columns (Type / Utilization / Revenue / Efficiency) are **not** in the source PDF — they are computed by the `_calc_*` helpers in `MarkdownReportGenerator` from `Cargo_Type`, `Cargo_Qty`/`GRT`, and `Section`. If a column looks wrong, fix the heuristic there. Note that `send_report_email.py` re-derives similar metrics for its HTML table; keep the two in sync.

CSV columns produced by the extractor include: `Vessel_Name`, `Length`, `Draft`, `GRT`, `Arrival_Date`, `Cargo_Type`, `Cargo_Qty`, `Local_Agent`, `Section`.

## Conventions to preserve

- Paths are hardcoded absolute: every class defaults to `project_dir="/home/musa/Desktop/osiris"`, and log handlers use full paths. Prefer threading `project_dir` through over adding new hardcoded strings.
- Logging is emoji-prefixed (`✅`/`❌`/`⚠️`) and goes to both a `.log` file and stdout; entry points `exit(0/1)` so cron can detect failure.
- The CPA scraper sets `session.verify = False` and suppresses urllib3 warnings — the site's TLS chain is broken; don't "fix" this by removing the flag without checking.
- Secrets live in `.env` (`GROQ_API_KEY`, `SENDER_EMAIL`, `SENDER_APP_PASSWORD`, `RECEIVER_EMAILS` comma-separated) and it is gitignored.

## Unrelated files in the tree

`benchmark_tooling.py` / `generate_tooling_report.py` / `benchmark_results.json` / `graphify-out/` measure token-compression savings over this repo's own source — a separate concern from vessel tracking. `fix_netdata.py` and `fix_umami.py` are one-off server-config patch scripts. `exmple.sh` is a bash trap demo. `index.html` and `full_vessel_report.html` are stale generated output.
