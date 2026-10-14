#!/usr/bin/env python3
"""
Analyze vessel data using Groq LLM via LangChain
"""

from langchain_groq import ChatGroq
import pandas as pd
import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv
import logging

from anwar_cargo import categorize_cargo, is_anwar_relevant, CATEGORY_SBU

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


class VesselAnalyzer:
    def __init__(self):
        """Initialize Groq LLM"""
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError(" GROQ_API_KEY not found in .env file")

        logger.info("🤖 Initializing Groq LLM...")

        self.llm = ChatGroq(
            api_key=api_key,
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=0.4,
            max_tokens=3000
        )

        logger.info("✅ Groq LLM initialized")

    def read_csv(self, csv_path):
        """Read CSV file"""
        try:
            logger.info(f"📖 Reading CSV: {csv_path}")
            df = pd.read_csv(csv_path)
            logger.info(f"✅ Loaded {len(df)} vessels")
            return df
        except Exception as e:
            logger.error(f"❌ Failed to read CSV: {str(e)}")
            return None

    def _parse_arrivals(self, df):
        """Parse Arrival_Date (DD/MM/YY) into datetimes and days-waiting.

        The reference "today" is the lineup's Update_Date, not the latest arrival --
        the lineup carries forward-dated arrivals (the forward book) that would
        otherwise make every vessel look overdue.
        """
        arrivals = pd.to_datetime(df.get('Arrival_Date'), format='%d/%m/%y', errors='coerce')
        reference = pd.NaT
        if 'Update_Date' in df.columns:
            reference = pd.to_datetime(df['Update_Date'], format='%d/%m/%Y', errors='coerce').max()
        if pd.isna(reference):
            reference = pd.Timestamp(datetime.now().date())
        return arrivals, reference, (reference - arrivals).dt.days

    def _is_laden(self, qty):
        """A vessel counts as laden when Cargo_Quantity holds a real number."""
        if pd.isna(qty):
            return False
        digits = re.sub(r'[^0-9]', '', str(qty).split('/')[0])
        return bool(digits) and int(digits) > 0

    def _load_weekly_trend(self):
        """Week-over-week deltas from weekly_data/weekly_history.json, if present."""
        history_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "weekly_data", "weekly_history.json"
        )
        try:
            with open(history_file, encoding='utf-8') as fh:
                history = json.load(fh)
            weeks = sorted(history.keys())
            if len(weeks) < 2:
                return "No previous week on record — this is the first tracked week."
            now, prev = history[weeks[-1]], history[weeks[-2]]

            def delta(current, previous):
                change = current - previous
                pct = (change / previous * 100) if previous else 0
                return f"{current:,.0f} vs {previous:,.0f} ({change:+,.0f}, {pct:+.1f}%)"

            return (
                f"- Vessel count: {delta(now['total_vessels'], prev['total_vessels'])}\n"
                f"- Total GRT: {delta(now['total_grt'], prev['total_grt'])}"
            )
        except Exception as e:
            logger.warning(f"⚠️  Weekly trend unavailable: {str(e)}")
            return "Weekly comparison unavailable."

    def build_data_brief(self, df):
        """Assemble the factual brief the LLM reasons over."""
        total_vessels = len(df)
        total_grt = pd.to_numeric(df['GRT'], errors='coerce').sum()
        avg_draft = pd.to_numeric(df['Draft'], errors='coerce').mean()
        avg_length = pd.to_numeric(df['Length'], errors='coerce').mean()

        arrivals, reference, days_waiting = self._parse_arrivals(df)
        laden = df['Cargo_Quantity'].apply(self._is_laden) if 'Cargo_Quantity' in df.columns else None

        # Demand side: per-category counts for Anwar-relevant cargoes only
        df = df.copy()
        df['_category'] = df['Cargo_Type'].apply(categorize_cargo)
        relevant = df[df['_category'].notna()]
        excluded_count = int((df['_category'].isna()).sum())

        cargo_lines = []
        for category, rows in relevant.groupby('_category', sort=False):
            count = len(rows)
            grt = pd.to_numeric(rows['GRT'], errors='coerce').sum()
            laden_txt = f", {int(laden[rows.index].sum())} laden / {int((~laden[rows.index]).sum())} empty" if laden is not None else ""
            cargo_lines.append(
                f"  • {category} ({CATEGORY_SBU.get(category, '')}): {count} vessels "
                f"({count / total_vessels * 100:.0f}% of lineup), {grt:,.0f} GRT{laden_txt}"
            )
        if excluded_count:
            cargo_lines.append(
                f"  • OUT OF SCOPE for Anwar Group (food, edible oil, wheat, sugar, fertiliser, "
                f"ballast, demolition, vehicles, paper pulp, etc.): {excluded_count} vessels "
                f"({excluded_count / total_vessels * 100:.0f}% of lineup) — ignored below."
            )

        # Supply side: where vessels are sitting
        section_counts = df['Section'].value_counts()
        section_lines = [
            f"  • {section}: {count} vessels ({count / total_vessels * 100:.0f}%)"
            for section, count in section_counts.head(8).items()
        ]
        waiting = int(section_counts.filter(regex='(?i)anchorage|awaiting|not entering').sum())
        ready = total_vessels - waiting

        # Long-stayers. Split matters: a laden vessel stuck for months is a discharge
        # bottleneck, an idle ballast tug parked for years is not. Only Anwar-relevant
        # cargoes are tracked; ballast and out-of-scope craft are summarised instead.
        aged = df.assign(_days=days_waiting)
        aged = aged[aged['_days'].notna() & (aged['_days'] > 14)]
        aged_relevant = aged[aged['_category'].notna()]
        aged_other = aged[aged['_category'].isna()]

        def stale_lines(rows):
            return [
                f"  • {row['Vessel_Name']} — {row['Cargo_Type']}, arrived {row['Arrival_Date']} "
                f"({int(row['_days'])} days ago), {row['Section']}, agent {row['Local_Agent']}"
                for _, row in rows.iterrows()
            ]

        if laden is not None:
            aged_cargo = aged_relevant[laden[aged_relevant.index]].nlargest(10, '_days')
            aged_idle = aged_relevant[~laden[aged_relevant.index]].nlargest(6, '_days')
        else:
            aged_cargo, aged_idle = aged_relevant.nlargest(10, '_days'), aged_relevant.iloc[0:0]

        cargo_stale_lines = stale_lines(aged_cargo)
        idle_stale_lines = stale_lines(aged_idle)
        other_stale_count = len(aged_other)

        # Forward book: how far out arrivals are committed
        future = arrivals[arrivals > reference]
        horizon = (
            f"{len(future)} vessels booked ahead, latest arrival {future.max():%d %b %Y}"
            if len(future) else "No forward-dated arrivals in the current lineup"
        )

        agent_lines = [
            f"  • {agent}: {count} vessels" for agent, count in df['Local_Agent'].value_counts().head(8).items()
        ]
        line_lines = [
            f"  • {line}: {count} vessels" for line, count in df['Shipping_Line'].value_counts().head(8).items()
        ] if 'Shipping_Line' in df.columns else []

        return f"""LINEUP DATE: {reference:%d %B %Y}

HEADLINE FIGURES
- Tracked vessels: {total_vessels}
- Waiting (anchorage / awaiting / not entering): {waiting}
- Working or ready to enter: {ready}
- Ready-to-waiting ratio: {ready} : {waiting}
- Total capacity: {total_grt:,.0f} GRT
- Average draft: {avg_draft:.2f} m | Average LOA: {avg_length:.2f} m

WEEK-OVER-WEEK
{self._load_weekly_trend()}

CARGO / PRODUCT MIX — ANWAR GROUP SUPPLY SCOPE (demand side)
{chr(10).join(cargo_lines)}

PORT SECTION DISTRIBUTION (supply side)
{chr(10).join(section_lines)}

LADEN ANWAR-RELEVANT VESSELS WAITING >14 DAYS (discharge bottleneck evidence)
{chr(10).join(cargo_stale_lines) if cargo_stale_lines else "  • None — every Anwar-relevant laden vessel arrived within the last 14 days"}

IDLE ANWAR-RELEVANT CRAFT PARKED >14 DAYS
{chr(10).join(idle_stale_lines) if idle_stale_lines else "  • None"}

OUT-OF-SCOPE VESSELS PARKED >14 DAYS (not Anwar Group's supply — ignore unless they block berths)
  • {other_stale_count} vessels

FORWARD BOOK
- {horizon}

TOP LOCAL AGENTS
{chr(10).join(agent_lines)}

TOP SHIPPING LINES
{chr(10).join(line_lines) if line_lines else "  • Not reported"}"""

    def create_analysis_prompt(self, df):
        """Create prompt for the strategic port-intelligence briefing"""
        return f"""You are a maritime market analyst writing the daily Chittagong Port intelligence
briefing for ANWAR GROUP OF INDUSTRIES. Your reader is a commercial decision-maker across the
group's strategic business units:
- Anwar Ispat — steel (melts scrap/iron ore, needs coal, produces billets, rods, rebar)
- Anwar Cement & Anwar Cement Sheet — needs clinker, limestone, gypsum, slag; watches construction demand
- Anwar Galvanizing — GI coils/sheets (galvanized iron, base metal)
- A1 Polymer — PP yarn and woven bags (polypropylene resin, mostly containerised)
The reader cares about container volumes, coal, cement clinker, limestone, GI and steel scrap,
gas/energy, ocean freight, crude oil, iron ore, PP resin, steel rod, cement sheet and cement bag
supply signals — never about food, edible oil, wheat, sugar, fertiliser, ballast, demolition,
vehicles or paper pulp, which are outside the group's scope.

TODAY'S LINEUP DATA
{self.build_data_brief(df)}

WRITE THE BRIEFING WITH EXACTLY THESE SECTIONS:

**1. Executive Snapshot**
One tight paragraph. State the headline counts and the week-over-week direction, then say what the
ratio of waiting-to-working vessels actually means for Anwar Group's cargo (is supply arriving
faster than the port absorbs it, or is the queue clearing?). Name the pattern in plain commercial
language.

**2. Anwar Group Supply Signals (by Product)**
A markdown table with columns: Product | Vessels | Reading. One row per Anwar-relevant category
listed in the data. The "Reading" column is interpretation, not repetition — tie each category to
the specific SBU that consumes it (e.g. clinker/limestone/gypsum for Anwar Cement, scrap/coal for
Anwar Ispat, GI for Anwar Galvanizing, PP resin for A1 Polymer) and say what the volume and
laden/empty split imply for that SBU's input pipeline.

**3. Supply-Side / Port Capacity Signals**
Bullets. Cover: the ready-to-anchorage ratio and what it says about berth throughput; the
longest-waiting Anwar-relevant vessels BY NAME with their cargo and arrival date as evidence of
whether the bottleneck is structural or a one-week spike; whether the average draft implies
lighterage at outer anchorage; and how far out the forward book commits inflow.

**4. Risks and Watch Items**
Bullets. Concrete risks visible in this lineup — congestion build-up, aged cargo at risk of
quality loss or demurrage, draft constraints, concentration in a single agent or product, and
any fuel/energy-price signal (coal, gas, HSFO, condensate) that could move Anwar Group's
production or freight costs.

**5. Anwar Group Demand Outlook — Bangladesh Market**
Two short bulleted lists that forecast demand for Anwar Group's products and inputs:
  - "Higher demand (rising / strong):" list Anwar-relevant products (steel/rod/rebar, cement,
    cement sheet, GI, PP bags, construction materials) you expect to see strong or growing demand
    for, each with a one-line reason grounded in Bangladesh's industries — construction,
    infrastructure, steel re-rolling, galvanizing, packaging. Anchor each to what the lineup
    shows (e.g. how many vessels of the related input are arriving).
  - "Lower demand (softening / weak):" list the Anwar-relevant products you expect weaker or
    declining demand for, each with a one-line reason (seasonality, substitution, saturation,
    thin arrivals).
Rank both lists from strongest to weakest. This is a country-demand read, not a port-status read.

**6. Actions for ANWAR GROUP OF INDUSTRIES**
3-5 numbered actions, each tied to a specific figure, vessel, agent or SBU named above — e.g.
secure clinker berths for Anwar Cement, lock scrap tonnage for Anwar Ispat, or time container
releases for A1 Polymer resin.

CARGO CODE GLOSSARY (use these meanings, do not invent expansions):
C.CLINK = cement clinker | GI(SCRAP) = galvanised iron / steel scrap | GI = galvanized iron |
CONT = containerised cargo | SLAG = steel slag for cement | LIMESTONE = cement-grade limestone |
GYPSUM = cement additive | LPG/LNG/GAS = gas energy | HSFO = high-sulphur fuel oil |
CONDENSATE = crude-related energy cargo | AGGREGATE/STONE = construction materials

RULES:
- Use only the numbers in the data above. Never invent a vessel, tonnage, or date.
- Quote real vessel names, agents, cargo codes, and dates as evidence. Copy vessel names
  character-for-character from the data — never shorten or alter a name.
- Discuss only Anwar-relevant cargoes; mention out-of-scope cargoes solely as port-congestion
  context, never as business signals.
- Analytical register: state what the data shows and what follows from it. No filler, no emoji,
  no motivational language, no advice that would read the same on any other day.
- If a figure is missing or zero, say so rather than guessing."""

    def analyze_vessels(self, csv_path):
        """Analyze vessel data using Groq LLM"""
        try:
            logger.info("=" * 60)
            logger.info("🤖 ANALYZING VESSELS WITH GROQ")
            logger.info("=" * 60)

            # Read CSV
            df = self.read_csv(csv_path)
            if df is None:
                return None

            # Create prompt
            logger.info("📝 Creating analysis prompt...")
            prompt = self.create_analysis_prompt(df)

            # Query LLM
            logger.info("🔄 Querying Groq LLM...")
            response = self.llm.invoke(prompt)

            analysis = response.content

            logger.info("✅ Analysis complete!")
            logger.info("=" * 60)

            return analysis

        except Exception as e:
            logger.error(f"❌ Analysis failed: {str(e)}")
            return None

    def save_analysis(self, analysis, output_path="analysis_output.txt"):
        """Save analysis to file"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(analysis)
            logger.info(f"✅ Analysis saved to {output_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to save analysis: {str(e)}")
            return False


if __name__ == "__main__":
    try:
        analyzer = VesselAnalyzer()

        # Analyze
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vessels_data.csv")
        analysis = analyzer.analyze_vessels(csv_path)

        if analysis:
            print("\n" + "=" * 60)
            print("📊 ANALYSIS RESULTS")
            print("=" * 60 + "\n")
            print(analysis)

            # Save to file
            analyzer.save_analysis(analysis)

    except ValueError as e:
        logger.error(str(e))
        print("\n⚠️  Setup Error:")
        print("1. Create .env file in project root")
        print("2. Add: GROQ_API_KEY=your_key_here")
        print("3. Get free key from: https://console.groq.com")
