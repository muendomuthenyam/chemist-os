import streamlit as st
import datetime
import os
import urllib.parse
import pandas as pd
from dotenv import load_dotenv
import database as db
import security
import payments
import email_service

load_dotenv()

st.set_page_config(
    page_title=os.getenv("APP_NAME", "ChemistOS"),
    page_icon="💊",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    div.stButton > button {
        width: 100%;
        height: 3.2em;
        font-size: 17px !important;
        font-weight: bold;
        border-radius: 8px;
    }
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 500px;
    }
    </style>
""", unsafe_allow_html=True)

db.init_db()

# Session State Setup
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user_role" not in st.session_state:
    st.session_state["user_role"] = None
if "username" not in st.session_state:
    st.session_state["username"] = None
if "reset_otp_sent" not in st.session_state:
    st.session_state["reset_otp_sent"] = False

conn = db.get_db_connection()
user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
conn.close()

# ---------------------------------------------------------
# FLOW 1: FIRST-TIME SETUP WITH EMAIL VERIFICATION
# ---------------------------------------------------------
if user_count == 0:
    st.title("🚀 Welcome to ChemistOS")
    st.subheader("First-Time Business Setup")

    if "otp_sent" not in st.session_state:
        st.session_state["otp_sent"] = False
    if "pending_data" not in st.session_state:
        st.session_state["pending_data"] = {}

    if not st.session_state["otp_sent"]:
        st.caption("Step 1 of 2: Business & Security Information")
        with st.form("setup_form_stage1"):
            biz_name = st.text_input("Chemist / Pharmacy Name*", placeholder="e.g. Goodlife Community Chemist")
            owner_phone = st.text_input("Owner M-Pesa Phone*", placeholder="07XXXXXXXX")
            owner_email = st.text_input("Owner Email Address*", placeholder="owner@pharmacy.co.ke")
            owner_pin = st.text_input("Create 4-Digit Owner PIN*", type="password", max_chars=4)
            confirm_pin = st.text_input("Confirm Owner PIN*", type="password", max_chars=4)

            if st.form_submit_button("Send Email Verification Code 📩"):
                if not biz_name or not owner_phone or not owner_email or not owner_pin:
                    st.error("Please fill in all required fields.")
                elif "@" not in owner_email or "." not in owner_email:
                    st.error("Please enter a valid email address.")
                elif owner_pin != confirm_pin:
                    st.error("PINs do not match.")
                elif not security.is_valid_pin(owner_pin):
                    st.error("PIN must be exactly 4 numeric digits.")
                else:
                    otp_code = email_service.generate_otp()
                    sent = email_service.send_otp_email(owner_email, otp_code)
                    if sent:
                        st.session_state["pending_data"] = {
                            "biz_name": biz_name,
                            "owner_phone": owner_phone,
                            "owner_email": owner_email,
                            "owner_pin": owner_pin,
                            "otp_code": otp_code
                        }
                        st.session_state["otp_sent"] = True
                        st.success(f"Verification code sent to {owner_email}!")
                        st.rerun()
                    else:
                        st.error("Failed to send verification email.")
    else:
        st.caption(f"Step 2 of 2: Code sent to **{st.session_state['pending_data']['owner_email']}**")
        with st.form("setup_form_stage2"):
            entered_otp = st.text_input("Enter 6-Digit Verification Code:", max_chars=6)
            submit_verify = st.form_submit_button("Verify & Finish Setup 🚀")

        if submit_verify:
            if entered_otp.strip() == st.session_state["pending_data"]["otp_code"]:
                p = st.session_state["pending_data"]
                conn = db.get_db_connection()
                conn.execute("INSERT INTO users (username, role, pin_hash) VALUES ('Owner', 'OWNER', ?)",
                             (security.hash_pin(p["owner_pin"]),))
                conn.execute("INSERT INTO users (username, role, pin_hash) VALUES ('Attendant', 'ATTENDANT', ?)",
                             (security.hash_pin('0000'),))
                conn.execute("INSERT INTO tenants (business_name, owner_phone, owner_email, pin_code_hash) VALUES (?, ?, ?, ?)",
                             (p["biz_name"], p["owner_phone"], p["owner_email"], security.hash_pin(p["owner_pin"])))
                conn.commit()
                conn.close()

                del st.session_state["otp_sent"]
                del st.session_state["pending_data"]
                st.success("Account Verified & Setup Complete!")
                st.rerun()
            else:
                st.error("Invalid verification code.")

        if st.button("⬅️ Edit Details"):
            st.session_state["otp_sent"] = False
            st.session_state["pending_data"] = {}
            st.rerun()

    st.stop()

# ---------------------------------------------------------
# FLOW 2: LOGIN SCREEN
# ---------------------------------------------------------
if not st.session_state["authenticated"]:
    st.title("🔒 ChemistOS Login")
    st.caption("Enter your security PIN to open counter app")

    pin_input = st.text_input("Enter 4-Digit PIN:", type="password", max_chars=4)

    if st.button("Unlock System"):
        conn = db.get_db_connection()
        users = conn.execute("SELECT username, role, pin_hash FROM users").fetchall()
        conn.close()

        auth_success = False
        for user in users:
            if security.verify_pin(pin_input, user["pin_hash"]):
                st.session_state["authenticated"] = True
                st.session_state["user_role"] = user["role"]
                st.session_state["username"] = user["username"]
                auth_success = True
                st.toast(f"Logged in as {user['username']}")
                st.rerun()

        if not auth_success:
            st.error("Invalid Security PIN.")

    st.stop()

# ---------------------------------------------------------
# LOGGED-IN MAIN INTERFACE & SUBSCRIPTION CHECK
# ---------------------------------------------------------
top_col1, top_col2 = st.columns([3, 1])
with top_col1:
    st.title("💊 ChemistOS Mobile")
    st.caption(f"User: **{st.session_state['username']}** ({st.session_state['user_role']})")
with top_col2:
    if st.button("Logout"):
        st.session_state["authenticated"] = False
        st.session_state["user_role"] = None
        st.session_state["username"] = None
        st.rerun()

# Subscription Status Banner & KCB PayBill Routing
conn = db.get_db_connection()
tenant = conn.execute("SELECT * FROM tenants LIMIT 1").fetchone()
conn.close()

is_allowed, days_remaining, sub_label = payments.check_subscription_status(tenant)
st.caption(f"Subscription Status: **{sub_label}**")

# Paywall Screen when trial expires
if not is_allowed and st.session_state["user_role"] == "OWNER":
    st.error("🔒 Your 30-Day Free Trial Has Expired!")
    st.markdown("Renew your subscription to keep full access to sales, stock control, and financial reporting.")
    st.markdown("### Plan: **KES 200 / month**")
    st.caption("💳 Direct Settlement Account: KCB Bank PayBill 522522 | Acc: 1342774620")
    
    pay_phone = st.text_input("M-Pesa Phone Number:", placeholder="07XXXXXXXX")
    if st.button("Pay KES 200 via M-Pesa STK 📲"):
        if pay_phone:
            res = payments.trigger_mpesa_stk_push(pay_phone)
            conn = db.get_db_connection()
            conn.execute("UPDATE tenants SET subscription_status = 'active', last_payment_date = CURRENT_TIMESTAMP")
            conn.commit()
            conn.close()
            st.success(f"{res['message']}. Funds settled to KCB PayBill 522522 (Acc: 1342774620).")
            st.rerun()
        else:
            st.error("Please provide a valid M-Pesa phone number.")
    st.stop()

# Tabs
if st.session_state["user_role"] == "OWNER":
    tab_pos, tab_inventory, tab_patients, tab_logs, tab_admin = st.tabs(["🛒 POS", "📦 Stock", "👥 Refills", "📊 Logs", "⚙️ Admin"])
else:
    tab_pos, tab_inventory, tab_patients = st.tabs(["🛒 POS", "📦 Stock", "👥 Refills"])
    tab_logs, tab_admin = None, None

# --- TAB 1: POS ENGINE ---
with tab_pos:
    st.subheader("Fast Counter POS")
    conn = db.get_db_connection()
    df_pos_inv = pd.read_sql_query("SELECT * FROM inventory WHERE is_quarantined = 0 AND stock_qty_units > 0 AND expiry_date >= DATE('now')", conn)
    conn.close()

    if df_pos_inv.empty:
        st.warning("⚠️ No available valid stock. Please add items in the '📦 Stock' tab.")
    else:
        drug_options = df_pos_inv['drug_name'].tolist()
        selected_drug_name = st.selectbox("Search & Select Medicine:", drug_options)
        drug_row = df_pos_inv[df_pos_inv['drug_name'] == selected_drug_name].iloc[0]
        
        st.info(f"📍 **In Stock:** {drug_row['stock_qty_units']} Units | **Price:** KES {drug_row['selling_price_unit']:.2f}/unit")

        col_qty, col_pay = st.columns(2)
        with col_qty:
            qty_sold = st.number_input("Quantity:", min_value=1, max_value=int(drug_row['stock_qty_units']), value=1)
        with col_pay:
            payment_mode = st.radio("Payment Mode:", ["Cash", "M-Pesa Express"], horizontal=True)

        total_amount = qty_sold * drug_row['selling_price_unit']
        unit_cost = drug_row['buying_price_box'] / max(1, drug_row['units_per_box'])
        profit_amount = (drug_row['selling_price_unit'] - unit_cost) * qty_sold

        st.markdown(f"### Total: **KES {total_amount:,.2f}**")

        doc_name, lic_ref = "", ""
        if drug_row['category'] == "POM":
            st.warning("⚠️ Prescription-Only Medicine (POM)")
            col_doc, col_lic = st.columns(2)
            with col_doc:
                doc_name = st.text_input("Prescriber Doctor*", placeholder="Dr. Omondi")
            with col_lic:
                lic_ref = st.text_input("License Ref No.", placeholder="RX-9901")

        cust_phone = st.text_input("Customer Phone (For SMS Receipt):", placeholder="07XXXXXXXX")

        if st.button("Complete Checkout"):
            if drug_row['category'] == "POM" and not doc_name:
                st.error("Prescriber Doctor Name is required for POM drugs.")
            else:
                conn = db.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO sales (cashier_name, payment_mode, total_amount, vat_amount) VALUES (?, ?, ?, 0.0)",
                               (st.session_state['username'], payment_mode, total_amount))
                sale_id = cursor.lastrowid

                cursor.execute("INSERT INTO sale_items (sale_id, inventory_id, unit_type, quantity, unit_price, profit_generated) VALUES (?, ?, 'Unit', ?, ?, ?)",
                               (sale_id, drug_row['id'], qty_sold, drug_row['selling_price_unit'], profit_amount))

                if drug_row['category'] == "POM":
                    cursor.execute("INSERT INTO pom_logs (sale_id, prescriber_doctor, license_ref, patient_name) VALUES (?, ?, ?, 'Walk-in Patient')",
                                   (sale_id, doc_name, lic_ref))

                new_stock = drug_row['stock_qty_units'] - qty_sold
                cursor.execute("UPDATE inventory SET stock_qty_units = ? WHERE id = ?", (new_stock, drug_row['id']))
                conn.commit()
                conn.close()

                st.success(f"Sale #{sale_id} Logged! KES {total_amount:,.2f} via {payment_mode}.")

                if cust_phone:
                    receipt_text = f"--- RECEIPT ---\nChemistOS Pharmacy\nRcpt #{sale_id} | {datetime.date.today()}\nItem: {selected_drug_name} x{qty_sold}\nTotal: KES {total_amount:,.2f} ({payment_mode})\nCashier: {st.session_state['username']}\nThank you! Quick Recovery."
                    sms_url = f"sms:{cust_phone}?body={urllib.parse.quote(receipt_text)}"
                    st.markdown(f'<a href="{sms_url}" target="_blank"><button style="width:100%; height:3.2em; background-color:#28a745; color:white; font-weight:bold; border-radius:8px; border:none; font-size:16px;">📲 Send Native SMS Receipt</button></a>', unsafe_allow_html=True)

# --- TAB 2: INVENTORY & EXPIRY MANAGER ---
with tab_inventory:
    st.subheader("Stock & Expiry Control")

    with st.expander("➕ Add New Medicine Batch", expanded=False):
        with st.form("add_stock_form", clear_on_submit=True):
            drug_name = st.text_input("Drug Commercial Name*", placeholder="e.g. Amoxicillin 500mg")
            generic_name = st.text_input("Generic Compound", placeholder="e.g. Amoxicillin Trihydrate")
            
            col_cat, col_vat = st.columns(2)
            with col_cat:
                category = st.selectbox("Category*", ["OTC", "POM", "Surgical", "Cosmetics"])
            with col_vat:
                vat_category = st.selectbox("VAT Type*", ["EXEMPT", "STANDARD_16", "ZERO_RATED"])

            col_batch, col_exp = st.columns(2)
            with col_batch:
                batch_number = st.text_input("Batch Ref*", placeholder="e.g. B-9041")
            with col_exp:
                expiry_date = st.date_input("Expiry Date*", min_value=datetime.date.today())

            col_units, col_qty = st.columns(2)
            with col_units:
                units_per_box = st.number_input("Units per Box", min_value=1, value=10)
            with col_qty:
                stock_qty_units = st.number_input("Total Units Received*", min_value=1, value=50)

            col_bp, col_sp = st.columns(2)
            with col_bp:
                buying_price_box = st.number_input("Cost / Box (KES)*", min_value=0.0, value=500.0)
            with col_sp:
                selling_price_unit = st.number_input("Selling Price / Unit (KES)*", min_value=0.0, value=80.0)

            min_reorder = st.number_input("Minimum Reorder Threshold", min_value=1, value=10)
            submit_stock = st.form_submit_button("Save Stock")

            if submit_stock and drug_name and batch_number:
                conn = db.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO inventory (
                        drug_name, generic_name, category, batch_number, expiry_date,
                        vat_category, units_per_box, stock_qty_units, buying_price_box,
                        selling_price_unit, min_reorder_level, is_quarantined
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (
                    drug_name, generic_name, category, batch_number, expiry_date,
                    vat_category, units_per_box, stock_qty_units, buying_price_box,
                    selling_price_unit, min_reorder
                ))
                conn.commit()
                conn.close()
                st.success(f"Saved {drug_name}!")
                st.rerun()

    conn = db.get_db_connection()
    df_inv = pd.read_sql_query("SELECT * FROM inventory", conn)
    conn.close()

    if not df_inv.empty:
        st.markdown("### 📋 Active Medicine Stock")
        today = datetime.date.today()
        
        for idx, row in df_inv.iterrows():
            exp_date = datetime.datetime.strptime(str(row['expiry_date']), "%Y-%m-%d").date()
            days_to_expiry = (exp_date - today).days

            if days_to_expiry <= 0:
                badge = "⛔ EXPIRED (QUARANTINED)"
                card_style = "background-color: rgba(128, 128, 128, 0.2); border-left: 5px solid black;"
            elif days_to_expiry < 30:
                badge = "🔴 EXPIRE CRITICAL"
                card_style = "background-color: rgba(255, 0, 0, 0.1); border-left: 5px solid red;"
            elif days_to_expiry <= 90:
                badge = "🟡 EXPIRE WARNING"
                card_style = "background-color: rgba(255, 165, 0, 0.1); border-left: 5px solid orange;"
            else:
                badge = "🟢 SAFE STOCK"
                card_style = "background-color: rgba(0, 255, 0, 0.1); border-left: 5px solid green;"

            cost_info = f" | Wholesale: KES {row['buying_price_box']:.2f}" if st.session_state["user_role"] == "OWNER" else ""

            with st.container():
                st.markdown(f"""
                    <div style="padding: 10px; border-radius: 8px; margin-bottom: 8px; {card_style}">
                        <strong>{row['drug_name']}</strong> ({row['category']})<br/>
                        <small>Batch: {row['batch_number']} | Exp: {row['expiry_date']} ({badge})</small><br/>
                        <strong>Stock: {row['stock_qty_units']} Units</strong> | Selling: KES {row['selling_price_unit']:.2f}{cost_info}
                    </div>
                """, unsafe_allow_html=True)

# --- TAB 3: CHRONIC REFILL TRACKER ---
with tab_patients:
    st.subheader("Chronic Patient Refill Tracker")
    reminder_msg = "Hello James Kamau, your 30-day refill for Metformin at ChemistOS Pharmacy is due in 3 days."
    sms_reminder_url = f"sms:0712345678?body={urllib.parse.quote(reminder_msg)}"
    st.markdown("""
        <div style="padding:10px; background-color:rgba(0,123,255,0.1); border-left:5px solid #007bff; border-radius:6px; margin-bottom:10px;">
            <strong>James Kamau</strong> • Metformin 500mg<br/>
            <small>Refill Due: In 3 Days</small>
        </div>
    """, unsafe_allow_html=True)
    st.markdown(f'<a href="{sms_reminder_url}" target="_blank"><button style="width:100%; height:2.8em; background-color:#007bff; color:white; font-weight:bold; border-radius:6px; border:none;">📲 Send Refill Reminder SMS</button></a>', unsafe_allow_html=True)

# --- TAB 4: FINANCIAL LOGS (OWNER ONLY) ---
if tab_logs and st.session_state["user_role"] == "OWNER":
    with tab_logs:
        st.subheader("Daily Sales Audit & Reports")
        conn = db.get_db_connection()
        df_sales = pd.read_sql_query("SELECT * FROM sales ORDER BY timestamp DESC", conn)
        df_items = pd.read_sql_query("SELECT SUM(profit_generated) as total_profit FROM sale_items", conn)
        df_pom = pd.read_sql_query("""
            SELECT p.sale_id, p.prescriber_doctor, p.license_ref, s.timestamp, s.total_amount
            FROM pom_logs p JOIN sales s ON p.sale_id = s.id ORDER BY s.timestamp DESC
        """, conn)
        conn.close()

        if not df_sales.empty:
            total_rev = df_sales['total_amount'].sum()
            total_profit = df_items['total_profit'].iloc[0] if not df_items.empty and df_items['total_profit'].iloc[0] is not None else 0.0

            col_r, col_p = st.columns(2)
            with col_r:
                st.metric("Total Revenue", f"KES {total_rev:,.2f}")
            with col_p:
                st.metric("Est. Gross Profit", f"KES {total_profit:,.2f}")

            st.markdown("---")
            st.markdown("### 📜 Transaction Log")
            st.dataframe(df_sales[['id', 'timestamp', 'cashier_name', 'payment_mode', 'total_amount']], use_container_width=True)

            if not df_pom.empty:
                st.markdown("---")
                st.markdown("### 📋 PPB Prescription Register (POM Log)")
                st.dataframe(df_pom, use_container_width=True)

# --- TAB 5: IN-APP USER & PIN MANAGER (OWNER ONLY) ---
if tab_admin and st.session_state["user_role"] == "OWNER":
    with tab_admin:
        st.subheader("⚙️ Users & Security Control")

        with st.expander("🔑 Change Owner PIN", expanded=False):
            new_owner_pin = st.text_input("New 4-Digit Owner PIN:", type="password", max_chars=4)
            if st.button("Update Owner PIN"):
                if security.is_valid_pin(new_owner_pin):
                    conn = db.get_db_connection()
                    conn.execute("UPDATE users SET pin_hash = ? WHERE role = 'OWNER'", (security.hash_pin(new_owner_pin),))
                    conn.commit()
                    conn.close()
                    st.success("Owner PIN updated successfully!")
                else:
                    st.error("PIN must be 4 digits.")

        with st.expander("➕ Add New Shop Attendant", expanded=False):
            att_name = st.text_input("Attendant Name / Username:", placeholder="e.g. Mary")
            att_pin = st.text_input("Set 4-Digit PIN for Attendant:", type="password", max_chars=4)
            if st.button("Create Attendant Account"):
                if att_name and security.is_valid_pin(att_pin):
                    conn = db.get_db_connection()
                    try:
                        conn.execute("INSERT INTO users (username, role, pin_hash) VALUES (?, 'ATTENDANT', ?)",
                                     (att_name, security.hash_pin(att_pin)))
                        conn.commit()
                        st.success(f"Attendant '{att_name}' created!")
                        st.rerun()
                    except Exception:
                        st.error("Username already exists.")
                    finally:
                        conn.close()

        st.markdown("### 👥 System Accounts")
        conn = db.get_db_connection()
        users_df = pd.read_sql_query("SELECT id, username, role FROM users", conn)
        conn.close()
        st.dataframe(users_df, use_container_width=True)