#!/usr/bin/env python3
"""
Weekly report generator and email sender
"""

import os
from datetime import datetime, timedelta
from weekly_analysis import WeeklyAnalyzer
from send_report_email import EmailReportSender
import logging

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(PROJECT_DIR, 'weekly_analysis.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class WeeklyReportSender:
    def __init__(self, project_dir=PROJECT_DIR):
        self.project_dir = project_dir
        self.analyzer = WeeklyAnalyzer(project_dir)
        try:
            self.email_sender = EmailReportSender()
        except ValueError as e:
            logger.warning(f"⚠️  Email not configured: {str(e)}")
            self.email_sender = None

    def send_weekly_report(self):
        """Generate and send weekly report"""
        logger.info("=" * 70)
        logger.info("📊 WEEKLY REPORT GENERATOR STARTED")
        logger.info("=" * 70)

        try:
            # Generate weekly report content
            logger.info("\n📝 Generating weekly analysis...")
            logger.info("-" * 70)

            report_content = self.analyzer.generate_weekly_markdown_report(
                os.path.join(self.project_dir, "vessels_data.csv")
            )

            if not report_content:
                logger.error("❌ Failed to generate weekly report")
                return False

            logger.info("✅ Weekly report generated successfully")

            # Save weekly report to file
            week_start = (datetime.now() - timedelta(days=datetime.now().weekday()))
            filename = f"weekly_report_{week_start.strftime('%d_%m_%Y')}.md"
            report_path = os.path.join(self.project_dir, "reports", filename)

            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_content)

            logger.info(f"✅ Report saved: {filename}")

            # Send via email if configured
            if self.email_sender:
                logger.info("\n📧 SENDING WEEKLY REPORT VIA EMAIL")
                logger.info("-" * 70)

                try:
                    # Create email-friendly HTML from markdown
                    html_content = self._markdown_to_html(report_content)
                    if self.email_sender._send_weekly_email(html_content):
                        logger.info("✅ Weekly report sent successfully")
                    else:
                        logger.warning("⚠️  Failed to send weekly report email")
                except Exception as e:
                    logger.warning(f"⚠️  Email sending error: {str(e)}")
            else:
                logger.info("⚠️  Email not configured (report saved locally)")

            logger.info("\n" + "=" * 70)
            logger.info("✅ WEEKLY REPORT COMPLETED SUCCESSFULLY!")
            logger.info("=" * 70)

            return True

        except Exception as e:
            logger.error(f"❌ Failed to process weekly report: {str(e)}")
            return False

    def _markdown_to_html(self, markdown_text):
        """Convert markdown to simple HTML for email"""
        html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 900px; margin: 0 auto; background: #fff; padding: 20px; }
        .header { background: #1a3a52; color: white; padding: 20px; border-radius: 8px; }
        .header h1 { margin: 0; font-size: 24px; }
        .section { margin: 20px 0; }
        .section h2 { color: #1a3a52; border-bottom: 2px solid #667eea; padding-bottom: 10px; }
        .section h3 { color: #2d5a7b; margin-top: 15px; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f0f4f8; font-weight: bold; color: #1a3a52; }
        ul { margin: 10px 0; padding-left: 20px; }
        li { margin: 5px 0; }
        .footer { background: #f0f4f8; padding: 15px; text-align: center; margin-top: 30px; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Anwar Group of Industries - Weekly Port Activity Report</h1>
            <p>Chittagong Port Authority - Marine Department</p>
        </div>
"""

        # Convert basic markdown to HTML
        lines = markdown_text.split('\n')
        in_table = False
        table_rows = []

        for line in lines:
            if line.startswith('# '):
                html += f'<div class="section"><h2>{line[2:]}</h2>'
            elif line.startswith('## '):
                html += f'<div class="section"><h2>{line[3:]}</h2>'
            elif line.startswith('### '):
                html += f'<h3>{line[4:]}</h3>'
            elif line.startswith('**') and line.endswith('**'):
                html += f'<strong>{line[2:-2]}</strong>'
            elif line.startswith('|'):
                if not in_table:
                    html += '<table>'
                    in_table = True

                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if '-' in cells[0]:
                    continue

                html += '<tr>'
                for cell in cells:
                    html += f'<th>{cell}</th>' if '---' not in line else f'<td>{cell}</td>'
                html += '</tr>'
            elif line.startswith('-'):
                html += f'<ul><li>{line[2:]}</li></ul>'
            elif line.strip() == '':
                if in_table:
                    html += '</table>'
                    in_table = False
            elif line.strip():
                html += f'<p>{line}</p>'

        if in_table:
            html += '</table>'

        html += """
        <div class="footer">
            <p><strong>Anwar Group of Industries Vessel Tracking System</strong></p>
            <p>Weekly Analysis - Automated Report</p>
            <p style="margin-top: 10px; color: #666; font-size: 12px;">
                For detailed data and historical trends, log in to your dashboard
            </p>
        </div>
    </div>
</body>
</html>
"""
        return html


# Extend EmailReportSender to add weekly email method
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

def _send_weekly_email(self, html_content):
    """Send weekly email"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📊 Anwar Group of Industries Weekly Port Report - Week of {datetime.now().strftime('%d %B %Y')}"
        msg["From"] = self.sender_email
        msg["To"] = ", ".join(self.receiver_emails)

        # Attach HTML
        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        # Send
        self._send(msg)

        return True
    except Exception as e:
        logger.error(f"Email error: {str(e)}")
        return False

# Monkey patch the method
EmailReportSender._send_weekly_email = _send_weekly_email


def main():
    """Main execution"""
    try:
        sender = WeeklyReportSender()
        success = sender.send_weekly_report()
        exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
