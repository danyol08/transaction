import os
import hashlib
from datetime import date

import pandas as pd
import streamlit as st
from supabase import create_client, Client
from streamlit_option_menu import option_menu

# --- Hide Streamlit Branding, GitHub, Fork, and Menu ---
hide_st_style = """
    <style>
        #MainMenu {visibility: hidden;}          /* Hamburger menu */
        footer {visibility: hidden;}             /* "Made with Streamlit" */
        header {visibility: hidden;}             /* Streamlit logo/header */
        [data-testid="stToolbar"] {display: none;}  /* GitHub, Fork, etc. */
    </style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)


# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="Salon Transaction System", layout="wide")
st.title("💅 Salon Transaction Management System")

# --- Hide Streamlit Branding, GitHub, Fork, and Menu ---
hide_st_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stAppDeployButton {display: none;}
    .stActionButton {display: none;}
    .stToolbar {display: none;}
    </style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# Read keys from Streamlit secrets (preferred) or environment variables
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL"))
SUPABASE_KEY = st.secrets.get("SUPABASE_ANON_KEY", os.getenv("SUPABASE_ANON_KEY"))

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Missing Supabase keys. Add them in .streamlit/secrets.toml")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# Helpers
# -----------------------------
def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def try_df(rows):
    return pd.DataFrame(rows) if rows else pd.DataFrame()

@st.cache_data(ttl=60)  # mas mataas ang cache para iwas Supabase rate limit
def get_transactions_df() -> pd.DataFrame:
    try:
        res = supabase.table("transactions").select("*").order("date_of_service", desc=True).execute()
        df = try_df(res.data)
        if not df.empty:
            if "amount" in df.columns:
                df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
            if "date_of_service" in df.columns:
                df["date_of_service"] = df["date_of_service"].astype(str)
        return df
    except Exception as e:
        st.error(f"⚠️ Database error: {e}")
        return pd.DataFrame()

def refresh_transactions_cache():
    get_transactions_df.clear()

def login_user(username: str, password: str) -> bool:
    hpw = hash_password(password)
    res = supabase.table("cashiers").select("id,username,active").eq("username", username).eq("password", hpw).eq("active", True).execute()
    return bool(res.data)

def get_cashier_usernames() -> list:
    res = supabase.table("cashiers").select("username").eq("active", True).execute()
    rows = res.data or []
    return [r["username"] for r in rows]

def insert_transaction(payload: dict):
    return supabase.table("transactions").insert(payload).execute()

# -----------------------------
# Session state init & clear inputs handling
# -----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.cashier = None

# Clear input fields after saving
if "clear_inputs" in st.session_state and st.session_state.clear_inputs:
    for key in [
        # Transaction form
        "customer_name", "service_provided", "addons",
        "tech_name", "tech_type", "service_date", "amount",
        # Cashier form
        "new_cashier_username", "new_cashier_password", "new_cashier_fullname"
    ]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.clear_inputs = False

# -----------------------------
# Login
# -----------------------------
if not st.session_state.logged_in:
    st.subheader("🔑 Cashier Login")
    col1, col2 = st.columns([1,1])
    with col1:
        username = st.text_input("Username", key="login_username")
    with col2:
        password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login", use_container_width=True, key="login_btn"):
        if login_user(username, password):
            st.session_state.logged_in = True
            st.session_state.cashier = username
            st.success(f"Welcome, {username}!")
            st.rerun()
        else:
            st.error("Invalid username/password or inactive account.")
    st.stop()

# -----------------------------
# Main App
# -----------------------------
with st.sidebar:
    st.success(f"Logged in as: {st.session_state.cashier}")
    menu = option_menu(
        "📋 Menu",
        ["Add Transaction", "View Transactions", "Search Customer", "Reports & CSV", "Logout"] + (["Cashier Management"] if st.session_state.cashier == "admin" else []),
        icons=["plus", "table", "search", "file-earmark-text", "box-arrow-right"] + (["people"] if st.session_state.cashier == "admin" else []),
        menu_icon="list",
        default_index=0,
    )

# (--- rest of your existing code here, unchanged ---)
