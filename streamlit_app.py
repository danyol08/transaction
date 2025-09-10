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
        # ✅ Convert created_at to Philippine Time (UTC+8) and show TIME only
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
            df["created_at"] = df["created_at"].dt.tz_convert("Asia/Manila")
            df["created_at_time"] = df["created_at"].dt.strftime("%H:%M:%S")

        # ✅ Format date_of_service for readability
        if "date_of_service" in df.columns:
            df["date_of_service"] = pd.to_datetime(df["date_of_service"], errors="coerce").dt.strftime("%b %d, %Y")

        # ✅ Sort by created_at (latest first)
        if "created_at" in df.columns:
            df = df.sort_values(by="created_at", ascending=False)

        # ✅ Drop unwanted columns (id + raw created_at), keep Time
        drop_cols = [c for c in ["id", "created_at"] if c in df.columns]
        df = df.drop(columns=drop_cols)

        # ✅ Rename time column and move beside date_of_service
        if "created_at_time" in df.columns:
            df = df.rename(columns={"created_at_time": "Time"})
            if "date_of_service" in df.columns:
                cols = [c for c in df.columns if c not in ["date_of_service", "Time"]]
                df = df[["date_of_service", "Time"] + cols]

        # Show table
        st.dataframe(df, use_container_width=True, height=460)

        # -----------------------------
        # 📥 Download Daily Report
        # -----------------------------
        st.markdown("---")
        st.subheader("📥 Download Daily Transaction Report")

        # Date picker
        report_date = st.date_input("Select a date", value=pd.to_datetime("today").date())

        # Filter by date_of_service
        daily_df = df[df["date_of_service"] == report_date.strftime("%b %d, %Y")]

        if not daily_df.empty:
            csv = daily_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label=f"⬇️ Download Report for {report_date.strftime('%b %d, %Y')}",
                data=csv,
                file_name=f"transactions_{report_date}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("ℹ️ No transactions for this date.")

        st.caption("Tip: Use this to generate daily cashier or sales reports.")


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
                # ✅ Convert created_at → Philippine Time (UTC+8)
                if "created_at" in results.columns:
                    results["created_at"] = pd.to_datetime(results["created_at"], errors="coerce", utc=True)
                    results["created_at"] = results["created_at"].dt.tz_convert("Asia/Manila")
                    results["created_at_time"] = results["created_at"].dt.strftime("%H:%M:%S")

                # ✅ Format date_of_service
                if "date_of_service" in results.columns:
                    results["date_of_service"] = pd.to_datetime(
                        results["date_of_service"], errors="coerce"
                    ).dt.strftime("%b %d, %Y")

                # ✅ Drop raw created_at, keep formatted time
                drop_cols = [c for c in ["id", "created_at"] if c in results.columns]
                results = results.drop(columns=drop_cols)
                if "created_at_time" in results.columns:
                    results = results.rename(columns={"created_at_time": "Time"})

                # ✅ Reorder: date_of_service beside Time
                if "date_of_service" in results.columns and "Time" in results.columns:
                    cols = ["date_of_service", "Time"] + [c for c in results.columns if c not in ["date_of_service", "Time"]]
                    results = results[cols]

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
# Cashier Management
# -----------------------------
elif menu == "Cashier Management":
    if st.session_state.cashier != "admin":
        st.error("❌ Only admin can manage cashiers.")
    else:
        st.subheader("👥 Cashier Management")

        # -----------------------------
        # Activity Logger
        # -----------------------------
        def log_activity(username: str, action: str, details: str = ""):
            try:
                supabase.table("activity_logs").insert({
                    "cashier_username": username,
                    "action": action,
                    "details": details
                }).execute()
            except Exception as e:
                st.error(f"⚠️ Failed to log activity: {e}")

        tab1, tab2, tab3 = st.tabs(["➕ Add Cashier", "📋 Manage Cashiers", "📝 Activity Logs"])

        # TAB 1: Add Cashier
        with tab1:
            st.subheader("➕ Add New Cashier")

            if st.session_state.get("cashier_success"):
                st.success(st.session_state.cashier_success)
                st.session_state.cashier_success = None

            # ✅ Clear form if flagged
            if st.session_state.get("clear_cashier_form"):
                st.session_state.new_cashier_username = ""
                st.session_state.new_cashier_password = ""
                st.session_state.new_cashier_confirm = ""
                st.session_state.new_cashier_fullname = ""
                st.session_state.clear_cashier_form = False

            new_username = st.text_input("👤 Username *", key="new_cashier_username", placeholder="e.g. cashier1")
            new_password = st.text_input("🔑 Password *", type="password", key="new_cashier_password")
            confirm_password = st.text_input("🔑 Confirm Password *", type="password", key="new_cashier_confirm")
            full_name = st.text_input("📝 Full Name", key="new_cashier_fullname", placeholder="Optional")

            if st.button("💾 Save Cashier", type="primary", use_container_width=True):
                if not new_username or not new_password or not confirm_password:
                    st.warning("⚠️ Please fill in all required fields.")
                elif new_password != confirm_password:
                    st.error("❌ Passwords do not match.")
                else:
                    hashed_pw = hash_password(new_password)
                    try:
                        supabase.table("cashiers").insert({
                            "username": new_username.strip(),
                            "password": hashed_pw,
                            "full_name": full_name.strip() if full_name else None,
                            "active": True
                        }).execute()

                        log_activity(st.session_state.cashier, "Add Cashier", f"Added '{new_username}'")

                        st.session_state.cashier_success = f"✅ Cashier '{new_username}' added successfully!"
                        st.session_state.clear_cashier_form = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Error adding cashier: {e}")

        # TAB 2: Manage Cashiers
        with tab2:
            st.subheader("📋 Cashier List & Actions")
            try:
                cashiers = supabase.table("cashiers").select("id, username, full_name, active").execute().data
                if cashiers:
                    df = pd.DataFrame(cashiers)
                    df["Status"] = df["active"].apply(lambda x: "🟢 Active" if x else "🔴 Inactive")
                    st.dataframe(df[["username", "full_name", "Status"]], use_container_width=True)

                    st.markdown("---")
                    st.subheader("⚙️ Manage Selected Cashier")

                    selected_user = st.selectbox("Select cashier:", [c["username"] for c in cashiers])

                    # Toggle status
                    current_status = next((c["active"] for c in cashiers if c["username"] == selected_user), True)
                    toggle_status = st.radio("Status", ["Active", "Inactive"],
                                             index=0 if current_status else 1,
                                             horizontal=True)

                    if st.button("🔄 Update Status", use_container_width=True):
                        try:
                            supabase.table("cashiers").update({
                                "active": (toggle_status == "Active")
                            }).eq("username", selected_user).execute()

                            log_activity(st.session_state.cashier, "Update Status", f"{selected_user} → {toggle_status}")

                            st.success(f"✅ Cashier '{selected_user}' status updated to {toggle_status}.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Error updating status: {e}")

                    st.markdown("---")
                    st.subheader("🔑 Reset Password")

                    if st.session_state.get("pass_success"):
                        st.success(st.session_state.pass_success)
                        st.session_state.pass_success = None

                    # ✅ Clear password form if flagged
                    if st.session_state.get("clear_pass_form"):
                        st.session_state.reset_pass_input = ""
                        st.session_state.reset_pass_confirm = ""
                        st.session_state.clear_pass_form = False

                    new_pass = st.text_input("Enter new password", type="password", key="reset_pass_input")
                    confirm_pass = st.text_input("Confirm new password", type="password", key="reset_pass_confirm")

                    if st.button("💾 Save New Password", type="primary", use_container_width=True):
                        if not new_pass or not confirm_pass:
                            st.warning("⚠️ Please enter and confirm the new password.")
                        elif new_pass != confirm_pass:
                            st.error("❌ Passwords do not match.")
                        else:
                            try:
                                hashed_pw = hash_password(new_pass)
                                supabase.table("cashiers").update({
                                    "password": hashed_pw
                                }).eq("username", selected_user).execute()

                                log_activity(st.session_state.cashier, "Reset Password", f"Password updated for {selected_user}")

                                st.session_state.pass_success = f"✅ Password for '{selected_user}' has been updated!"
                                st.session_state.clear_pass_form = True
                                st.rerun()
                            except Exception as e:
                                st.error(f"⚠️ Error updating password: {e}")
                else:
                    st.info("ℹ️ No cashiers found.")
            except Exception as e:
                st.error(f"⚠️ Error fetching cashiers: {e}")

        # TAB 3: Activity Logs
        with tab3:
            st.subheader("📝 Cashier Activity Logs")
            try:
                logs = supabase.table("activity_logs").select("*").order("created_at", desc=True).limit(50).execute().data
                if logs:
                    df_logs = pd.DataFrame(logs)
                    df_logs["created_at"] = pd.to_datetime(df_logs["created_at"]).dt.strftime("%Y-%m-%d %I:%M %p")
                    st.dataframe(df_logs[["cashier_username", "action", "details", "created_at"]],
                                 use_container_width=True, height=400)
                else:
                    st.info("ℹ️ No activity logs yet.")
            except Exception as e:
                st.error(f"⚠️ Error fetching logs: {e}")




# -----------------------------
# Logout
# -----------------------------
elif menu == "Logout":
    st.session_state.logged_in = False
    st.session_state.cashier = None
    st.success("Logged out. See you next time! 👋")
    st.rerun()
