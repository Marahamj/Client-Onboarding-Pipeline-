import os
import requests
import streamlit as st
API_URL = os.getenv("API_URL","http://localhost:8000")
ICONS = {
    "completed": "✅",
    "running": "⏳",
    "pending": "⚪",
    "failed": "❌",
}
st.set_page_config(page_title="Onboarding Dashboard", layout="wide")
st.title("Client Onboarding Dashboard")

if st.button("Refresh"):
    st.rerun()
try:
     onboardings = requests.get(f"{API_URL}/onboardings", timeout=10).json()
     dlq = requests.get(f"{API_URL}/dlq", timeout=10).json()
except requests.RequestException as error:
    st.error(f"Cannot reach the API: {error}")
    st.stop()
st.subheader("Onboardings")


for o in onboardings:
    title= f"#{o['id']} | {o['crm_deal_id']} | {o['status']}"
    with st.expander(title):
        columns =  st.columns(len(o["steps"]))
        for column, step in zip(columns,o["steps"]):
           icon = ICONS.get(step["status"], "❔")
           column.markdown(
                f"{icon}\n\n**{step['step_name']}**\n\n{step['status']}"
            )
        if o["status"] != "completed":
            if st.button("Run / Retry ", key=f"run-{o['id']}"):
                response = requests.post(f"{API_URL}/onboardings/{o['id']}/run", timeout=60)
                st.json(response.json())
                
st.subheader("Dead Letter Queue")

if dlq:
    st.dataframe(dlq, use_container_width=True)
else:
    st.success("No failed steps")
        