#!/usr/bin/env python3

import smtplib
import os
import re
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

from anwar_cargo import CATEGORY_SBU

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


class EmailReportSender:
    def __init__(self):
        """Initialize email configuration"""
        self.sender_email = os.getenv("SENDER_EMAIL")
        self.sender_password = os.getenv("SENDER_APP_PASSWORD")
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "465"))
        self.smtp_username = os.getenv("SMTP_USERNAME", self.sender_email)
        self.receiver_emails = os.getenv("RECEIVER_EMAILS", "").split(",")
        self.receiver_emails = [email.strip() for email in self.receiver_emails if email.strip()]

        if not self.sender_email or not self.sender_password:
            raise ValueError("❌ Email credentials not found in .env file")

        if not self.receiver_emails:
            raise ValueError("❌ No receiver emails configured in .env file")

        logger.info(f"📧 Email sender configured: {self.sender_email}")
        logger.info(f"📧 SMTP: {self.smtp_server}:{self.smtp_port} (user {self.smtp_username})")
        logger.info(f"📧 Recipients: {', '.join(self.receiver_emails)}")

    def _authenticate(self, server):
        """LOGIN/PLAIN first; fall back to NTLM for Exchange servers."""
        try:
            server.login(self.smtp_username, self.sender_password)
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPNotSupportedError):
            from smtp_ntlm import ntlm_login
            ntlm_login(server, self.smtp_username, self.sender_password)

    def _send(self, msg):
        """Send message via configured SMTP (SSL on 465, STARTTLS otherwise)."""
        if self.smtp_port == 465:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=60) as server:
                self._authenticate(server)
                server.sendmail(self.sender_email, self.receiver_emails, msg.as_string())
        else:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=60) as server:
                server.ehlo()
                try:
                    server.starttls()
                    server.ehlo()
                except smtplib.SMTPException:
                    pass
                self._authenticate(server)
                server.sendmail(self.sender_email, self.receiver_emails, msg.as_string())

    def read_report(self, report_path):
        """Read markdown report"""
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"✅ Report loaded: {report_path}")
            return content
        except Exception as e:
            logger.error(f"❌ Failed to read report: {str(e)}")
            return None

    def extract_stats_from_markdown(self, markdown_text):
        """Extract key statistics from markdown"""
        stats = {}
        lines = markdown_text.split('\n')

        in_stats_table = False
        for i, line in enumerate(lines):
            if 'Fleet Statistics Summary' in line or '📊 Fleet Summary' in line:
                in_stats_table = True
                continue
            if in_stats_table and '|' in line and '---' not in line:
                cells = [cell.strip() for cell in line.split('|')]
                if len(cells) >= 3 and cells[1] and cells[2]:
                    metric = cells[1].replace('**', '').strip()
                    value = cells[2].replace('**', '').strip()
                    if metric and value and metric.lower() != 'metric':  # Skip header row
                        stats[metric] = value
            if in_stats_table and (line.strip().startswith('###') or line.strip().startswith('##')):
                if 'Fleet Statistics' not in line:
                    break

        return stats

    def extract_weekly_comparison(self, markdown_text):
        """Extract weekly comparison data from markdown"""
        comparison = {}
        lines = markdown_text.split('\n')

        in_weekly_table = False
        skip_next_separator = False

        for i, line in enumerate(lines):
            # Find Weekly Comparison section
            if 'Weekly Comparison' in line:
                in_weekly_table = True
                skip_next_separator = True
                continue

            if in_weekly_table:
                # Skip separator and header rows
                if '---' in line or skip_next_separator:
                    skip_next_separator = False
                    continue

                # Skip if it looks like a header row
                if 'Metric' in line and 'This Week' in line:
                    continue

                # Extract data rows
                if line.startswith('|') and line.endswith('|'):
                    cells = [cell.strip() for cell in line.split('|')[1:-1]]

                    if len(cells) >= 5 and cells[0] and not cells[0].startswith('-'):
                        metric = cells[0].replace('**', '').strip()
                        if metric and metric != 'Metric':
                            comparison[metric] = {
                                'this_week': cells[1].strip(),
                                'last_week': cells[2].strip(),
                                'change': cells[3].strip(),
                                'percent': cells[4].strip() if len(cells) > 4 else '0%'
                            }

                # Stop at blank line
                if line.strip() == '' and len(comparison) > 0:
                    break

        return comparison

    def _calculate_utilization(self, cargo_qty, grt):
        """Calculate cargo utilization percentage"""
        try:
            if not cargo_qty or cargo_qty == '-' or cargo_qty == '':
                return '🔴 Empty'
            if '/' in str(cargo_qty):
                cargo_qty = str(cargo_qty).split('/')[0]
            cargo_num = float(cargo_qty)
            grt_num = float(grt) if grt else 1
            if grt_num == 0:
                return 'N/A'
            utilization = (cargo_num / grt_num) * 100
            if utilization >= 80:
                return '🟢 Full'
            elif utilization >= 50:
                return '🟡 Half'
            else:
                return '🔴 Low'
        except:
            return 'N/A'

    def _get_revenue_tier(self, cargo_type):
        """Categorize cargo by revenue potential"""
        cargo_str = str(cargo_type).upper()
        if any(x in cargo_str for x in ['CONT', 'VEHICLE']):
            return '💰 High'
        elif any(x in cargo_str for x in ['COAL', 'GI', 'SLAG', 'MANGANESE', 'LIMESTONE']):
            return '💵 Medium'
        elif any(x in cargo_str for x in ['BALLAST', 'BUNKERING', 'DEMOLITION']):
            return '💸 Low'
        return '💵 Medium'

    def _get_vessel_type(self, cargo_type):
        """Determine vessel type from cargo"""
        cargo_str = str(cargo_type).upper()
        if 'CONT' in cargo_str:
            return 'Container'
        elif any(x in cargo_str for x in ['COAL', 'LIMESTONE', 'SLAG', 'ORE']):
            return 'Bulk'
        elif 'VEHICLE' in cargo_str:
            return 'Car'
        elif 'TANKER' in cargo_str:
            return 'Tanker'
        return 'General'

    def _get_port_efficiency(self, status):
        """Categorize port efficiency based on status"""
        status_str = str(status).lower()
        if 'berth' in status_str:
            return '⚡ Quick'
        elif 'waiting' in status_str:
            return '⚠️ Delayed'
        else:
            return '⏳ Normal'

    def extract_vessel_rows(self, markdown_text):
        """Extract all vessel rows from markdown table with business metrics"""
        vessels = []
        lines = markdown_text.split('\n')
        found_header = False

        def cells_from_markdown_row(line):
            return [cell.strip() for cell in line.split('|')[1:-1]]

        try:
            for i, line in enumerate(lines):
                # Look for the Vessel Inventory section
                if 'Vessel Inventory' in line:
                    # Next non-empty line should have headers
                    found_header = True
                    continue

                # Process lines after finding Vessel Inventory
                if found_header and line.startswith('|'):
                    cells = cells_from_markdown_row(line)

                    # Skip separator line
                    if '---' in line:
                        continue

                    # Skip if it looks like headers (has SL and Vessel Name)
                    if len(cells) > 0 and ('SL' in cells[0] or 'Vessel' in cells[1:2]):
                        continue

                    # Extract vessel data - must have at least vessel name in position 1
                    if len(cells) >= 9:
                        vessel_name = cells[1].strip()
                        if vessel_name and vessel_name not in ['Vessel Name', '']:
                            vessel = {
                                'sl': cells[0].strip(),
                                'name': vessel_name,
                                'arrival': cells[2].strip() if len(cells) > 2 else '',
                                'cargo_type': cells[3].strip() if len(cells) > 3 else '',
                                'status': cells[4].strip() if len(cells) > 4 else '',
                                'type': cells[5].strip() if len(cells) > 5 else '',
                                'utilization': cells[6].strip() if len(cells) > 6 else '',
                                'revenue': cells[7].strip() if len(cells) > 7 else '',
                                'agent': cells[8].strip() if len(cells) > 8 else '',
                            }
                            vessels.append(vessel)

                # Stop when we reach next major section
                if found_header and line.startswith('##') and 'Inventory' not in line:
                    break

        except Exception as e:
            logger.warning(f"⚠️  Error extracting vessel rows: {str(e)}")

        return vessels

    def extract_strategic_analysis(self, markdown_text):
        """Extract the full strategic analysis block (LLM briefing) from markdown"""
        lines = markdown_text.split('\n')
        block = []

        in_analysis = False
        for line in lines:
            if line.startswith('## ') and 'Strategic Analysis' in line:
                in_analysis = True
                continue
            if in_analysis:
                if line.startswith('## '):
                    break
                block.append(line)

        # Drop the trailing horizontal rule that separates this section from the next
        while block and block[-1].strip() in ('', '---'):
            block.pop()

        return '\n'.join(block).strip()

    def extract_cargo_distribution(self, markdown_text):
        """Extract cargo type distribution from markdown"""
        cargo_types = []
        lines = markdown_text.split('\n')

        in_cargo = False
        for line in lines:
            if 'Cargo Type Distribution' in line:
                in_cargo = True
                continue
            if in_cargo:
                if line.strip().startswith('###') or line.strip().startswith('##'):
                    break
                if line.strip().startswith('- **'):
                    # Format: - **TYPE**: count vessels — SBU note
                    parts = line.replace('- **', '').replace('**:', ':').split(':')
                    if len(parts) >= 2:
                        cargo_type = parts[0].strip()
                        count_text = parts[1].strip()
                        count = count_text.split('vessels')[0].strip()
                        sbu = count_text.split('—')[-1].strip() if '—' in count_text else ''
                        cargo_types.append({'type': cargo_type, 'count': count, 'sbu': sbu})

        return cargo_types

    def extract_section_distribution(self, markdown_text):
        """Extract vessel distribution by section from markdown"""
        sections = []
        lines = markdown_text.split('\n')

        in_sections = False
        for line in lines:
            if 'Vessel Distribution by Section' in line:
                in_sections = True
                continue
            if in_sections:
                if line.strip().startswith('###') or line.strip().startswith('##'):
                    break
                if line.strip().startswith('- **'):
                    # Format: - **SECTION**: count vessels
                    parts = line.replace('- **', '').replace('**:', ':').split(':')
                    if len(parts) >= 2:
                        section = parts[0].strip()
                        count_text = parts[1].strip()
                        sections.append({'section': section, 'count': count_text})

        return sections

    def extract_critical_alerts(self, markdown_text):
        """Extract critical supply alert lines from markdown"""
        lines = markdown_text.split('\n')
        alerts = []
        in_alerts = False
        for line in lines:
            if 'Critical Supply Alerts' in line:
                in_alerts = True
                continue
            if in_alerts:
                if line.strip().startswith('##') or line.strip().startswith('---'):
                    break
                if line.strip().startswith('-'):
                    alerts.append(line.strip()[1:].strip())
        return alerts

    def _build_subject(self, markdown_text):
        """Headline subject: port ratio + top supply category"""
        stats = self.extract_stats_from_markdown(markdown_text)
        sections = self.extract_section_distribution(markdown_text)
        waiting = 0
        for s in sections:
            if any(k in s['section'].lower() for k in ('anchorage', 'awaiting', 'not entering')):
                m = re.search(r'\d+', str(s['count']))
                waiting += int(m.group()) if m else 0
        total_m = re.search(r'\d+', stats.get('Total Fleet', ''))
        total = int(total_m.group()) if total_m else 0
        ready = max(total - waiting, 0)
        cargo = self.extract_cargo_distribution(markdown_text)
        part = f"Anwar Group of Industries - Port {ready}:{waiting}"
        if cargo:
            part += f" | {cargo[0]['type']} {cargo[0]['count']} vessels"
        return f"{part} - {datetime.now().strftime('%d %B %Y')}"

    def markdown_to_html(self, markdown_text):
        """Create professional HTML email from markdown"""
        stats = self.extract_stats_from_markdown(markdown_text)
        vessels = self.extract_vessel_rows(markdown_text)
        strategic_analysis = self.extract_strategic_analysis(markdown_text)
        weekly_comparison = self.extract_weekly_comparison(markdown_text)
        cargo_distribution = self.extract_cargo_distribution(markdown_text)
        section_distribution = self.extract_section_distribution(markdown_text)

        # Extract generated date
        generated_date = "30 June 2026"
        for line in markdown_text.split('\n'):
            if "Generated" in line:
                generated_date = line.split("**Generated**: ")[-1].strip() if "**Generated**:" in line else generated_date

        # Build vessel table rows with comparison metrics (all vessels)
        vessel_rows = ""
        for vessel in vessels:
            vessel_rows += f"""
            <tr>
                <td>{vessel.get('sl', '')}</td>
                <td>{vessel.get('name', '')}</td>
                <td>{vessel.get('arrival', '')}</td>
                <td>{vessel.get('cargo_type', '')}</td>
                <td>{vessel.get('status', '')}</td>
                <td>{vessel.get('type', '')}</td>
                <td>{vessel.get('utilization', '')}</td>
                <td>{vessel.get('revenue', '')}</td>
                <td>{vessel.get('agent', '')}</td>
            </tr>
            """

        # Critical supply banner: clinker/coal/scrap vessels waiting >14 days
        critical_alerts = self.extract_critical_alerts(markdown_text)
        has_alerts = bool(critical_alerts) and not any(
            'No critical supply alerts' in a for a in critical_alerts
        )
        alert_banner = ""
        if has_alerts:
            alert_lines = "".join(
                f'<div style="font-size: 11px; color: #742a2a; padding: 3px 0;">• {self._inline_md(a)}</div>'
                for a in critical_alerts
            )
            alert_banner = f"""
            <div style="background: #fff5f5; border: 1px solid #fc8181; border-left: 5px solid #e53e3e; border-radius: 6px; padding: 12px 16px; margin-bottom: 14px;">
                <div style="font-size: 13px; font-weight: 700; color: #c53030; margin-bottom: 6px;">🚨 Critical Supply Alerts — clinker / coal / scrap waiting over 14 days</div>
                {alert_lines}
            </div>"""

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, 'Segoe UI', 'Helvetica Neue', sans-serif;
            background-color: #f5f6fa;
            color: #2d3748;
            line-height: 1.6;
        }}
        .container {{
            max-width: 750px;
            margin: 0 auto;
            background-color: #ffffff;
            box-shadow: 0 8px 24px rgba(25, 103, 210, 0.12);
            border-radius: 12px;
            overflow: hidden;
        }}
        .header {{
            background: #123F76;
            background: linear-gradient(135deg, #123F76 0%, #1e5a9f 50%, #123F76 100%);
            color: white;
            padding: 16px 20px 14px 20px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}
        .header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: radial-gradient(circle at top right, rgba(255,255,255,0.1), transparent);
            pointer-events: none;
        }}
        .header::after {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
            animation: glitch-shimmer 3s infinite;
            pointer-events: none;
        }}
        @keyframes glitch-shimmer {{
            0%, 100% {{ left: -100%; }}
            50% {{ left: 100%; }}
        }}
        .header h1 {{
            font-size: 22px;
            margin-bottom: 2px;
            font-weight: 700;
            letter-spacing: 0.2px;
            position: relative;
            z-index: 1;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        }}
        .header .subtitle {{
            font-size: 11px;
            opacity: 0.9;
            margin-bottom: 6px;
            font-weight: 400;
            position: relative;
            z-index: 1;
        }}
        .header .date {{
            font-size: 10px;
            opacity: 0.8;
            border-top: 1px solid rgba(255,255,255,0.2);
            padding-top: 6px;
            position: relative;
            z-index: 1;
        }}
        .content {{
            padding: 20px;
        }}
        .section {{
            margin-bottom: 14px;
        }}
        .section h2 {{
            color: #123F76;
            font-size: 14px;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 2px solid #123F76;
            font-weight: 700;
            letter-spacing: 0.2px;
        }}
        .stats-container {{
            width: 100%;
        }}
        .stat-card {{
            width: 25%;
            background: #f0f7ff;
            padding: 12px 10px;
            border-radius: 6px;
            border-left: 4px solid #123F76;
            vertical-align: top;
            position: relative;
        }}
        .stat-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(25, 103, 210, 0.2), transparent);
        }}
        .stat-card.blue {{
            background: #123F76;
            background: linear-gradient(135deg, #123F76 0%, #1e5a9f 100%);
            border-left: 5px solid #1e5a9f;
            color: white;
        }}
        .stat-card.blue .stat-label {{
            color: rgba(255,255,255,0.85);
        }}
        .stat-card.blue .stat-value {{
            color: white;
        }}
        .stat-card.green {{
            background: #0d4f7f;
            background: linear-gradient(135deg, #0d4f7f 0%, #1669a3 100%);
            border-left: 5px solid #1669a3;
            color: white;
        }}
        .stat-card.green .stat-label {{
            color: rgba(255,255,255,0.85);
        }}
        .stat-card.green .stat-value {{
            color: white;
        }}
        .stat-card.orange {{
            background: #2b8fc4;
            background: linear-gradient(135deg, #2b8fc4 0%, #2196f3 100%);
            border-left: 5px solid #2196f3;
            color: white;
        }}
        .stat-card.orange .stat-label {{
            color: rgba(255,255,255,0.85);
        }}
        .stat-card.orange .stat-value {{
            color: white;
        }}
        .stat-card.purple {{
            background: #4d9fc6;
            background: linear-gradient(135deg, #4d9fc6 0%, #3a8ec4 100%);
            border-left: 5px solid #3a8ec4;
            color: white;
        }}
        .stat-card.purple .stat-label {{
            color: rgba(255,255,255,0.85);
        }}
        .stat-card.purple .stat-value {{
            color: white;
        }}
        .stat-label {{
            font-size: 8px;
            color: #718096;
            text-transform: uppercase;
            margin-bottom: 4px;
            font-weight: 600;
            letter-spacing: 0.6px;
        }}
        .stat-value {{
            font-size: 15px;
            font-weight: 700;
            color: #123F76;
            line-height: 1;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
            font-size: 11px;
        }}
        thead {{
            background: #123F76;
            background: linear-gradient(135deg, #123F76 0%, #1e5a9f 100%);
            color: white;
        }}
        th {{
            padding: 10px 10px;
            text-align: left;
            font-weight: 700;
            letter-spacing: 0.2px;
            font-size: 10px;
            text-transform: uppercase;
        }}
        td {{
            padding: 8px 10px;
            border-bottom: 1px solid #e2e8f0;
            color: #2d3748;
        }}
        tbody tr {{
            transition: background-color 0.2s ease;
        }}
        tbody tr:nth-child(odd) {{
            background: #f8fafc;
        }}
        tbody tr:nth-child(even) {{
            background: #ffffff;
        }}
        tbody tr:hover {{
            background: #eef2ff;
        }}
        .card {{
            background: #ffffff;
            padding: 16px;
            border-radius: 8px;
            border-left: 4px solid #123F76;
            margin-bottom: 10px;
            box-shadow: 0 1px 3px rgba(25, 103, 210, 0.08);
            border-top: 1px solid #e2e8f0;
        }}
        .card-title {{
            font-size: 13px;
            color: #123F76;
            font-weight: 700;
            margin-bottom: 6px;
        }}
        .card-detail {{
            font-size: 12px;
            color: #4a5568;
            line-height: 1.5;
        }}
        .divider {{
            border: none;
            border-top: 1px solid #e2e8f0;
            margin: 8px 0;
        }}
        .footer {{
            background: #123F76;
            background: linear-gradient(135deg, #123F76 0%, #1e5a9f 100%);
            padding: 15px 25px;
            text-align: center;
            font-size: 11px;
            color: #ffffff;
            border-top: 3px solid #123F76;
        }}
        .footer p {{
            margin: 2px 0;
            opacity: 0.9;
        }}
        .footer strong {{
            font-weight: 700;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>BlueRoute Shipping Intelligence</h1>
            <div class="subtitle">Anwar Group of Industries — Chittagong Port Supply Intelligence</div>
            <div class="date">Generated: {generated_date}</div>
        </div>

        <!-- Content -->
        <div class="content">
            {alert_banner}
            <!-- Fleet Statistics -->
            <div class="section">
                <h2>📊 Fleet Summary</h2>
                <table width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="width: 100%;">
                    <tr>
                        <td width="25%" valign="top" style="padding: 5px;">
                            <div class="stat-card blue">
                                <div class="stat-label">Total Fleet</div>
                                <div class="stat-value">{stats.get('Total Fleet', '0')}</div>
                            </div>
                        </td>
                        <td width="25%" valign="top" style="padding: 5px;">
                            <div class="stat-card green">
                                <div class="stat-label">Active Vessels</div>
                                <div class="stat-value">{stats.get('Active Vessels', '0')}</div>
                            </div>
                        </td>
                        <td width="25%" valign="top" style="padding: 5px;">
                            <div class="stat-card orange">
                                <div class="stat-label">Total Capacity</div>
                                <div class="stat-value" style="font-size: 16px;">{stats.get('Total Capacity', '0 GRT')}</div>
                            </div>
                        </td>
                        <td width="25%" valign="top" style="padding: 5px;">
                            <div class="stat-card purple">
                                <div class="stat-label">Avg Draft</div>
                                <div class="stat-value">{stats.get('Average Draft', '0')}m</div>
                            </div>
                        </td>
                    </tr>
                </table>
            </div>

            <div class="divider"></div>

            <!-- Weekly Comparison Section -->
            {self._format_weekly_comparison(weekly_comparison)}

            <div class="divider"></div>

            <!-- SBU Supply Radar -->
            {self._format_sbu_radar(cargo_distribution)}

            <!-- Cargo Type Distribution -->
            {self._format_cargo_distribution(cargo_distribution)}

            <!-- Section Distribution -->
            {self._format_section_distribution(section_distribution)}

            <div class="divider"></div>

            <!-- Strategic Analysis Section -->
            <div class="section">
                <h2>🎯 AI-Powered Strategic Insights</h2>
                <div style="margin: 15px 0;">
                    {self._format_strategic_analysis(strategic_analysis)}
                </div>
            </div>

            <div class="divider"></div>

            <!-- Vessel Table -->
            <div class="section">
                <h2>Anwar Group Supply Lineup ({len(vessels)} Vessels)</h2>
                <table>
                    <thead>
                        <tr>
                            <th style="width: 5%;">No.</th>
                            <th style="width: 14%;">Vessel Name</th>
                            <th style="width: 8%;">Arrival</th>
                            <th style="width: 10%;">Cargo Type</th>
                            <th style="width: 10%;">Status</th>
                            <th style="width: 9%;">Type</th>
                            <th style="width: 11%;">Utilization</th>
                            <th style="width: 9%;">Revenue</th>
                            <th style="width: 14%;">Agent</th>
                        </tr>
                    </thead>
                    <tbody>
                        {vessel_rows if vessel_rows else '<tr><td colspan="9" style="text-align: center; padding: 20px; color: #999;">No vessel data available</td></tr>'}
                    </tbody>
                </table>
            </div>

        </div>

        <!-- Footer -->
        <div class="footer">
            <p><strong>BlueRoute Shipping Intelligence</strong></p>
            <p>Prepared for Anwar Group of Industries — Anwar Ispat · Anwar Cement · Anwar Cement Sheet · Anwar Galvanizing · A1 Polymer</p>
            <p style="margin-top: 14px; font-size: 12px; letter-spacing: 0.4px;">WE'D LOVE TO HEAR FROM YOU</p>
            <div style="margin-top: 10px;">
                <a href="https://docs.google.com/forms/d/e/1FAIpQLScW9S5lbqIvDKIXgS8iUtXanF7K25cYdxcKzf7Qc-4MCoCdFQ/viewform" style="display: inline-block; background-color: #ffffff; color: #123F76; font-weight: 700; font-size: 13px; padding: 10px 18px; border-radius: 6px; text-decoration: none; margin: 4px 6px;">Share Your Feedback</a>
                <a href="https://docs.google.com/forms/d/e/1FAIpQLSfnblxWqVcz4OqBYBSErxD19RFKt8z0gUip9oljkKz3r8IWIQ/viewform" style="display: inline-block; background-color: #1e5a9f; color: #ffffff; font-weight: 700; font-size: 13px; padding: 10px 18px; border-radius: 6px; text-decoration: none; border: 2px solid #ffffff; margin: 4px 6px;">Stakeholder Satisfaction Survey</a>
            </div>
            <p style="margin-top: 10px;">Generated by Digital Transformation Team</p>
        </div>
    </div>
</body>
</html>
        """
        return html

    def _format_weekly_comparison(self, weekly_comparison):
        """Format weekly comparison with user-friendly design"""
        if not weekly_comparison:
            return ""

        html = '<div class="section"><h2>Weekly Comparison (vs Last Week)</h2>'
        html += '<table style="width: 100%; border-collapse: collapse;">'

        metrics = list(weekly_comparison.items())
        for i in range(0, len(metrics), 2):
            html += '<tr style="vertical-align: top;">'

            # First metric
            metric, data = metrics[i]
            if '+' in data['percent']:
                badge_color = '#10b981'
                badge_bg = '#d1fae5'
            elif '-' in data['percent']:
                badge_color = '#ef4444'
                badge_bg = '#fee2e2'
            else:
                badge_color = '#8b5cf6'
                badge_bg = '#ede9fe'

            html += f"""<td style="width: 50%; padding: 4px;">
                <div style="background: white; padding: 8px; border-radius: 6px; border: 1px solid #e2e8f0; box-shadow: 0 1px 2px rgba(25, 103, 210, 0.03);">
                    <div style="font-size: 9px; color: #123F76; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">{metric}</div>
                    <div style="background: {badge_bg}; color: {badge_color}; padding: 2px 4px; border-radius: 3px; font-size: 9px; font-weight: 700; display: inline-block; margin-bottom: 4px;">{data['percent']}</div>
                    <table style="width: 100%; border-collapse: collapse; margin-top: 4px;">
                        <tr>
                            <td style="width: 50%; padding: 2px; text-align: center; border-right: 1px solid #e2e8f0;">
                                <div style="color: #718096; font-size: 7px; margin-bottom: 2px; text-transform: uppercase; font-weight: 600;">This Wk</div>
                                <div style="color: #123F76; font-weight: 700; font-size: 11px;">{data['this_week']}</div>
                            </td>
                            <td style="width: 50%; padding: 2px; text-align: center;">
                                <div style="color: #718096; font-size: 7px; margin-bottom: 2px; text-transform: uppercase; font-weight: 600;">Last Wk</div>
                                <div style="color: #4a5568; font-weight: 600; font-size: 11px;">{data['last_week']}</div>
                            </td>
                        </tr>
                    </table>
                </div>
            </td>"""

            # Second metric (if exists)
            if i + 1 < len(metrics):
                metric, data = metrics[i + 1]
                if '+' in data['percent']:
                    badge_color = '#10b981'
                    badge_bg = '#d1fae5'
                elif '-' in data['percent']:
                    badge_color = '#ef4444'
                    badge_bg = '#fee2e2'
                else:
                    badge_color = '#8b5cf6'
                    badge_bg = '#ede9fe'

                html += f"""<td style="width: 50%; padding: 4px;">
                    <div style="background: white; padding: 8px; border-radius: 6px; border: 1px solid #e2e8f0; box-shadow: 0 1px 2px rgba(25, 103, 210, 0.03);">
                        <div style="font-size: 9px; color: #123F76; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">{metric}</div>
                        <div style="background: {badge_bg}; color: {badge_color}; padding: 2px 4px; border-radius: 3px; font-size: 9px; font-weight: 700; display: inline-block; margin-bottom: 4px;">{data['percent']}</div>
                        <table style="width: 100%; border-collapse: collapse; margin-top: 4px;">
                            <tr>
                                <td style="width: 50%; padding: 2px; text-align: center; border-right: 1px solid #e2e8f0;">
                                    <div style="color: #718096; font-size: 7px; margin-bottom: 2px; text-transform: uppercase; font-weight: 600;">This Wk</div>
                                    <div style="color: #123F76; font-weight: 700; font-size: 11px;">{data['this_week']}</div>
                                </td>
                                <td style="width: 50%; padding: 2px; text-align: center;">
                                    <div style="color: #718096; font-size: 7px; margin-bottom: 2px; text-transform: uppercase; font-weight: 600;">Last Wk</div>
                                    <div style="color: #4a5568; font-weight: 600; font-size: 11px;">{data['last_week']}</div>
                                </td>
                            </tr>
                        </table>
                    </div>
                </td>"""
            else:
                html += '<td style="width: 50%; padding: 4px;"></td>'

            html += '</tr>'

        html += '</table></div>'
        return html

    def _format_cargo_distribution(self, cargo_types):
        """Format cargo type distribution as modern badge cards"""
        if not cargo_types:
            return ""

        colors = ['#123F76', '#1e5a9f', '#0d4f7f', '#1669a3', '#2b8fc4', '#3a8ec4', '#4d9fc6', '#0369a1']
        bg_colors = ['#e3f2fd', '#e1f5fe', '#e0f2f1', '#e3f2fd', '#e1f5fe', '#e0f2f1', '#e3f2fd', '#e1f5fe']

        rows = ""
        # Create rows with 3 items per row
        for idx in range(0, len(cargo_types), 3):
            rows += "<tr style='vertical-align: top;'>"
            for jdx in range(3):
                if idx + jdx < len(cargo_types):
                    cargo = cargo_types[idx + jdx]
                    count = str(cargo['count']).replace(' vessels', '')
                    color = colors[(idx + jdx) % len(colors)]
                    bg_color = bg_colors[(idx + jdx) % len(bg_colors)]
                    rows += f"<td style='width: 33%; padding: 4px; text-align: center;'><div style='background: {bg_color}; border: 1px solid {color}; border-radius: 6px; padding: 8px;'><div style='font-size: 10px; color: {color}; font-weight: 700; margin-bottom: 3px;'>{cargo['type']}</div><div style='font-size: 12px; color: {color}; font-weight: 700;'>{count}</div></div></td>"
                else:
                    rows += "<td style='width: 33%; padding: 4px;'></td>"
            rows += "</tr>"

        return f"""<div style="margin-bottom: 18px;">
                <h3 style="color: #123F76; font-size: 14px; margin-bottom: 10px; margin-top: 0; font-weight: 700;">Anwar Group Supply Categories</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 10px;">
                    {rows}
                </table>
            </div>"""

    def _format_sbu_radar(self, cargo_distribution):
        """Map each Anwar supply category to its consuming SBU as a resource table"""
        if not cargo_distribution:
            return ""

        rows = ""
        for cargo in cargo_distribution:
            category = cargo.get('type', '')
            count = cargo.get('count', '')
            sbu = cargo.get('sbu', '') or CATEGORY_SBU.get(category, '')
            rows += f"""
            <tr>
                <td style="padding: 6px 8px; border-bottom: 1px solid #e2e8f0; font-size: 11px; font-weight: 700; color: #123F76;">{category}</td>
                <td style="padding: 6px 8px; border-bottom: 1px solid #e2e8f0; font-size: 11px; color: #123F76; text-align: center; font-weight: 700;">{count} vessels</td>
                <td style="padding: 6px 8px; border-bottom: 1px solid #e2e8f0; font-size: 11px; color: #4a5568;">{sbu}</td>
            </tr>"""

        return f"""<div class="section">
            <h2>🏭 Anwar Group SBU Supply Radar</h2>
            <table style="width: 100%; border-collapse: collapse; margin-top: 0;">
                <thead>
                    <tr>
                        <th style="width: 28%;">Supply Category</th>
                        <th style="width: 18%; text-align: center;">Vessels</th>
                        <th style="width: 54%;">Consuming SBU</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>"""

    def _format_section_distribution(self, sections):
        """Format section distribution as modern badge cards"""
        if not sections:
            return ""

        colors = ['#123F76', '#1e5a9f', '#0d4f7f', '#1669a3', '#2b8fc4', '#3a8ec4']
        bg_colors = ['#e3f2fd', '#e1f5fe', '#e0f2f1', '#e3f2fd', '#e1f5fe', '#e0f2f1']

        rows = ""
        # Create rows with 2 items per row
        for idx in range(0, len(sections), 2):
            rows += "<tr style='vertical-align: top;'>"
            for jdx in range(2):
                if idx + jdx < len(sections):
                    section = sections[idx + jdx]
                    count = str(section['count']).replace(' vessels', '')
                    color = colors[(idx + jdx) % len(colors)]
                    bg_color = bg_colors[(idx + jdx) % len(bg_colors)]
                    rows += f"<td style='width: 50%; padding: 4px;'><div style='background: {bg_color}; border: 1px solid {color}; border-radius: 6px; padding: 8px; text-align: center;'><div style='font-size: 10px; color: {color}; font-weight: 700; margin-bottom: 3px;'>{section['section']}</div><div style='font-size: 12px; color: {color}; font-weight: 700;'>{count}</div></div></td>"
                else:
                    rows += "<td style='width: 50%; padding: 4px;'></td>"
            rows += "</tr>"

        return f"""<div style="margin-bottom: 18px;">
                <h3 style="color: #123F76; font-size: 14px; margin-bottom: 10px; margin-top: 0; font-weight: 700;">Port Section Distribution</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 10px;">
                    {rows}
                </table>
            </div>"""

    def _inline_md(self, text):
        """Convert inline markdown emphasis to HTML"""
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
        return text

    def _format_strategic_analysis(self, analysis_md):
        """Render the strategic briefing markdown (headings, tables, bullets) as email HTML"""
        if not analysis_md:
            return ('<div style="font-size: 12px; color: #4a5568;">'
                    'Strategic analysis unavailable for this run — see the markdown report for raw figures.'
                    '</div>')

        color = '#123F76'
        html = []
        table_rows = []

        def flush_table():
            if not table_rows:
                return
            header, body = table_rows[0], table_rows[1:]
            head_html = ''.join(
                f'<th style="background: {color}; color: white; padding: 7px 9px; font-size: 11px; '
                f'text-align: left; border: 1px solid #d7dee8;">{self._inline_md(cell)}</th>'
                for cell in header
            )
            body_html = ''.join(
                '<tr>' + ''.join(
                    f'<td style="padding: 7px 9px; font-size: 11px; color: #33404f; '
                    f'border: 1px solid #d7dee8; vertical-align: top;">{self._inline_md(cell)}</td>'
                    for cell in row
                ) + '</tr>'
                for row in body
            )
            html.append(
                '<table style="width: 100%; border-collapse: collapse; margin: 10px 0;">'
                f'<thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>'
            )
            table_rows.clear()

        for raw in analysis_md.split('\n'):
            line = raw.strip()

            # Markdown table rows
            if line.startswith('|') and line.endswith('|'):
                cells = [c.strip() for c in line.strip('|').split('|')]
                if all(set(c) <= set('-: ') for c in cells):   # separator row
                    continue
                table_rows.append(cells)
                continue
            flush_table()

            if not line:
                continue

            if set(line) == {'-'} and len(line) >= 3:
                html.append('<div style="border-top: 1px solid #e2e8f0; margin: 14px 0;"></div>')
            elif line.startswith('#'):
                heading = self._inline_md(line.lstrip('#').strip())
                if 'AI-Powered Strategic Insights' in heading:
                    continue   # already the section's own h2
                html.append(
                    f'<div style="font-size: 13px; font-weight: 700; color: {color}; '
                    f'margin: 16px 0 6px 0;">{heading}</div>'
                )
            elif line.startswith(('- ', '• ', '* ')):
                html.append(
                    '<div style="font-size: 12px; color: #4a5568; line-height: 1.55; '
                    f'margin: 4px 0 4px 14px; border-left: 3px solid {color}; padding-left: 9px;">'
                    f'{self._inline_md(line[2:].strip())}</div>'
                )
            elif re.match(r'^\d+\.\s', line):
                html.append(
                    '<div style="font-size: 12px; color: #33404f; line-height: 1.55; '
                    f'margin: 6px 0 6px 6px;">{self._inline_md(line)}</div>'
                )
            elif line.startswith('**') and line.endswith('**'):
                # A bold-only line acts as a section title in the briefing
                html.append(
                    f'<div style="font-size: 13px; font-weight: 700; color: {color}; '
                    f'margin: 16px 0 6px 0;">{self._inline_md(line)}</div>'
                )
            else:
                html.append(
                    '<div style="font-size: 12px; color: #4a5568; line-height: 1.6; '
                    f'margin: 6px 0;">{self._inline_md(line)}</div>'
                )

        flush_table()

        return (
            '<div style="background: white; border: 1px solid #e2e8f0; border-radius: 8px; '
            'padding: 14px 16px;">' + ''.join(html) + '</div>'
        )

    def _sent_marker(self, report_path):
        """Path of the sent-marker file for a report."""
        return os.path.join(os.path.dirname(report_path), f".{os.path.basename(report_path)}.sent")

    def _already_sent(self, report_path):
        """True if this exact report has already been emailed."""
        return os.path.exists(self._sent_marker(report_path))

    def _mark_sent(self, report_path):
        """Record that this report has been emailed (once-per-day guard)."""
        try:
            with open(self._sent_marker(report_path), "w", encoding="utf-8") as f:
                f.write(datetime.now().isoformat())
            logger.info(f"✅ Marked as sent: {os.path.basename(report_path)}")
        except Exception as e:
            logger.warning(f"⚠️  Could not write sent-marker: {str(e)}")

    def send_email(self, report_path):
        """Send report via email, at most once per report."""
        try:
            if os.getenv("ALLOW_RESEND", "0") == "1":
                logger.info("ℹ️  ALLOW_RESEND=1 - bypassing once-per-report guard")
            elif self._already_sent(report_path):
                logger.info(f"⏭️  Report already sent, skipping: {os.path.basename(report_path)}")
                return True

            # Read report
            report_content = self.read_report(report_path)
            if not report_content:
                return False

            # Create email message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = self._build_subject(report_content)
            msg["From"] = self.sender_email
            msg["To"] = ", ".join(self.receiver_emails)

            # Create plain text version
            text_part = MIMEText(report_content, "plain")
            msg.attach(text_part)

            # Create HTML version
            html_content = self.markdown_to_html(report_content)
            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)

            # Send email
            logger.info(f"📧 Connecting to SMTP server {self.smtp_server}:{self.smtp_port}...")
            self._send(msg)

            logger.info(f"✅ Report sent successfully to {len(self.receiver_emails)} recipient(s)")
            logger.info(f"📧 Recipients: {', '.join(self.receiver_emails)}")
            self._mark_sent(report_path)
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("❌ SMTP authentication failed!")
            logger.error("   - Check SENDER_EMAIL / SMTP_USERNAME is correct")
            logger.error("   - Check SENDER_APP_PASSWORD is correct")
            return False

        except Exception as e:
            logger.error(f"❌ Failed to send email: {str(e)}")
            return False


def main():
    """Main execution"""
    try:
        sender = EmailReportSender()

        # Find latest report
        reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
        if not os.path.exists(reports_dir):
            logger.error(f"❌ Reports directory not found: {reports_dir}")
            return False

        # Get latest markdown report by modification time
        md_files = [f for f in os.listdir(reports_dir) if f.endswith('.md')]
        if not md_files:
            logger.error("❌ No markdown reports found in reports directory")
            return False

        latest_report = max([os.path.join(reports_dir, f) for f in md_files], key=os.path.getmtime)
        report_path = latest_report

        logger.info("=" * 70)
        logger.info("📧 SENDING VESSEL ANALYSIS REPORT")
        logger.info("=" * 70)

        success = sender.send_email(report_path)

        logger.info("=" * 70)
        return success

    except ValueError as e:
        logger.error(str(e))
        return False

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
