#!/usr/bin/env python3
"""
Generate professional HTML report with vessel data + AI analysis
"""

import pandas as pd
from datetime import datetime
import os
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


class ReportGenerator:
    def __init__(self, project_dir=PROJECT_DIR):
        self.project_dir = project_dir
        self.reports_dir = os.path.join(project_dir, "reports")

        # Create reports directory
        os.makedirs(self.reports_dir, exist_ok=True)

    def read_csv(self, csv_path):
        """Read CSV file"""
        try:
            df = pd.read_csv(csv_path)
            return df
        except Exception as e:
            logger.error(f"❌ Failed to read CSV: {str(e)}")
            return None

    def calculate_statistics(self, df):
        """Calculate fleet statistics"""
        try:
            # Convert numeric columns
            df['GRT'] = pd.to_numeric(df['GRT'], errors='coerce')
            df['Draft'] = pd.to_numeric(df['Draft'], errors='coerce')
            df['Length'] = pd.to_numeric(df['Length'], errors='coerce')

            # Handle Section column - may not exist
            section_col = 'Section' if 'Section' in df.columns else None

            if section_col:
                active_vessels = len(df[~df[section_col].str.contains('Awaiting|Not Entering', na=False)])
                sections = df[section_col].value_counts().to_dict()
            else:
                active_vessels = len(df)
                sections = {}

            stats = {
                'total_vessels': len(df),
                'active_vessels': active_vessels,
                'total_grt': df['GRT'].sum(),
                'avg_draft': df['Draft'].mean(),
                'avg_length': df['Length'].mean(),
                'cargo_types': df['Cargo_Type'].value_counts().to_dict() if 'Cargo_Type' in df.columns else {},
                'sections': sections,
            }
            return stats
        except Exception as e:
            logger.error(f"Error calculating stats: {str(e)}")
            # Return fallback stats if calculation fails
            return {
                'total_vessels': len(df),
                'active_vessels': len(df),
                'total_grt': 0,
                'avg_draft': 0,
                'avg_length': 0,
                'cargo_types': {},
                'sections': {},
            }

    def generate_html_report(self, csv_path, analysis_text, output_filename=None):
        """Generate professional HTML report"""
        try:
            logger.info("📝 Generating HTML report...")

            # Read CSV
            df = self.read_csv(csv_path)
            if df is None:
                return None

            # Calculate stats
            stats = self.calculate_statistics(df)

            # Generate filename with date
            if output_filename is None:
                today = datetime.now().strftime("%d_%m_%Y")
                output_filename = f"vessel_analysis_{today}.html"

            output_path = os.path.join(self.reports_dir, output_filename)

            # Create HTML
            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BlueRoute Shipping Intelligence</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 40px 20px;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #1a3a52 0%, #2d5a7b 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}

        .content {{
            padding: 40px;
        }}

        .analysis-section {{
            background: #f8f9fa;
            border-left: 5px solid #667eea;
            padding: 25px;
            margin-bottom: 30px;
            border-radius: 8px;
        }}

        .analysis-section h2 {{
            color: #1a3a52;
            margin-bottom: 15px;
            font-size: 1.5em;
        }}

        .analysis-section p {{
            color: #333;
            line-height: 1.8;
            margin-bottom: 10px;
            font-size: 1.05em;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            text-align: center;
        }}

        .stat-card h3 {{
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 10px;
            text-transform: uppercase;
        }}

        .stat-card .value {{
            font-size: 2.5em;
            font-weight: bold;
        }}

        .stat-card .unit {{
            font-size: 0.9em;
            opacity: 0.8;
            margin-top: 5px;
        }}

        .charts-section {{
            margin: 40px 0;
        }}

        .charts-section h2 {{
            color: #1a3a52;
            margin-bottom: 20px;
            font-size: 1.5em;
        }}

        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            margin-bottom: 40px;
        }}

        .chart-container {{
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 20px;
            position: relative;
            height: 400px;
        }}

        .table-section {{
            margin-top: 40px;
        }}

        .table-section h2 {{
            color: #1a3a52;
            margin-bottom: 20px;
            font-size: 1.5em;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.95em;
        }}

        table thead {{
            background: linear-gradient(135deg, #1a3a52 0%, #2d5a7b 100%);
            color: white;
        }}

        table th {{
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}

        table td {{
            padding: 12px 15px;
            border-bottom: 1px solid #e0e0e0;
        }}

        table tbody tr:hover {{
            background: #f5f5f5;
        }}

        .footer {{
            background: #f8f9fa;
            color: #666;
            padding: 20px 40px;
            text-align: center;
            font-size: 0.9em;
            border-top: 1px solid #e0e0e0;
        }}

        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>BlueRoute Shipping Intelligence</h1>
            <p>Daily Vessel Analysis Report</p>
            <p>Generated: {datetime.now().strftime('%d/%m/%Y at %H:%M:%S')}</p>
        </div>

        <!-- Content -->
        <div class="content">
            <!-- Statistics Cards -->
            <h2 style="color: #1a3a52; margin-bottom: 20px; font-size: 1.5em;">📊 Fleet Statistics</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Total Fleet</h3>
                    <div class="value">{stats['total_vessels']}</div>
                    <div class="unit">vessels</div>
                </div>
                <div class="stat-card">
                    <h3>Active Vessels</h3>
                    <div class="value">{stats['active_vessels']}</div>
                    <div class="unit">in operation</div>
                </div>
                <div class="stat-card">
                    <h3>Total Capacity</h3>
                    <div class="value">{stats['total_grt']:,.0f}</div>
                    <div class="unit">GRT</div>
                </div>
                <div class="stat-card">
                    <h3>Avg Draft</h3>
                    <div class="value">{stats['avg_draft']:.2f}</div>
                    <div class="unit">meters</div>
                </div>
                <div class="stat-card">
                    <h3>Avg Length</h3>
                    <div class="value">{stats['avg_length']:.2f}</div>
                    <div class="unit">meters</div>
                </div>
            </div>

            <!-- Charts Section -->
            <div class="charts-section">
                <h2>📈 Data Visualization</h2>
                <div class="charts-grid">
                    <div class="chart-container">
                        <canvas id="cargoChart"></canvas>
                    </div>
                    <div class="chart-container">
                        <canvas id="sectionChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- Vessel Table -->
            <div class="table-section">
                <h2>📋 Vessel Inventory</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Vessel</th>
                            <th>Length (m)</th>
                            <th>Draft (m)</th>
                            <th>Capacity (GRT)</th>
                            <th>Cargo Type</th>
                            <th>Port Status</th>
                            <th>Previous Port</th>
                            <th>Flag</th>
                        </tr>
                    </thead>
                    <tbody>
{self._generate_table_rows(df)}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            <p>Report generated by BlueRoute Shipping Intelligence</p>
            <p>Next update: {(datetime.now().replace(hour=6, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)).strftime('%d/%m/%Y at 06:00 AM')}</p>
        </div>
    </div>

    <!-- Chart.js Script -->
    <script>
        const cargoLabels = {json.dumps(list(stats['cargo_types'].keys()))};
        const cargoData = {json.dumps(list(stats['cargo_types'].values()))};
        const sectionLabels = {json.dumps(list(stats['sections'].keys()))};
        const sectionData = {json.dumps(list(stats['sections'].values()))};

        // Cargo Type Chart
        const cargoCtx = document.getElementById('cargoChart').getContext('2d');
        new Chart(cargoCtx, {{
            type: 'doughnut',
            data: {{
                labels: cargoLabels,
                datasets: [{{
                    data: cargoData,
                    backgroundColor: [
                        '#667eea', '#764ba2', '#f093fb', '#4facfe',
                        '#43e97b', '#fa709a', '#30cfd0', '#a8edea'
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }},
                    title: {{
                        display: true,
                        text: 'Cargo Type Distribution'
                    }}
                }}
            }}
        }});

        // Section Distribution Chart
        const sectionCtx = document.getElementById('sectionChart').getContext('2d');
        new Chart(sectionCtx, {{
            type: 'bar',
            data: {{
                labels: sectionLabels,
                datasets: [{{
                    label: 'Vessels',
                    data: sectionData,
                    backgroundColor: '#667eea',
                    borderRadius: 8
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }},
                    title: {{
                        display: true,
                        text: 'Vessel Distribution by Section'
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            stepSize: 1
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

            # Save HTML file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)

            logger.info(f"✅ Report saved: {output_filename}")
            return output_path

        except Exception as e:
            logger.error(f"❌ Report generation failed: {str(e)}")
            return None

    def _format_analysis(self, text):
        """Format analysis text for HTML"""
        if not text:
            return "No analysis available"
        return text.replace('<', '&lt;').replace('>', '&gt;')

    def _generate_table_rows(self, df):
        """Generate HTML table rows"""
        html = ""
        for idx, row in df.iterrows():
            vessel_name = row.get('Vessel_Name', '')
            length = row.get('Length', '')
            draft = row.get('Draft', '')
            grt = row.get('GRT', '')
            cargo_type = row.get('Cargo_Type', '')
            section = row.get('Section', '')
            last_port = row.get('Last_Port', '')
            call_flag = row.get('Call_Flag', '')

            html += f"""                        <tr>
                            <td>{vessel_name}</td>
                            <td>{length}</td>
                            <td>{draft}</td>
                            <td>{grt}</td>
                            <td>{cargo_type}</td>
                            <td>{section}</td>
                            <td>{last_port}</td>
                            <td>{call_flag}</td>
                        </tr>
"""
        return html


if __name__ == "__main__":
    generator = ReportGenerator()

    csv_path = os.path.join(PROJECT_DIR, "vessels_data.csv")

    # Sample analysis text (for testing without Groq)
    sample_analysis = """
FLEET SUMMARY:
The port currently has 58 vessels, with 32 actively in operation. The average vessel draft is 46.87 meters, indicating the presence of large ocean-going vessels. Total cargo capacity is approximately 4.4 million GRT.

CARGO ANALYSIS:
Container vessels (CONT) dominate the fleet at 48%, followed by bulk carriers (COAL) at 21%. This indicates the port's primary business is containerized goods transportation and coal imports.

PORT STATUS OVERVIEW:
- 27 vessels currently in Outer Anchorage
- 3 tankers arriving soon
- 2 vessels ready to enter port
- 21 vessels not entering (in holding pattern)
- 3 vessels awaiting employment assignment
- 2 vessels not ready for operation

KEY FINDINGS:
1. Port capacity utilization is at 55%, indicating moderate congestion
2. Container ships dominate operations (48% of fleet)
3. Average vessel size is significantly large (average length 120+ meters)
4. Fleet composition shows focus on containerized cargo handling
5. Multiple vessels in various stages of berth assignment

RECOMMENDATIONS:
1. Prioritize processing of 27 vessels in Outer Anchorage to improve throughput
2. Prepare dock space for 3 incoming tankers to avoid delays
3. Review assignment procedures for 3 vessels awaiting employment
4. Consider load balancing to reduce overall wait times
5. Monitor compliance for vessels with extended berth time
"""

    # Generate report
    report_path = generator.generate_html_report(
        csv_path,
        sample_analysis
    )

    if report_path:
        print(f"\n✅ Report generated successfully!")
        print(f"📁 Location: {report_path}")
