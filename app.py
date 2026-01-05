import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from modules import data_loader, ai_parser
import modules.db_manager as db_manager
import modules.d3_treemap as d3_treemap

# Initialize DB
db_manager.init_db()
# --- Page Config ---
st.set_page_config(
    page_title="가족 자산 대시보드",
    layout="wide",
    initial_sidebar_state="collapsed"
)
# --- Password Protection ---
# --- Password Protection (Streamlit Authenticator) ---
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

def run_authentication():
    # 1. Get Password from Secrets
    plain_password = st.secrets["general"]["password"]
    
    # 2. Hash the password (Runtime hashing - okay for single user)
    # Note: efficient enough for single user startup
    hashed_passwords = [stauth.Hasher().hash(plain_password)]
    
    # 3. Create Config Dictionary
    config = {
        'credentials': {
            'usernames': {
                'admin': {
                    'name': 'Admin',
                    'password': hashed_passwords[0]
                },
                'park': { # Added User 'park'
                    'name': '박행자',
                    'password': hashed_passwords[0] # Using same password for now
                }
            }
        },
        'cookie': {
            'expiry_days': 1,
            'key': 'asset_dashboard_signature_key', # Random string
            'name': 'asset_dashboard_cookie'
        },
        'pre-authorized': {'emails': []}
    }
    
    # 4. Initialize Authenticator
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days'],
        # preheaders deprecated in some versions, simpler usage:
    )
    
    # 5. Login Widget
    # Custom widget location: center of screen (main)
    # location='main' (default)
    login_result = authenticator.login(location="main")
    
    if login_result:
        name, authentication_status, username = login_result
    else:
        # Fallback if login returns None (initial state or pending)
        name = st.session_state.get('name')
        authentication_status = st.session_state.get('authentication_status')
        username = st.session_state.get('username')
    
    if authentication_status:
        # Success
        return authenticator
    elif authentication_status is False:
        st.error('Username/password is incorrect')
        st.stop()
    elif authentication_status is None:
        st.warning('Please enter your username and password')
        st.stop()
        
    return None

# Execution
authenticator = run_authentication()
if not st.session_state.get("authentication_status"):
    st.stop()

# Logout Button in Sidebar (Optional but good practice)
with st.sidebar:
    authenticator.logout('Logout', 'main')

# --- Styling ---
# --- Styling ---
st.markdown("""
<style>
    /* Import SUIT Font */
    @import url('https://cdn.jsdelivr.net/gh/sunn-us/SUIT/fonts/static/woff2/SUIT.css');
    /* Global Styling - SUIT Font Application */
    /* REMOVED 'button', 'div', 'span' to fix Sidebar Icon breaking. 
       We rely on inheritance from 'body' for generic containers, 
       and target text-specific tags for enforcement. */
    html, body, p, label, 
    h1, h2, h3, h4, h5, h6, [data-testid="stMarkdownContainer"] {
        font-family: 'SUIT', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif !important;
        background-color: transparent; 
    }
    /* FIX: Force Dark Background on Body to prevent White Bar on Mobile */
    html, body {
        background-color: #0E1117 !important;
    }
    /* Apply SUIT to Streamlit Widgets explicitly, safely */
    .stButton button, .stTextInput input, .stSelectbox, .stTextArea textarea {
        font-family: 'SUIT', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif !important;
    }
    /* Explicitly protect Material Icons */
    i, .material-icons, [class*="material-symbols"] {
        font-family: 'Material Symbols Rounded', 'Material Icons' !important;
    }
    /* Metrics Label Adjustment for SUIT */
    [data-testid="stMetricLabel"] {
        font-weight: 500 !important;
    }
    [data-testid="stMetricValue"] {
        font-weight: 700 !important;
    }
    /* Fix Mobile White Space */
    .block-container {
        padding-top: 4rem;
        padding-bottom: 2rem !important;
    }
    /* Hide Footer */
    footer {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)
# --- Load Data ---
data = data_loader.load_data()

# --- Auth & Filtering Logic ---
# Get current user
current_user = st.session_state.get('username')
target_owner = None

# Define User Roles/Permissions
if current_user == 'park':
    target_owner = '박행자'
    st.toast(f"Welcome, {target_owner}! (Filtered View)", icon="🔒")
elif current_user == 'admin':
    # Admin sees all
    pass 

# Apply Filters if target_owner is set
if target_owner and data:
    # 1. Filter Transactions
    if 'transactions' in data and not data['transactions'].empty:
        df_t = data['transactions']
        if '소유자' in df_t.columns:
            data['transactions'] = df_t[df_t['소유자'] == target_owner]
            
    # 2. Filter History (Columns)
    if 'history' in data and not data['history'].empty:
        df_h = data['history']
        # Always keep Date/Day info
        keep_cols = [c for c in df_h.columns if c in ['날짜', '요일']]
        # Add Owner's Portfolio Column
        # Assuming Owner Name exactly matches Portfolio Name in the sheet columns
        if target_owner in df_h.columns:
            keep_cols.append(target_owner)
        # Add Index Col
        idx_col = f"{target_owner}_idx"
        if idx_col in df_h.columns:
             keep_cols.append(idx_col)
             
        data['history'] = df_h[keep_cols]
        
    # 3. Filter Temp History (Current Value)
    if 'temp_history' in data and not data['temp_history'].empty:
        df_tmp = data['temp_history']
        # Filter rows where Portfolio/Owner matches
        # Assuming there is a column that identifies the portfolio
        # Based on previous code: '포트폴리오' column likely exists
        port_col = next((c for c in df_tmp.columns if '포트폴리오' in c), None)
        if port_col:
            data['temp_history'] = df_tmp[df_tmp[port_col] == target_owner]

    # 4. Filter Inventory (Asset Details) - CRITICAL FIX
    if 'inventory' in data and not data['inventory'].empty:
        df_i = data['inventory']
        if '소유자' in df_i.columns:
            data['inventory'] = df_i[df_i['소유자'] == target_owner]

if data:
    df_hist = data["history"]
    df_cagr = data["cagr"]
    df_inv = data["inventory"]
    df_beta = data["beta_plan"]
else:
    st.error("Failed to load data")
    st.stop()
# --- Constants & Configuration ---
# Updated Color Palette (Grouped Logic)
# Shoho Group (Blue/Cool): Light Blue, Slate/Cornflower
# Jo Group (Warm/Orange): Peach, Pale Yellow
# Park Group (Distinct): Coral Red
PORT_COLORS = {
    '쇼호 α': "#AECBEB", # Light Blue
    '쇼호 β': "#6495ED", # Cornflower Blue (Similar but distinct)
    '조연재': "#F99D65", # Peach Orange
    '조이재': "#FBD7AC", # Pale Yellow
    '박행자': "#EB5E55", # Coral Red
}
# Revert to Korean Names
portfolios = ['쇼호 α', '쇼호 β', '조연재', '조이재', '박행자']

# Filter Portfolios List based on User
if target_owner:
    portfolios = [p for p in portfolios if p == target_owner]
# --- Sidebar Navigation ---
st.sidebar.header("Menu")
# Get Options (Owners, etc.)
txn_options = data_loader.get_transaction_options()
owners_list = txn_options.get('owners', [])

# Filter Owners List too
if target_owner:
    owners_list = [o for o in owners_list if o == target_owner]

# Custom CSS...
st.markdown("""
<style>
    /* ... (CSS Content same as before) ... */
    div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        padding: 12px 20px;
        margin-bottom: 8px;
        border-radius: 12px;
        transition: all 0.3s ease;
        cursor: pointer;
        display: block; 
        border: 1px solid transparent;
        color: #E0E0E0; 
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background-color: rgba(174, 203, 235, 0.15); 
        color: #AECBEB;
        border: 1px solid rgba(174, 203, 235, 0.3);
    }
    .stMain div[role="radiogroup"] {
        display: flex;
        gap: 10px;
        flex-direction: row;
        flex-wrap: wrap; 
    }
    .stMain div[role="radiogroup"] > label {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 5px 15px;
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        cursor: pointer;
        transition: 0.2s;
    }
    .stMain div[role="radiogroup"] > label:hover {
        background-color: rgba(255, 255, 255, 0.1);
        border-color: #AECBEB;
    }
    section[data-testid="stSidebar"] {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }
</style>
""", unsafe_allow_html=True)

# Define Logic for Menu Options
menu_options = [
    "Asset Trend", 
    "Portfolio Scorecard", 
    "Asset Details", 
    "Transaction Log", 
    "Beta Rebalancing",
    "Historical Analysis"
]

# Admin Only Menu
if current_user == 'admin' or current_user == 'park': # Allow park to debug too
    pass # menu_options.append("Admin: DB Viewer")

# Hide 'Beta Rebalancing' for 'park'
if target_owner == '박행자':
    menu_options = [m for m in menu_options if m != "Beta Rebalancing"]

# Robust Page Persistence (Versioned Key)
# This prevents "Index Error" by forcing new widget if menu length changes.

if "menu_len" not in st.session_state:
    st.session_state.menu_len = len(menu_options)
    st.session_state.menu_ver = 0

# If menu length changed (e.g. switching users), increment version to reset widget
if len(menu_options) != st.session_state.menu_len:
    st.session_state.menu_len = len(menu_options)
    st.session_state.menu_ver += 1
    # Reset selection to safe default
    st.session_state.current_page_selection = menu_options[0]

nav_key = f"nav_v{st.session_state.menu_ver}"

if "current_page_selection" not in st.session_state:
    st.session_state.current_page_selection = menu_options[0]

# Calculate valid index
try:
    nav_index = menu_options.index(st.session_state.current_page_selection)
except ValueError:
    nav_index = 0
    st.session_state.current_page_selection = menu_options[0]

def update_page_selection():
    st.session_state.current_page_selection = st.session_state[nav_key]

page = st.sidebar.radio(
    "Select a page:",
    menu_options,
    index=nav_index,
    label_visibility="collapsed",
    key=nav_key,
    on_change=update_page_selection
)
st.sidebar.markdown("---")
# Global Filters (Apply to relevant pages like Asset Details)
selected_owners = []
if page == "Asset Details" and owners_list:
    st.sidebar.subheader("Filters")
    selected_owners = st.sidebar.multiselect("Owners", owners_list, default=owners_list)

# --- DB Sync Control ---
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Sync Database"):
    with st.sidebar.status("Syncing to SQLite...", expanded=True) as status:
        st.write("Fetching GSheet Data...")
        # Force fresh fetch
        fresh_data = data_loader.load_data() 
        st.write("Updating DB...")
        success, msg = data_loader.sync_to_sqlite(fresh_data)
        if success:
            status.update(label="Sync Complete!", state="complete", expanded=False)
            st.sidebar.success(msg)
        else:
            status.update(label="Sync Failed", state="error")
            st.sidebar.error(msg)
st.sidebar.markdown("---")
st.sidebar.caption("Last Update: " + (df_hist['날짜'].iloc[-1].strftime('%Y-%m-%d') if not df_hist.empty else "N/A"))
if st.sidebar.button("Clear Cache"):
    st.cache_data.clear()
    st.rerun()

# --- Page Routing ---
if page == "Asset Trend":
    # (Previous Logic...) - Existing logic is embedded in large blocks, need to append
    pass # Placeholder strictly for search match, actual logic below

# === INSERT ADMIN DB VIEWER LOGIC ===
if page == "Admin: DB Viewer":
    st.title("Admin: Database Viewer 🗄️")
    
    import sqlite3
    conn = db_manager.get_connection()
    
    # Tabs
    tab_browser, tab_sql = st.tabs(["Browse Tables", "Execute SQL"])
    
    with tab_browser:
        # Get List of Tables
        tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn)['name'].tolist()
        views = pd.read_sql("SELECT name FROM sqlite_master WHERE type='view';", conn)['name'].tolist()
        
        selected_table = st.selectbox("Select Table/View", tables + views)
        
        if selected_table:
            st.subheader(f"Data: {selected_table}")
            df_table = pd.read_sql(f"SELECT * FROM {selected_table}", conn)
            st.dataframe(df_table, use_container_width=True)
            st.caption(f"Rows: {len(df_table)}")
            
    with tab_sql:
        st.subheader("Execute SQL Query")
        query = st.text_area("SQL Query", "SELECT * FROM transaction_log ORDER BY date DESC LIMIT 10")
        if st.button("Run Query"):
            try:
                df_sql = pd.read_sql(query, conn)
                st.dataframe(df_sql, use_container_width=True)
            except Exception as e:
                st.error(f"Error: {e}")
                
    conn.close()

# Keep existing Main Page Logic below... but wait, structure of app.py is page-linear?
# Typically: if page == "A": ... elif page == "B": ...
# I need to ensure I don't break the existing flow.
# The user's file likely has a large `if page == "Asset Trend": ...` block.
# Since I cannot see the whole file, I will append this logic condition at the END or carefully strictly match valid insertion point.
# I will use the "sidebar logic" replacement as anchor, and assume standard Streamlit structure implies I should put the new page check ALONGSIDE others.
# Actually, standard Streamlit app structure often has:
# if page == "Asset Trend": ...
# elif page == "Portfolio Scorecard": ...
# To modify this safely without reading 2000 lines, I will verify where the `page` routing starts.
# It seems `app.py` has implicit flow. I'll rely on adding the new condition *after* the sidebar setup, 
# and importantly, I must ensure that `if page == "Admin: DB Viewer":` is handled.
# Since I'm replacing the Sidebar definition block, I will just ensure the Menu Option is added.
# THE ACTUAL PAGE RENDERING LOGIC for "Admin: DB Viewer" needs to be added where other pages are rendered.
# I will append it to the very end of the file, assuming simple if/elif structure.

# RE-READ PLAN:
# 1. Update Menu Options (done in replacement).
# 2. Append Page Logic at the END of file (need separate call or very smart Match).
# I'll do Step 1 (Sidebar) here.

# --- Page 1: Asset & Index Trend ---
if page == "Asset Trend":
    st.header("Asset & Index Trend")
    # Frequency Toggle
    freq_option = st.radio("Frequency", ["Daily", "Weekly", "Monthly"], horizontal=True)
    # Resample Logic
    df_chart = df_hist.copy()
    if not df_chart.empty and '날짜' in df_chart.columns:
        df_chart = df_chart.set_index('날짜')
        # Preserve the very first data point (Baseline)
        first_row = df_chart.iloc[[0]].copy()
        if freq_option == "Weekly":
            df_resampled = df_chart.resample('W').last().dropna()
            # Combine first row if it's not effectively the same as the first resampled point
            if not df_resampled.empty and first_row.index[0] != df_resampled.index[0]:
                df_chart = pd.concat([first_row, df_resampled]).drop_duplicates().sort_index()
            else:
                 df_chart = df_resampled
        elif freq_option == "Monthly":
            df_resampled = df_chart.resample('ME').last().dropna()
            # Combine first row
            if not df_resampled.empty and first_row.index[0] != df_resampled.index[0]:
                df_chart = pd.concat([first_row, df_resampled]).drop_duplicates().sort_index()
            else:
                 df_chart = df_resampled
        df_chart = df_chart.reset_index()
    tab_asset, tab_idx = st.tabs(["Asset Trend", "Index (100)"])
    # Common Rangebreaks (Hide Weekends only for Daily)
    if freq_option == "Daily":
        weekend_breaks = [dict(bounds=["sat", "mon"])]
    else:
        weekend_breaks = []
    # Fix for Plotly TypeError: Convert to epoch milliseconds
    baseline_ts = pd.Timestamp("2025-09-22")
    baseline_date = baseline_ts.value // 10**6 
    with tab_asset:
        if not df_chart.empty:
            fig_asset = go.Figure()
            for i, port in enumerate(portfolios):
                if port in df_chart.columns:
                    fig_asset.add_trace(go.Scatter(
                        x=df_chart['날짜'], 
                        y=df_chart[port], 
                        mode='lines', 
                        name=port,
                        line=dict(color=PORT_COLORS.get(port, "#FFFFFF"), width=2) # Thinner Line (User Request)
                    ))
            fig_asset.add_vline(x=baseline_date, line_width=1, line_dash="dash", line_color="gray", annotation_text="Base: 2025.09.22")
            fig_asset.update_layout(
                template="plotly_dark", 
                title="Portfolio Asset Trend",
                xaxis_title="Date",
                yaxis_title="Value (KRW)",
                hovermode="x unified",
                xaxis=dict(rangebreaks=weekend_breaks),
                plot_bgcolor='rgba(0,0,0,0)', # Transparent background
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_asset, use_container_width=True)
    with tab_idx:
        if not df_chart.empty:
            fig_idx = go.Figure()
            for i, port in enumerate(portfolios):
                idx_col = f"{port}_idx"
                if idx_col in df_chart.columns:
                    fig_idx.add_trace(go.Scatter(
                        x=df_chart['날짜'], 
                        y=df_chart[idx_col], 
                        mode='lines', 
                        name=port,
                        line=dict(color=PORT_COLORS.get(port, "#FFFFFF"), width=2) # Thinner Line (User Request)
                    ))
            fig_idx.add_vline(x=baseline_date, line_width=1, line_dash="dash", line_color="gray", annotation_text="Start")
            fig_idx.add_hline(y=100, line_width=1, line_color="white")
            fig_idx.update_layout(
                template="plotly_dark", 
                title="Index Comparison (Base=100)",
                xaxis_title="Date",
                yaxis_title="Index",
                hovermode="x unified",
                xaxis=dict(rangebreaks=weekend_breaks),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_idx, use_container_width=True)
            st.markdown("""
            <div style="text-align: right; color: #999999; font-size: 11px; margin-top: 5px;">
            Index: 각포트폴리오 별로 '25.9.22 기준(100) 대비 상대 수익률 지수화
            </div>
            """, unsafe_allow_html=True)
# --- Page 2: Portfolio Performance (DoD & CAGR) ---
elif page == "Portfolio Scorecard":
    st.header("Portfolio Scorecard")
    st.caption("Detailed breakdown by portfolio")
    
    st.divider()
    


    # Access Data
    df_temp = data.get("temp_history")
    df_hist_local = df_hist.copy() if not df_hist.empty else None

    # Standard Streamlit Layout for Scorecard
    cols = st.columns(len(portfolios))

    for idx, port in enumerate(portfolios):
        with cols[idx]:
            # 1. Get Current Value (from TEMP)
            val = 0
            principal_val = 0
            
            if df_temp is not None and not df_temp.empty:
                # Filter by Portfolio Name
                # Assuming '포트폴리오' column exists as per User Request context
                # "자산기록_TEMP 시트의 포트폴리오 별..."
                target_port_col = next((c for c in df_temp.columns if '포트폴리오' in c), None)
                if target_port_col:
                    row = df_temp[df_temp[target_port_col] == port]
                    if not row.empty:
                        # Summing just in case multiple rows exist (though unlikely for Summary)
                        if '평가금액' in row.columns:
                            val = pd.to_numeric(row['평가금액'], errors='coerce').sum()
                        if '투자원금' in row.columns:
                            principal_val = pd.to_numeric(row['투자원금'], errors='coerce').sum()
            
            # 2. Get Previous Day Value (Strictly Yesterday or Before)
            prev_val = 0
            if df_hist_local is not None and not df_hist_local.empty:
                # Ensure date column exists and is datetime
                if '날짜' in df_hist_local.columns:
                     # Get today's date (System Local Time)
                     today_date = datetime.now().date()
                     # Filter for rows BEFORE today
                     mask = df_hist_local['날짜'].dt.date < today_date
                     df_past = df_hist_local[mask]
                     
                     if not df_past.empty:
                         # The last row of "Past" is the true Previous Day
                         if port in df_past.columns:
                             prev_val = df_past.iloc[-1][port]
                     else:
                         # Fallback: If no past data (very first day?), use last available?
                         # Or 0? Let's use 0 to indicate N/A delta.
                         pass
                else:
                    # Fallback if no date column (unlikely)
                    if port in df_hist_local.columns:
                         prev_val = df_hist_local.iloc[-1][port] 
            
            # Calculate DoD
            diff = val - prev_val
            pct = (diff / prev_val) if prev_val != 0 else 0
            
            # --- Fallback if TEMP is empty (to avoid zeros) ---
            # If val is 0, maybe use History last row as current? 
            # User explicitly asked for TEMP. If TEMP is empty/missing, 0 is correct or "N/A".
            # But let's respect the source.
            
            # 3. Get CAGR
            cagr_val = None
            if df_cagr is not None:
                col_port = next((c for c in df_cagr.columns if 'Portfolio' in c or '포트폴리오' in c or '이름' in c or '구분' in c or '소유자' in c), None)
                col_cagr = next((c for c in df_cagr.columns if 'CAGR' in c or '수익률' in c or '연환산' in c), None)
                if col_port and col_cagr:
                    match = df_cagr[df_cagr[col_port] == port]
                    if match.empty:
                        port_nospace = port.replace(" ", "")
                        names_nospace = df_cagr[col_port].astype(str).str.replace(" ", "")
                        match_idx = names_nospace[names_nospace == port_nospace].index
                        if not match_idx.empty:
                            match = df_cagr.loc[match_idx]
                    if not match.empty:
                        val_raw = match[col_cagr].iloc[0]
                        if isinstance(val_raw, str):
                                val_raw = float(val_raw.replace('%', '').replace(',', '')) / 100.0 if '%' in val_raw else float(val_raw)
                        cagr_val = val_raw

            # 4. Get Total Return
            total_return_pct = None
            if principal_val > 0:
                total_return_pct = (val - principal_val) / principal_val
            
            # Display Metric
            st.metric(
                label=port,
                value=f"₩{val:,.0f}",
                delta=f"{diff:,.0f} ({pct:+.1%})"
            )
            
            # Sub-metrics (CAGR / Total Return)
            sub_info = []
            if total_return_pct is not None:
                sub_info.append(f"Total Return: {total_return_pct:+.1%}")
            if cagr_val is not None:
                sub_info.append(f"CAGR: {cagr_val:.1%}")
            
            if sub_info:
                st.caption(" | ".join(sub_info))
    
    
    # 5. Definitions Footnote (Using st.info for theme-adaptive visibility)

    
    st.divider()
    
    # 5. Definitions (Minimalist, Right-aligned, Small - Moved to Bottom)
    st.markdown("""
    <div style="text-align: right; color: #999999; font-size: 11px; margin-top: 5px;">
    Total Return: 배당/확정손익 제외, 매입 대비 평가수익률 &nbsp;|&nbsp; CAGR: '25.9.22 기준(100) 대비 연환산 상승률
    </div>
    """, unsafe_allow_html=True)
# --- Page 3: Asset Inventory ---
elif page == "Asset Details":
    # Custom Title to anchor the top of the page
    st.markdown("<h1 style='font-size: 2.5rem; margin-bottom: 30px;'>Asset Inventory Details</h1>", unsafe_allow_html=True)
    # 1. Prepare Data
    df_asset = data['inventory'].copy()
    df_master = data['account_master'].copy()
    # Ensure numeric types
    num_cols = ['매입금액', '평가금액', '총평가손익']
    for col in num_cols:
        if col in df_asset.columns:
            df_asset[col] = pd.to_numeric(df_asset[col], errors='coerce').fillna(0)
    # 2. Use '포트폴리오 구분' directly (No Merge)
    # User confirmed '포트폴리오 구분' exists in '자산종합' sheet.
    target_port_col = '포트폴리오 구분'
    if target_port_col in df_asset.columns:
        # Rename to standard '포트폴리오' for downstream consistency
        df_merged = df_asset.rename(columns={target_port_col: '포트폴리오'})
    else:
        st.error(f"'{target_port_col}' 컬럼을 찾을 수 없습니다. (데이터 컬럼: {list(df_asset.columns)})")
        st.stop()
    # 3. Filter by Owner (if selected in Sidebar)
    # Assumes '소유자' col exists in df_asset
    if selected_owners and '소유자' in df_merged.columns:
        df_merged = df_merged[df_merged['소유자'].isin(selected_owners)]
    # 4. Portfolio Filter (Added Widget)
    all_ports = sorted(df_merged['포트폴리오'].dropna().unique())
    # Custom Sort if possible
    custom_order = ['쇼호 α', '쇼호 β', '조연재', '조이재', '박행자']
    all_ports.sort(key=lambda x: custom_order.index(x) if x in custom_order else 999)
    selected_portfolios = st.multiselect("Select Portfolios", all_ports, default=all_ports)
    if selected_portfolios:
        df_merged = df_merged[df_merged['포트폴리오'].isin(selected_portfolios)]
    # 5. Filter out zero evaluation assets
    df_merged = df_merged[df_merged['평가금액'] > 0]
    # 6. GroupBy & Aggregate (The Pivot Step)
    # Ensure numeric types for new columns
    # User requested to use sheet columns for '평단가', '현재가'
    extra_nums = ['보유주수', '배당수익', '확정손익', '평단가', '현재가']
    for c in extra_nums:
        if c in df_merged.columns:
            df_merged[c] = pd.to_numeric(df_merged[c], errors='coerce').fillna(0)
        else:
            df_merged[c] = 0
    # Group by [Portfolio, Ticker] -> Sum [Invested, Eval, Profit, Qty, Div, Realized]
    # For Prices, we average them (assuming consistency per ticker).
    df_pivot = df_merged.groupby(['포트폴리오', '종목'], as_index=False).agg({
        '매입금액': 'sum',
        '평가금액': 'sum',
        '총평가손익': 'sum',
        '보유주수': 'sum',
        '배당수익': 'sum',
        '확정손익': 'sum',
        '평단가': 'mean', # User requested sheet column
        '현재가': 'mean', # User requested sheet column
        '화폐': 'first'   # NEW: Capture Currency
    })
    def get_currency_symbol(curr):
        s = str(curr).strip().upper()
        if s in ['USD', '달러', 'DOLLAR']: return '$'
        return '₩'
    df_pivot['CurSymbol'] = df_pivot['화폐'].apply(get_currency_symbol)
    # 7. Calculate Derived Metrics (ReturnRate only)
    # ReturnRate
    df_pivot['ReturnRate'] = 0.0
    mask_invest = df_pivot['매입금액'] != 0
    df_pivot.loc[mask_invest, 'ReturnRate'] = (df_pivot.loc[mask_invest, '평가금액'] / df_pivot.loc[mask_invest, '매입금액'] - 1) * 100
    # Removed Manual AvgPrice/CurPrice Calc as per User Request
    # Removed Manual AvgPrice/CurPrice Calc as per User Request
    # 8. Render Treemaps & Tables
    unique_ports = sorted(df_pivot['포트폴리오'].unique())
    # Re-sort using custom order
    unique_ports.sort(key=lambda x: custom_order.index(x) if x in custom_order else 999)
    if not unique_ports:
        st.info("데이터가 없습니다.")
    else:
        for port in unique_ports:
            st.subheader(port)
            df_p = df_pivot[df_pivot['포트폴리오'] == port].copy()
            if df_p.empty:
                continue
            # --- Dynamic Font Size Logic ---
            min_val = df_p['평가금액'].min()
            max_val = df_p['평가금액'].max()
            def get_font_size(val):
                if max_val == min_val: return 24
                norm = (val - min_val) / (max_val - min_val)
                return 14 + (norm * 66) 
            df_p['TargetFontSize'] = df_p['평가금액'].apply(get_font_size)
            # --- Debug: Show Data ---
            # st.dataframe(df_p) # Uncomment if needed
            # --- Custom Coloring & Structure (go.Treemap) ---
            # User Request: Dark Portfolio Background, Colored Tiles, No Borders, Big Text.
            # Strategy: Pre-calculate Hex colors for all nodes.
            # Helper to generate color from value (-30 to +30)
            def get_color_hex(val):
                # Clamp to range
                v = max(-30, min(30, val))
                # Normalize to 0-1 for Red-Yellow-Green (0=Red, 0.5=Yellow, 1=Green)
                # But typically RdYlGn: 0=Red, 1=Green.
                # My range: -30(Red) -> 0(Gray/Black?) -> +30(Green).
                # Plotly 'RdYlGn' is Red(Low) -> Green(High).
                norm = (v + 30) / 60.0
                return px.colors.sample_colorscale('RdYlGn', [norm])[0]
            # 1. Prepare Data
            df_p['종목'] = df_p['종목'].astype(str)
            # Root Node
            root_id = port
            root_label = "" # Hide visual label (User Request)
            root_parent = ""
            root_value = df_p['평가금액'].sum()
            root_color = "#262626" 
            # Root Custom Data (Sum/Mean where applicable for Portfolio Level)
            # Order: [TotalProfit, ReturnRate, Invested, Qty, AvgPrice, CurPrice, Div, Realized, CurSymbol]
            # Note: Prices/Qty not meaningful for Root Sum, but fill 0 for structure.
            root_custom = [
                df_p['총평가손익'].sum(), 
                0, # Root Return
                df_p['매입금액'].sum(),
                0, 0, 0, # Qty, Avg, Cur
                df_p['배당수익'].sum(),
                df_p['확정손익'].sum(),
                '₩' # Root Currency Default
            ]
            # Child Nodes
            child_ids = df_p['종목'].tolist()
            child_labels = df_p['종목'].tolist()
            child_parents = [root_id] * len(df_p)
            child_values = df_p['평가금액'].tolist()
            child_colors = df_p['ReturnRate'].apply(get_color_hex).tolist()
            # Columns to pass to tooltips
            # Order MUST match root_custom
            cols_to_hover = ['총평가손익', 'ReturnRate', '매입금액', '보유주수', '평단가', '현재가', '배당수익', '확정손익', 'CurSymbol']
            child_custom = df_p[cols_to_hover].values.tolist()
            ids = [root_id] + child_ids
            labels = [root_label] + child_labels
            parents = [root_parent] + child_parents
            values = [root_value] + child_values
            colors = [root_color] + child_colors
            custom_data = [root_custom] + child_custom
            # Rich Hover Template (Modern/Sophisticated Design)
            # Uses HTML styling for "Card" look.
            # 0:Profit, 1:Return, 2:Invest, 3:Qty, 4:Avg, 5:Cur, 6:Div, 7:Realized, 8:Symbol
            hover_template = (
                "<span style='font-size:18px; font-weight:bold'>%{label}</span><br>" +
                "<span style='font-size:12px; color:#aaaaaa'>%{customdata[3]:,.0f}주 보유</span><br><br>" +
                "<span style='color:#aaaaaa'>평가금액:</span> <b style='font-size:16px'>₩%{value:,.0f}</b> " +
                "<span style='font-size:14px'>(%{customdata[1]:.2f}%)</span><br>" +
                "<span style='color:#aaaaaa'>매입금액:</span> <b>₩%{customdata[2]:,.0f}</b><br>" +
                "<span style='color:#aaaaaa'>총 손 익:</span> <b>₩%{customdata[0]:,.0f}</b><br><br>" +
                "<span style='color:#aaaaaa'>현 재 가:</span> %{customdata[8]}%{customdata[5]:,.0f}<br>" +
                "<span style='color:#aaaaaa'>평 단 가:</span> %{customdata[8]}%{customdata[4]:,.0f}<br><br>" +
                "<span style='font-size:11px; color:#888888'>배당금 ₩%{customdata[6]:,.0f} | 실현손익 ₩%{customdata[7]:,.0f}</span>" +
                "<extra></extra>"
            )
            # 1. Calculate Adaptive Font Sizes (Python Logic)
            # Scaling up to 180px as per User Request (Extreme Max)
            total_val = df_p['평가금액'].sum()
            def calc_font_size_aggressive(val):
                if total_val == 0: return 20
                size = (val / total_val) * 450 # Further Increased Boost for 180px
                return int(max(20, min(180, size))) # Cap at 180px
            font_sizes = df_p['평가금액'].apply(calc_font_size_aggressive).tolist()
            font_sizes = [150] + font_sizes # Root gets Max (Title)
            # 2. Adaptive Text Color (Contrast Check)
            # Yellowish (Near 0%) -> Black Text
            # Strong Red/Green -> White Text
            def get_text_color(val):
                if abs(val) < 10: # Neutral/Yellow Zone
                    return 'black'
                return 'white'
            text_colors = df_p['ReturnRate'].apply(get_text_color).tolist()
            # Root is Dark Grey (#262626) -> White Text
            text_colors = ['white'] + text_colors
            # --- D3.js Treemap ---
            # Helper to generate HTML logic (Finviz Style)
            if not df_p.empty:
                html_code = d3_treemap.generate_d3_treemap_v6(df_p, port_name=port)
                st.components.v1.html(html_code, height=520, scrolling=False)
            else:
                st.info("No data available for visualization.")
            
            st.markdown("""
            <div style="text-align: right; color: #999999; font-size: 11px; margin-top: 5px;">
            Evaluated Profit: 평가금액 - 매입금액 | Return Rate: (평가금액 / 매입금액 - 1) * 100 | Display Size: 평가금액 비례 (Max 180px)
            </div>
            """, unsafe_allow_html=True)
# --- Page 4: Transaction Input ---
elif page == "Transaction Log":
    st.header("Transaction Log")
    st.caption("Entries will be saved to Google Sheet '00_거래일지'.")
    # 1. Layout with Tabs
    # Defaulting to AI Input as per User Request (to prevent random switching)
    tab_auto, tab_input, tab_view = st.tabs(["AI Input (Beta) 🤖", "Manual Input", "View Log"])
    # Fetch options dynamically
    options = data_loader.get_transaction_options()
    # --- TAB 1: Manual Input ---
    with tab_input:
        st.caption("Add a new transaction")
        with st.form("transaction_form_page", clear_on_submit=True):
            col_date, col_dummy = st.columns([1, 1])
            with col_date:
                txn_date = st.date_input("Date", datetime.today())
            # Enums
            owners = options.get("owners", [])
            accounts = options.get("accounts", [])
            tickers = options.get("tickers", [])
            types = options.get("types", [])
            currencies = options.get("currencies", [])
            c1, c2 = st.columns(2)
            with c1:
                sel_owner = st.selectbox("Owner", owners if owners else ["Custom"], index=None, placeholder="Select Owner...")
            with c2:
                sel_account = st.selectbox("Account", accounts if accounts else ["Custom"], index=None, placeholder="Select Account...")
            # Ticker Select with capability to add new
            sel_ticker = st.selectbox("Ticker", tickers if tickers else ["Custom"], index=None, placeholder="Select or Type Ticker...")
            c3, c4 = st.columns(2)
            with c3:
                sel_type = st.selectbox("Type", types if types else ["Buy", "Sell", "Div"], index=None, placeholder="Type")
            with c4:
                sel_currency = st.selectbox("Currency", currencies if currencies else ["$", "₩"], index=None, placeholder="Cur")
            c5, c6 = st.columns(2)
            with c5:
                txn_amount = st.number_input("Amount", min_value=0.0, step=1.0, format="%.0f", value=None, placeholder="0")
            with c6:
                txn_qty = st.number_input("Qty", min_value=0.0, step=0.0001, format="%.4f", value=None, placeholder="0.0000")
            txn_note = st.text_input("Note")
            submitted = st.form_submit_button("💾 Save to Sheet")
            if submitted:
                new_row = {
                    "날짜": txn_date.strftime("%Y-%m-%d"),
                    "소유자": sel_owner,
                    "계좌": sel_account,
                    "종목": sel_ticker,
                    "거래구분": sel_type,
                    "통화": sel_currency,
                    "거래금액": txn_amount if txn_amount is not None else 0,
                    "수량": txn_qty if txn_qty is not None else 0,
                    "비고": txn_note
                }
                if data_loader.add_transaction_log(new_row):
                    st.success("Successfully Saved!")
                    st.toast("Transaction added.", icon="✅")
    # --- TAB 2: AI Input ---
    with tab_auto:
        st.info("Upload MTS screenshots (one or multiple) to auto-extract transaction details.")
        uploaded_files = st.file_uploader("Upload Screenshots", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
        
        if 'ai_draft_data' not in st.session_state:
            st.session_state.ai_draft_data = None
            
        if uploaded_files:
            if st.button("🔍 Analyze with AI"):
                with st.spinner(f"Analyzing {len(uploaded_files)} images..."):
                    # Read bytes for all files
                    img_data_list = [f.getvalue() for f in uploaded_files]
                    parsed_data = ai_parser.parse_transaction_image(img_data_list)
                    
                    if parsed_data == "API_KEY_MISSING":
                        st.error("Gemini API Key missing in secrets.toml.")
                    elif parsed_data:
                        # Convert to DataFrame
                        dfer = pd.DataFrame(parsed_data)
                        
                        # Normalize columns
                        required_cols = ["date", "type", "ticker", "price", "qty", "amount", "currency", "account_number"]
                        for c in required_cols:
                            if c not in dfer.columns:
                                dfer[c] = None
                        
                        # --- Master Data Parsing & Mapping ---
                        # Reload data to ensure we have Masters
                        data = data_loader.load_data()
                        df_acct_master = data.get('account_master', pd.DataFrame())
                        df_asset_master = data.get('asset_master', pd.DataFrame())
                        
                        # 1. Owner/Account Mapping (by Account Number)
                        # We assume the first row's account_number applies to all (since it's one screenshot session usually)
                        # OR if AI extracted different accounts per row, handle row by row.
                        
                        # Build Lookup Dict for Accounts: { '123-45...': {'owner': 'Name', 'account': 'AccName'} }
                        acc_map = {}
                        if not df_acct_master.empty:
                             # Try to identify columns. Valid guesses: '계좌번호', 'AccountNo' / '소유자', 'Owner' / '계좌명', 'AccountName'
                             # Let's standardize column names for the map
                             ac_cols = df_acct_master.columns
                             c_num = next((c for c in ac_cols if '계좌번호' in c or 'Number' in c), None)
                             c_own = next((c for c in ac_cols if '소유자' in c or 'Owner' in c), None)
                             c_acc = next((c for c in ac_cols if '계좌명' in c or 'Account' in c and 'Number' not in c), None)
                             
                             if c_num and c_own:
                                 for _, r in df_acct_master.iterrows():
                                     acc_num_clean = str(r[c_num]).strip()
                                     acc_map[acc_num_clean] = {
                                         'owner': r[c_own],
                                         'account': r[c_acc] if c_acc else "General"
                                     }

                        # 2. Asset Mapping (Ticker -> Name) & Name Validation
                        # Build Lookup Dicts
                        ticker_map = {}
                        valid_names = set()
                        
                        if not df_asset_master.empty:
                            as_cols = df_asset_master.columns
                            c_tick = next((c for c in as_cols if '티커' in c or 'Ticker' in c), None)
                            c_name = next((c for c in as_cols if '종목명' in c or 'Name' in c), None)
                            
                            if c_tick and c_name:
                                for _, r in df_asset_master.iterrows():
                                    t = str(r[c_tick]).strip().upper()
                                    n = str(r[c_name]).strip()
                                    ticker_map[t] = n
                                    valid_names.add(n)

                        # Apply Mappings
                        final_owners = []
                        final_accounts = []
                        final_tickers = []
                        
                        for idx, row in dfer.iterrows():
                            # Account Logic
                            ai_acc_num = str(row['account_number']).strip() if row['account_number'] else ""
                            matched_acc = acc_map.get(ai_acc_num)
                            if matched_acc:
                                final_owners.append(matched_acc['owner'])
                                final_accounts.append(matched_acc['account'])
                            else:
                                # Fallback (Try partial match)
                                found = False
                                for k, v in acc_map.items():
                                    if k in ai_acc_num or ai_acc_num in k: 
                                        final_owners.append(v['owner'])
                                        final_accounts.append(v['account'])
                                        found = True
                                        break
                                if not found:
                                    final_owners.append(None)
                                    final_accounts.append(None)
                            
                            # Ticker/Name Logic
                            raw_ticker = str(row['ticker']).strip().upper() if row['ticker'] else ""
                            
                            # 1. Try mapping Ticker -> Name
                            if raw_ticker in ticker_map:
                                final_tickers.append(ticker_map[raw_ticker])
                            # 2. Check if it's already a valid Name (e.g. "현대차2우B")
                            elif raw_ticker in valid_names:
                                final_tickers.append(raw_ticker) # It's valid name
                            # 3. Fallback: Use raw value
                            else:
                                final_tickers.append(raw_ticker)

                        dfer['owner'] = final_owners
                        dfer['account'] = final_accounts
                        dfer['ticker'] = final_tickers # Validated Name or Raw Ticker
                        
                        # --- NOTE / STATUS HANDLING (CRITICAL FIX) ---
                        # 1. Preserve AI output if valid ('Pending' or 'Settled')
                        # 2. Fallback to Heuristics if empty/invalid
                        final_notes = []
                        for idx, row in dfer.iterrows():
                            # Get AI output (case-insensitive check)
                            raw_note = str(row.get('note', '')).strip().capitalize()
                            
                            # Validates
                            if raw_note in ['Pending', 'Settled']:
                                final_notes.append(raw_note)
                            else:
                                # Apply Heuristics
                                row_str = str(row.to_dict()).lower()
                                if '체결' in row_str or '주문' in row_str or 'pending' in row_str:
                                    final_notes.append('Pending')
                                elif '정산' in row_str or '거래내역' in row_str or 'settled' in row_str:
                                    final_notes.append('Settled')
                                else:
                                    # Final Default
                                    final_notes.append('Settled')
                        
                        dfer['note'] = final_notes
                        
                        # --- Post-Processing: Merge Dividend Tax (배당세) ---
                        # LS Securities: '배당금' and '배당세' are separate rows.
                        # Logic: Find '배당세', subtract from matching '배당금' (Same Date, Ticker, Account), then remove '배당세' row.
                        
                        # Indices to drop
                        drop_indices = []
                        
                        for idx, row in dfer.iterrows():
                            if row['type'] == '배당세':
                                try:
                                    tax_amount = float(row['amount']) if row['amount'] else 0
                                    
                                    # Find matching dividend (Same Date, Ticker, Account, Type='배당금')
                                    # Looking for indices NOT in drop_indices already
                                    match_mask = (
                                        (dfer['date'] == row['date']) & 
                                        (dfer['ticker'] == row['ticker']) & 
                                        (dfer['account'] == row['account']) & 
                                        (dfer['type'] == '배당금')
                                    )
                                    match_indices = dfer.index[match_mask].tolist()
                                    
                                    if match_indices:
                                        # Deduct from the first match found
                                        target_idx = match_indices[0]
                                        current_val = float(dfer.at[target_idx, 'amount'])
                                        dfer.at[target_idx, 'amount'] = round(current_val - tax_amount, 2)
                                        
                                        # Mark tax row for deletion
                                        drop_indices.append(idx)
                                except Exception as e:
                                    print(f"Error merging tax: {e}")
                                    
                        if drop_indices:
                            dfer = dfer.drop(drop_indices).reset_index(drop=True)
                            st.info(f"Merged {len(drop_indices)} dividend tax rows.")
                        
                        # --- Duplicate Warning System ---
                        # Load existing transactions
                        df_txn_log = data.get('transactions', pd.DataFrame())
                        
                        # Helper for strict normalization
                        def normalize_for_key(val):
                            if pd.isna(val): return ""
                            s = str(val).replace(',', '').replace(' ', '').replace('₩', '').replace('$', '')
                            try:
                                # Convert to float then back to string to handle 1000.0 vs 1000
                                f = float(s)
                                return f"{f:.2f}"
                            except:
                                return s

                        # Create a 'key' for comparison: Date + Ticker + Type + Qty (Amount can vary by tax)
                        def make_key(row):
                            d = str(row.get('날짜','')).split(' ')[0] # just date part
                            t = str(row.get('종목','')).strip()
                            ty = str(row.get('거래구분','')).strip()
                            q = normalize_for_key(row.get('수량', 0))
                            # Optional: Include Amount if needed, but Qty+Ticker+Date+Type is usually unique enough
                            # a = normalize_for_key(row.get('거래금액', 0)) 
                            return f"{d}_{t}_{ty}_{q}"

                        existing_keys = set()
                        if not df_txn_log.empty:
                            existing_keys = set(df_txn_log.apply(make_key, axis=1))
                            
                        # Check draft rows
                        warnings = []
                        for idx, row in dfer.iterrows():
                            # 1. Fallback Logic for Pending Status (Python-side safety net)
                            # If AI missed it, check columns again
                            current_note = str(row.get('note', ''))
                            if "Pending" not in current_note and "Settled" not in current_note:
                                # Check heuristics
                                if any(x in str(row) for x in ['체결', '주문']): 
                                     row['note'] = "Pending"
                                     dfer.at[idx, 'note'] = "Pending"
                                elif any(x in str(row) for x in ['정산', '거래내역']):
                                     row['note'] = "Settled"
                                     dfer.at[idx, 'note'] = "Settled"
                                else:
                                     # Default to Settled if totally unknown, but leave as matches AI
                                     pass

                            # 2. Duplicate Check
                            mapped_row = {
                                '날짜': row['date'],
                                '종목': row['ticker'],
                                '거래구분': row['type'],
                                '수량': row['qty'],
                                '거래금액': row['amount']
                            }
                            draft_key = make_key(mapped_row)
                            
                            if draft_key in existing_keys:
                                warnings.append("Duplicate")
                            else:
                                warnings.append(None)
                        
                        dfer['warning'] = warnings
                        
                        # Add Selection Column (Default True unless duplicate)
                        dfer['select'] = [w is None for w in warnings]

                        st.session_state.ai_draft_data = dfer
                        # Update editor key to force reset component
                        if 'editor_key' not in st.session_state: st.session_state.editor_key = 0
                        st.session_state.editor_key += 1
                        
                        st.toast("Analysis & Mapping Complete!", icon="🤖")
                    else:
                        st.error("Failed to parse image. Try again.")

        # Display Editor if data exists
        if st.session_state.ai_draft_data is not None:
            st.subheader("Verify & Edit Data")
            
            # Show checking status
            if st.session_state.ai_draft_data['warning'].notna().any():
                st.warning(f"Found {st.session_state.ai_draft_data['warning'].count()} potential duplicates. They are unselected by default.")

            # Ensure key exists if session was cleared
            if 'editor_key' not in st.session_state: st.session_state.editor_key = 0

            # FORCE RESET INDEX to prevent 'Bad setIn index' errors
            if st.session_state.ai_draft_data is not None:
                st.session_state.ai_draft_data = st.session_state.ai_draft_data.reset_index(drop=True)

            with st.form("ai_input_form"):
                # Prepare Stock Options from Asset Master
                data_source = data_loader.load_data()
                valid_stock_names = []
                if data_source and 'asset_master' in data_source and not data_source['asset_master'].empty:
                     # Assume '종목명' (Stock Name) is the target
                     # Check column names like '종목명', 'Name', or 'Asset'
                     am_cols = data_source['asset_master'].columns
                     c_name = next((c for c in am_cols if '종목명' in c or 'Name' in c), None)
                     if c_name:
                         valid_stock_names = sorted(data_source['asset_master'][c_name].dropna().unique().tolist())
                         
                     # SOFT VALIDATION: Add existing AI values to options so they don't disappear
                     # This allows users to see "Hyundai Motor" (Invalid) and change it to "현대차" (Valid)
                     current_ai_tickers = st.session_state.ai_draft_data['ticker'].dropna().unique().tolist()
                     for t in current_ai_tickers:
                         t_str = str(t).strip()
                         if t_str and t_str not in valid_stock_names:
                             valid_stock_names.append(t_str) # Temporarily add invalid ones to dropdown

                edited_df = st.data_editor(
                    st.session_state.ai_draft_data,
                    key=f"ai_editor_{st.session_state.editor_key}", # Unique key per analysis
                    num_rows="dynamic",
                    use_container_width=True,
                    column_config={
                        "select": st.column_config.CheckboxColumn("Save?", help="Select rows to save"),
                        "warning": st.column_config.TextColumn("Status", disabled=True),
                        "type": st.column_config.SelectboxColumn(options=['매수', '매도', '배당금', '배당세', '이자', '입금', '출금', '환전', '확정손익']), # Korean Options
                        "ticker": st.column_config.SelectboxColumn(
                            "Asset Name",
                            options=valid_stock_names,
                            required=True,
                            help="Select from Asset Master. If 'Invalid' value appears, please change it."
                        ),
                        "owner": st.column_config.SelectboxColumn(options=owners),
                        "account": st.column_config.SelectboxColumn(options=accounts),
                        "currency": st.column_config.SelectboxColumn(options=['$', '₩']),
                        "note": st.column_config.SelectboxColumn(
                            "Status (Pending/Settled)",
                            options=["Pending", "Settled"],
                            help="Pending: Order Execution (체결)\nSettled: Transaction/Deposit (정산)",
                            required=True
                        )
                    },
                    column_order=["select", "warning", "date", "type", "ticker", "amount", "qty", "price", "currency", "owner", "account", "note"]
                )
                
                # Submit Button
                submitted = st.form_submit_button("💾 Confirm & Save Selected")
                
                if submitted:
                    # Logic: Load -> Merge/Update -> Overwrite
                    # CRITICAL: Use fresh data!
                    df_current_log = data_loader.get_latest_transaction_log()
                    
                    # Ensure columns exist in current log
                    required_cols = ["날짜", "소유자", "계좌", "종목", "거래구분", "통화", "거래금액", "수량", "비고"]
                    for col in required_cols:
                        if col not in df_current_log.columns:
                            df_current_log[col] = None

                    selected_rows = edited_df[edited_df['select'] == True]
                    
                    if selected_rows.empty:
                        st.warning("No rows selected to save.")
                    else:
                        updates_count = 0
                        new_count = 0
                        
                        for index, row in selected_rows.iterrows():
                            # Extract details
                            r_date = str(row['date'])
                            r_ticker = str(row['ticker'])
                            r_type = row['type']
                            r_qty = float(row['qty']) if row['qty'] else 0
                            r_price = float(row['amount']) if row['amount'] else 0
                            r_note = row['note'] # 'Pending' or 'Settled' by AI
                            
                            managed = False
                            
                            # Case: AI says "Settled", try to find "Pending" in existing log
                            if "Settled" in str(r_note): 
                                # Find potential match: Same Ticker, Type, Qty, Note="Pending"
                                # Allow date to be within 7 days (Order [Pending] -> Settlement [Settled] lag)
                                # Data Types: Ensure loose comparison for float/string
                                
                                # Filter candidates
                                # 1. Status Check
                                match_mask = df_current_log['비고'].astype(str).str.contains("Pending", na=False)
                                
                                # 2. Ticker Check (Exact or Partial?) -> Exact for now to be safe
                                match_mask &= (df_current_log['종목'] == r_ticker)
                                
                                # 3. Type Check (Strict)
                                match_mask &= (df_current_log['거래구분'] == r_type)
                                
                                candidates = df_current_log[match_mask].copy()
                                
                                # 4. Quantity Check (Loose for Float)
                                if not candidates.empty:
                                    # Convert to float for comparison
                                    qty_col = pd.to_numeric(candidates['수량'], errors='coerce').fillna(0)
                                    # Tolerance 0.001
                                    candidates = candidates[abs(qty_col - r_qty) < 0.001]
                                
                                # 5. Date Check (Current Date >= Log Date)
                                # Settled Date (r_date) should be AFTER or EQUAL to Pending Date
                                if not candidates.empty:
                                    # Parse dates
                                    try:
                                        log_dates = pd.to_datetime(candidates['날짜'], errors='coerce')
                                        curr_date = pd.to_datetime(r_date, errors='coerce')
                                        
                                        if pd.notna(curr_date):
                                            # Match if: 0 <= (Settled - Pending) <= 10 days
                                            date_diff = (curr_date - log_dates).dt.days
                                            valid_dates = (date_diff >= 0) & (date_diff <= 14) # generous 2 weeks
                                            candidates = candidates[valid_dates]
                                    except Exception:
                                        pass # Skip date check if error

                                if not candidates.empty:
                                    # Found match! Take the first one.
                                    match_idx = candidates.index[0]
                                    
                                    # Update that row
                                    df_current_log.at[match_idx, '날짜'] = r_date # Update to Settlement Date
                                    df_current_log.at[match_idx, '거래금액'] = r_price # Update to Settlement Amount
                                    df_current_log.at[match_idx, '비고'] = "Settled" # Update Status
                                    
                                    updates_count += 1
                                    managed = True
                            
                            if not managed:
                                # Append as new
                                new_row = {
                                    "날짜": r_date,
                                    "소유자": row['owner'],
                                    "계좌": row['account'],
                                    "종목": r_ticker,
                                    "거래구분": r_type,
                                    "통화": row['currency'],
                                    "거래금액": r_price,
                                    "수량": r_qty,
                                    "비고": r_note
                                }
                                df_current_log = pd.concat([df_current_log, pd.DataFrame([new_row])], ignore_index=True)
                                new_count += 1

                        # Save Full DF
                        if data_loader.overwrite_transaction_log(df_current_log):
                            st.success(f"Processed! (New: {new_count}, Updated: {updates_count})")
                            st.session_state.ai_draft_data = None
                            st.rerun()

    # --- TAB 3: View Log ---
    with tab_view:
        df_txn_log = data.get('transactions', pd.DataFrame()).copy()

        # 1. Metric: Pending Count
        pending_count = 0
        if '비고' in df_txn_log.columns:
            pending_count = df_txn_log[df_txn_log['비고'].astype(str).str.contains("Pending", na=False)].shape[0]
        
        if pending_count > 0:
            st.info(f"⚡ Settlement Pending: **{pending_count}** transactions.")

        if df_txn_log is not None and not df_txn_log.empty:
            # 2. Filters
            with st.expander("Filter Log", expanded=False):
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    filter_owner = st.multiselect("Filter Owner", df_txn_log['소유자'].unique().tolist())
                with col_f2:
                    filter_ticker = st.multiselect("Filter Ticker", df_txn_log['종목'].unique().tolist())
            
            # Apply Filter
            df_display = df_txn_log.copy()
            if filter_owner:
                df_display = df_display[df_display['소유자'].isin(filter_owner)]
            if filter_ticker:
                df_display = df_display[df_display['종목'].isin(filter_ticker)]

            # 3. Date Processing (Legacy Logic preserved for robustness)
            if '날짜' in df_display.columns:
                # Create a new series for processed dates
                raw_dates = df_display['날짜'].astype(str).str.strip()
                processed_dates = pd.Series(pd.NaT, index=df_display.index)
                
                # Identify Numeric (Excel Serial)
                dates_as_num = pd.to_numeric(raw_dates, errors='coerce')
                is_serial = dates_as_num.notna() & (dates_as_num > 25569)
                
                if is_serial.any():
                    processed_dates[is_serial] = pd.to_datetime(
                        dates_as_num[is_serial], unit='D', origin='1899-12-30'
                    )
                
                # Process Strings
                mask_string = ~is_serial
                if mask_string.any():
                    processed_dates[mask_string] = pd.to_datetime(
                        raw_dates[mask_string], errors='coerce'
                    )
                
                # Assign back safely
                df_display['날짜'] = processed_dates
                
                # Filter NaT/Invalid
                df_display = df_display[df_display['날짜'].notna()]
                # Sanity Check > 1980
                df_display = df_display[df_display['날짜'] > '1980-01-01']
                
                # Format for Display
                df_display['날짜'] = df_display['날짜'].dt.strftime('%Y-%m-%d')
            
            # Sort by Date Descending
            if '날짜' in df_display.columns:
                df_display = df_display.sort_values('날짜', ascending=False)

            # 4. Highlight Pending Rows & Display
            def highlight_pending(row):
                note = str(row.get('비고', ''))
                if "Pending" in note:
                    return ['background-color: #FFF4E5; color: #594736'] * len(row) # Light Orange
                return [''] * len(row)

            # Columns Order
            cols_order = ['날짜', '소유자', '계좌', '종목', '거래구분', '통화', '거래금액', '수량', '비고']
            # Filter columns that actually exist
            cols_to_show = [c for c in cols_order if c in df_display.columns]

            st.dataframe(
                df_display[cols_to_show].style.apply(highlight_pending, axis=1),
                use_container_width=True,
                height=600,
                hide_index=True
            )
        else:
            st.info("No transaction logs found.")
# --- Page 5: Beta Rebalancing ---
elif page == "Beta Rebalancing":
    st.header("Beta Portfolio Breakdown (쇼호 β)")
    # Check dependencies
    try:
        import yfinance as yf
    except ImportError:
        st.error("`yfinance` needed for Correlation/Risk analysis. Please install it.")
        yf = None
    if df_beta is not None and not df_beta.empty:
        col_ticker = next((c for c in df_beta.columns if '종목' in c or 'Ticker' in c), None)
        col_cur_w = next((c for c in df_beta.columns if '현재' in c or 'Current' in c), None)
        col_tgt_w = next((c for c in df_beta.columns if '목표' in c or 'Target' in c), None)
        col_owner = next((c for c in df_beta.columns if '소유자' in c or 'Owner' in c), None)
            # --- Data Prep & Aggregation ---
        if col_ticker and col_cur_w and col_tgt_w and col_owner:
            df_beta_calc = df_beta.copy()
            # Filter empty tickers
            df_beta_calc = df_beta_calc.dropna(subset=[col_ticker])
            df_beta_calc = df_beta_calc[df_beta_calc[col_ticker].astype(str).str.strip() != '']
            # Identify Value Column (Amount)
            col_eval_val = next((c for c in df_beta.columns if '평가금액' in c or '금액' in c or 'Eval' in c or 'Amount' in c), None)
            if not col_eval_val:
                 st.error("Cannot find 'Eval Value' column to calculate amounts.")
            else:
                for c in [col_cur_w, col_tgt_w, col_eval_val]:
                    df_beta_calc[c] = pd.to_numeric(df_beta_calc[c], errors='coerce').fillna(0)
                # Normalize decimals if percentages were > 1
                if df_beta_calc[col_tgt_w].max() > 1.0:
                    df_beta_calc[col_tgt_w] /= 100
                # --- CORE LOGIC: Per-Owner Rebalancing ---
                # 1. Total Equity per Owner
                owner_equity = df_beta_calc.groupby(col_owner)[col_eval_val].sum()
                # 2. Map Owner Equity to each row
                df_beta_calc['OwnerTotal'] = df_beta_calc[col_owner].map(owner_equity)
                # 3. Target Amount = OwnerTotal * TargetWeight
                df_beta_calc['TargetAmount'] = df_beta_calc['OwnerTotal'] * df_beta_calc[col_tgt_w]
                # 4. Diff Amount = Current - Target
                # If Current > Target, Positive Diff -> SELL
                # If Current < Target, Negative Diff -> BUY
                df_beta_calc['DiffAmount'] = df_beta_calc[col_eval_val] - df_beta_calc['TargetAmount']
                # 5. Diff Weight (for Chart)
                df_beta_calc['OwnerCurWeight'] = df_beta_calc[col_eval_val] / df_beta_calc['OwnerTotal']
                df_beta_calc['DiffWeight'] = df_beta_calc['OwnerCurWeight'] - df_beta_calc[col_tgt_w]
                # 6. Calc Tolerance (Relative Band: Target * 20%)
                df_beta_calc['Tolerance'] = df_beta_calc[col_tgt_w] * 0.20
                # Enforce Custom Sort
                custom_order = ['SPY', 'QQQ', 'GMF', 'VEA', 'BND', 'TIP', 'PDBC', 'GLD', 'VNQ', '달러', '원화']
                df_beta_calc['SortKey'] = df_beta_calc[col_ticker].apply(
                    lambda x: custom_order.index(x) if x in custom_order else 999
                )
                # Sort by Ticker then Owner
                df_beta_calc = df_beta_calc.sort_values(['SortKey', col_owner]).reset_index(drop=True)
                # Total Equity (Global)
                total_equity = df_beta_calc[col_eval_val].sum()
            # --- TABS ---
            t_rebal, t_attr, t_corr, t_risk = st.tabs(["Rebalancing", "Attribution", "Correlation", "Signals"])
            # 1. Rebalancing Tab
            with t_rebal:
                c1, c2 = st.columns([1.5, 1])
                with c1:
                    # Deviation Bar Chart (Horizontal)
                    # Label: Ticker (Owner)
                    # Label already created in Data Prep IF col_owner exists? 
                    # Re-check Data Prep. In Step 1386 replacement:
                    # df_beta_calc['Label'] IS NOT created there. It was in the Aggregation logic which I removed.
                    # So I must create it here.
                    if col_owner:
                        df_beta_calc['Label'] = df_beta_calc[col_ticker] + " (" + df_beta_calc[col_owner] + ")"
                    else:
                        df_beta_calc['Label'] = df_beta_calc[col_ticker]
                    # Status based on Relative Tolerance
                    def get_status(row):
                        w_diff = row['DiffWeight']
                        tol = row['Tolerance']
                        if w_diff > tol: return "Over"
                        elif w_diff < -tol: return "Under"
                        return "Normal"
                    df_beta_calc['Status'] = df_beta_calc.apply(get_status, axis=1)
                    fig_diff = px.bar(
                        df_beta_calc,
                        y='Label',
                        x='DiffWeight',
                        color='Status',
                        orientation='h',
                        title="Deviation from Target (Per Account)",
                        color_discrete_map={
                            "Over": "#FF5252",
                            "Under": "#4CAF50",
                            "Normal": "#AECBEB"
                        },
                        text_auto='.1%'
                    )
                    # Sort logic
                    sorted_labels = df_beta_calc['Label'].tolist()
                    fig_diff.update_yaxes(categoryorder='array', categoryarray=sorted_labels[::-1]) 
                    fig_diff.add_vline(x=0, line_width=1, line_color="white")
                    fig_diff.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        xaxis_title="Weight Difference",
                        yaxis_title=None,
                        xaxis=dict(tickformat=".0%")
                    )
                    st.plotly_chart(fig_diff, use_container_width=True)
                with c2:
                    st.markdown("#### Action Table (Per Account)")
                    st.caption(f"Total Equity: ₩{total_equity:,.0f} (Threshold: Target ±20%)")
                    def get_action_str(row):
                        d_amt = row['DiffAmount']
                        w_diff = row['DiffWeight']
                        tol = row['Tolerance']
                        cost = abs(d_amt)
                        fmt_cost = f"₩{cost:,.0f}"
                        if w_diff > tol: return f"SELL {fmt_cost}"
                        elif w_diff < -tol: return f"BUY {fmt_cost}"
                        return "-"
                    df_beta_calc['Action'] = df_beta_calc.apply(get_action_str, axis=1)
                    # Highlight Styles
                    def style_action(v):
                        if "SELL" in v: return 'color: #FF5252; font-weight: bold;'
                        elif "BUY" in v: return 'color: #4CAF50; font-weight: bold;'
                        return 'color: gray; opacity: 0.5;'
                    # Show Owner in Table if exists
                    cols_to_disp = [col_ticker, 'Action']
                    if col_owner:
                        cols_to_disp.insert(1, col_owner)
                    # Display with formatting
                    st.dataframe(
                        df_beta_calc[cols_to_disp].style.map(style_action, subset=['Action']),
                        use_container_width=True,
                        hide_index=True
                    )
                    st.markdown("""
                    <div style="text-align: right; color: #999999; font-size: 11px; margin-top: 5px;">
                    Diff Amount: 평가금액 - 목표금액 | Action: Diff > 0 매도, Diff < 0 매수 | Tolerance: 목표비중의 ±20%
                    </div>
                    """, unsafe_allow_html=True)
            # 2. Attribution Tab
            with t_attr:
                st.markdown("#### Profit Contribution by Asset")
                # Need detailed inventory data for '쇼호 β'
                if df_inv is not None:
                     # Filter for Shoho Beta
                     # Need correct column name for portfolio in inv
                     inv_port_col = next((c for c in df_inv.columns if '포트폴리오' in c or 'Portfolio' in c), None)
                     inv_pl_col = next((c for c in df_inv.columns if '손익' in c or 'Profit' in c or 'Gain' in c), None)
                     inv_ticker_col = next((c for c in df_inv.columns if '종목' in c or 'Ticker' in c), None)
                     if inv_port_col and inv_pl_col and inv_ticker_col:
                         df_attr = df_inv[df_inv[inv_port_col].str.contains('쇼호 β', na=False)].copy()
                         if not df_attr.empty:
                             # Group by Ticker
                             df_attr = df_attr.groupby(inv_ticker_col, as_index=False)[inv_pl_col].sum()
                             # Sort by custom order
                             df_attr['SortKey'] = df_attr[inv_ticker_col].apply(lambda x: custom_order.index(x) if x in custom_order else 999)
                             df_attr = df_attr.sort_values('SortKey')
                             df_attr['Color'] = df_attr[inv_pl_col].apply(lambda x: '#66bb6a' if x >= 0 else '#EB5E55')
                             fig_attr = px.bar(
                                 df_attr,
                                 x=inv_ticker_col,
                                 y=inv_pl_col,
                                 title="Total Profit/Loss Contribution (KRW)",
                                 text_auto=True
                             )
                             fig_attr.update_traces(marker_color=df_attr['Color'])
                             fig_attr.update_layout(
                                 plot_bgcolor='rgba(0,0,0,0)',
                                 paper_bgcolor='rgba(0,0,0,0)',
                                 xaxis_title=None,
                                 yaxis_title="Profit/Loss (KRW)"
                             )
                             st.plotly_chart(fig_attr, use_container_width=True)
                         else:
                             st.info("No holding details found for '쇼호 β'.")
                     else:
                         st.warning("Inventory columns missing.")
            # 3. Correlation Tab
            with t_corr:
                st.markdown("#### Asset Correlation Heatmap (1Y Daily)")
                st.caption("Fetches live data via yfinance. '원화' and '달러' excluded.")
                # Filter tickers valid for yfinance (exclude KRW/USD cash proxies if they are just cash)
                # Tickers: SPY, QQQ, GMF, VEA, BND, TIP, PDBC, GLD, VNQ
                # Note: '달러', '원화' are not tickers.
                # Also deduplicate keys (unique tickers only)
                valid_tickers = [t for t in df_beta_calc[col_ticker].unique() if t not in ['달러', '원화', '현금']]
                if st.button("Generate Correlation Matrix"):
                    with st.spinner(f"Fetching data for {len(valid_tickers)} assets..."):
                        if yf:
                            try:
                                # Try to use curl_cffi session if yfinance requires it
                                try:
                                    from curl_cffi import requests as cffi_requests
                                    # Impersonate Chrome to avoid rate limiting
                                    session = cffi_requests.Session(impersonate="chrome")
                                    # curl_cffi session verify=False
                                    session.verify = False
                                except ImportError:
                                    # Fallback to standard requests if curl_cffi missing
                                    import requests
                                    from requests.packages.urllib3.exceptions import InsecureRequestWarning
                                    import warnings
                                    warnings.simplefilter('ignore', InsecureRequestWarning)
                                    session = requests.Session()
                                    session.verify = False
                                data_frames = []
                                failed_tickers = []
                                progress_bar = st.progress(0)
                                for idx, t in enumerate(valid_tickers):
                                    try:
                                        # Use Ticker object with session
                                        ticker_obj = yf.Ticker(t, session=session)
                                        hist = ticker_obj.history(period="1y", interval="1d")
                                        if not hist.empty and 'Close' in hist.columns:
                                            s_close = hist['Close']
                                            s_close.name = t
                                            # Remove timezone
                                            if s_close.index.tz is not None:
                                                s_close.index = s_close.index.tz_localize(None)
                                            data_frames.append(s_close)
                                        else:
                                            # Sometimes rate limit helps to wait
                                            failed_tickers.append(t)
                                    except Exception as e:
                                        failed_tickers.append(f"{t}")
                                    progress_bar.progress((idx + 1) / len(valid_tickers))
                                progress_bar.empty()
                                if data_frames:
                                    # Merge
                                    yf_data = pd.concat(data_frames, axis=1)
                                    corr_matrix = yf_data.corr()
                                    # Plot
                                    fig_corr = px.imshow(
                                        corr_matrix,
                                        text_auto=".2f",
                                        aspect="auto",
                                        color_continuous_scale="RdBu_r",
                                        zmin=-1, zmax=1,
                                        title=f"Asset Correlation Matrix ({len(data_frames)} Tickers)"
                                    )
                                    fig_corr.update_layout(
                                        plot_bgcolor='rgba(0,0,0,0)',
                                        paper_bgcolor='rgba(0,0,0,0)'
                                    )
                                    st.plotly_chart(fig_corr, use_container_width=True)
                                    if failed_tickers:
                                        st.warning(f"Could not fetch: {', '.join(failed_tickers)}")
                                else:
                                    st.error("No data fetched. Check tickers or network.")
                                    if failed_tickers:
                                        st.write("Failures:", failed_tickers)
                            except Exception as e:
                                st.error(f"Critical Error: {e}")
                                st.write("Tickers attempted:", valid_tickers)
            # 4. Signals Tab (Autocorrelation)
            with t_risk:
                st.markdown("#### Portfolio Autocorrelation (Trend Strength)")
                st.caption("Checks if portfolio returns are correlated with past returns. < 0 means trend breakdown.")
                if df_hist is not None and not df_hist.empty and '쇼호 β' in df_hist.columns:
                     # Calculate Daily Returns
                     series = df_hist.set_index('날짜')['쇼호 β'].sort_index()
                     returns = series.pct_change().dropna()
                     # Calculate Autocorrelation for lags 1 to 252 (1 year)
                     lags = range(1, 60) # 2 months view usually enough for momentum check
                     autocorrs = [returns.autocorr(lag=l) for l in lags]
                     df_ac = pd.DataFrame({'Lag': lags, 'Autocorrelation': autocorrs})
                     fig_ac = px.line(
                         df_ac, x='Lag', y='Autocorrelation',
                         title="Autocorrelation vs Lag (Days)",
                         markers=True
                     )
                     fig_ac.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Zero Correlation")
                     # Highlight danger zones
                     fig_ac.update_traces(line_color="#AECBEB")
                     fig_ac.update_layout(
                         plot_bgcolor='rgba(0,0,0,0)', 
                         paper_bgcolor='rgba(0,0,0,0)',
                         xaxis_title="Lag (Days)",
                         yaxis_title="Correlation Coefficient"
                     )
                     st.plotly_chart(fig_ac, use_container_width=True)
                     # Simple Signal Interpretation
                     # e.g. if Lag 1 autocorrelation is negative -> Mean Reversion?
                     # if Lag 1 is positive -> Momentum?
                     ac_1 = autocorrs[0] if autocorrs else 0
                     st.info(f"**Lag-1 Autocorrelation**: {ac_1:.3f}")
                     if ac_1 > 0.05:
                         st.success("Currently in **Momentum** phase (Positive Correlation). Trend Likely to continue.")
                     elif ac_1 < -0.05:
                         st.warning("Currently in **Mean Reversion** phase (Negative Correlation). Volatility Expected.")
                     else:
                         st.write("Random Walk phase (No significant correlation).")
        else:
             st.warning("Beta Portfolio columns not found.")
# --- Page 6: Historical Analysis ---
# --- Page 6: Historical Analysis ---
elif page == "Historical Analysis":
    st.markdown("<h1 style='font-size: 2.5rem; margin-bottom: 30px;'>Historical Analysis</h1>", unsafe_allow_html=True)
    # Create Tabs
    tab_perf, tab_corr, tab_mdd = st.tabs(["Performance Attribution", "Correlation Matrix", "Drawdown (MDD)"])
    # --- TAB 1: Performance Attribution (Existing Logic) ---
    with tab_perf:
        st.caption("Total Profit = Dividend + Realized Profit")
        if df_inv is not None and not df_inv.empty:
            # 1. Map Columns
            col_port =   next((c for c in df_inv.columns if '포트폴리오' in c or 'Portfolio' in c), None)
            col_ticker = next((c for c in df_inv.columns if '종목' in c or 'Ticker' in c), None)
            col_div =    next((c for c in df_inv.columns if '배당수익' in c or 'Dividend' in c), None)
            col_real =   next((c for c in df_inv.columns if '확정손익' in c or 'Realized' in c), None)
            if col_port and col_ticker and col_div and col_real:
                # 2. Select & Rename
                df_hist_view = df_inv[[col_port, col_ticker, col_div, col_real]].copy()
                df_hist_view.columns = ['Portfolio', 'Ticker', 'Dividend', 'Realized']
                # Numeric conversion
                for c in ['Dividend', 'Realized']:
                    df_hist_view[c] = pd.to_numeric(df_hist_view[c], errors='coerce').fillna(0)
                # 3. Aggregate
                df_hist_view = df_hist_view.groupby(['Portfolio', 'Ticker'], as_index=False)[['Dividend', 'Realized']].sum()
                df_hist_view['TotalProfit'] = df_hist_view['Dividend'] + df_hist_view['Realized']
                # 4. Filter by Portfolio (Default: Shoho Alpha)
                all_ports = sorted(df_hist_view['Portfolio'].unique().tolist())
                default_selection = ['쇼호 α'] if '쇼호 α' in all_ports else [all_ports[0]] if all_ports else []
                sel_ports = st.multiselect("Select Portfolio", all_ports, default=default_selection)
                # 5. Global Controls (Best/Worst, Top N)
                c_sort1, c_sort2 = st.columns([1,1])
                with c_sort1:
                    view_type = st.radio("View Type", ["Best Performers", "Worst Performers"], horizontal=True)
                with c_sort2:
                    top_n = st.slider("Number of items", 5, 30, 10)
                ascending = True if view_type == "Worst Performers" else False
                # 6. Render per Portfolio
                if sel_ports:
                    for port in sel_ports:
                        st.markdown(f"### {port}")
                        # Filter for specific portfolio
                        df_port = df_hist_view[df_hist_view['Portfolio'] == port]
                        # Filter Zero Results
                        df_port = df_port[df_port['TotalProfit'] != 0]
                        # Sort
                        df_sorted = df_port.sort_values('TotalProfit', ascending=ascending).head(top_n)
                        if df_sorted.empty:
                            st.info(f"No data for {port}")
                            st.markdown("---")
                            continue
                        # Chart Prep
                        df_long = df_sorted.melt(id_vars=['Ticker', 'Portfolio'], value_vars=['Dividend', 'Realized'], var_name='Type', value_name='Value')
                        # Sort order for chart
                        df_long['Ticker'] = pd.Categorical(df_long['Ticker'], categories=df_sorted['Ticker'].tolist(), ordered=True)
                        df_long = df_long.sort_values('Ticker')
                        # Chart
                        fig_hist = px.bar(
                            df_long,
                            x='Ticker',
                            y='Value',
                            color='Type',
                            title=f"{view_type} - {port} (Top {top_n})",
                            text='Value',
                            color_discrete_map={
                                'Dividend': '#fbc02d', # Gold
                                'Realized': '#4caf50', # Green
                            }
                        )
                        fig_hist.update_traces(texttemplate='%{value:,.0f}', textposition='inside')
                        fig_hist.update_layout(
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)',
                            barmode='relative',
                            yaxis_title="Profit (KRW)",
                            xaxis_title=None,
                            legend_title="Profit Type"
                        )
                        st.plotly_chart(fig_hist, use_container_width=True)
                        # Table
                        st.markdown(f"**{port} - Breakdown Table**")
                        def style_profit(val):
                            if not isinstance(val, (int, float)):
                                return ''
                            color = '#66bb6a' if val >= 0 else '#EB5E55'
                            return f'color: {color}'
                        st.dataframe(
                            df_sorted.style.format("{:,.0f}", subset=['Dividend', 'Realized', 'TotalProfit'])
                            .map(style_profit, subset=['Dividend', 'Realized', 'TotalProfit']),
                            use_container_width=True
                        )
                        st.markdown("---")
                
                    st.markdown("""
                    <div style="text-align: right; color: #999999; font-size: 11px; margin-top: 5px;">
                    Total PnL: 배당수익 + 실현손익 | Dividend: 세후 배당, 이자 합계 | Realized: 매도 확정 손익 합계
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("Please select at least one portfolio.")
            else:
                st.warning("Required columns (Dividend, Realized) not found in Inventory data.")
        else:
            st.info("No asset data available.")
    # --- TAB 2: Correlation Matrix ---
    with tab_corr:
        st.caption("How closely do your portfolios move together? (1.0 = Identical, -1.0 = Opposite)")
        if df_hist is not None and not df_hist.empty:
            df_hist_calc = df_hist.set_index('날짜').sort_index()
            # Filter numeric columns (portfolios)
            valid_ports = [p for p in portfolios if p in df_hist_calc.columns]
            if valid_ports:
                df_prices = df_hist_calc[valid_ports]
                df_returns = df_prices.pct_change().dropna()
                corr_matrix = df_returns.corr()
                fig_corr = px.imshow(
                    corr_matrix,
                    text_auto=".2f",
                    aspect="auto",
                    color_continuous_scale="RdBu_r",
                    zmin=-1, zmax=1,
                    labels=dict(x="Portfolio", y="Portfolio", color="Correlation")
                )
                fig_corr.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=500)
                st.plotly_chart(fig_corr, use_container_width=True)
                st.info("High (>0.7): Move together | Low (<0.3): Diversified | Negative: Hedging")
            else:
                st.warning("No portfolio history data available (Columns missing).")
        else:
            st.warning("No historical data available.")
    # --- TAB 3: Drawdown (MDD) ---
    with tab_mdd:
        st.caption("Visualizing the decline from the historical peak. How 'deep' did we go?")
        if df_hist is not None and not df_hist.empty:
            df_hist_calc = df_hist.set_index('날짜').sort_index()
            valid_ports = [p for p in portfolios if p in df_hist_calc.columns]
            if valid_ports:
                df_prices = df_hist_calc[valid_ports]
                # Calculate Drawdown
                rolling_max = df_prices.cummax()
                drawdown = (df_prices - rolling_max) / rolling_max
                # Tidy format
                df_dd_tidy = drawdown.reset_index().melt(id_vars='날짜', var_name='Portfolio', value_name='Drawdown')
                fig_dd = go.Figure()
                for p in valid_ports:
                    subset = df_dd_tidy[df_dd_tidy['Portfolio'] == p]
                    fig_dd.add_trace(go.Scatter(
                        x=subset['날짜'],
                        y=subset['Drawdown'],
                        mode='lines',
                        name=p,
                        fill='tozeroy',
                        line=dict(width=1)
                    ))
                fig_dd.update_layout(
                    template="plotly_dark",
                    title="Historical Drawdown (from Peak)",
                    xaxis_title="Date",
                    yaxis_title="Drawdown (%)",
                    yaxis_tickformat=".1%",
                    hovermode="x unified",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_dd, use_container_width=True)
                # Stat Table
                mdd_max = drawdown.min()
                st.write("Max Drawdown Records")
                st.dataframe(pd.DataFrame(mdd_max, columns=["Max Drawdown"]).sort_values("Max Drawdown").style.format("{:.2%}"), use_container_width=True)
            else:
                st.warning("No portfolio data for MDD.")
        else:
            st.warning("No historical data available.")
