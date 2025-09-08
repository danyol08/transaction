import os
import hashlib
from datetime import date

import pandas as pd
import streamlit as st
from supabase import create_client, Client
from streamlit_option_menu import option_menu

# -----------------------------
# Streamlit Config & Branding
# -----------------------------
st.set_page_config(page_title="Salon Transaction System", layout="wide")
st.title("💅 Salon Transaction Management System")

# Hide Streamlit branding and menus
hide_st_style = """
    <style>
        #MainMenu, footer, header {visibility: hidden;}
        .stAppDeployButton, .stActionButton, .stToolbar {display: none;}
        [data-testid="stToolbar"] {display: none;}
    </style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# -----------------------------
# Supabase Configuration
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
# Session State Initialization
# -----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.cashier = None

# Clear inputs if flag is set
if "clear_inputs" in st.session_state and st.session_state.clear_inputs:
    for key in [
        "customer_name", "service_provided", "addons",
        "tech_name", "tech_type", "service_date", "amount",
        "new_cashier_username", "new_cashier_password", "new_cashier_fullname"
    ]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.clear_inputs = False

# -----------------------------
# Login Page
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
# Sidebar Menu
# -----------------------------
with st.sidebar:
    st.success(f"Logged in as: {st.session_state.cashier}")
    menu = option_menu(
        "📋 Menu",
        ["Add Transaction", "View Transactions", "Search Customer", "Reports & CSV", "Logout"] +
        (["Cashier Management"] if st.session_state.cashier == "admin" else []),
        icons=["plus", "table", "search", "file-earmark-text", "box-arrow-right"] +
        (["people"] if st.session_state.cashier == "admin" else []),
        menu_icon="list",
        default_index=0,
    )

# -----------------------------
# Page: Add Transaction
# -----------------------------
if menu == "Add Transaction":
    st.subheader("➕ Add New Transaction")

    with st.form("txn_form", clear_on_submit=True):
        c1, c2 = st.columns([2,1])
        with c1:
            customer = st.text_input("Customer Name *")
            service = st.text_input("Service Provided *", placeholder="e.g., Gel Manicure, Classic Lashes")
            addons = st.text_area("Add-ons (optional)", placeholder="e.g., Nail art, Extra volume")
        with c2:
            technician_name = st.text_input("Technician Name *")
            technician_type = st.selectbox("Technician Type *", ["Nails", "Lashes", "Other"])
            service_date = st.date_input("Date of Service *", value=date.today())
            amount = st.number_input("Amount (₱) *", min_value=0.0, step=50.0, format="%.2f")

        submitted = st.form_submit_button("💾 Save Transaction")

    if submitted:
        if customer and service and technician_name and technician_type and amount > 0:
            payload = {
                "customer_name": customer.strip(),
                "service": service.strip(),
                "technician_name": technician_name.strip(),
                "technician_type": technician_type,
                "addons": addons.strip() if addons else None,
                "date_of_service": str(service_date),
                "amount": float(amount),
                "cashier_username": st.session_state.cashier,
            }
            try:
                insert_transaction(payload)
                refresh_transactions_cache()
                st.success("✅ Transaction saved!")
            except Exception as e:
                st.error(f"Error saving transaction: {e}")
        else:
            st.warning("Please complete all required fields (*) and amount > 0.")

# -----------------------------
# Page: View Transactions
# -----------------------------
elif menu == "View Transactions":
    st.subheader("📊 All Transactions")
    df = get_transactions_df()
    if df.empty:
        st.info("No transactions yet.")
    else:
        st.dataframe(df, use_container_width=True, height=460)
        st.caption("Tip: Use the ‘Reports & CSV’ tab to filter by date/cashier and download CSV.")

# -----------------------------
# Page: Search Customer
# -----------------------------
elif menu == "Search Customer":
    st.subheader("🔍 Search Customer Records")
    df = get_transactions_df()
    if df.empty:
        st.info("No transactions yet.")
    else:
        name_query = st.text_input("Enter customer name (full or partial):", key="search_customer")
        if name_query:
            results = df[df["customer_name"].str.contains(name_query, case=False, na=False)]
            if results.empty:
                st.warning("No records found.")
            else:
                st.write(f"Found **{len(results)}** record(s) for “{name_query}”:")
                st.dataframe(results, use_container_width=True, height=420)
                total_spent = results["amount"].sum()
                st.success(f"💰 Total spent by {name_query}: ₱{total_spent:,.2f}")

# -----------------------------
# Page: Reports & CSV Export
# -----------------------------
elif menu == "Reports & CSV":
    st.subheader("🧾 Daily Totals, Filters & CSV Export")
    df = get_transactions_df()
    if df.empty:
        st.info("No transactions available.")
    else:
        left, right = st.columns([1,1])
        with left:
            report_date = st.date_input("Select date", value=date.today(), key="report_date")
        with right:
            cashier_options = ["(Current Cashier Only)", "All Cashiers"] + get_cashier_usernames()
           cashier_choice = st.selectbox("Cashier filter", options=cashier_options, index=0, key="cashier_filter")

