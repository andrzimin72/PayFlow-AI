## PayFlow AI - Demo Suite

This directory contains comprehensive demonstration scripts that showcase all PayFlow AI platform capabilities using synthetic data.

### 🎯 Overview

The demo suite allows you to:
- **Showcase all features** without requiring PayPal API credentials or external services
- **Run instantly** with zero setup - just Python and basic dependencies
- **Demonstrate the complete platform** including AI, forecasting, risk management, invoicing, and disputes
- **Perfect for presentations** to stakeholders, interviewers, or portfolio viewers

### 📦 Demo Scripts

#### 1. Terminal Demo (`demo_terminal.py`)

A rich terminal-based demonstration with beautiful formatting, tables, and ASCII charts.

**Features:**
- ✅ Synthetic data generation (100 transactions, 5 invoices, 3 disputes)
- ✅ AI transaction categorization
- ✅ Cash flow forecasting with ASCII visualization
- ✅ Anomaly detection
- ✅ Risk management with portfolio metrics
- ✅ Invoice management
- ✅ Dispute resolution with AI responses

**Usage:**
```bash
python demo_terminal.py
```

Output:

Rich formatted tables
Progress indicators
Color-coded output
ASCII charts
Panel displays

### 2. Streamlit Dashboard (demo_dashboard.py)

A complete interactive dashboard that looks identical to the production app.

Features:
- ✅ Full interactive UI
- ✅ Real-time filtering and search
- ✅ Interactive Plotly charts
- ✅ Risk gauge visualization
- ✅ All platform sections
- ✅ Responsive design

**Usage:**
```bash
streamlit run demo_dashboard.py
```

Output:

Interactive web dashboard
Charts and visualizations
Filterable data tables
Professional UI

### 🚀 Quick Start

#### Installation

```bash
# Install demo dependencies
pip install -r requirements-demo.txt

# Or install everything
pip install -r requirements.txt
```

#### Run Terminal Demo

```bash
python demo_terminal.py
```

#### Run Streamlit Dashboard
```bash
streamlit run demo_dashboard.py
```

### 📊 What's Demonstrated

#### 1. Synthetic Data Generation
100 realistic transactions with varied categories and amounts
Intentional anomalies for detection testing
5 sample invoices with different statuses
3 sample disputes with AI-generated responses

#### 2. AI Transaction Categorization
- Zero-shot NLP classification
- 4 categories: Freelance Income, Software Subscription, Personal Expense, Suspicious Activity
- Confidence scores for each prediction
- Category distribution analysis

#### 3. Cash Flow Forecasting
- 30-day predictions using Prophet-like methodology
- Confidence intervals (upper/lower bounds)
- Best/worst day identification
- Visual trend charts

#### 4. Anomaly Detection
- Isolation Forest-inspired detection
- Flags unusual transactions
- Anomaly rate calculation
- Detailed anomaly reporting

#### 5. Risk Management
- Weighted risk scoring (0-100)
- Portfolio-level risk assessment
- Risk distribution (LOW/MEDIUM/HIGH/CRITICAL)
- High-risk transaction identification

#### 6. Invoice Management
- Professional invoice tracking
- Status management (PAID/SENT/UNPAID)
- Client information
- Amount tracking

#### 7. Dispute Resolution
- Dispute tracking
- AI-generated response samples
- Status management
- Reason categorization

### 📝 Notes

- No external APIs required - Everything runs locally
- Synthetic data only - No real PayPal transactions
- Mock AI models - Uses simple keyword matching for demo
- Reproducible - Same seed produces same data
- Fast execution - Terminal demo runs in <5 seconds

### 🎉 Success Criteria

After running the demos, you should see:
- ✅ Terminal demo completes without errors
- ✅ Streamlit dashboard loads in browser
- ✅ All 7 sections display correctly
- ✅ Charts and tables render properly
- ✅ Risk scores calculate correctly
- ✅ Anomalies are detected
- ✅ Invoices and disputes display

### 📞 Support

If you encounter issues:
- Check that all dependencies are installed
- Ensure you're running from the project root
- Verify Python version (3.9+)
- Check the troubleshooting section above
