import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from prompt_ops.database.connection import get_session
from prompt_ops.database.models import (
    TelemetryLog,
    PromptVersion,
    Alert,
    CostRoutingLog,
    EvaluationResult
)
from prompt_ops.telemetry import telemetry_tracker
from prompt_ops.config import settings
from sqlalchemy import select, func

# 1. Page Config
st.set_page_config(page_title="Prompt-Ops | Command Center", layout="wide", page_icon="🚀")

# 2. Premium CSS Injection
def inject_custom_css():
    st.markdown("""
    <style>
        /* Base Theme */
        .stApp {
            background-color: #0E1117;
            color: #E0E6ED;
        }
        
        /* Typography */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        html, body, [class*="css"]  {
            font-family: 'Inter', sans-serif;
        }
        
        /* Headers */
        h1, h2, h3 {
            background: -webkit-linear-gradient(45deg, #00C9FF, #92FE9D);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700 !important;
            margin-bottom: 1.5rem !important;
        }
        
        /* Metric Cards */
        div[data-testid="metric-container"] {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 1.5rem;
            border-radius: 12px;
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        div[data-testid="metric-container"]:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 40px rgba(0, 201, 255, 0.1);
            border: 1px solid rgba(0, 201, 255, 0.3);
        }
        div[data-testid="metric-container"] label {
            color: #A0AEC0 !important;
            font-size: 1rem !important;
            font-weight: 500;
        }
        div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
            color: #FFFFFF !important;
            font-size: 2.2rem !important;
            font-weight: 700;
            margin-top: 0.5rem;
        }
        
        /* Sidebar styling */
        .css-1d391kg, [data-testid="stSidebar"] {
            background-color: #151923 !important;
            border-right: 1px solid rgba(255,255,255,0.05);
        }
        
        /* Dataframes */
        .stDataFrame {
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        /* Alert Cards */
        .alert-card {
            padding: 1.2rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            backdrop-filter: blur(5px);
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        .alert-critical {
            background: rgba(255, 75, 75, 0.1);
            border-left: 4px solid #FF4B4B;
        }
        .alert-warning {
            background: rgba(255, 179, 64, 0.1);
            border-left: 4px solid #FFB340;
        }
        .alert-info {
            background: rgba(0, 201, 255, 0.1);
            border-left: 4px solid #00C9FF;
        }
        .alert-resolved {
            background: rgba(46, 204, 113, 0.05);
            border-left: 4px solid #2ECC71;
            opacity: 0.7;
        }
        
        .alert-title {
            font-weight: 600;
            font-size: 1.1rem;
            color: #fff;
        }
        .alert-meta {
            font-size: 0.85rem;
            color: #8892B0;
        }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# 3. Sidebar Navigation
st.sidebar.markdown("<h1>Prompt-Ops V2</h1>", unsafe_allow_html=True)
page = st.sidebar.radio("", [
    "Overview", 
    "Model Monitoring", 
    "Prompt A/B Testing", 
    "Quality Evaluation", 
    "Cost Routing", 
    "System Alerts", 
    "Configuration"
])

def render_overview():
    st.markdown("## Overview Dashboard")
    stats = telemetry_tracker.get_stats()
    
    # Hero Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Requests", f"{stats.get('total_requests', 0):,}")
    with col2:
        error_rate = (stats.get("failed_requests", 0) / max(1, stats.get("total_requests", 1))) * 100
        st.metric("Error Rate", f"{error_rate:.1f}%")
    with col3:
        avg_latency = stats.get("avg_latency_ms", 0) / 1000.0
        st.metric("Avg Latency", f"{avg_latency:.2f}s")
    with col4:
        total_cost = stats.get("total_cost_usd", 0)
        st.metric("Total Cost", f"${total_cost:.4f}")
        
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Recent Activity Feed")
    with get_session() as session:
        recent_logs = session.execute(
            select(TelemetryLog).order_by(TelemetryLog.timestamp.desc()).limit(15)
        ).scalars().all()
        
        if recent_logs:
            df = pd.DataFrame([{
                "Time": log.timestamp.strftime("%H:%M:%S"),
                "Prompt ID": log.prompt_id,
                "Model": log.model_used or "Unknown",
                "Duration": f"{log.latency_ms / 1000:.2f}s",
                "Tokens": (log.input_tokens or 0) + (log.output_tokens or 0),
                "Status": "✅ Success" if log.success else "❌ Failed",
                "Cost": f"${log.cost_usd:.4f}"
            } for log in recent_logs])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No activity logged yet. Run a prompt-ops request to see data here.")

def render_model_monitoring():
    st.markdown("## LLM Model Intelligence")
    comparison = telemetry_tracker.get_model_comparison()
    
    if not comparison:
        st.info("No model data available.")
        return
        
    # It's a list of dicts.
    df = pd.DataFrame(comparison)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Request Volume
        fig1 = px.bar(df, x="model", y="request_count", 
                     title="Request Volume by Model",
                     color="model", 
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        fig1.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#E0E6ED")
        st.plotly_chart(fig1, use_container_width=True)
        
        # Quality Scores
        fig2 = px.bar(df, x="model", y="avg_quality",
                     title="Average Quality Score (0-1)",
                     color="model",
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#E0E6ED")
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        # Latency
        df["avg_latency_s"] = df["avg_latency_ms"] / 1000.0
        fig3 = px.bar(df, x="model", y="avg_latency_s",
                     title="Average Latency (Seconds)",
                     color="model",
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        fig3.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#E0E6ED")
        st.plotly_chart(fig3, use_container_width=True)
        
        # Cost
        fig4 = px.pie(df, values="total_cost_usd", names="model",
                     title="Spend Distribution",
                     hole=0.4,
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        fig4.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#E0E6ED")
        st.plotly_chart(fig4, use_container_width=True)

def render_ab_testing():
    st.markdown("## Prompt A/B Testing Engine")
    
    with get_session() as session:
        versions = session.execute(
            select(PromptVersion).where(PromptVersion.is_active == True)
        ).scalars().all()
        
        if not versions:
            st.info("No active prompt versions found.")
            return
            
        st.markdown("### Active Prompt Variants")
        data = []
        for v in versions:
            # Average composite score from evaluation results matching this version id
            avg_score = session.execute(
                select(func.avg(EvaluationResult.composite))
                .join(TelemetryLog, EvaluationResult.telemetry_log_id == TelemetryLog.id)
                .where(TelemetryLog.prompt_version == v.version_name, TelemetryLog.prompt_id == v.prompt_id)
            ).scalar()
            
            data.append({
                "Prompt ID": v.prompt_id,
                "Variant Name": v.version_name,
                "Traffic Weight": f"{v.traffic_weight * 100:.0f}%",
                "Executions": v.request_count,
                "Quality Score": f"{avg_score:.2f}" if avg_score else "N/A",
                "Template Preview": v.template[:60] + "..." if len(v.template) > 60 else v.template
            })
            
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

def render_quality_scores():
    st.markdown("## Quality Evaluation Matrices")
    
    with get_session() as session:
        results = session.execute(
            select(EvaluationResult).order_by(EvaluationResult.timestamp.desc()).limit(100)
        ).scalars().all()
        
        if not results:
            st.info("No evaluation results available. Background evaluator may still be running.")
            return
            
        df = pd.DataFrame([{
            "Time": r.timestamp,
            "Composite": r.composite,
            "Relevance": r.relevance,
            "Accuracy": r.accuracy,
            "Completeness": r.completeness,
            "Format": r.format_compliance,
            "Safety": r.safety
        } for r in results])
        
        st.markdown("### Evaluation Trends (Last 100 Calls)")
        
        # Melt dataframe for line chart
        df_melted = df.melt(id_vars=["Time"], value_vars=["Composite", "Relevance", "Accuracy", "Completeness", "Format", "Safety"])
        fig = px.line(df_melted, x="Time", y="value", color="variable",
                     title="Dimension Scores Over Time",
                     color_discrete_sequence=["#00C9FF", "#92FE9D", "#FF9A9E", "#FECFEF", "#A18CD1", "#FBC2EB"])
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#E0E6ED")
        fig.update_yaxes(range=[0, 1.1])
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("### Raw Audit Log")
        st.dataframe(df, use_container_width=True, hide_index=True)

def render_cost_routing():
    st.markdown("## Cascade Cost Routing")
    
    with get_session() as session:
        logs = session.execute(
            select(CostRoutingLog).order_by(CostRoutingLog.timestamp.desc())
        ).scalars().all()
        
        if not logs:
            st.info("No cost routing events recorded yet. Ensure `enable_cost_routing=True` in your decorators.")
            return
            
        total_saved = sum((log.cost_saved_usd or 0) for log in logs)
        
        # Big metric for money saved
        st.markdown(f"""
        <div style="background: linear-gradient(45deg, #11998e, #38ef7d); padding: 2rem; border-radius: 12px; text-align: center; margin-bottom: 2rem;">
            <h3 style="color: white !important; margin: 0; background: none; -webkit-text-fill-color: white;">Total Capital Saved</h3>
            <h1 style="color: white !important; margin: 0; font-size: 3rem; background: none; -webkit-text-fill-color: white;">${total_saved:.4f}</h1>
        </div>
        """, unsafe_allow_html=True)
        
        data = [{
            "Time": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "Target Prompt": log.prompt_id,
            "Requested (Expensive)": log.requested_model,
            "Routed (Cheaper)": log.used_model,
            "Cost Avoided": f"${log.cost_saved_usd:.4f}",
            "Quality Retained": f"{log.quality_score:.2f}"
        } for log in logs]
        
        df = pd.DataFrame(data)
        st.markdown("### Routing Intercept Log")
        st.dataframe(df, use_container_width=True, hide_index=True)

def render_alerts():
    st.markdown("## Active System Alerts")
    
    with get_session() as session:
        alerts = session.execute(
            select(Alert).order_by(Alert.created_at.desc()).limit(50)
        ).scalars().all()
        
        if not alerts:
            st.success("All systems operational. No alerts.")
            return
            
        unresolved = [a for a in alerts if not a.resolved]
        resolved = [a for a in alerts if a.resolved]
        
        if unresolved:
            st.markdown(f"### Needs Attention ({len(unresolved)})")
            for alert in unresolved:
                alert_class = "alert-critical" if alert.severity == "HIGH" else "alert-warning" if alert.severity == "MEDIUM" else "alert-info"
                st.markdown(f"""
                <div class="alert-card {alert_class}">
                    <div class="alert-title">{alert.severity.upper()} — {alert.alert_type.replace('_', ' ').title()}</div>
                    <div style="color: #E0E6ED;">{alert.message}</div>
                    <div class="alert-meta">Triggered: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("No active anomalies!")
            
        if resolved:
            st.markdown("### Previously Handled")
            for alert in resolved[:10]:
                st.markdown(f"""
                <div class="alert-card alert-resolved">
                    <div class="alert-title" style="color: #A0AEC0;">[RESOLVED] {alert.alert_type}</div>
                    <div style="color: #A0AEC0;">{alert.message}</div>
                </div>
                """, unsafe_allow_html=True)

def render_settings():
    st.markdown("## SDK Configuration")
    st.markdown("These values are currently active in your environment memory/config.")
    
    settings_dict = settings.model_dump()
    
    # Hide sensitive values (API keys)
    for key, value in settings_dict.items():
        if "api_key" in key.lower() and value:
            settings_dict[key] = "*" * 8 + str(value)[-4:] if len(str(value)) > 4 else "***"
            
    df = pd.DataFrame([
        {"Parameter": k, "Configured Value": str(v)} 
        for k, v in settings_dict.items()
    ])
    
    st.dataframe(df, use_container_width=True, hide_index=True)

# Route to correct page
if page == "Overview":
    render_overview()
elif page == "Model Monitoring":
    render_model_monitoring()
elif page == "Prompt A/B Testing":
    render_ab_testing()
elif page == "Quality Evaluation":
    render_quality_scores()
elif page == "Cost Routing":
    render_cost_routing()
elif page == "System Alerts":
    render_alerts()
elif page == "Configuration":
    render_settings()
