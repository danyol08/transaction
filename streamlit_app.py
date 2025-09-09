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
# Sidebar Menu
# -----------------------------
with st.sidebar:
    st.success(f"Logged in as: {st.session_state.cashier}")
    menu = option_menu(
        "📋 Menu",
        ["Add Transaction", "View Transactions", "Search Customer", "Reports & CSV", "Logout"]
        + (["Cashier Management"] if st.session_state.cashier == "admin" else []),
        icons=["plus", "table", "search", "file-earmark-text", "box-arrow-right"]
        + (["people"] if st.session_state.cashier == "admin" else []),
        menu_icon="list",
        default_index=0,
    )

# -----------------------------
# Add Transaction
# -----------------------------
if menu == "Add Transaction":
    st.subheader("➕ Add New Transaction")

    # ✅ Clear inputs if flagged
    if st.session_state.get("_clear_txn"):
        for k in ["customer_name", "service_provided", "addons",
                  "tech_name", "tech_type", "service_date", "amount"]:
            st.session_state.pop(k, None)
        st.session_state._clear_txn = False

    c1, c2 = st.columns([2, 1])
    with c1:
        customer = st.text_input("Customer Name *", key="customer_name")
        service = st.text_input("Service Provided *", key="service_provided", placeholder="e.g., Gel Manicure, Classic Lashes")
        addons = st.text_area("Add-ons (optional)", key="addons", placeholder="e.g., Nail art, Extra volume")
    with c2:
        technician_name = st.text_input("Technician Name *", key="tech_name")
        technician_type = st.selectbox("Technician Type *", ["Nails", "Lashes", "Other"], key="tech_type")
        service_date = st.date_input("Date of Service *", value=date.today(), key="service_date")
        amount = st.number_input("Amount (₱) *", min_value=0.0, step=50.0, format="%.2f", key="amount")

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
                st.success("✅ Transaction saved!")
                st.session_state._clear_txn = True
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

        tab1, tab2 = st.tabs(["➕ Add Cashier", "📋 View / Manage Cashiers"])

        # Tab 1: Add Cashier
        with tab1:
            # ✅ Clear cashier form inputs if flagged
            if st.session_state.get("_clear_cashier"):
                for k in ["new_cashier_username", "new_cashier_password", "new_cashier_fullname"]:
                    st.session_state.pop(k, None)
                st.session_state._clear_cashier = False

            new_username = st.text_input("New Cashier Username *", key="new_cashier_username")
            new_password = st.text_input("New Cashier Password *", type="password", key="new_cashier_password")
            full_name = st.text_input("Full Name", key="new_cashier_fullname")

            if st.button("Save Cashier", type="primary", key="save_cashier_btn"):
                if new_username and new_password:
                    hashed_pw = hash_password(new_password)
                    try:
                        supabase.table("cashiers").insert({
                            "username": new_username.strip(),
                            "password": hashed_pw,
                            "full_name": full_name.strip() if full_name else None,
                            "active": True
                        }).execute()
                        st.success(f"✅ Cashier '{new_username}' added successfully!")
                        st.session_state._clear_cashier = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Error adding cashier: {e}")
                else:
                    st.warning("Please fill in username and password.")

        # Tab 2: Manage Cashiers
        with tab2:
            res = supabase.table("cashiers").select("id, username, full_name, active").order("id").execute()
            cashiers_df = pd.DataFrame(res.data) if res.data else pd.DataFrame()

            if cashiers_df.empty:
                st.info("No cashiers found.")
            else:
                st.dataframe(cashiers_df, use_container_width=True)
                cashier_to_update = st.selectbox("Select cashier to activate/deactivate", cashiers_df["username"].tolist(), key="manage_cashier")
                action = st.radio("Action", ["Deactivate", "Activate"], horizontal=True, key="manage_action")

                if st.button("Update Status", key="update_cashier_btn"):
                    new_status = True if action == "Activate" else False
                    supabase.table("cashiers").update({"active": new_status}).eq("username", cashier_to_update).execute()
                    st.success(f"✅ Cashier '{cashier_to_update}' status updated to {action}")
                    st.rerun()

# -----------------------------
# Logout
# -----------------------------
elif menu == "Logout":
    st.session_state.logged_in = False
    st.session_state.cashier = None
    st.success("Logged out. See you next time!")
    st.rerun()
