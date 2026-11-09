"""
PayFlow AI Streamlit Dashboard
==============================

Interactive dashboard covering the full platform:

    1. Generative financial summary (Mistral-7B)
    2. Elasticsearch-backed fuzzy search
    3. AG Grid ledger with colour-coded confidence
    4. Prophet cash-flow forecast
    5. Isolation Forest anomaly detection
    6. Weighted risk management dashboard
    7. Invoice management
    8. Dispute resolution

Version: 4.1.0
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
from transformers import pipeline

import ai_engine
import anomaly_detector
import dispute_manager
import elastic_manager
import forecasting
import generative_ai
import invoice_manager
import paypal_client
import risk_engine
from observability import logging as obs_logging

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="PayFlow AI | Enterprise Dashboard",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded",
)

obs_logging.setup_logging()
logger = obs_logging.get_logger("streamlit-dashboard")

st.markdown(
    """
    <style>
    .main-header { font-size: 2.5rem; font-weight: 700; color: #003087; margin-bottom: 0.5rem; }
    .sub-header  { font-size: 1.2rem; color: #666; margin-bottom: 2rem; }
    .stAlert     { border-radius: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# MODEL CACHE
# =============================================================================

@st.cache_resource(show_spinner="🧠 Loading NLP categorisation model...")
def _load_classifier():
    logger.info("loading_categorisation_model")
    return pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    st.markdown('<p class="main-header">💸 PayFlow AI</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">Intelligent PayPal Transaction Dashboard & Risk Management Platform</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    # Session state
    for key, default in [
        ("df", None),
        ("summary", None),
        ("last_fetch_time", None),
        ("invoice_items", [{"name": "", "quantity": 1, "unit_price": 0.0, "description": ""}]),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Control Panel")
        st.markdown("Fetch PayPal transactions, run the AI pipeline, and index into Elasticsearch.")
        if st.session_state.last_fetch_time:
            st.info(f"🕐 Last updated: {st.session_state.last_fetch_time}")

        if st.button("🚀 Fetch, Analyze & Index", type="primary", use_container_width=True):
            _run_pipeline()

    # Main content
    if st.session_state.summary:
        st.subheader("📊 AI Financial Analyst Summary")
        st.info(st.session_state.summary)
        st.divider()

    st.subheader("🔍 Search Transaction Ledger")
    query = st.text_input(
        "Search by description or AI category:",
        placeholder="Type to search Elastic...",
    )
    if query:
        display_df = elastic_manager.search_transactions(query)
        st.caption(f"🎯 Found {len(display_df)} matching transactions.")
        logger.info("search_performed", query=query, results=len(display_df))
    else:
        display_df = elastic_manager.get_all_transactions()

    if not display_df.empty:
        _render_ledger(display_df)
        st.divider()
        _render_forecast()
        st.divider()
        _render_anomaly_detection()
        st.divider()
        _render_risk_dashboard()
        st.divider()
        _render_invoices()
        st.divider()
        _render_disputes()
    else:
        st.info("📭 No data in Elasticsearch yet. Click **Fetch, Analyze & Index** in the sidebar.")

    st.divider()
    st.caption(
        "**Built with:** PayPal API • Hugging Face NLP • Mistral-7B • Elasticsearch • "
        "AG Grid • Prophet • Scikit-learn • Streamlit"
    )
    st.caption("© 2026 PayFlow AI — Enterprise Financial Analytics & Risk Management Platform v4.1.0")


# =============================================================================
# PIPELINE
# =============================================================================

def _run_pipeline() -> None:
    logger.info("fetch_analyze_index_triggered")

    with st.spinner("🔐 Authenticating with PayPal..."):
        token = paypal_client.get_access_token()
        if not token:
            logger.error("paypal_authentication_failed")
            st.error("❌ PayPal authentication failed. Check your .env file.")
            return

    with st.spinner("📥 Fetching transactions..."):
        raw = paypal_client.fetch_transactions(token)
        if not raw:
            logger.warning("no_transactions_found")
            st.warning("No transactions found in the last 30 days.")
            return

    with st.spinner("🤖 AI is categorising transactions..."):
        classifier = _load_classifier()
        st.session_state.df = ai_engine.process_transactions(raw, classifier)
        logger.info("ai_categorisation_completed", count=len(st.session_state.df))

    with st.spinner("💾 Saving to Elasticsearch..."):
        elastic_manager.index_transactions(st.session_state.df)
        logger.info("indexed_to_elasticsearch", count=len(st.session_state.df))

    with st.spinner("📝 Mistral-7B is writing your financial summary..."):
        st.session_state.summary = generative_ai.generate_financial_summary(st.session_state.df)
        logger.info("generative_summary_completed")

    st.session_state.last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.success("✅ Data processed, indexed, and analysed successfully!")
    st.balloons()
    logger.info("fetch_analyze_index_completed")

# =============================================================================
# LEDGER
# =============================================================================

def _render_ledger(df: pd.DataFrame) -> None:
    st.subheader("📈 Interactive Financial Ledger")

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(editable=False, sortable=True, filter=True, resizable=True)
    gb.configure_column("Amount", type=["numericColumn"])
    gb.configure_column("AI Category", filter="agTextColumnFilter")

    confidence_renderer = JsCode(
        """
        function(params) {
            let val = params.value * 100;
            let color = val > 80 ? '#28a745' : (val > 60 ? '#ffc107' : '#dc3545');
            return `<div style="width:100%;background:#eee;border-radius:5px;padding:2px;">
                        <div style="width:${val}%;background:${color};height:18px;border-radius:5px;
                                    text-align:center;color:white;font-size:11px;line-height:18px;font-weight:bold;">
                            ${val.toFixed(1)}%
                        </div>
                    </div>`;
        }
        """
    )
    gb.configure_column("Confidence", header_name="AI Confidence", cell_renderer=confidence_renderer, maxWidth=150)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)

    AgGrid(
        df,
        gridOptions=gb.build(),
        update_mode="NO_UPDATE",
        fit_columns_on_grid_load=True,
        theme="streamlit",
        height=400,
    )

# =============================================================================
# FORECAST
# =============================================================================

def _render_forecast() -> None:
    st.subheader("📈 30-Day Cash Flow Forecast")
    st.markdown("*Predicted net cash flow based on historical transactions (Meta's Prophet).*")

    with st.spinner("🔮 Generating forecast..."):
        try:
            summary = forecasting.get_forecast_summary()
            logger.info("forecast_generated", status=summary["status"])
            if summary["status"] != "success":
                st.warning(summary["message"])
                return

            c1, c2, c3 = st.columns(3)
            c1.metric("Predicted Net (30d)", f"${summary['total_predicted_net']:,.2f}")
            c2.metric("Best Day", f"${summary['best_day']['predicted_net']:,.2f}", summary["best_day"]["date"])
            c3.metric("Worst Day", f"${summary['worst_day']['predicted_net']:,.2f}", summary["worst_day"]["date"])

            data = summary["forecast_data"]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=data["ds"], y=data["yhat_upper"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=data["ds"], y=data["yhat_lower"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(68,68,255,0.2)", showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=data["ds"], y=data["yhat"], mode="lines", line=dict(color="#003087", width=3), name="Predicted Cash Flow"))
            fig.update_layout(title="Cash Flow Forecast with Confidence Intervals", xaxis_title="Date", yaxis_title="Net Cash Flow ($)", hovermode="x unified", height=400)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as exc:
            logger.error("forecast_failed", error=str(exc), exc_info=True)
            st.error(f"Forecasting error: {exc}")

# =============================================================================
# ANOMALY DETECTION
# =============================================================================

def _render_anomaly_detection() -> None:
    st.subheader("🚨 Anomaly Detection (Fraud & Error Detection)")
    st.markdown("*Unusual transactions flagged by Isolation Forest (unsupervised ML).*")

    with st.spinner("🔍 Scanning for anomalies..."):
        try:
            summary = anomaly_detector.get_anomaly_summary()
            logger.info("anomaly_detection_completed", status=summary["status"])
            if summary["status"] != "success":
                st.warning(summary["message"])
                return

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Transactions", summary["total_transactions"])
            c2.metric(
                "Anomalies Detected",
                summary["total_anomalies"],
                delta=f"-{summary['total_anomalies']}" if summary["total_anomalies"] else None,
                delta_color="inverse",
            )
            c3.metric("Anomaly Rate", summary["anomaly_rate"])

            if summary["total_anomalies"] > 0:
                st.warning(f"⚠️ Found {summary['total_anomalies']} potentially suspicious transactions:")
                st.dataframe(pd.DataFrame(summary["anomalies"]), use_container_width=True, hide_index=True)
            else:
                st.success("✅ No anomalies detected. All transactions appear normal.")
        except Exception as exc:
            logger.error("anomaly_detection_failed", error=str(exc), exc_info=True)
            st.error(f"Anomaly detection error: {exc}")

# =============================================================================
# RISK DASHBOARD
# =============================================================================

def _render_risk_dashboard() -> None:
    st.subheader("🛡️ Risk Management Dashboard")
    st.markdown("*Weighted risk scoring: anomaly 50% + AI uncertainty 30% + financial impact 20%.*")

    with st.spinner("🛡️ Calculating risk scores..."):
        try:
            m = risk_engine.get_portfolio_risk_metrics()
            logger.info("portfolio_risk_assessed", status=m["status"])
            if m["status"] != "success":
                st.warning(m["message"])
                return

            c1, c2 = st.columns([1, 2])
            with c1:
                fig = go.Figure(
                    go.Indicator(
                        mode="gauge+number",
                        value=m["portfolio_risk_score"],
                        domain={"x": [0, 1], "y": [0, 1]},
                        title={"text": f"Portfolio Risk Score<br><span style='font-size:0.8em;color:{m['risk_color']}'>{m['risk_level']}</span>"},
                        gauge={
                            "axis": {"range": [None, 100]},
                            "bar": {"color": m["risk_color"]},
                            "steps": [
                                {"range": [0, 39], "color": "#d4edda"},
                                {"range": [40, 59], "color": "#fff3cd"},
                                {"range": [60, 79], "color": "#ffe5d0"},
                                {"range": [80, 100], "color": "#f8d7da"},
                            ],
                            "threshold": {"line": {"color": "black", "width": 4}, "thickness": 0.75, "value": 80},
                        },
                    )
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)

            with c2:
                st.markdown(
                    f"""
                    <div style="padding:15px;background:#f8f9fa;border-radius:8px;border-left:4px solid {m['risk_color']};">
                        <h4 style="margin:0;">Recommended Action: <span style="color:{m['risk_color']};">{m['recommended_action']}</span></h4>
                        <p style="margin:5px 0 0 0;color:#666;">{m['risk_description']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("🟢 LOW", m["risk_distribution"]["LOW"])
                d2.metric("🟡 MEDIUM", m["risk_distribution"]["MEDIUM"])
                d3.metric("🟠 HIGH", m["risk_distribution"]["HIGH"])
                d4.metric("🔴 CRITICAL", m["risk_distribution"]["CRITICAL"])

                s1, s2, s3 = st.columns(3)
                s1.metric("Avg Risk Score", f"{m['average_risk_score']}/100")
                s2.metric("Max Risk Score", f"{m['max_risk_score']}/100")
                s3.metric("High-Risk %", f"{m['high_risk_percentage']}%")

            st.divider()
            st.markdown("#### 📋 Risk-Scored Transactions")
            st.markdown("*Sorted by risk score (highest first). Transactions ≥ 80 require immediate investigation.*")

            scored_df = pd.DataFrame(m["scored_transactions"])[
                ["description", "amount", "ai_category", "risk_score", "risk_level", "recommended_action"]
            ]

            risk_score_renderer = JsCode(
                """
                function(params) {
                    let val = params.value;
                    let color = val >= 80 ? '#dc3545' : (val >= 60 ? '#fd7e14' : (val >= 40 ? '#ffc107' : '#28a745'));
                    return `<div style="width:100%;background:#eee;border-radius:5px;padding:2px;">
                                <div style="width:${val}%;background:${color};height:18px;border-radius:5px;
                                            text-align:center;color:white;font-size:11px;line-height:18px;font-weight:bold;">
                                    ${val.toFixed(1)}
                                </div>
                            </div>`;
                }
                """
            )
            risk_level_renderer = JsCode(
                """
                function(params) {
                    let colorMap = {'LOW':'#28a745','MEDIUM':'#ffc107','HIGH':'#fd7e14','CRITICAL':'#dc3545'};
                    let color = colorMap[params.value] || '#6c757d';
                    return `<span style="background:${color};color:white;padding:3px 10px;border-radius:12px;font-weight:bold;font-size:0.85em;">${params.value}</span>`;
                }
                """
            )

            gb = GridOptionsBuilder.from_dataframe(scored_df)
            gb.configure_default_column(editable=False, sortable=True, filter=True, resizable=True)
            gb.configure_column("risk_score", header_name="Risk Score (0-100)", cell_renderer=risk_score_renderer, maxWidth=150)
            gb.configure_column("risk_level", header_name="Risk Level", cell_renderer=risk_level_renderer, maxWidth=120)
            gb.configure_column("recommended_action", header_name="Action Required")
            gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)

            AgGrid(
                scored_df,
                gridOptions=gb.build(),
                update_mode="NO_UPDATE",
                fit_columns_on_grid_load=True,
                theme="streamlit",
                height=400,
            )

            critical = [t for t in m["scored_transactions"] if t["risk_score"] >= 80]
            if critical:
                st.error(f"🚨 **{len(critical)} CRITICAL transaction(s)** require immediate investigation:")
                for tx in critical[:5]:
                    st.markdown(f"- **{tx['description']}** — {tx['amount']} (Risk: {tx['risk_score']}/100)")
        except Exception as exc:
            logger.error("risk_assessment_failed", error=str(exc), exc_info=True)
            st.error(f"Risk assessment error: {exc}")

# =============================================================================
# INVOICES
# =============================================================================

def _render_invoices() -> None:
    st.subheader("📄 Invoice Management")
    st.markdown("*Create, send, and track professional PayPal invoices.*")

    with st.expander("Create New Invoice", expanded=False):
        with st.form("invoice_form"):
            c1, c2 = st.columns(2)
            with c1:
                merchant_email = st.text_input("Your Business Email", value="business@example.com")
                client_email = st.text_input("Client Email", value="client@example.com")
                client_name = st.text_input("Client Name", value="John Doe")
            with c2:
                payment_terms = st.selectbox("Payment Terms", ["NET_10", "NET_15", "NET_30", "DUE_ON_RECEIPT"], index=2)
                note = st.text_area("Note to Client", value="Thank you for your business!")

            st.markdown("**Invoice Items**")
            for idx, item in enumerate(st.session_state.invoice_items):
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                with c1:
                    item["name"] = st.text_input("Item Name", value=item["name"], key=f"name_{idx}")
                with c2:
                    item["quantity"] = st.number_input("Qty", min_value=1, value=item["quantity"], key=f"qty_{idx}")
                with c3:
                    item["unit_price"] = st.number_input("Price", min_value=0.0, value=item["unit_price"], key=f"price_{idx}")
                with c4:
                    if idx > 0 and st.button("🗑️", key=f"rm_{idx}"):
                        st.session_state.invoice_items.pop(idx)
                        st.rerun()

            if st.form_submit_button("➕ Add Item"):
                st.session_state.invoice_items.append({"name": "", "quantity": 1, "unit_price": 0.0, "description": ""})
                st.rerun()

            total = sum(i["quantity"] * i["unit_price"] for i in st.session_state.invoice_items)
            st.info(f"**Total Amount:** ${total:,.2f}")

            if st.form_submit_button("🚀 Create & Send Invoice", type="primary"):
                valid = [i for i in st.session_state.invoice_items if i["name"] and i["quantity"] > 0 and i["unit_price"] > 0]
                if not valid:
                    st.error("Please add at least one valid item.")
                else:
                    with st.spinner("Creating invoice..."):
                        token = paypal_client.get_access_token()
                        if not token:
                            st.error("❌ PayPal authentication failed.")
                            return
                        invoice = invoice_manager.create_invoice(
                            token=token,
                            merchant_email=merchant_email,
                            client_email=client_email,
                            client_name=client_name,
                            items=valid,
                            note=note,
                            payment_terms=payment_terms,
                        )
                        if not invoice:
                            st.error("❌ Failed to create invoice.")
                        else:
                            invoice_id = invoice.get("id")
                            sent = invoice_manager.send_invoice(token, invoice_id)
                            if sent:
                                st.success(f"✅ Invoice created and sent! Invoice ID: {invoice_id}")
                                st.session_state.invoice_items = [{"name": "", "quantity": 1, "unit_price": 0.0, "description": ""}]
                                logger.info("invoice_created_via_ui", invoice_id=invoice_id)
                            else:
                                st.warning(f"⚠️ Invoice created but failed to send. Invoice ID: {invoice_id}")

    with st.expander("View Recent Invoices", expanded=False):
        with st.spinner("Loading invoices..."):
            try:
                token = paypal_client.get_access_token()
                if not token:
                    st.error("❌ PayPal authentication failed.")
                    return
                data = invoice_manager.list_invoices(token, page=1, page_size=10)
                invoices = (data or {}).get("invoices", [])
                if not invoices:
                    st.info("No invoices found.")
                    return
                for inv in invoices:
                    detail = inv.get("detail", {})
                    inv_id = inv.get("id", "Unknown")
                    inv_number = detail.get("invoice_number", "Unknown")
                    status = inv.get("status", "Unknown")
                    amount = detail.get("total_amount", {}).get("value", "0.00")
                    currency = detail.get("total_amount", {}).get("currency_code", "USD")
                    color = {"PAID": "green", "SENT": "orange", "UNPAID": "orange"}.get(status, "gray")
                    st.markdown(
                        f"""
                        <div style="padding:10px;border-left:4px solid {color};margin:5px 0;background:#f8f9fa;">
                            <strong>Invoice #{inv_number}</strong> |
                            Status: <span style="color:{color};font-weight:bold;">{status}</span> |
                            Amount: {amount} {currency} | ID: {inv_id}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            except Exception as exc:
                logger.error("load_invoices_failed", error=str(exc))
                st.error(f"Failed to load invoices: {exc}")

# =============================================================================
# DISPUTES
# =============================================================================

def _render_disputes() -> None:
    st.subheader("⚖️ Dispute Resolution")
    st.markdown("*Manage customer disputes with AI-powered response generation.*")

    with st.spinner("Loading disputes..."):
        try:
            token = paypal_client.get_access_token()
            if not token:
                st.error("❌ PayPal authentication failed.")
                return
            data = dispute_manager.list_disputes(token, page_size=10)
            disputes = (data or {}).get("items", [])
            if not disputes:
                st.success("✅ No active disputes.")
                return
            for dispute in disputes:
                d_id = dispute.get("dispute_id", "Unknown")
                reason = dispute.get("reason", "Unknown")
                status = dispute.get("status", "Unknown")
                amount = dispute.get("dispute_amount", {}).get("value", "0.00")
                currency = dispute.get("dispute_amount", {}).get("currency_code", "USD")
                with st.expander(f"Dispute {d_id} — {reason} ({amount} {currency})"):
                    st.markdown(
                        f"**Dispute ID:** {d_id}  \n"
                        f"**Reason:** {reason}  \n"
                        f"**Status:** {status}  \n"
                        f"**Amount:** {amount} {currency}"
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🤖 Generate AI Response", key=f"gen_{d_id}"):
                            with st.spinner("Generating response..."):
                                st.session_state[f"ai_{d_id}"] = dispute_manager.generate_dispute_response(dispute)
                                logger.info("dispute_response_generated_ui", dispute_id=d_id)
                            st.rerun()
                    with c2:
                        if st.button("✅ Accept Dispute", key=f"acc_{d_id}"):
                            with st.spinner("Accepting dispute..."):
                                if dispute_manager.accept_dispute(token, d_id):
                                    st.success("✅ Dispute accepted.")
                                    logger.info("dispute_accepted_ui", dispute_id=d_id)
                                else:
                                    st.error("❌ Failed to accept dispute.")
                    if f"ai_{d_id}" in st.session_state:
                        st.markdown("**AI-Generated Response:**")
                        st.info(st.session_state[f"ai_{d_id}"])
        except Exception as exc:
            logger.error("load_disputes_failed", error=str(exc))
            st.error(f"Failed to load disputes: {exc}")


if __name__ == "__main__":
    logger.info("streamlit_app_started")
    main()