# 📅 Anwar Group of Industries Vessel Tracking - Automation Schedule

## 🎯 Daily Operations (Every Day at 6:00 AM)

**Command:**
```bash
0 6 * * * cd ~/Desktop/osiris && python3 daily_analysis.py >> daily_analysis.log 2>&1
```

**What it does:**
- ✅ Downloads latest vessel data from Chittagong Port Authority (CPA)
- ✅ Extracts vessel information from PDF
- ✅ Stores data in CSV format
- ✅ Analyzes with Groq LLM
- ✅ Generates professional report with:
  - **Fleet Summary** (Total vessels, capacity, draft)
  - **AI-Powered Business Recommendations** (5 insights)
  - **Enhanced Vessel Table** with 8 columns:
    - SL / Vessel Name / Arrival Date
    - Type (Container, Bulk, General, Car)
    - Utilization (🟢 Full / 🟡 Half / 🔴 Low / Empty)
    - Revenue (💰 High / 💵 Medium / 💸 Low)
    - Efficiency (⚡ Quick / ⏳ Normal / ⚠️ Delayed)
    - Local Agent

- ✅ Sends professional HTML email to: **ms.mucha18@gmail.com**

---

## 📊 Weekly Analysis (Every Sunday at 8:00 AM)

**Command:**
```bash
0 8 * * 0 cd ~/Desktop/osiris && python3 weekly_report.py >> weekly_analysis.log 2>&1
```

**What it does:**
- ✅ Aggregates 7 days of vessel data
- ✅ Compares with previous week:
  - 📈 Vessel count trends
  - 📈 Total capacity trends
  - 📊 Percentage changes
- ✅ Analyzes patterns:
  - Cargo type distribution
  - Port status breakdown
  - Top performing agents (Top 5)
- ✅ Generates insights:
  - Traffic volume trends
  - Capacity utilization analysis
  - Agent performance ranking
  - Cargo focus analysis
  - Operational status summary
  - Next week forecast

- ✅ Stores weekly history for long-term trend analysis
- ✅ Sends comprehensive weekly email summary

---

## 📋 Setup Instructions

### Step 1: Set Up Daily Reports (6 AM)
```bash
crontab -e

# Add this line:
0 6 * * * cd ~/Desktop/osiris && python3 daily_analysis.py >> daily_analysis.log 2>&1
```

### Step 2: Set Up Weekly Reports (8 AM on Sunday)
```bash
crontab -e

# Add this line:
0 8 * * 0 cd ~/Desktop/osiris && python3 weekly_report.py >> weekly_analysis.log 2>&1
```

### Step 3: Verify Setup
```bash
crontab -l   # List all scheduled jobs
```

---

## 📈 Data Comparison Columns Explained

### **Type**
- **Container**: Container vessels (CONT cargo)
- **Bulk**: Bulk carriers (Coal, Limestone, Slag)
- **Car**: Car carriers (Vehicle cargo)
- **General**: General cargo vessels

### **Utilization %**
- 🟢 **Full**: 80%+ cargo capacity used
- 🟡 **Half**: 50-79% capacity
- 🔴 **Low**: <50% capacity
- **Empty**: No cargo loaded

### **Revenue Tier**
- 💰 **High**: Premium cargo (Containers, Vehicles) = High revenue
- 💵 **Medium**: Standard cargo (Coal, Metals, Limestone) = Medium revenue
- 💸 **Low**: Basic cargo (Ballast, Bunkering) = Low revenue

### **Efficiency**
- ⚡ **Quick**: At berth (fast turnaround)
- ⏳ **Normal**: In anchorage (normal wait)
- ⚠️ **Delayed**: Waiting for berth (slowest)

---

## 📊 Weekly Reports Include

1. **Weekly Summary**
   - Total vessels this week
   - Total fleet capacity (GRT)
   - Average draft & length

2. **Weekly Trends**
   - Vessel count change vs last week
   - Capacity change vs last week
   - Percentage increases/decreases

3. **Distribution Analysis**
   - Cargo types breakdown
   - Port status breakdown
   - Top 5 agents by vessel count

4. **AI Insights**
   - Traffic volume analysis
   - Capacity utilization status
   - Top agent performance
   - Dominant cargo focus
   - Operational status
   - Next week forecast

---

## 📝 Log Files

- **Daily Reports**: `daily_analysis.log`
- **Weekly Reports**: `weekly_analysis.log`
- **Reports Folder**: `reports/` (markdown files)
- **Weekly History**: `weekly_data/weekly_history.json`

---

## 🚀 Manual Execution

Run anytime without waiting for schedule:

```bash
# Daily Report
python3 daily_analysis.py

# Weekly Report
python3 weekly_analysis.py
```

---

## ✅ System Status

- ✅ Groq LLM Integration: **ACTIVE** (Real-time analysis)
- ✅ Email Delivery: **ACTIVE** (Gmail SMTP)
- ✅ Daily Reports: **READY**
- ✅ Weekly Reports: **READY**
- ✅ Comparison Columns: **ALL 6 IMPLEMENTED**
  - Type ✅
  - Utilization ✅
  - Revenue ✅
  - Efficiency ✅
  - Plus: Vessel Name, Arrival Date, Agent

---

## 💡 Tips

1. **Check Email**: Reports arrive automatically at scheduled times
2. **Review History**: Check `weekly_data/weekly_history.json` for trend data
3. **Customize Email**: Edit `.env` to change recipient emails
4. **Change Schedule**: Modify cron times if needed
5. **Monitor Logs**: Check `.log` files for any issues

---

**System Created**: 2026-07-06
**Last Updated**: 2026-07-06
**Status**: ✅ PRODUCTION READY
