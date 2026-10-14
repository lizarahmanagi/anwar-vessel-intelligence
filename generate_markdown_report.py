#!/usr/bin/env python3
"""
Generate professional Markdown report with vessel data + AI analysis
"""

import pandas as pd
from datetime import datetime
import os
import logging

from anwar_cargo import categorize_cargo, is_anwar_relevant, CATEGORY_SBU

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


class MarkdownReportGenerator:
    def __init__(self, project_dir=PROJECT_DIR):
        self.project_dir = project_dir
        self.reports_dir = os.path.join(project_dir, "reports")
        os.makedirs(self.reports_dir, exist_ok=True)

    def read_csv(self, csv_path):
        """Read CSV file"""
        try:
            df = pd.read_csv(csv_path)
            return df
        except Exception as e:
            logger.error(f"❌ Failed to read CSV: {str(e)}")
            return None

    def _get_weekly_comparison(self):
        """Get weekly comparison data from history file"""
        try:
            import json
            from datetime import datetime

            history_file = os.path.join(self.project_dir, "weekly_data", "weekly_history.json")

            if not os.path.exists(history_file):
                return None

            with open(history_file, 'r') as f:
                history = json.load(f)

            if len(history) < 2:
                return None

            weeks = sorted(history.keys())
            current_week = history[weeks[-1]]
            previous_week = history[weeks[-2]] if len(weeks) >= 2 else None

            if not previous_week:
                return None

            comparison = {
                'current_vessels': current_week['total_vessels'],
                'previous_vessels': previous_week['total_vessels'],
                'vessel_change': current_week['total_vessels'] - previous_week['total_vessels'],
                'vessel_percent': ((current_week['total_vessels'] - previous_week['total_vessels']) / previous_week['total_vessels'] * 100) if previous_week['total_vessels'] > 0 else 0,
                'current_grt': current_week['total_grt'],
                'previous_grt': previous_week['total_grt'],
                'grt_change': current_week['total_grt'] - previous_week['total_grt'],
                'grt_percent': ((current_week['total_grt'] - previous_week['total_grt']) / previous_week['total_grt'] * 100) if previous_week['total_grt'] > 0 else 0,
            }

            return comparison
        except Exception as e:
            logger.warning(f"⚠️  Could not load weekly comparison: {str(e)}")
            return None

    def calculate_statistics(self, df):
        """Calculate fleet statistics"""
        try:
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
            return {
                'total_vessels': len(df),
                'active_vessels': len(df),
                'total_grt': 0,
                'avg_draft': 0,
                'avg_length': 0,
                'cargo_types': {},
                'sections': {},
            }

    def generate_markdown_report(self, csv_path, analysis_text, output_filename=None):
        """Generate professional Markdown report with weekly comparison"""
        try:
            logger.info("📝 Generating Markdown report...")

            # Read CSV
            df = self.read_csv(csv_path)
            if df is None:
                return None

            # Calculate stats
            stats = self.calculate_statistics(df)

            # Load weekly comparison data
            weekly_comparison = self._get_weekly_comparison()

            # Generate filename with date
            if output_filename is None:
                today = datetime.now().strftime("%d_%m_%Y")
                output_filename = f"vessel_analysis_{today}.md"

            output_path = os.path.join(self.reports_dir, output_filename)

            # Create Markdown report with weekly comparison
            md_content = self._generate_markdown_content(df, stats, analysis_text, weekly_comparison)

            # Save Markdown file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(md_content)

            logger.info(f"✅ Markdown report saved: {output_filename}")
            return output_path

        except Exception as e:
            logger.error(f"❌ Report generation failed: {str(e)}")
            return None

    def _generate_cargo_recommendations(self, stats):
        """Generate data-driven recommendations based on actual cargo types"""
        if not stats['cargo_types']:
            return "No cargo data available for recommendations."

        # Aggregate raw cargo codes into Anwar Group supply categories
        category_counts = {}
        for cargo_type, count in stats['cargo_types'].items():
            category = categorize_cargo(cargo_type)
            if category:
                category_counts[category] = category_counts.get(category, 0) + count

        sorted_cargos = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        top_cargos = sorted_cargos[:5]

        recommendations = []

        # Cargo-specific recommendations tied to Anwar Group SBUs
        cargo_recommendations = {
            'Containerized Cargo': {
                'demand': 'Very High',
                'insight': 'Container traffic carries Anwar Group raw materials (PP resin, GI base metal, machinery), packaging, and exports across all SBUs.',
                'action': 'Track container lines serving Chittagong to secure stable freight rates and timely releases for SBU inputs.'
            },
            'Coal': {
                'demand': 'High',
                'insight': 'Coal fuels Anwar Ispat furnaces and Anwar Cement kilns; every coal arrival lowers group energy cost risk.',
                'action': 'Lock coal tonnage with reliable agents to smooth furnace and kiln fuel supply.'
            },
            'Cement Clinker': {
                'demand': 'High',
                'insight': 'Clinker is the core raw material for Anwar Cement and Anwar Cement Sheet; the construction boom drives continuous demand.',
                'action': 'Prioritise berthing and discharge of clinker vessels to keep cement grinding plants fed.'
            },
            'Limestone': {
                'demand': 'High',
                'insight': 'Cement-grade limestone is a direct input for Anwar Cement clinker blending.',
                'action': 'Secure long-term limestone supply windows around peak construction seasons.'
            },
            'Gypsum & Slag': {
                'demand': 'Medium',
                'insight': 'Gypsum and slag are grinding additives that keep Anwar Cement cost-competitive.',
                'action': 'Batch gypsum/slag bookings with clinker arrivals to share freight legs.'
            },
            'Iron & Steel Scrap': {
                'demand': 'Very High',
                'insight': 'Ferrous scrap is the primary melting feedstock for Anwar Ispat and base metal for Anwar Galvanizing.',
                'action': 'Monitor scrap arrivals daily; aged scrap vessels are direct supply risk for the Ispat furnace.'
            },
            'Galvanized Iron': {
                'demand': 'High',
                'insight': 'GI coils feed Anwar Galvanizing for sheets used across construction.',
                'action': 'Track GI discharge slots to keep the galvanizing line running without idle days.'
            },
            'Iron Ore / Steel': {
                'demand': 'High',
                'insight': 'Iron ore and steel semis (billet, rod) are alternative furnace feed and product market signals for Anwar Ispat.',
                'action': 'Use ore/steel arrivals as a price and supply benchmark for Ispat procurement.'
            },
            'Gas & Energy': {
                'demand': 'High',
                'insight': 'Gas, LPG, LNG, fuel oil and condensate arrivals signal energy costs that set Anwar Group furnace, kiln and freight economics.',
                'action': 'Watch energy cargo volumes as a leading indicator for production cost planning.'
            },
            'Polymer / PP Resin': {
                'demand': 'High',
                'insight': 'PP resin arrivals (mostly containerised) directly feed A1 Polymer yarn and woven bag production.',
                'action': 'Align PP resin container releases with A1 Polymer extrusion schedules.'
            },
            'Cement': {
                'demand': 'High',
                'insight': 'Cement cargoes in the lineup signal competitive supply into the local market that Anwar Cement must price against.',
                'action': 'Track incoming cement tonnage to anticipate market price pressure.'
            },
            'Construction Materials': {
                'demand': 'Medium',
                'insight': 'Aggregate and stone arrivals are a demand proxy for concrete — the end market for Anwar Cement and Cement Sheet.',
                'action': 'Use construction-material volumes to forecast cement and sheet order books.'
            },
        }

        # Generate recommendations for top 5 cargos
        for cargo_type, count in top_cargos:
            if cargo_type in cargo_recommendations:
                rec = cargo_recommendations[cargo_type]
                recommendations.append(
                    f"**{cargo_type}** ({count} vessels) - {rec['demand']} Demand\n"
                    f"- {rec['insight']}\n"
                    f"- Action: {rec['action']}"
                )
            else:
                # Generic recommendation for unknown cargo types
                recommendations.append(
                    f"**{cargo_type}** ({count} vessels)\n"
                    f"- Monitor market trends and establish partnerships with relevant industries in Bangladesh."
                )

        return "\n\n".join(recommendations)

    def _generate_critical_alerts(self, df):
        """Flag clinker/coal/scrap vessels waiting >14 days for the email banner."""
        try:
            critical = {'C.CLINK', 'CLINKER', 'COAL', 'GI(SCRAP)', 'SCRAP'}
            ref = pd.NaT
            if 'Update_Date' in df.columns:
                ref = pd.to_datetime(df['Update_Date'], format='%d/%m/%Y', errors='coerce').max()
            if pd.isna(ref):
                ref = pd.Timestamp(datetime.now().date())
            arrivals = pd.to_datetime(df['Arrival_Date'], format='%d/%m/%y', errors='coerce')
            d = df.copy()
            d['_days'] = (ref - arrivals).dt.days
            wait_mask = d['Section'].str.contains('Anchorage|Awaiting|Not Entering', case=False, na=False)
            crit = d[(d['_days'] > 14) & wait_mask & (d['Cargo_Type'].isin(critical))]
            crit = crit.sort_values('_days', ascending=False).head(8)
            lines = [
                f"- {r['Vessel_Name']} — {r['Cargo_Type']}, arrived {r['Arrival_Date']}, {int(r['_days'])} days waiting, agent {r['Local_Agent']}"
                for _, r in crit.iterrows()
            ]
            if not lines:
                lines = ["- No critical supply alerts — all clinker/coal/scrap vessels arrived within 14 days."]
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"⚠️  Critical alerts unavailable: {str(e)}")
            return "- No critical supply alerts."

    def _generate_markdown_content(self, df, stats, analysis_text, weekly_comparison=None):
        """Generate Markdown content with weekly comparison"""

        # Cargo types markdown — Anwar Group supply scope only, grouped by category
        category_counts = {}
        for cargo_type, count in stats['cargo_types'].items():
            category = categorize_cargo(cargo_type)
            if category:
                category_counts[category] = category_counts.get(category, 0) + count
        cargo_md = "\n".join(
            [f"- **{k}**: {v} vessels — {CATEGORY_SBU.get(k, '')}" for k, v in category_counts.items()]
        )

        # Sections markdown
        sections_md = "\n".join([f"- **{k}**: {v} vessels" for k, v in list(stats['sections'].items())[:10]])

        # Generate vessel table (Anwar-relevant cargoes only)
        relevant_df = df[df['Cargo_Type'].apply(is_anwar_relevant)]
        vessel_table = self._generate_vessel_table(relevant_df)

        # Strategic insights: the LLM briefing when available, canned cargo notes otherwise
        formatted_analysis = self._format_analysis(analysis_text)
        if formatted_analysis and formatted_analysis != "No analysis available":
            insights_heading = "### AI-Powered Strategic Insights"
            insights_body = formatted_analysis
        else:
            insights_heading = "### Cargo-Based Strategy (LLM unavailable — fallback view)"
            insights_body = self._generate_cargo_recommendations(stats)

        # Weekly comparison section
        weekly_section = ""
        if weekly_comparison:
            vessel_trend = "📈 UP" if weekly_comparison['vessel_change'] > 0 else "📉 DOWN" if weekly_comparison['vessel_change'] < 0 else "→"
            grt_trend = "📈 UP" if weekly_comparison['grt_change'] > 0 else "📉 DOWN" if weekly_comparison['grt_change'] < 0 else "→"

            weekly_section = f"""
## 📊 Weekly Comparison (vs Last Week)

| Metric | This Week | Last Week | Change | % Change |
|--------|-----------|-----------|--------|----------|
| **Vessel Count** | {weekly_comparison['current_vessels']} | {weekly_comparison['previous_vessels']} | {vessel_trend} {weekly_comparison['vessel_change']:+d} | {weekly_comparison['vessel_percent']:+.1f}% |
| **Total Capacity** | {weekly_comparison['current_grt']:,.0f} GRT | {weekly_comparison['previous_grt']:,.0f} GRT | {grt_trend} {weekly_comparison['grt_change']:+,.0f} | {weekly_comparison['grt_percent']:+.1f}% |

"""

        md_content = f"""# Anwar Group of Industries — BlueRoute Shipping Intelligence - Chittagong Port

**Generated**: {datetime.now().strftime('%d %B %Y at %H:%M:%S')}
**Source**: Chittagong Port Authority (CPA) - Marin
**Port**: Chittagong Port, Bangladesh{weekly_section}

---

## 📊 Fleet Statistics Summary

| Metric | Value |
|--------|-------|
| **Total Fleet** | {stats['total_vessels']} vessels |
| **Active Vessels** | {stats['active_vessels']} in operation |
| **Total Capacity** | {stats['total_grt']:,.0f} GRT |
| **Average Draft** | {stats['avg_draft']:.2f} meters |
| **Average Length** | {stats['avg_length']:.2f} meters |

### Cargo Type Distribution

{cargo_md}

### Vessel Distribution by Section

{sections_md}

---

## 🚨 Critical Supply Alerts

{self._generate_critical_alerts(df)}

---

## 📋 Vessel Inventory — Anwar Group Supply Scope ({len(relevant_df)} of {len(df)} port vessels)

{vessel_table}

---

## 📌 Business Insights

### Key Takeaways

1. **Port Fleet**: **{stats['total_vessels']} vessels** tracked — **{len(relevant_df)}** inside Anwar Group's supply scope
2. **Cargo Focus**: Primary supply category is **{list(category_counts.keys())[0] if category_counts else 'N/A'}** ({list(category_counts.values())[0] if category_counts else 0} vessels) — {CATEGORY_SBU.get(list(category_counts.keys())[0], '') if category_counts else ''}
3. **Port Operations**: Largest section is **{list(stats['sections'].keys())[0] if stats['sections'] else 'N/A'}** with **{list(stats['sections'].values())[0] if stats['sections'] else '0'} vessels**
4. **Fleet Capacity**: Total capacity of **{stats['total_grt']:,.0f} GRT** indicates large ocean-going vessels
5. **Average Dimensions**: {stats['avg_length']:.0f}m length, {stats['avg_draft']:.0f}m draft (deep-water capable)

### Decision Support

- **Capacity Planning**: Monitor the {list(stats['cargo_types'].keys())[0] if stats['cargo_types'] else 'primary'} cargo segment
- **Port Utilization**: {stats['active_vessels']}/{stats['total_vessels']} vessels active ({(stats['active_vessels']/stats['total_vessels']*100):.1f}%)
- **Fleet Performance**: Review section distribution for operational efficiency

---

## 🎯 Strategic Analysis

{insights_heading}

{insights_body}

---

## 📅 Report Information

- **Report Date**: {datetime.now().strftime('%Y-%m-%d')}
- **Next Update**: {(datetime.now().replace(hour=6, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)).strftime('%d %B %Y at 06:00 AM')}
- **Source**: BlueRoute Shipping Intelligence
- **Analysis Engine**: Groq LLM ({os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")})

---

*Report generated automatically by BlueRoute Shipping Intelligence*
"""
        return md_content

    def _calc_vessel_type(self, cargo_type):
        """Determine vessel type"""
        cargo_str = str(cargo_type).upper()
        if 'CONT' in cargo_str:
            return 'Container'
        elif any(x in cargo_str for x in ['COAL', 'LIMESTONE', 'SLAG', 'ORE']):
            return 'Bulk'
        elif 'VEHICLE' in cargo_str:
            return 'Car'
        return 'General'

    def _calc_utilization(self, cargo_qty, grt):
        """Calculate utilization"""
        try:
            if not cargo_qty or cargo_qty == '-':
                return 'Empty'
            if '/' in str(cargo_qty):
                cargo_qty = str(cargo_qty).split('/')[0]
            cargo_num = float(cargo_qty)
            grt_num = float(grt) if grt else 1
            util = (cargo_num / grt_num) * 100 if grt_num else 0
            return 'Full' if util >= 80 else 'Half' if util >= 50 else 'Low'
        except:
            return 'N/A'

    def _calc_revenue(self, cargo_type):
        """Categorize revenue potential for Anwar Group supply cargoes"""
        cargo_str = str(cargo_type).upper()
        if 'CONT' in cargo_str:
            return 'High'
        return 'Medium'

    def _calc_efficiency(self, section):
        """Get efficiency status"""
        section_str = str(section).lower()
        return 'Quick' if 'berth' in section_str else 'Delayed' if 'waiting' in section_str else 'Normal'

    def _get_cargo_priority(self, cargo_type):
        """Anwar Group supply-scope priority for table sorting"""
        category = categorize_cargo(cargo_type)
        if category is None:
            return 99
        order = [
            'Cement Clinker',
            'Limestone',
            'Gypsum & Slag',
            'Cement',
            'Construction Materials',
            'Iron & Steel Scrap',
            'Galvanized Iron',
            'Iron Ore / Steel',
            'Coal',
            'Polymer / PP Resin',
            'Gas & Energy',
            'Containerized Cargo',
        ]
        return order.index(category) if category in order else 50

    def _calc_status(self, section):
        """Determine vessel status from section"""
        section_str = str(section).lower()
        if 'berth' in section_str:
            return 'Berth'
        elif 'anchorage' in section_str:
            return 'Anchorage'
        elif 'awaiting' in section_str:
            return 'Awaiting'
        elif 'not entering' in section_str:
            return 'Not Entering'
        elif 'ready' in section_str:
            return 'Ready'
        return section

    def _generate_vessel_table(self, df):
        """Generate Markdown table with cargo type and status, sorted by cargo type"""
        try:
            # Create table header
            table = "| SL | Vessel Name | Arrival | Cargo Type | Status | Type | Utilization | Revenue | Agent |\n"
            table += "|---|---|---|---|---|---|---|---|---|\n"

            # Sort by cargo type priority first, then by vessel name.
            # AMOY FORTUNE is pinned to the top of the table on request.
            df_sorted = df.copy()
            df_sorted['cargo_priority'] = df_sorted['Cargo_Type'].apply(self._get_cargo_priority)
            df_sorted['pin_top'] = df_sorted['Vessel_Name'].str.strip().str.upper().ne('AMOY FORTUNE')
            df_sorted = df_sorted.sort_values(['pin_top', 'cargo_priority', 'Vessel_Name'])

            # Add rows with calculated metrics
            for _, row in df_sorted.iterrows():
                sl = str(row.get('SL.NO', ''))
                vessel = str(row.get('Vessel_Name', ''))[:30]
                arrival = str(row.get('Arrival_Date', ''))
                cargo_type = str(row.get('Cargo_Type', ''))
                cargo_qty = row.get('Cargo_Quantity', '')
                grt = row.get('GRT', '')
                agent = str(row.get('Local_Agent', ''))[:15]
                section = str(row.get('Section', ''))

                # Calculate metrics
                vessel_type = self._calc_vessel_type(cargo_type)
                status = self._calc_status(section)
                utilization = self._calc_utilization(cargo_qty, grt)
                revenue = self._calc_revenue(cargo_type)

                # Add row
                table += f"| {sl} | {vessel} | {arrival} | {cargo_type} | {status} | {vessel_type} | {utilization} | {revenue} | {agent} |\n"

            return table

        except Exception as e:
            logger.error(f"Error generating table: {str(e)}")
            return "| Error | Generating vessel table |"

    def _format_analysis(self, text):
        """Format analysis text for Markdown"""
        if not text:
            return "No analysis available"

        # Clean up HTML entities if present
        text = text.replace('&lt;', '<').replace('&gt;', '>')

        return text


if __name__ == "__main__":
    generator = MarkdownReportGenerator()

    csv_path = os.path.join(PROJECT_DIR, "vessels_data.csv")

    # Sample analysis text
    sample_analysis = """
### Fleet Summary
The port currently has 20 vessels with varying operational status. The fleet composition shows a diverse cargo handling capability, with an average vessel draft of approximately 7.5 meters, indicating medium-sized ocean-going vessels.

### Cargo Analysis
The fleet is primarily engaged in:
- General cargo and multipurpose shipping (dominant segment)
- Container vessel operations
- Bulk commodity transportation

This diversified cargo portfolio indicates resilient business operations across multiple market segments.

### Port Status Overview
- **Outer Anchorage**: Primary staging area with vessels awaiting berth assignment
- **Active Operations**: Vessels engaged in loading/unloading operations
- **Scheduled Arrivals**: Multiple vessels in pipeline for port entry
- **Section Distribution**: Well-balanced across operational zones

### Key Findings
1. Fleet utilization is at a healthy operational level
2. Average vessel size suggests deep-water port capability
3. Cargo diversity provides revenue stream stability
4. Vessel arrival patterns indicate consistent business flow
5. Port infrastructure appears adequate for current fleet size

### Recommendations for Business Decision-Making
1. **Optimize Berth Allocation**: Review scheduling to reduce vessel wait times and improve port efficiency
2. **Cargo Mix Analysis**: Monitor high-margin cargo segments and allocate vessel capacity accordingly
3. **Maintenance Planning**: Schedule dry-dock operations during low-demand periods
4. **Expansion Planning**: Current fleet size supports growth; consider vessel additions for underutilized routes
5. **Risk Management**: Diversified cargo types provide good hedge against market volatility
"""

    # Generate report
    report_path = generator.generate_markdown_report(
        csv_path,
        sample_analysis
    )

    if report_path:
        print(f"\n✅ Markdown report generated successfully!")
        print(f"📁 Location: {report_path}")
