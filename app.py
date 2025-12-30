import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from modules import data_loader

# --- Page Config ---
st.set_page_config(
    page_title="가족 자산 대시보드",
    layout="wide"
)

# --- Password Protection ---
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["general"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "비밀번호를 입력하세요 (Password)", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input(
            "비밀번호를 입력하세요 (Password)", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 비밀번호가 틀렸습니다.")
        return False
    else:
        # Password correct.
        return True

if not check_password():
    st.stop()

# --- Styling ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Nanum+Gothic:wght@400;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Nanum Gothic', sans-serif !important;
    }
    
    .metric-container {
        border: 1px solid #333;
        border-radius: 8px;
        padding: 10px;
        background-color: #0e1117;
    }
    .big-font { font-size: 1.2rem; font-weight: bold; }

    /* Mobile Responsiveness Tweaks */
    @media (max-width: 768px) {
        /* Force columns to stack vertically on small screens */
        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 auto !important;
            min-width: 100% !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# --- Load Data ---
data_map = data_loader.load_data()

if not data_map:
    st.error("Failed to load data. Please check connections.")
    st.stop()

df_hist = data_map['history']
df_cagr = data_map['cagr']
df_inv = data_map['inventory']
df_beta = data_map['beta_plan']

# --- Sidebar ---
st.sidebar.header("자산 모니터링")
st.sidebar.caption("최근 업데이트: " + (df_hist['날짜'].iloc[-1].strftime('%Y-%m-%d') if not df_hist.empty else "N/A"))

# --- 1. Top Section: Scoreboard (CAGR & DoD) ---
st.subheader("🚀 포트폴리오 성과")

# Calculate DoD
dod_data = data_loader.calculate_dod(df_hist)

# Identify portfolios common to both or just use known list
# Hardcoded mostly to match user request "5개 가족 포트폴리오"
# Expected headers in History: 쇼호 α, 쇼호 β, 조연재, 조이재, 박행자
portfolios = ['쇼호 α', '쇼호 β', '조연재', '조이재', '박행자']

cols = st.columns(len(portfolios))
for i, port in enumerate(portfolios):
    with cols[i]:
        # Get Current Value & DoD
        if port in dod_data:
            val = dod_data[port]['value']
            diff = dod_data[port]['diff']
            pct = dod_data[port]['pct']
            
            # Get CAGR (Look up in df_cagr)
            # Robust lookup for CAGR
            cagr_val = 0.0
            
            # 1. Identify Key Columns
            col_port = next((c for c in df_cagr.columns if 'Portfolio' in c or '포트폴리오' in c or '이름' in c or '구분' in c or '소유자' in c), None)
            col_cagr = next((c for c in df_cagr.columns if 'CAGR' in c or '수익률' in c or '연환산' in c), None)
            
            if col_port and col_cagr:
                # 2. Try Exact Match
                match = df_cagr[df_cagr[col_port] == port]
                if match.empty:
                    # 3. Try removing spaces (e.g. '쇼호 α' -> '쇼호α')
                    port_nospace = port.replace(" ", "")
                    # Create temporary series for comparison
                    names_nospace = df_cagr[col_port].astype(str).str.replace(" ", "")
                    match_idx = names_nospace[names_nospace == port_nospace].index
                    if not match_idx.empty:
                        match = df_cagr.loc[match_idx]
                
                if not match.empty:
                    val_raw = match[col_cagr].iloc[0]
                    # Ensure numeric
                    if isinstance(val_raw, str):
                         val_raw = float(val_raw.replace('%', '').replace(',', '')) / 100.0 if '%' in val_raw else float(val_raw)
                    cagr_val = val_raw
            
            st.metric(
                label=port,
                value=f"₩{val:,.0f}",
                delta=f"{diff:,.0f} ({pct:+.2%})",
                help=f"CAGR: {cagr_val:.2%}" # Show CAGR in tooltip or separate line
            )
            st.caption(f"**CAGR**: `{cagr_val:.2%}`")

st.markdown("---")

# --- 2. Main Charts: Asset & Index Trend ---
st.subheader("📈 자산 및 지수 추이")

tab_asset, tab_idx = st.tabs(["💰 자산 추이", "📊 인덱스 추이 (Base: 2025.09.22)"])

# Fix for Plotly TypeError: Convert to epoch milliseconds for robustness
baseline_ts = pd.Timestamp("2025-09-22")
baseline_date = baseline_ts.value // 10**6  # Convert ns to ms for Plotly date axis compatibility

with tab_asset:
    # Plot each portfolio value over time
    if not df_hist.empty:
        fig_asset = go.Figure()
        for port in portfolios:
            if port in df_hist.columns:
                fig_asset.add_trace(go.Scatter(
                    x=df_hist['날짜'], 
                    y=df_hist[port], 
                    mode='lines', 
                    name=port
                ))
        
        # Add VLine
        fig_asset.add_vline(x=baseline_date, line_width=1, line_dash="dash", line_color="yellow", annotation_text="Base: 2025.09.22")
        fig_asset.update_layout(
            template="plotly_dark", 
            title="포트폴리오 자산 추이",
            xaxis_title="날짜",
            yaxis_title="평가액 (원)",
            hovermode="x unified"
        )
        st.plotly_chart(fig_asset, use_container_width=True)

with tab_idx:
    # Plot index columns (ending in _idx)
    # Mapping port name to its idx col (e.g., 쇼호α -> 쇼호α_idx)
    if not df_hist.empty:
        fig_idx = go.Figure()
        for port in portfolios:
            idx_col = f"{port}_idx"
            if idx_col in df_hist.columns:
                fig_idx.add_trace(go.Scatter(
                    x=df_hist['날짜'], 
                    y=df_hist[idx_col], 
                    mode='lines', 
                    name=port
                ))
        
        fig_idx.add_vline(x=baseline_date, line_width=1, line_dash="dash", line_color="yellow", annotation_text="Start")
        fig_idx.add_hline(y=100, line_width=1, line_color="gray")
        fig_idx.update_layout(
            template="plotly_dark", 
            title="기준 지수 성과 비교 (Base=100)",
            xaxis_title="날짜",
            yaxis_title="지수",
            hovermode="x unified"
        )
        st.plotly_chart(fig_idx, use_container_width=True)

# --- 3. Beta Portfolio Rebalancing Zone ---
st.markdown("---")
st.subheader("⚖️ 베타 포트폴리오 리밸런싱 (쇼호β)")

if df_beta is not None and not df_beta.empty:
    # Assume cols: 'Ticker', 'CurrentWeight', 'TargetWeight'
    # Adapt to Korean headers if necessary
    # Let's standardize in data_loader but here we check what we have.
    
    # Check required columns
    # We might need to map Korean headers to English for logic if not done in loader
    # In loader, I added _clean_numeric_cols but didn't rename.
    # Let's check keys.
    
    # For now, let's assume specific columns exist or fallback.
    # User said: "베타포트폴리오': '쇼호β' 전용 목표 비중 및 현재 비중 데이터 포함."
    
    # Let's try to interpret the DF columns dynamically
    col_ticker = next((c for c in df_beta.columns if '종목' in c or 'Ticker' in c), None)
    col_cur_w = next((c for c in df_beta.columns if '현재' in c or 'Current' in c), None)
    col_tgt_w = next((c for c in df_beta.columns if '목표' in c or 'Target' in c), None)
    col_owner = next((c for c in df_beta.columns if '소유자' in c or 'Owner' in c), None)
    
    if col_ticker and col_cur_w and col_tgt_w:
        df_beta['Diff'] = df_beta[col_cur_w] - df_beta[col_tgt_w]
        
        c_chart, c_table = st.columns([1, 2])
        
        with c_chart:
            # Donut Chart for Current Allocation
            fig_donut = px.pie(
                df_beta, 
                names=col_ticker, 
                values=col_cur_w, 
                hole=0.4,
                title="현재 자산 배분"
            )
            st.plotly_chart(fig_donut, use_container_width=True)
            
        with c_table:
            # Table with Alerts
            st.write("#### 리밸런싱 신호 (허용범위 ±5%)")
            
            def highlight_beta(row):
                val = row['Diff']
                if val > 0.05:
                    # Sell: Soft Red background, White text
                    return ['background-color: #ef5350; color: white; font-weight: bold;'] * len(row) 
                elif val < -0.05:
                    # Buy: Soft Green background, White text
                    return ['background-color: #66bb6a; color: white; font-weight: bold;'] * len(row) 
                return [''] * len(row)

            # Format for display
            display_beta = df_beta.copy()
            
            # Normalize to 0.0-1.0 if it looks like 0-100
            # Ensure columns are numeric just in case
            cols_to_check = [col_cur_w, col_tgt_w, 'Diff']
            for c in cols_to_check:
                display_beta[c] = pd.to_numeric(display_beta[c], errors='coerce').fillna(0)

            if display_beta[col_tgt_w].max() > 1.0: # Likely 0-100 scale
                display_beta[col_cur_w] /= 100
                display_beta[col_tgt_w] /= 100
                display_beta['Diff'] /= 100
            
            # Define formatting
            format_dict = {
                col_cur_w: '{:.1%}',
                col_tgt_w: '{:.1%}',
                'Diff': '{:+.1%}'
            }

            cols_to_show = [col_ticker, col_cur_w, col_tgt_w, 'Diff']
            if col_owner:
                 cols_to_show.insert(0, col_owner)

            st.dataframe(
                display_beta[cols_to_show].style.format(format_dict).apply(highlight_beta, axis=1),
                use_container_width=True,
                hide_index=True
            )
            
            # Actionable Alerts
            alarms = []
            for idx, row in df_beta.iterrows():
                diff = row['Diff']
                ticker = row[col_ticker]
                owner_info = f"[{row[col_owner]}] " if col_owner and pd.notna(row[col_owner]) else ""
                
                # Re-check scale
                threshold = 0.05 if row[col_tgt_w] <= 1.0 else 5.0
                
                if diff > threshold:
                    alarms.append(f"🔴 **매도 (SELL)**: {owner_info}{ticker} 비중 초과 ({diff:.1%} > +5%)")
                elif diff < -threshold:
                    alarms.append(f"🟢 **매수 (BUY)**: {owner_info}{ticker} 비중 미달 ({diff:.1%} < -5%)")
            
            if alarms:
                for a in alarms:
                    if "SELL" in a:
                        st.error(a)
                    else:
                        st.success(a)
    else:
        st.warning("Beta Portfolio columns not found. Check sheet headers.")


# --- 4. Asset Inventory ---
st.markdown("---")
st.subheader("📦 전체 자산 상세")

if df_inv is not None and not df_inv.empty:
    with st.expander("상세 보기", expanded=True):
        # 1. Define Column Mapping (Sheet Header -> Display Name)
        # We try to find the best matching column in the sheet
        col_map_targets = {
            '포트폴리오 구분': ['포트폴리오', 'Portfolio', '구분'],
            '종목': ['종목명', '종목', 'Item', 'Ticker'],
            # Removed 'Owner' mapping
            '평가금액': ['평가금액', 'EvalValue', 'Amount'],
            '자산비중': ['자산비중', '비중', 'Weight'],
            '총평가손익': ['총평가손익', '평가손익', '손익', 'GainLoss']
        }
        
        final_cols = []
        rename_map = {}
        
        for target, candidates in col_map_targets.items():
            found = next((c for c in df_inv.columns if c in candidates or any(cand in c for cand in candidates)), None)
            if found:
                final_cols.append(found)
                rename_map[found] = target
        
        # 2. Filter & Rename
        if final_cols:
            df_view = df_inv[final_cols].rename(columns=rename_map)
            
            # Ensure numeric columns before grouping
            numeric_cols = ['평가금액', '자산비중', '총평가손익']
            for nc in numeric_cols:
                if nc in df_view.columns:
                    df_view[nc] = pd.to_numeric(df_view[nc], errors='coerce').fillna(0)

            # 3. Aggregate by Portfolio and Ticker
            group_cols = [c for c in ['포트폴리오 구분', '종목'] if c in df_view.columns]
            if group_cols:
                 df_view = df_view.groupby(group_cols, as_index=False).sum()
            
            # Sort by Portfolio (Custom Order) then Evaluation Value (Desc)
            sort_cols = []
            ascending_vals = []
            
            if '포트폴리오 구분' in df_view.columns:
                # Use the 'portfolios' list defined earlier for custom order
                # Ensure existing values map to these categories
                df_view['포트폴리오 구분'] = pd.Categorical(
                    df_view['포트폴리오 구분'], 
                    categories=portfolios, 
                    ordered=True
                )
                sort_cols.append('포트폴리오 구분')
                ascending_vals.append(True)
            
            if '평가금액' in df_view.columns:
                sort_cols.append('평가금액')
                ascending_vals.append(False)
                
            if sort_cols:
                df_view = df_view.sort_values(by=sort_cols, ascending=ascending_vals)

            # 4. Filtering by Portfolio
            if '포트폴리오 구분' in df_view.columns:
                ports = list(df_view['포트폴리오 구분'].unique())
                sel_port = st.multiselect("포트폴리오 필터", ports, default=ports)
                df_view = df_view[df_view['포트폴리오 구분'].isin(sel_port)]

            # Numeric conversion handled before grouping
            
            # Handle Percentage Scaling (0.12 -> 12)
            if '자산비중' in df_view.columns:
                if df_view['자산비중'].max() <= 1.0:
                     df_view['자산비중'] *= 100
            
            # Cast Amount/Profit to int for clean display
            int_cols = ['평가금액', '총평가손익']
            for ic in int_cols:
                if ic in df_view.columns:
                    df_view[ic] = df_view[ic].astype(int)

            # Determine View Mode (Mobile Card vs Table)
            mobile_view = st.toggle("📱 모바일 카드 뷰 (카드형 보기)", value=True)

            if mobile_view:
                for index, row in df_view.iterrows():
                    # Format values
                    fmt_amt = "{:,.0f}".format(row['평가금액'])
                    fmt_profit = "{:+,.0f}".format(row['총평가손익'])
                    fmt_weight = "{:.0f}%".format(row['자산비중']) if '자산비중' in row else "-"
                    
                    # Profit Color
                    profit_color = "#ff4b4b" if row['총평가손익'] < 0 else "#4CAF50" # Red for loss, Green for profit
                    
                    card_html = f"""
                    <div style="
                        background: linear-gradient(135deg, #2b2b2b 0%, #1a1a1a 100%);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        border-radius: 15px;
                        padding: 20px;
                        margin-bottom: 15px;
                        box-shadow: 0 10px 20px rgba(0,0,0,0.15);
                        transition: transform 0.2s;
                    ">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                            <span style="font-size: 1.15rem; font-weight: 700; color: #F5F5F7;">{row['종목']}</span>
                            <span style="font-size: 0.8rem; color: #D1D1D6; background: rgba(255,255,255,0.1); padding: 4px 10px; border-radius: 12px; font-weight: 500;">{row['포트폴리오 구분']}</span>
                        </div>
                        <div style="font-size: 1.6rem; font-weight: 800; color: #FFFFFF; margin-bottom: 10px; letter-spacing: -0.5px;">
                            ₩{fmt_amt}
                        </div>
                        <hr style="border: 0; height: 1px; background-image: linear-gradient(to right, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0)); margin-bottom: 10px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.95rem;">
                            <span style="color: {profit_color}; font-weight: 700;">{fmt_profit}</span>
                            <span style="color: #8E8E93; font-weight: 500;">자산 비중 {fmt_weight}</span>
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)

            else:
                # Apply formatting using Pandas Styler to ensure commas are shown
                # This is the most reliable way to get thousand separators
                styler_view = df_view.style.format({
                    "평가금액": "{:,.0f}",
                    "총평가손익": "{:,.0f}",
                    "자산비중": "{:.0f}%" 
                })

                # Display with Styler
                st.dataframe(
                    styler_view,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "평가금액": st.column_config.NumberColumn(label="평가금액"),
                        "총평가손익": st.column_config.NumberColumn(label="총평가손익"),
                        "자산비중": st.column_config.NumberColumn(label="자산비중")
                    }
                )
        else:
            st.warning("요청하신 컬럼을 찾을 수 없습니다. 원본 데이터를 표시합니다.")
            st.dataframe(df_inv)

