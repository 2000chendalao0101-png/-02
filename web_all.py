import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime

# --- 1️⃣ 基础配置与隐藏菜单 ---
st.set_page_config(page_title="AI量化多因子分析系统 V4 (移动端优化)", page_icon="📱", layout="wide")

# 依然保留隐藏菜单，让界面像个 App
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            .stApp > header {display: none;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 2️⃣ 密码保护 ---
def check_password():
    actual_password = st.secrets.get("app_password") 
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    def password_entered():
        if st.session_state["password"] == actual_password:
            st.session_state.password_correct = True
            del st.session_state["password"]
        else:
            st.session_state.password_correct = False
    if not st.session_state.password_correct:
        st.text_input("🔑 请输入访问密码", type="password", on_change=password_entered, key="password")
        return False
    else:
        return True

if not check_password():
    st.stop()

# ==========================================
#      👇 核心逻辑 👇
# ==========================================

def process_ticker(code):
    code = code.strip().upper()
    if code.isdigit() and len(code) == 5:
        if code.startswith("0"): return f"{code[1:]}.HK" 
        return f"{code}.HK"
    if code.isdigit() and len(code) == 6:
        if code.startswith("6"): return f"{code}.SS"
        else: return f"{code}.SZ"
    return code

@st.cache_data(ttl=3600)
def get_stock_data_v4(user_code):
    try:
        yf_code = process_ticker(user_code)
        stock = yf.Ticker(yf_code)
        df = stock.history(period="2y")
        if df.empty: return None, f"⚠️ 未找到数据: {yf_code}"
        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        if 'date' in df.columns: df['time_key'] = df['date'].dt.strftime('%Y-%m-%d')
        else: return None, "数据异常"
        needed_cols = ['time_key', 'open', 'high', 'low', 'close', 'volume']
        df = df[[c for c in needed_cols if c in df.columns]]
        return df, f"成功 (Yahoo: {yf_code})"
    except Exception as e:
        return None, f"报错: {str(e)}"

def calculate_indicators(df):
    try:
        close = df['close'].astype(float)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = (dif - dea) * 2
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        df['BB_Middle'] = close.rolling(window=20).mean()
        std_dev = close.rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (2 * std_dev)
        df['BB_Lower'] = df['BB_Middle'] - (2 * std_dev)
        return df
    except: return df

# --- 📱 界面布局 (移动端优化版) ---
# 把登出按钮放在右上角一个小角落，或者直接放在最下面
if st.button("🔒 退出", help="点击退出登录"):
    st.session_state.password_correct = False
    st.rerun()

st.title("📱 AI量化多因子分析系统 V4")

# 👇【关键修改】直接在主页面显示搜索框，而不是 Sidebar
c1, c2 = st.columns([3, 1]) # 分两列，左边输入框，右边按钮
with c1:
    stock_code = st.text_input("请输入股票代码", value="00700", label_visibility="collapsed", placeholder="输入代码 (如 00700)")
with c2:
    run_btn = st.button("🚀 分析", type="primary")

# --- 结果展示区 ---
if run_btn:
    with st.spinner(f"正在分析 {stock_code}..."):
        df, msg = get_stock_data_v4(stock_code)

    if df is not None:
        st.success(f"✅ {msg}")
        df = calculate_indicators(df)
        if len(df) > 200: df = df.tail(200).reset_index(drop=True)
        curr = df.iloc[-1]
        
        # 手机端适配：使用 container 也就是纵向排列，而不是 4列横排
        # 但 Streamlit 在手机上会自动把 columns 变成堆叠，所以保留 columns 写法也没事
        st.divider()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💰 收盘", f"{curr['close']:.2f}")
        k2.metric("📈 RSI", f"{curr['RSI']:.2f}")
        trend = "🔴" if curr['MACD_Hist'] > 0 else "🟢"
        k3.metric("MACD", trend, f"{curr['MACD_Hist']:.3f}")
        b_pos = (curr['close'] - curr['BB_Lower']) / (curr['BB_Upper'] - curr['BB_Lower']) * 100 if curr['BB_Upper'] != curr['BB_Lower'] else 50
        k4.metric("布林位置", f"{b_pos:.0f}%")

        st.line_chart(df[['time_key', 'close', 'BB_Upper', 'BB_Lower']].set_index('time_key'), color=["#0000FF", "#FF0000", "#00FF00"])

        # 深度报告
        macd_text = "上升趋势 🔴" if curr['MACD_Hist'] > 0 else "下跌趋势 🟢"
        final_signal = "⏸️ 观望"
        color = "blue"
        if curr['close'] < curr['BB_Lower'] and curr['RSI'] < 30:
            final_signal = "🚀 抄底机会"
            color = "green"
        elif curr['RSI'] > 70:
            final_signal = "⚠️ 止盈风险"
            color = "red"
            
        st.info(f"**分析结论**：{macd_text} | 建议：:{color}[**{final_signal}**]")
        
        st.dataframe(df.sort_values('time_key', ascending=False).head(5), use_container_width=True)
    else:
        st.error(msg)


