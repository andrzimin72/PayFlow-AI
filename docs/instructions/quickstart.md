## 🚀 PayFlow AI — Quick Start Guide

**Get up and running in 5 to 30 minutes.**

This guide walks you through setting up PayFlow AI on your local machine. Choose the path that fits your needs:

| Path | Time | What You Get | Best For |
|:---|:---:|:---|:---|
| **A. 5-Minute Demo** | 5 min | Synthetic data demo (no accounts needed) | Quick exploration, portfolio viewing |
| **B. 30-Minute Full Setup** | 30 min | Live PayPal Sandbox integration | Real development, interviews |

---

### 📋 Prerequisites

Before you begin, make sure you have the following installed:

#### Required Software

| Software | Version | Installation |
|:---|:---|:---|
| **Python** | 3.9 – 3.11 | [python.org](https://www.python.org/downloads/) |
| **Docker** | 20.10+ | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **Git** | 2.30+ | [git-scm.com](https://git-scm.com/downloads) |

#### Verify Your Installation

Run these commands to confirm everything is ready:

```bash
python --version     # Should show 3.9, 3.10, or 3.11
docker --version     # Should show Docker version 20.10+
git --version        # Should show git version 2.30+
```

#### Optional (for Full Setup only)

- **PayPal Developer Account** — [developer.paypal.com](https://developer.paypal.com/) (free)
- **Hugging Face Account** — [huggingface.co](https://huggingface.co/) (free, for AI summaries)
- **ngrok Account** — [ngrok.com](https://ngrok.com/) (free, for webhook testing)

---

### 🎯 Path A: 5-Minute Demo (No Setup Required)

**Perfect for:** Quick exploration, portfolio viewing, initial impressions.

This path uses synthetic data — no PayPal account, no API keys, no external services needed.

#### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/payflow-ai.git
cd payflow-ai
```

#### Step 2: Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# OR: .venv\Scripts\activate     # Windows
```

#### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements-demo.txt
```

⏱️ *This takes 2–5 minutes. The ML libraries (PyTorch, transformers) are large.*

#### Step 4: Run the Terminal Demo

```bash
python demo_terminal.py
```

✅ **You should see:** A rich, color-coded terminal output walking through all platform capabilities — AI categorization, forecasting, anomaly detection, risk scoring, invoicing, and dispute resolution — all using synthetic data.

#### Step 5: Run the Dashboard Demo

```bash
streamlit run demo_dashboard.py
```

✅ **You should see:** Your browser opens to `http://localhost:8501` showing the full interactive dashboard with synthetic data.

#### 🎉 You're Done!

You've just seen PayFlow AI in action. To stop the demo, press `Ctrl+C` in the terminal.

---

### 🔧 Path B: 30-Minute Full Setup

**Perfect for:** Real development, interview preparation, contributing to the project.

This path sets up the complete platform with live PayPal Sandbox integration.

#### Step 1: Clone and Set Up Environment

```bash
git clone https://github.com/yourusername/payflow-ai.git
cd payflow-ai
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
pip install --upgrade pip
pip install -r requirements-dev.txt
```

#### Step 2: Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in your credentials:

```bash
# Required for PayPal integration
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_SECRET=your_sandbox_secret
PAYPAL_WEBHOOK_ID=your_webhook_id

# Required for AI summaries
HF_TOKEN=your_huggingface_token

# Optional (for webhook testing)
NGROK_AUTH_TOKEN=your_ngrok_token
ZAPIER_WEBHOOK_URL=your_zapier_webhook_url
```

##### Where to Get These Credentials

| Credential | Where to Get It |
|:---|:---|
| `PAYPAL_CLIENT_ID` / `PAYPAL_SECRET` | [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/applications/sandbox) → Create a Sandbox App |
| `PAYPAL_WEBHOOK_ID` | PayPal Dashboard → Webhooks → Create Webhook → Copy ID |
| `HF_TOKEN` | [Hugging Face Settings](https://huggingface.co/settings/tokens) → New Token (Read access) |
| `NGROK_AUTH_TOKEN` | [ngrok Dashboard](https://dashboard.ngrok.com/get-started/your-authtoken) |
| `ZAPIER_WEBHOOK_URL` | Zapier → Create Zap → Webhooks by Zapier → Copy Custom Webhook URL |

#### Step 3: Start the Infrastructure

Open a new terminal and start Elasticsearch:

```bash
docker run -d \
  --name payflow-es \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms1g -Xmx1g" \
  docker.elastic.co/elasticsearch/elasticsearch:8.11.1
```

✅ **Verify Elasticsearch is running:**
```bash
curl http://localhost:9200/_cluster/health
# Should return JSON with "status": "green" or "yellow"
```

#### Step 4: Start the Platform Services

You need **three terminals** for the three services:

**Terminal 1 — REST API:**
```bash
python api.py
```
✅ Access at: `http://localhost:8000`  
✅ API docs at: `http://localhost:8000/docs`

**Terminal 2 — Webhook Listener:**
```bash
python webhook_listener.py
```
✅ Note the ngrok URL printed (e.g., `https://abc123.ngrok.io/paypal-webhook`)  
✅ Paste this URL into your PayPal Developer Dashboard under Webhooks

**Terminal 3 — Dashboard:**
```bash
streamlit run app.py
```
✅ Access at: `http://localhost:8501`

#### Step 5: Start the Monitoring Stack (Optional)

In a fourth terminal:

```bash
docker compose --profile monitoring up -d
```

✅ **Access the monitoring tools:**
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (login: `admin` / `admin123`)
- Jaeger: `http://localhost:16686`

#### Step 6: Make Your First Test Transaction

To populate data, you need at least one PayPal Sandbox transaction:

1. Go to [PayPal Sandbox](https://www.sandbox.paypal.com/)
2. Log in with a **sandbox buyer account** (created in the Developer Dashboard)
3. Send a small payment (e.g., $10) to your sandbox business account
4. Wait ~30 seconds for the webhook to fire

✅ **Verify in the dashboard:**
- Open `http://localhost:8000/transactions` — you should see your transaction
- Open `http://localhost:8501` — you should see the transaction in the dashboard

#### 🎉 You're Running the Full Platform!

You now have:
- ✅ Live PayPal integration
- ✅ AI-powered categorization
- ✅ Real-time webhook processing
- ✅ Risk scoring and anomaly detection
- ✅ Full observability stack
- ✅ Interactive dashboard

---

### ✅ Verification Checklist

After setup, verify everything is working:

```bash
# 1. Check API health
curl http://localhost:8000/health
# Expected: {"status": "healthy", "service": "PayFlow AI Financial API", ...}

# 2. Check webhook listener
curl http://localhost:8001/health
# Expected: {"status": "healthy", "service": "PayFlow AI Webhook Listener", ...}

# 3. Check Elasticsearch
curl http://localhost:9200/_cluster/health
# Expected: JSON with "status": "green" or "yellow"

# 4. Run the test suite
pytest tests/ -v
# Expected: 155 tests pass

# 5. Check Prometheus metrics
curl http://localhost:8000/metrics
# Expected: Prometheus-formatted metrics output
```

If all five checks pass, your setup is complete and healthy.

---

### 🎓 Common Tasks

#### Fetch and Analyze Transactions

In the dashboard (`http://localhost:8501`), click the **"🚀 Fetch, Analyze & Index"** button in the sidebar. This will:
1. Pull the last 30 days of transactions from PayPal
2. Categorize them with AI
3. Index them into Elasticsearch
4. Generate a financial summary

#### Search Transactions

In the dashboard's search bar, try queries like:
- `Adobe` — finds software subscriptions
- `Freelance Income` — finds all income
- `Suspicious` — finds flagged transactions

#### Trigger a Webhook Manually (Testing)

```bash
curl -X POST http://localhost:8001/paypal-webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "PAYMENT.CAPTURE.COMPLETED",
    "resource": {
      "transaction_id": "TEST-001",
      "amount": {"value": "100.00", "currency_code": "USD"},
      "custom_note": "Test payment for consulting"
    }
  }'
```

⚠️ **Note:** Without valid PayPal signature headers, this will be rejected with 401. This is the security system working correctly!

#### Run Performance Benchmarks

```bash
pytest tests/performance/ -v
```

#### Generate Architecture Diagrams

```bash
python docs/architecture/render_diagrams.py
```

---

### 🛠️ Troubleshooting

#### Issue: `ModuleNotFoundError: No module named 'torch'`

**Cause:** PyTorch installation failed or was skipped.

**Fix:**
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
# OR for GPU support:
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

#### Issue: Elasticsearch connection refused

**Cause:** Elasticsearch isn't running or isn't ready yet.

**Fix:**
```bash
# Check if container is running
docker ps | grep payflow-es

# If not running, start it
docker start payflow-es

# Wait for it to be ready (can take 30-60 seconds)
until curl -s http://localhost:9200/_cluster/health | grep -q "green\|yellow"; do
  echo "Waiting for Elasticsearch..."
  sleep 2
done
```

#### Issue: `PAYPAL_CLIENT_ID and PAYPAL_SECRET must be set`

**Cause:** The `.env` file is missing or credentials aren't filled in.

**Fix:**
```bash
# Verify .env exists
ls -la .env

# Verify credentials are set
grep PAYPAL_CLIENT_ID .env
```

#### Issue: Dashboard shows "No data in Elasticsearch yet"

**Cause:** No transactions have been fetched yet.

**Fix:** Click the **"🚀 Fetch, Analyze & Index"** button in the dashboard sidebar.

#### Issue: Webhook returns 401 Unauthorized

**Cause:** The webhook signature verification is working — it's rejecting unsigned requests. This is correct behavior!

**Fix:** For testing, either:
- Send a real PayPal webhook (requires live PayPal Sandbox transaction)
- Temporarily disable verification in `webhook_listener.py` (NOT recommended for production)

#### Issue: Port already in use

**Cause:** Another process is using port 8000, 8001, 8501, or 9200.

**Fix:**
```bash
# Find what's using the port (macOS/Linux)
lsof -i :8000

# Kill the process
kill -9 <PID>

# OR use a different port
PORT=8002 python api.py
```

#### Issue: Out of memory errors

**Cause:** ML models are memory-intensive.

**Fix:**
- Close other applications
- Increase Docker memory allocation (Docker Desktop → Settings → Resources → 4GB+)
- Use the demo path instead of the full setup

---

### 📚 Next Steps

Once you have the platform running, here's where to go next:

#### For Developers
- **Architecture Overview:** `docs/WHITEPAPER.pdf` — Deep technical dive
- **API Documentation:** `http://localhost:8000/docs` — Interactive API explorer
- **Test Suite:** `pytest tests/ -v` — Explore the 155 tests
- **Contributing:** See `CONTRIBUTING.md` (if available)

#### For Business Stakeholders
- **Executive Summary:** `docs/EXECUTIVE_SUMMARY.md` — Business value and ROI
- **Architecture Diagrams:** `docs/architecture/png/` — Visual system overview
- **Risk Register:** `docs/RISK_REGISTER.md` — Risk management approach

#### For Interview Preparation
- Practice explaining the 4 pillars (AI Automation, Risk Management, Predictive Analytics, Production Engineering)
- Review the C4 diagrams and be ready to walk through each level
- Be prepared to discuss the Risk Register and architectural trade-offs

---

### 🆘 Getting Help

If you run into issues not covered in this guide:

1. **Check the troubleshooting section above** — most common issues are covered
2. **Review the logs** — `logs/api.log`, `logs/webhook.log`, etc.

---

### 🎉 Congratulations!

You've successfully set up PayFlow AI. You now have a fully functional, production-grade financial intelligence platform running on your machine.

**What's next:**
- Explore the dashboard and try different queries
- Make test transactions in PayPal Sandbox
- Review the architecture diagrams
- Read the technical whitepaper for deep understanding
- Consider contributing to the project or extending it

Welcome to PayFlow AI! 🚀

---

*© 2026 Andre Zimin. Licensed under the Apache-2.0 License.*
