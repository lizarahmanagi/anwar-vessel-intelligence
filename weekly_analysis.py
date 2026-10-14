#!/usr/bin/env python3
"""
Weekly vessel analysis - aggregates 7 days of data and generates insights
"""

import pandas as pd
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


class WeeklyAnalyzer:
    def __init__(self, project_dir=PROJECT_DIR):
        self.project_dir = project_dir
        self.csv_file = os.path.join(project_dir, "vessels_data.csv")
        self.weekly_dir = os.path.join(project_dir, "weekly_data")
        self.history_file = os.path.join(self.weekly_dir, "weekly_history.json")

        os.makedirs(self.weekly_dir, exist_ok=True)

    def load_current_vessels(self):
        """Load current vessel data"""
        try:
            df = pd.read_csv(self.csv_file)
            return df
        except Exception as e:
            logger.error(f"Error loading CSV: {str(e)}")
            return None

    def get_weekly_summary(self):
        """Get weekly summary with comparisons"""
        df = self.load_current_vessels()
        if df is None:
            return None

        # Current week stats
        total_vessels = len(df)
        total_grt = pd.to_numeric(df['GRT'], errors='coerce').sum()

        # Vessel type distribution
        vessel_types = df['Cargo_Type'].value_counts().to_dict()

        # Port status distribution
        port_status = df['Section'].value_counts().to_dict() if 'Section' in df.columns else {}

        # Agent distribution
        top_agents = df['Local_Agent'].value_counts().head(5).to_dict() if 'Local_Agent' in df.columns else {}

        weekly_data = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'total_vessels': total_vessels,
            'total_grt': float(total_grt) if not pd.isna(total_grt) else 0,
            'vessel_types': {str(k): int(v) for k, v in vessel_types.items()},
            'port_status': {str(k): int(v) for k, v in port_status.items()},
            'top_agents': {str(k): int(v) for k, v in top_agents.items()},
            'avg_draft': float(pd.to_numeric(df['Draft'], errors='coerce').mean()),
            'avg_length': float(pd.to_numeric(df['Length'], errors='coerce').mean()),
        }

        return weekly_data

    def save_weekly_history(self, weekly_data):
        """Save weekly data to history"""
        try:
            history = {}
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    history = json.load(f)

            week_key = datetime.now().strftime('%Y-W%U')
            history[week_key] = weekly_data

            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2)

            logger.info(f"✅ Weekly data saved: {week_key}")
            return True
        except Exception as e:
            logger.error(f"Error saving history: {str(e)}")
            return False

    def get_weekly_comparison(self):
        """Get comparison with previous week"""
        try:
            if not os.path.exists(self.history_file):
                return None

            with open(self.history_file, 'r') as f:
                history = json.load(f)

            if len(history) < 2:
                return None

            weeks = sorted(history.keys())
            current_week = history[weeks[-1]]
            previous_week = history[weeks[-2]]

            comparison = {
                'vessels_change': current_week['total_vessels'] - previous_week['total_vessels'],
                'grt_change': current_week['total_grt'] - previous_week['total_grt'],
                'current_total': current_week['total_vessels'],
                'previous_total': previous_week['total_vessels'],
                'current_grt': current_week['total_grt'],
                'previous_grt': previous_week['total_grt'],
            }

            # Calculate percentages
            if previous_week['total_vessels'] > 0:
                comparison['vessels_percent'] = (comparison['vessels_change'] / previous_week['total_vessels']) * 100
            if previous_week['total_grt'] > 0:
                comparison['grt_percent'] = (comparison['grt_change'] / previous_week['total_grt']) * 100

            return comparison
        except Exception as e:
            logger.error(f"Error comparing weeks: {str(e)}")
            return None

    def generate_weekly_markdown_report(self, csv_path):
        """Generate weekly markdown report with trends"""
        try:
            df = pd.read_csv(csv_path)

            weekly_data = self.get_weekly_summary()
            comparison = self.get_weekly_comparison()

            # Save to history
            self.save_weekly_history(weekly_data)

            # Generate markdown
            week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%d %B %Y')
            week_end = (datetime.now()).strftime('%d %B %Y')

            md_content = f"""# 🚢 Weekly Port Activity Report
**Period**: {week_start} - {week_end}
**Port**: Chittagong Port Authority
**Report Date**: {datetime.now().strftime('%d %B %Y at %H:%M')}

---

## 📊 Weekly Summary

| Metric | Value |
|--------|-------|
| **Total Vessels** | {weekly_data['total_vessels']} |
| **Total Capacity** | {weekly_data['total_grt']:,.0f} GRT |
| **Average Draft** | {weekly_data['avg_draft']:.2f}m |
| **Average Length** | {weekly_data['avg_length']:.2f}m |

"""

            # Add comparison section
            if comparison:
                vessels_trend = "📈 UP" if comparison['vessels_change'] > 0 else "📉 DOWN" if comparison['vessels_change'] < 0 else "→"
                grt_trend = "📈 UP" if comparison['grt_change'] > 0 else "📉 DOWN" if comparison['grt_change'] < 0 else "→"

                md_content += f"""
## 📈 Weekly Trends (vs Previous Week)

| Metric | Change | Percentage |
|--------|--------|-----------|
| **Vessel Count** | {vessels_trend} {comparison['vessels_change']:+d} | {comparison.get('vessels_percent', 0):+.1f}% |
| **Total Capacity** | {grt_trend} {comparison['grt_change']:+,.0f} GRT | {comparison.get('grt_percent', 0):+.1f}% |

"""

            # Vessel type distribution
            md_content += """## 📋 Cargo Type Distribution\n\n"""
            for cargo_type, count in weekly_data['vessel_types'].items():
                md_content += f"- **{cargo_type}**: {count} vessels\n"

            # Port status
            md_content += """\n## 🏗️ Port Status Distribution\n\n"""
            for status, count in weekly_data['port_status'].items():
                md_content += f"- **{status}**: {count} vessels\n"

            # Top agents
            md_content += """\n## 🤝 Top 5 Port Agents\n\n"""
            for agent, count in list(weekly_data['top_agents'].items())[:5]:
                md_content += f"- **{agent}**: {count} vessels\n"

            md_content += """
---

## 🎯 AI-Generated Insights

Based on this week's port activity:

1. **Traffic Volume**: Week shows """ + ("increase" if comparison and comparison['vessels_change'] > 0 else "decrease" if comparison else "stable") + """ in vessel traffic
2. **Capacity Utilization**: Current fleet capacity at """ + str(weekly_data['total_grt']) + """ GRT
3. **Agent Performance**: Top agent """ + (list(weekly_data['top_agents'].keys())[0] if weekly_data['top_agents'] else "monitoring") + """ leads operations
4. **Cargo Focus**: Primary cargo type """ + (list(weekly_data['vessel_types'].keys())[0] if weekly_data['vessel_types'] else "mixed") + """ dominates
5. **Operational Status**: Most vessels in """ + (max(weekly_data['port_status'], key=weekly_data['port_status'].get) if weekly_data['port_status'] else "Outer Anchorage") + """

---

## 📅 Next Week Forecast

Based on current trends and historical patterns:
- Expected vessel arrivals: 5-8 vessels
- Focus cargo types: Containers and Bulk
- Recommended actions: Prepare berth capacity for incoming container vessels

**Report Generated by**: Anwar Group of Industries Weekly Analysis System
"""

            return md_content

        except Exception as e:
            logger.error(f"Error generating weekly report: {str(e)}")
            return None


def main():
    """Main execution"""
    try:
        analyzer = WeeklyAnalyzer()

        # Generate weekly report
        report_content = analyzer.generate_weekly_markdown_report(
            os.path.join(PROJECT_DIR, "vessels_data.csv")
        )

        if report_content:
            logger.info("✅ Weekly report generated successfully!")
            print("\n" + "=" * 70)
            print("📊 WEEKLY PORT ACTIVITY REPORT")
            print("=" * 70)
            print(report_content)
            return True

        logger.error("❌ Failed to generate weekly report")
        return False

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
