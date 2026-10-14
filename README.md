# Osiris — Anwar Group of Industries Vessel Tracking

Osiris is a Python automation service that turns Chittagong Port Authority (CPA) vessel-lineup PDFs into a daily business report. It downloads the latest CPA PDF, extracts vessel records into a CSV file, optionally asks Groq for a port-intelligence briefing, produces a Markdown report, and can deliver a styled HTML email through Gmail.

This repository is a collection of runnable Python scripts, not a packaged application or web service. The production entry points are `daily_analysis.py` and `weekly_report.py`.

## Quick start

Use Python 3.10 or later. From the project root, create and activate a virtual environment, then install the libraries used by the scripts:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests beautifulsoup4 PyPDF2 pandas python-dotenv langchain-groq
```

`benchmark_tooling.py` and `generate_tooling_report.py` are separate utilities and additionally need `tiktoken` and `PyMuPDF`.

Create a `.env` file in the repository root:

```dotenv
# Optional: without this, the daily report uses a built-in fallback analysis.
GROQ_API_KEY=your_groq_key
GROQ_MODEL=openai/gpt-oss-120b

# Optional: without these, reports are created locally but not emailed.
SENDER_EMAIL=sender@example.com
SENDER_APP_PASSWORD=gmail_app_password
RECEIVER_EMAILS=first@example.com,second@example.com
```

Run the complete daily workflow:

```bash
python3 daily_analysis.py
```

The extractor needs access to the CPA website. The implementation deliberately disables TLS verification for that site because its certificate chain has historically been unreliable; do not change that behavior without validating the live endpoint.

## Daily workflow

```text
CPA common-documents page
        │
        ▼
PDFExtractor ──► downloaded PDF ──► vessels_data.csv
        │
        ├──► VesselAnalyzer (Groq, optional) ──► analysis_output.txt
        │
        ▼
MarkdownReportGenerator ──► reports/vessel_analysis_DD_MM_YYYY.md
        │
        ▼
EmailReportSender (Gmail SMTP, optional) ──► recipients
```

`DailyAnalysisPipeline.run()` in `daily_analysis.py` coordinates these steps.

1. `PDFExtractor` finds the first PDF in CPA's vessel-information document listing, downloads it to the project root, parses its text with `PyPDF2` and regular expressions, and overwrites `vessels_data.csv`.
2. `VesselAnalyzer` reads that CSV and sends a computed data brief to Groq. Its prompt requests a factual maritime/business analysis and uses the weekly history when available.
3. `MarkdownReportGenerator` calculates headline metrics and derived vessel labels, embeds the analysis, and writes the date-stamped report.
4. `EmailReportSender` reads the Markdown report, rebuilds its presentation as HTML, and sends it with Gmail SMTP over SSL.

Extraction is the safety boundary: if CPA download, parsing, or CSV creation fails, the daily run fails before any report is emailed. Groq and email are optional integrations: their configuration or runtime failure leaves a local report available, with fallback analysis when needed.

## Main components

| File | Main class/function | Responsibility |
| --- | --- | --- |
| `daily_analysis.py` | `DailyAnalysisPipeline` | Production daily orchestrator. |
| `extract_pdf_to_csv.py` | `PDFExtractor` | Scrapes CPA, downloads a PDF, detects section headings, parses several PDF row layouts, and writes the canonical CSV. |
| `analyze_with_groq.py` | `VesselAnalyzer` | Builds data-derived prompt context and invokes Groq through LangChain. |
| `generate_markdown_report.py` | `MarkdownReportGenerator` | Creates the daily Markdown report and its business-oriented vessel table. |
| `send_report_email.py` | `EmailReportSender` | Converts a daily Markdown report into a styled email and sends it through Gmail SMTP. |
| `weekly_analysis.py` | `WeeklyAnalyzer` | Summarizes the current CSV and stores one snapshot per calendar week. |
| `weekly_report.py` | `WeeklyReportSender` | Produces, saves, and optionally emails the weekly report. |

## Data contract

`vessels_data.csv` is the shared boundary between the extractor and the reporting/analysis code. The extractor writes these columns:

| Group | Columns |
| --- | --- |
| Identity | `SL.NO`, `Vessel_Name`, `IMO` |
| Dimensions and timing | `Length`, `Draft`, `Arrival_Date`, `GRT`, `Update_Date` |
| Routing and ownership | `Last_Port`, `Call_Flag`, `Local_Agent`, `Shipping_Line`, `Loading_Port` |
| Cargo and state | `Cargo_Quantity`, `Cargo_Type`, `Section` |

The source PDF is semi-structured. `PDFExtractor._parse_vessel_line()` contains the regular expressions for the known CPA layouts, while `_section_from_line()` maps CPA headings to `Section`. When the CPA document changes, update and test those helpers first.

The report's `Type`, `Utilization`, `Revenue`, `Efficiency`, and `Status` values are derived labels, not fields supplied by CPA. Daily Markdown logic lives in the `_calc_*` helpers of `generate_markdown_report.py`; similar formatting logic is duplicated in `send_report_email.py`. If a rule changes, update both implementations so the emailed table agrees with the saved report.

## Reports and stored output

| Path | Produced by | Meaning |
| --- | --- | --- |
| `vessels_data.csv` | extractor | Latest extracted vessel lineup; overwritten on each successful daily extraction. |
| `analysis_output.txt` | Groq analyzer | Latest successful LLM response; overwritten. |
| `reports/vessel_analysis_DD_MM_YYYY.md` | daily report generator | Date-stamped daily report. |
| `reports/weekly_report_DD_MM_YYYY.md` | weekly report sender | Date-stamped weekly report. |
| `weekly_data/weekly_history.json` | weekly analyzer | A summary snapshot keyed by `YYYY-W%U`; used for week-over-week comparison. |
| `daily_analysis.log`, `weekly_analysis.log` | entry points / cron | Operational logs. |
| `*.pdf` in the root | extractor | Downloaded source PDFs; retained rather than automatically deleted. |

The daily report reads weekly history but does not add a new weekly snapshot. A weekly snapshot is added only by `weekly_report.py` (or direct execution of `weekly_analysis.py`).

## Running individual stages

```bash
# Download and parse the latest CPA PDF only
python3 extract_pdf_to_csv.py

# Generate Groq analysis for the current CSV
python3 analyze_with_groq.py

# Re-send the newest Markdown report
python3 send_report_email.py

# Generate and optionally email the weekly report
python3 weekly_report.py

# Print a weekly report without saving/emailing it
python3 weekly_analysis.py
```

Run a stage only when its input already exists. For example, `analyze_with_groq.py` expects `vessels_data.csv`, and the email script expects at least one Markdown file in `reports/`.

## Scheduling

The intended cron jobs are documented in `SCHEDULE.md`. Typical entries are:

```cron
0 6 * * * cd /home/musa/Desktop/osiris && /path/to/python daily_analysis.py >> daily_analysis.log 2>&1
0 8 * * 0 cd /home/musa/Desktop/osiris && /path/to/python weekly_report.py >> weekly_analysis.log 2>&1
```

Use an absolute Python path (for example, the virtual environment interpreter) in cron. Cron has a minimal environment, so the `cd` is important for locating `.env` and output paths.

## Developer notes and common changes

- **Change where data is sourced:** start in `PDFExtractor.get_latest_pdf()`. Preserve the `run()` contract: return `False` when no fresh usable CSV can be produced.
- **Support a new CPA PDF layout:** add a narrowly scoped pattern in `_parse_vessel_line()`, then run it against a saved source PDF and inspect the resulting CSV for shifted fields.
- **Change LLM content or model:** edit `VesselAnalyzer.create_analysis_prompt()` and `GROQ_MODEL`. The model must be available in the configured Groq account.
- **Change report calculations:** edit `MarkdownReportGenerator.calculate_statistics()` and its `_calc_*` helpers, then mirror relevant per-row changes in `EmailReportSender`.
- **Change recipients or Gmail account:** update `.env`; never commit credentials.
- **Relocate the project:** most classes default to `/home/musa/Desktop/osiris`, and the daily/weekly log handlers are hard-coded there. Pass `project_dir` when constructing classes or refactor these defaults together before moving the project.

## Non-production and legacy files

`generate_report.py` is an older HTML report generator. The daily pipeline instantiates `ReportGenerator` but does not call it; `generate_markdown_report.py` is the live report path.

`benchmark_tooling.py`, `generate_tooling_report.py`, `benchmark_results.json`, and `graphify-out/` are a separate source-context compression experiment. `fix_netdata.py`, `fix_umami.py`, `exmple.sh`, `index.html`, `full_vessel_report.html`, and the Dockerfile are not part of the vessel-report runtime. In particular, the Dockerfile describes an unrelated Next.js build and should not be used to deploy this Python pipeline without replacement.

## Troubleshooting

| Symptom | First checks |
| --- | --- |
| Daily pipeline stops at extraction | Check `daily_analysis.log`, CPA availability, and whether the current PDF format still matches the parser patterns. |
| Report contains stale data | The daily pipeline normally prevents this; verify that `vessels_data.csv` was modified during the run and that no stage was run manually against an old file. |
| No AI analysis | Confirm `GROQ_API_KEY`, the selected `GROQ_MODEL`, network access, and Groq service availability. The report should still be produced with fallback text. |
| Report is saved but not emailed | Verify all three email variables, use a Gmail App Password, and inspect the daily or weekly log. |
| No weekly comparison | At least two entries must exist in `weekly_data/weekly_history.json`; run the weekly workflow on separate calendar weeks. |

