import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy.orm import Session
from prompt_ops.database.connection import get_session
from prompt_ops.database.models import TelemetryLog, PromptVersion, EvaluationResult, CostRoutingLog, Alert

st.set_page_config(page_title="PROMPT-OPS Dashboard", layout="wide")

def load_data():
    with get_session() as session:
        logs = pd.read_sql(session.query(TelemetryLog).statement, session.bind)
        versions = pd.read_sql(session.query(PromptVersion).statement, session.bind)
        evals = pd.read_sql(session.query(EvaluationResult).statement, session.bind)
        routing = pd.read_sql(session.query(CostRoutingLog).statement, session.bind)
        alerts = pd.read_sql(session.query(Alert).statement, session.bind)
    return logs, versions, evals, routing, alerts

logs, versions, evals, routing, alerts = load_data()

st.sidebar.title("PROMPT-OPS")
page = st.sidebar.radio("Navigation", [
    "Overview", 
    "Model Monitoring", 
    "Prompt A/B", 
    "Quality Scores", 
    "Temperature", 
    "Cost Routing", 
    "Alerts", 
    "Settings"
])

if page == "Overview":
    st.title("Overview")
    if not logs.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Requests", len(logs))
        col2.metric("Avg Quality", f"{logs['quality_score'].mean():.2f}")
        col3.metric("Active Prompts", versions['prompt_id'].nunique())
        col4.metric("Total Cost", f"${logs['cost_usd'].sum():.4f}")
    else:
        st.info("No data yet.")

elif page == "Model Monitoring":
    st.title("Model Monitoring")
    if not logs.empty:
        st.subheader("Latency over time")
        fig = px.line(logs, x="timestamp", y="latency_ms", color="model_used")
        st.plotly_chart(fig)
        
        st.subheader("Requests by Model")
        fig2 = px.pie(logs, names="model_used")
        st.plotly_chart(fig2)

elif page == "Prompt A/B":
    st.title("Prompt A/B Testing")
    if not versions.empty:
        st.dataframe(versions)
        fig = px.bar(versions, x="version_name", y="avg_quality_score", color="prompt_id")
        st.plotly_chart(fig)

elif page == "Quality Scores":
    st.title("Quality Scores")
    if not evals.empty:
        fig = px.histogram(evals, x="composite")
        st.plotly_chart(fig)
        # Simplified radar chart replacement
        avg_scores = evals[["relevance", "accuracy", "completeness", "format_compliance", "safety"]].mean().reset_index()
        avg_scores.columns = ["Dimension", "Score"]
        fig2 = px.bar(avg_scores, x="Dimension", y="Score")
        st.plotly_chart(fig2)

elif page == "Temperature":
    st.title("Temperature Optimization")
    st.info("Temperature sweeps data visualization here.")

elif page == "Cost Routing":
    st.title("Cost Routing")
    if not routing.empty:
        st.metric("Total Saved", f"${routing['cost_saved_usd'].sum():.4f}")
        fig = px.pie(routing, names="tier_used")
        st.plotly_chart(fig)
        st.dataframe(routing)

elif page == "Alerts":
    st.title("Alerts")
    st.dataframe(alerts)

elif page == "Settings":
    st.title("Settings")
    from prompt_ops.config import settings
    st.json(settings.model_dump())
