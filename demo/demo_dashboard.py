"""
PayFlow AI - Streamlit Dashboard Demo
======================================

A complete interactive dashboard showcasing all platform capabilities
using synthetic data. Looks identical to the production app but runs
entirely offline with no external dependencies.

Features:
- Full interactive UI with all platform features
- Real-time AI categorization
- Interactive charts and visualizations
- Risk management dashboard
- Invoice and dispute management
- Search and filtering

Usage:
    streamlit run demo_dashboard.py

Version: 1.0.0
"""

import sys
import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo.synthetic_data_generator import generate_demo_data

# Page configuration
st.set_page_config(
    page_title="PayFlow AI Demo",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header { 
        font-size: 2.5rem; 
        font-weight: 700; 
        color: #003087; 
        margin-bottom: 0.5rem;
    }
    .sub-header { 
        font-size: 1.2rem; 
        color: #666; 
        margin-bottom: 2rem; 
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        border-left: 4px solid #003087;
    }
    </style>
""", unsafe_allow_html=True)


# Initialize session state
if 'data' not in st.session_state:
    st.session_state.data = None
if 'categorized_df' not in st.session_state:
    st.session_state.categorized_df = None


def load_demo_data():
    """Load synthetic demo data."""
    with st.spinner("Generating synthetic financial data..."):
        data = generate_demo_data(
            transactions=100,
            invoices=5,
            disputes=3
        )
        st.session_state.data = data
    return data


def categorize_transactions(transactions_df):
    """Categorize transactions with mock AI."""
    with st.spinner("Categorizing transactions with AI..."):
        # Mock categorization
        categorized = transactions_df.copy()
        
        # Assign categories based on description keywords
        def assign_category(desc):
            desc_lower = desc.lower()
            if any(word in desc_lower for word in ['freelance', 'consulting', 'payment from', 'project']):
                return 'Freelance Income', 0.92
            elif any(word in desc_lower for word in ['subscription', 'adobe', 'github', 'aws', 'slack']):
                return 'Software Subscription', 0.88
            elif any(word in desc_lower for word in ['suspicious', 'wire transfer', 'offshore', 'urgent']):
                return 'Suspicious Activity', 0.65
            else:
                return 'Personal Expense', 0.75
        
        categorized['AI Category'] = categorized['description'].apply(lambda x: assign_category(x)[0])
        categorized['Confidence'] = categorized['description'].apply(lambda x: assign_category(x)[1])
        
        st.session_state.categorized_df = categorized
        return categorized


def main():
    """Main dashboard."""
    # Header
    st.markdown('<p class="main-header">💸 PayFlow AI - Demo Dashboard</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Complete Platform Showcase with Synthetic Data</p>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Demo Controls")
        
        if st.button("🔄 Regenerate Data", use_container_width=True):
            st.session_state.data = None
            st.session_state.categorized_df = None
            st.rerun()
        
        st.divider()
        st.markdown("### About This Demo")
        st.markdown("""
        This dashboard demonstrates all PayFlow AI capabilities using synthetic data.
        
        **Features:**
        - AI transaction categorization
        - Cash flow forecasting
        - Anomaly detection
        - Risk management
        - Invoice management
        - Dispute resolution
        
        **No external APIs required!**
        """)
    
    # Load data if not already loaded
    if st.session_state.data is None:
        data = load_demo_data()
    else:
        data = st.session_state.data
    
    transactions_df = data['transactions']
    invoices = data['invoices']
    disputes = data['disputes']
    
    # Categorize if not already done
    if st.session_state.categorized_df is None:
        categorized_df = categorize_transactions(transactions_df)
    else:
        categorized_df = st.session_state.categorized_df
    
    # Main content
    st.divider()
    
    # Section 1: AI Categorization
    st.header("🧠 AI Transaction Categorization")
    
    col1, col2, col3, col4 = st.columns(4)
    
    for idx, category in enumerate(['Freelance Income', 'Software Subscription', 'Personal Expense', 'Suspicious Activity']):
        cat_data = categorized_df[categorized_df['AI Category'] == category]
        col = [col1, col2, col3, col4][idx]
        
        with col:
            st.metric(
                label=category,
                value=len(cat_data),
                delta=f"{len(cat_data)/len(categorized_df):.1%}"
            )
    
    st.divider()
    
    # Transaction table
    st.subheader("Transaction Ledger")
    
    # Search filter
    search_query = st.text_input("🔍 Search transactions...", placeholder="Type to filter...")
    
    if search_query:
        display_df = categorized_df[
            categorized_df['description'].str.contains(search_query, case=False) |
            categorized_df['AI Category'].str.contains(search_query, case=False)
        ]
    else:
        display_df = categorized_df
    
    # Display table
    st.dataframe(
        display_df[['timestamp', 'description', 'amount', 'AI Category', 'Confidence']],
        use_container_width=True,
        hide_index=True,
        column_config={
            "timestamp": st.column_config.DatetimeColumn("Date"),
            "description": st.column_config.TextColumn("Description"),
            "amount": st.column_config.TextColumn("Amount"),
            "AI Category": st.column_config.TextColumn("AI Category"),
            "Confidence": st.column_config.ProgressColumn(
                "Confidence",
                min_value=0,
                max_value=1,
                format="%.1f%%"
            )
        }
    )
    
    st.divider()
    
    # Section 2: Cash Flow Forecasting
    st.header("📈 Cash Flow Forecasting")
    
    # Mock forecast data
    dates = pd.date_range(start=datetime.now(), periods=30, freq='D')
    predictions = np.random.normal(500, 200, 30)
    upper_bound = predictions + 150
    lower_bound = predictions - 150
    
    # Forecast chart
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=upper_bound,
        mode='lines',
        line=dict(width=0),
        showlegend=False,
        hoverinfo='skip'
    ))
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=lower_bound,
        mode='lines',
        line=dict(width=0),
        fill='tonexty',
        fillcolor='rgba(68, 68, 255, 0.2)',
        showlegend=False,
        hoverinfo='skip'
    ))
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=predictions,
        mode='lines',
        line=dict(color='#003087', width=3),
        name='Predicted Cash Flow'
    ))
    
    fig.update_layout(
        title="30-Day Cash Flow Forecast with Confidence Intervals",
        xaxis_title="Date",
        yaxis_title="Net Cash Flow ($)",
        hovermode='x unified',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Forecast metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Predicted", f"${sum(predictions):,.2f}")
    
    with col2:
        best_day_idx = np.argmax(predictions)
        st.metric("Best Day", f"${predictions[best_day_idx]:,.2f}", dates[best_day_idx].strftime('%Y-%m-%d'))
    
    with col3:
        worst_day_idx = np.argmin(predictions)
        st.metric("Worst Day", f"${predictions[worst_day_idx]:,.2f}", dates[worst_day_idx].strftime('%Y-%m-%d'))
    
    st.divider()
    
    # Section 3: Anomaly Detection
    st.header("🚨 Anomaly Detection")
    
    # Mock anomaly detection
    anomaly_df = categorized_df.copy()
    anomaly_df['is_anomaly'] = (
        (anomaly_df['Confidence'] < 0.7) | 
        (anomaly_df['amount_value'] > anomaly_df['amount_value'].quantile(0.9))
    )
    
    anomalies = anomaly_df[anomaly_df['is_anomaly']]
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Transactions", len(anomaly_df))
    
    with col2:
        st.metric("Anomalies Detected", len(anomalies), delta=f"-{len(anomalies)}", delta_color="inverse")
    
    with col3:
        st.metric("Anomaly Rate", f"{len(anomalies)/len(anomaly_df):.1%}")
    
    if len(anomalies) > 0:
        st.warning(f"⚠️ Found {len(anomalies)} potentially suspicious transactions:")
        
        st.dataframe(
            anomalies[['description', 'amount', 'AI Category', 'Confidence']].head(10),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("✅ No anomalies detected!")
    
    st.divider()
    
    # Section 4: Risk Management
    st.header("🛡️ Risk Management Dashboard")
    
    # Calculate risk scores
    risk_df = categorized_df.copy()
    avg_amount = risk_df['amount_value'].mean()
    
    risk_df['risk_score'] = risk_df.apply(
        lambda row: min(100, (
            ((row['Confidence'] < 0.7) * 50) +
            ((1 - row['Confidence']) * 30) +
            (min(1, row['amount_value'] / (avg_amount * 5)) * 20)
        )),
        axis=1
    )
    
    # Portfolio risk gauge
    portfolio_score = risk_df['risk_score'].quantile(0.75)
    
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=portfolio_score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"Portfolio Risk Score<br><span style='font-size:0.8em'>75th Percentile</span>"},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 39], 'color': '#d4edda'},
                {'range': [40, 59], 'color': '#fff3cd'},
                {'range': [60, 79], 'color': '#ffe5d0'},
                {'range': [80, 100], 'color': '#f8d7da'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 80
            }
        }
    ))
    
    fig_gauge.update_layout(height=300)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.plotly_chart(fig_gauge, use_container_width=True)
    
    with col2:
        # Risk distribution
        low = len(risk_df[risk_df['risk_score'] < 40])
        medium = len(risk_df[(risk_df['risk_score'] >= 40) & (risk_df['risk_score'] < 60)])
        high = len(risk_df[(risk_df['risk_score'] >= 60) & (risk_df['risk_score'] < 80)])
        critical = len(risk_df[risk_df['risk_score'] >= 80])
        
        st.markdown("#### Risk Distribution")
        
        dist_col1, dist_col2, dist_col3, dist_col4 = st.columns(4)
        
        with dist_col1:
            st.metric("🟢 LOW", low)
        with dist_col2:
            st.metric("🟡 MEDIUM", medium)
        with dist_col3:
            st.metric("🟠 HIGH", high)
        with dist_col4:
            st.metric("🔴 CRITICAL", critical)
    
    # High-risk transactions
    high_risk = risk_df[risk_df['risk_score'] >= 60]
    
    if len(high_risk) > 0:
        st.subheader("⚠️ High-Risk Transactions")
        
        st.dataframe(
            high_risk[['description', 'amount', 'AI Category', 'risk_score']].head(10),
            use_container_width=True,
            hide_index=True,
            column_config={
                "risk_score": st.column_config.ProgressColumn(
                    "Risk Score",
                    min_value=0,
                    max_value=100,
                    format="%.1f"
                )
            }
        )
    
    st.divider()
    
    # Section 5: Invoice Management
    st.header("📄 Invoice Management")
    
    st.dataframe(
        pd.DataFrame(invoices)[['invoice_number', 'client_name', 'amount', 'status']],
        use_container_width=True,
        hide_index=True,
        column_config={
            "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
        }
    )
    
    st.divider()
    
    # Section 6: Dispute Resolution
    st.header("⚖️ Dispute Resolution")
    
    st.dataframe(
        pd.DataFrame(disputes)[['dispute_id', 'reason', 'amount', 'status']],
        use_container_width=True,
        hide_index=True,
        column_config={
            "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
        }
    )
    
    # Footer
    st.divider()
    st.markdown("""
    **Built with:** Synthetic Data Generator • AI Categorization • Cash Flow Forecasting • 
    Anomaly Detection • Risk Management • Streamlit
    
    © 2026 PayFlow AI - Demo Dashboard
    """)


if __name__ == "__main__":
    main()