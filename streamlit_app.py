import os
import hashlib
from datetime import date

import pandas as pd
import streamlit as st
from supabase import create_client, Client
from streamlit_option_menu import option_menu

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
        [data-testid="stToolbar"] {display: none;}
    </style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

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
# Login
# -----------------------------
if not st.session_state.logged_in:
    st.subheader("🔑 Cashier Login")
    col1, col2 = st.columns([1, 1])
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
# Top Menu Bar (Horizontal)
# -----------------------------
menu = option_menu(
    "📋 Salon Menu",
    ["Add Transaction", "View Transactions", "Search Customer", "Reports & CSV", "Logout"]
    + (["Cashier Management"] if st.session_state.cashier == "admin" else []),
    icons=["plus", "table", "search", "file-earmark-text", "box-arrow-right"]
    + (["people"] if st.session_state.cashier == "admin" else []),
    menu_icon="cast",
    default_index=0,
    orientation="horizontal"
)

st.markdown(f"✅ Logged in as: **{st.session_state.cashier}**")

# -----------------------------
# Add Transaction
# -----------------------------
if menu == "Add Transaction":
    st.subheader("➕ Add New Transaction")

    # ✅ Show success message if present
    if st.session_state.get("txn_success"):
        st.success(st.session_state.txn_success)
        st.session_state.txn_success = None  # clear after showing once

    # ✅ Check if we should reset defaults
    if st.session_state.get("reset_txn", False):
        default_customer = ""
        default_service = ""
        default_addons = ""
        default_tech_name = ""
        default_tech_type = "Nails"
        default_service_date = date.today()
        default_amount = 0.0
        st.session_state.reset_txn = False
    else:
        default_customer = st.session_state.get("customer_name", "")
        default_service = st.session_state.get("service_provided", "")
        default_addons = st.session_state.get("addons", "")
        default_tech_name = st.session_state.get("tech_name", "")
        default_tech_type = st.session_state.get("tech_type", "Nails")
        default_service_date = st.session_state.get("service_date", date.today())
        default_amount = st.session_state.get("amount", 0.0)

    c1, c2 = st.columns([2, 1])
    with c1:
        customer = st.text_input("Customer Name *", value=default_customer, key="customer_name")
        service = st.text_input("Service Provided *", value=default_service, key="service_provided")
        addons = st.text_area("Add-ons (optional)", value=default_addons, key="addons")
    with c2:
        technician_name = st.text_input("Technician Name *", value=default_tech_name, key="tech_name")
        technician_type = st.selectbox("Technician Type *", ["Nails", "Lashes", "Other"], 
                                       index=["Nails", "Lashes", "Other"].index(default_tech_type), 
                                       key="tech_type")
        service_date = st.date_input("Date of Service *", value=default_service_date, key="service_date")
        amount = st.number_input("Amount (₱) *", min_value=0.0, step=50.0, format="%.2f", value=default_amount, key="amount")

    if st.button("💾 Save Transaction", type="primary", key="save_txn_btn"):
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

                # ✅ Save success message in session_state
                st.session_state.txn_success = "✅ Transaction saved!"

                # ✅ Clear next render
                st.session_state.reset_txn = True
                st.rerun()

            except Exception as e:
                st.error(f"Error saving transaction: {e}")
        else:
            st.warning("Please complete all required fields (*) and amount > 0.")

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
        st.caption("Tip: Use the ‘Reports & CSV’ tab to filter by date/cashier and download CSV.")

# -----------------------------
# Search Customer
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
# Reports & CSV
# -----------------------------
elif menu == "Reports & CSV":
    st.subheader("🧾 Daily Totals, Filters & CSV Export")
    df = get_transactions_df()
    if df.empty:
        st.info("No transactions available.")
    else:
        left, right = st.columns([1, 1])
        with left:
            report_date = st.date_input("Select date", value=date.today(), key="report_date")
        with right:
            cashier_options = ["(Current Cashier Only)", "All Cashiers"] + get_cashier_usernames()
            cashier_choice = st.selectbox("Cashier filter", options=cashier_options, index=0, key="cashier_filter")

        filtered = df[df["date_of_service"] == str(report_date)]

        if cashier_choice == "(Current Cashier Only)":
            filtered = filtered[filtered["cashier_username"] == st.session_state.cashier]
        elif cashier_choice not in ["(Current Cashier Only)", "All Cashiers"]:
            filtered = filtered[filtered["cashier_username"] == cashier_choice]

        st.markdown("### 📅 Daily Transactions")
        if filtered.empty:
            st.info("No transactions for selected filters.")
        else:
            st.dataframe(filtered, use_container_width=True, height=360)
            total_sales = filtered["amount"].sum()
            who = cashier_choice if cashier_choice not in ["(Current Cashier Only)", "All Cashiers"] else (
                st.session_state.cashier if cashier_choice == "(Current Cashier Only)" else "ALL cashiers"
            )
            st.success(f"💰 Total sales for {report_date} ({who}): ₱{total_sales:,.2f}")

            csv_daily = filtered.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download CSV (Daily Report)",
                csv_daily,
                file_name=f"transactions_{report_date}_{who}.csv",
                mime="text/csv",
                key="download_daily"
            )

        st.markdown("---")
        st.markdown("### 📦 Full Export")
        csv_all = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download ALL Transactions (CSV)",
            csv_all,
            file_name="transactions_full.csv",
            mime="text/csv",
            key="download_all"
        )

# -----------------------------
# Cashier Management
# -----------------------------
elif menu == "Cashier Management":
    if st.session_state.cashier != "admin":
        st.error("❌ Only admin can manage cashiers.")
    else:
        st.subheader("👥 Cashier Management")

        tab1, tab2 = st.tabs(["➕ Add Cashier", "📋 Cashier List"])

        # TAB 1: Add Cashier
        with tab1:
            st.subheader("➕ Add New Cashier")

            if st.session_state.get("cashier_success"):
                st.success(st.session_state.cashier_success)
                st.session_state.cashier_success = None

            if st.session_state.get("reset_cashier", False):
                default_username = ""
                default_password = ""
                default_fullname = ""
                st.session_state.pop("new_cashier_username", None)
                st.session_state.pop("new_cashier_password", None)
                st.session_state.pop("new_cashier_fullname", None)
                st.session_state.reset_cashier = False
            else:
                default_username = st.session_state.get("new_cashier_username", "")
                default_password = st.session_state.get("new_cashier_password", "")
                default_fullname = st.session_state.get("new_cashier_fullname", "")

            new_username = st.text_input("New Cashier Username *", value=default_username, key="new_cashier_username")
            new_password = st.text_input("New Cashier Password *", type="password", value=default_password, key="new_cashier_password")
            full_name = st.text_input("Full Name", value=default_fullname, key="new_cashier_fullname")

            if st.button("💾 Save Cashier", type="primary", key="save_cashier_btn"):
                if new_username and new_password:
                    hashed_pw = hash_password(new_password)
                    try:
                        supabase.table("cashiers").insert({
                            "username": new_username.strip(),
                            "password": hashed_pw,
                            "full_name": full_name.strip() if full_name else None,
                            "active": True
                        }).execute()

                        st.session_state.cashier_success = f"✅ Cashier '{new_username}' added successfully!"
                        st.session_state.reset_cashier = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Error adding cashier: {e}")
                else:
                    st.warning("Please fill in username and password.")

        # TAB 2: Cashier List
        with tab2:
            st.subheader("📋 Cashier List")
            try:
                cashiers = supabase.table("cashiers").select("id, username, full_name, active").execute().data
                if cashiers:
                    df = pd.DataFrame(cashiers)
                    st.dataframe(df, use_container_width=True)

                    if st.session_state.get("pass_success"):
                        st.success(st.session_state.pass_success)
                        st.session_state.pass_success = None

                    selected_user = st.selectbox("Select cashier to change password:", [c["username"] for c in cashiers])
                    new_pass = st.text_input("Enter new password", type="password", key="reset_pass_input")

                    if st.button("🔑 Update Password", type="primary", key="reset_pass_btn"):
                        if not new_pass:
                            st.warning("⚠️ Please enter a new password.")
                        else:
                            try:
                                hashed_pw = hash_password(new_pass)
                                supabase.table("cashiers").update({
                                    "password": hashed_pw
                                }).eq("username", selected_user).execute()

                                st.session_state.pass_success = f"✅ Password for cashier '{selected_user}' has been updated!"
                                st.session_state.pop("reset_pass_input", None)
                                st.rerun()
                            except Exception as e:
                                st.error(f"⚠️ Error updating password: {e}")
                else:
                    st.info("No cashiers found.")
            except Exception as e:
                st.error(f"⚠️ Error fetching cashiers: {e}")

# -----------------------------
# Logout
# -----------------------------
elif menu == "Logout":
    st.session_state.logged_in = False
    st.session_state.cashier = None
    st.success("Logged out. See you next time!")
    st.rerun()
