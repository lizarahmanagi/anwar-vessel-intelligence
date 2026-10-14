#!/usr/bin/env python3
"""
Daily analysis orchestrator - combines PDF extraction, LLM analysis, and report generation
"""

import os
import logging
from datetime import datetime
from extract_pdf_to_csv import PDFExtractor
from analyze_with_groq import VesselAnalyzer
from generate_report import ReportGenerator
from generate_markdown_report import MarkdownReportGenerator
from send_report_email import EmailReportSender

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(PROJECT_DIR, 'daily_analysis.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DailyAnalysisPipeline:
    def __init__(self, project_dir=PROJECT_DIR):
        self.project_dir = project_dir
        self.csv_file = os.path.join(project_dir, "vessels_data.csv")
        self.analysis_file = os.path.join(project_dir, "analysis_output.txt")

        self.extractor = PDFExtractor(project_dir)
        self.generator = ReportGenerator(project_dir)
        self.md_generator = MarkdownReportGenerator(project_dir)

        # Initialize LLM analyzer (optional - pipeline can still report CSV data)
        try:
            self.analyzer = VesselAnalyzer()
        except ValueError as e:
            logger.warning(f"⚠️  LLM analysis not configured: {str(e)}")
            self.analyzer = None

        # Initialize email sender (optional - may fail if .env not configured)
        try:
            self.email_sender = EmailReportSender()
        except ValueError as e:
            logger.warning(f"⚠️  Email not configured: {str(e)}")
            self.email_sender = None

    def run(self):
        """Run complete daily analysis pipeline"""
        logger.info("=" * 70)
        logger.info("🚀 DAILY ANALYSIS PIPELINE STARTED")
        logger.info("=" * 70)

        try:
            # STEP 1: Download latest CPA PDF and extract vessel table to CSV
            logger.info("\n📋 STEP 1: Downloading and Extracting Vessel Data...")
            logger.info("-" * 70)

            if not self.extractor.run():
                logger.error("❌ PDF extraction failed; stopping to avoid stale report data")
                return False

            if not os.path.exists(self.csv_file) or os.path.getsize(self.csv_file) == 0:
                logger.error(f"❌ CSV file missing or empty after extraction: {self.csv_file}")
                return False

            # STEP 2: Analyze with Groq LLM
            logger.info("\n🤖 STEP 2: Analyzing with Groq LLM...")
            logger.info("-" * 70)

            analysis_text = self.analyzer.analyze_vessels(self.csv_file) if self.analyzer else None

            if analysis_text:
                # Save analysis to file
                self.analyzer.save_analysis(analysis_text, self.analysis_file)
            else:
                logger.error("❌ LLM analysis failed")
                analysis_text = self._get_fallback_analysis()

            # STEP 3: Generate Markdown Report
            logger.info("\n📝 STEP 3: Generating Markdown Report...")
            logger.info("-" * 70)

            md_report = self.md_generator.generate_markdown_report(
                self.csv_file,
                analysis_text
            )

            if md_report:
                logger.info(f"✅ Markdown Report: {md_report}")
            else:
                logger.error("❌ Report generation failed")
                return False

            # STEP 4: Send Email Report
            if self.email_sender:
                logger.info("\n📧 STEP 4: Sending Report via Email...")
                logger.info("-" * 70)

                try:
                    if self.email_sender.send_email(md_report):
                        logger.info("✅ Report email sent successfully")
                    else:
                        logger.warning("⚠️  Failed to send report email")
                except Exception as e:
                    logger.warning(f"⚠️  Email sending error: {str(e)}")
            else:
                logger.info("\n📧 STEP 4: Email sending disabled (not configured)")

            # STEP 5: Summary
            logger.info("\n" + "=" * 70)
            logger.info("✅ DAILY ANALYSIS PIPELINE COMPLETED SUCCESSFULLY!")
            logger.info("=" * 70)

            logger.info(f"\n📊 Summary:")
            logger.info(f"   • CSV: {self.csv_file}")
            logger.info(f"   • Analysis: {self.analysis_file}")
            logger.info(f"   • Report: {md_report}")
            logger.info(f"   • Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            return True

        except Exception as e:
            logger.error(f"\n❌ PIPELINE FAILED: {str(e)}")
            logger.error("=" * 70)
            return False

    def _get_fallback_analysis(self):
        """Fallback analysis if LLM fails"""
        return """
ERROR: LLM analysis temporarily unavailable.

FALLBACK STATUS:
- Vessel data extracted and stored in CSV
- Fleet statistics calculated
- Report will be generated with available data

Please check:
1. Groq API key is valid (.env file)
2. Internet connection is working
3. Groq API service is online

The system will retry at next scheduled run (6 AM daily).
"""


def main():
    """Main entry point"""
    try:
        pipeline = DailyAnalysisPipeline()
        success = pipeline.run()
        exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
