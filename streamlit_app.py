import os
import hashlib
from datetime import date

import pandas as pd
import streamlit as st
import plotly.express as px
from supabase import create_client, Client
from streamlit_option_menu import option_menu

# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="Salon Transaction System", layout="wide")
st.title("Transaction Management System")

# --- Custom Pink Theme ---
pink_style = """
    <style>
        /* Hide Streamlit Branding */
        #MainMenu, footer, header, [data-testid="stToolbar"] {visibility: hidden;}

        /* Background & text */
        body, .main {
            background-color: #fff5f8;
            color: #4a0033;
        }

        /* Buttons */
        button[kind="primary"] {
            background-color: #ff5ca2 !important;
            color: white !important;
            border-radius: 8px !important;
        }

        /* Subheaders */
        h2, h3, h4 {
            color: #d63384 !important;
        }

        /* KPI Cards */
        .kpi-card {
            background-color: #ffe6f0;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0px 2px 6px rgba(0,0,0,0.1);
        }
    </style>
"""
st.markdown(pink_style, unsafe_allow_html=True)

# -----------------------------
# Supabase Config
# -----------------------------
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

@st.cache_data(ttl=60)
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
# Session State Init
# -----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.cashier = None

# -----------------------------
# Login Screen
# -----------------------------
if not st.session_state.logged_in:
    st.subheader("🔑 Cashier Login")
    col1, col2 = st.columns([1, 1])
    with col1:
        username = st.text_input("👤 Username", key="login_username")
    with col2:
        password = st.text_input("🔒 Password", type="password", key="login_password")

    if st.button("➡️ Login", use_container_width=True, key="login_btn"):
        if login_user(username, password):
            st.session_state.logged_in = True
            st.session_state.cashier = username
            st.success(f"Welcome, {username}! 💖")
            st.rerun()
        else:
            st.error("❌ Invalid username/password or inactive account.")
    st.stop()

# -----------------------------
# Top Menu Bar (Pink Navbar)
# -----------------------------
menu = option_menu(
    "📋 Salon Menu",
    ["Add Transaction", "View Transactions", "Search Customer", "Reports & CSV", "Logout"]
    + (["Cashier Management"] if st.session_state.cashier == "admin" else []),
    icons=["plus", "table", "search", "bar-chart", "box-arrow-right"]
    + (["people"] if st.session_state.cashier == "admin" else []),
    menu_icon="cast",
    default_index=0,
    orientation="horizontal"
)

st.markdown(f"✅ Logged in as: **{st.session_state.cashier}**")

# -----------------------------
# Add Transaction (Improved UX)
# -----------------------------
if menu == "Add Transaction":
    st.subheader("➕ Add New Transaction")

    with st.form("txn_form", clear_on_submit=True):
        c1, c2 = st.columns([2, 1])
        with c1:
            customer = st.text_input("👤 Customer Name *", placeholder="Enter customer name")
            service = st.text_input("💅 Service Provided *", placeholder="E.g., Gel Manicure")
            addons = st.text_area("✨ Add-ons (optional)", placeholder="E.g., Nail art, extra lashes")
        with c2:
            technician_name = st.text_input("🧑‍🎨 Technician Name *", placeholder="Enter technician name")
            technician_type = st.radio("Technician Type *", ["Nails 💅", "Lashes 👁", "Others"], horizontal=True)
            service_date = st.date_input("📅 Date of Service *", value=date.today())
            amount = st.number_input("💰 Amount (₱) *", min_value=0.0, step=50.0, format="%.2f")

        submitted = st.form_submit_button("💾 Save Transaction", type="primary")
        if submitted:
            if customer and service and technician_name and amount > 0:
                payload = {
                    "customer_name": customer.strip(),
                    "service": service.strip(),
                    "technician_name": technician_name.strip(),
                    "technician_type": technician_type.split()[0],  # get text only
                    "addons": addons.strip() if addons else None,
                    "date_of_service": str(service_date),
                    "amount": float(amount),
                    "cashier_username": st.session_state.cashier,
                }
                try:
                    insert_transaction(payload)
                    refresh_transactions_cache()
                    st.success("✅ Transaction saved successfully!")
                   # st.balloons()
                except Exception as e:
                    st.error(f"⚠️ Error saving transaction: {e}")
            else:
                st.warning("⚠️ Please complete all required fields and amount > 0.")

# -----------------------------
# View Transactions
# -----------------------------
elif menu == "View Transactions":
    st.subheader("📊 All Transactions")
    df = get_transactions_df()
    if df.empty:
        st.info("No transactions yet.")
    else:
        st.dataframe(df, use_container_width=True, height=460)

# -----------------------------
# Search Customer
# -----------------------------
elif menu == "Search Customer":
    st.subheader("🔍 Search Customer Records")
    df = get_transactions_df()
    if df.empty:
        st.info("No transactions yet.")
    else:
        name_query = st.text_input("Enter customer name (full or partial):")
        if name_query:
            results = df[df["customer_name"].str.contains(name_query, case=False, na=False)]
            if results.empty:
                st.warning("No records found.")
            else:
                st.write(f"Found **{len(results)}** record(s):")
                st.dataframe(results, use_container_width=True, height=420)
                total_spent = results["amount"].sum()
                st.success(f"💰 Total spent: ₱{total_spent:,.2f}")

# -----------------------------
# Reports & CSV with KPIs + Charts
# -----------------------------
elif menu == "Reports & CSV":
    st.subheader("📈 Reports & CSV Export")
    df = get_transactions_df()
    if df.empty:
        st.info("No transactions available.")
    else:
        # KPI cards
        c1, c2, c3 = st.columns(3)
        today = str(date.today())
        today_df = df[df["date_of_service"] == today]
        with c1:
            st.markdown(f"<div class='kpi-card'>💰 <br> Today's Sales<br><b>₱{today_df['amount'].sum():,.2f}</b></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='kpi-card'>🧾 <br> Transactions<br><b>{len(today_df)}</b></div>", unsafe_allow_html=True)
        with c3:
            if not today_df.empty:
                top_tech = today_df.groupby("technician_name")["amount"].sum().idxmax()
                st.markdown(f"<div class='kpi-card'>👑 <br> Top Tech<br><b>{top_tech}</b></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='kpi-card'>👑 <br> Top Tech<br><b>None</b></div>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📊 Sales by Technician")
        fig1 = px.bar(df, x="technician_name", y="amount", color="technician_type", title="Sales by Technician")
        st.plotly_chart(fig1, use_container_width=True)

        st.markdown("### 📈 Daily Sales Trend")
        fig2 = px.line(df, x="date_of_service", y="amount", color="cashier_username", title="Daily Sales Trend")
        st.plotly_chart(fig2, use_container_width=True)

        # CSV export
        st.markdown("### ⬇️ Export Data")
        csv_all = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download ALL Transactions (CSV)", csv_all, "transactions_full.csv", "text/csv")

# -----------------------------
# Logout
# -----------------------------
elif menu == "Logout":
    st.session_state.logged_in = False
    st.session_state.cashier = None
    st.success("Logged out. See you next time! 👋")
    st.rerun()
