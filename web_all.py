import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime

# --- 1️⃣ 基础配置与隐藏菜单 ---
st.set_page_config(page_title="全球量化 V4 (云端版)", page_icon="☁️", layout="wide")

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            .stApp > header {display: none;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 2️⃣ 密码保护 (带缓存，防止刷新丢失) ---
def check_password():
    # 👇 如果你还没设 Secrets，先临时用这个明文密码，部署后记得去后台改 Secrets
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
#      👇 V4 核心：带缓存的数据获取引擎 👇
# ==========================================

# 🛠️ 辅助函数：把用户输入的简单代码，转成雅虎能看懂的代码
def process_ticker(code):
    code = code.strip().upper()
    
    # 1. 港股 (5位数字 -> 0XXXX.HK)
    if code.isdigit() and len(code) == 5:
        # 雅虎的港股代码有些需要去零，有些不需要，通常 00700 -> 0700.HK
        if code.startswith("0"):
            return f"{code[1:]}.HK" 
        return f"{code}.HK"
    
    # 2. A股 (6位数字 -> XXXXXX.SS 或 .SZ)
    if code.isdigit() and len(code) == 6:
        # 简单判断：60/68开头是上海(.SS)，00/30开头是深圳(.SZ)
        if code.startswith("6"):
            return f"{code}.SS"
        else:
            return f"{code}.SZ"
            
    # 3. 美股 (纯字母 -> 直接用)
    return code

# 🚀 核心：使用 @st.cache_data 防止重复请求被封 IP
@st.cache_data(ttl=3600)  # ttl=3600 表示数据缓存 1 小时
def get_stock_data_v4(user_code):
    """
    使用 yfinance 获取数据，专门针对海外服务器优化
    """
    try:
        yf_code = process_ticker(user_code)
        
        # 获取数据 (只要最近 2 年，保证速度)
        stock = yf.Ticker(yf_code)
        df = stock.history(period="2y")
        
        if df.empty:
            return None, f"⚠️ 雅虎财经未返回数据: {yf_code} (请检查代码或退市)"
            
        # 格式清洗
        df = df.reset_index()
        # 雅虎列名: Date, Open, High, Low, Close, Volume
        df.columns = [c.lower() for c in df.columns] # 转小写
        
        # 雅虎的 Date 列带有因时区导致的时间戳，需要清洗成纯日期字符串
        if 'date' in df.columns:
            df['time_key'] = df['date'].dt.strftime('%Y-%m-%d')
        else:
            return None, "数据格式异常: 缺少日期列"

        # 只要核心列
        needed_cols = ['time_key', 'open', 'high', 'low', 'close', 'volume']
        # 容错处理
        df = df[[c for c in needed_cols if c in df.columns]]
        
        return df, f"成功 (源: Yahoo {yf_code})"
        
    except Exception as e:
        return None, f"雅虎接口报错: {str(e)}"

# --- 🧮 指标计算 ---
def calculate_indicators(df):
    try:
        close = df['close'].astype(float)
        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = (dif - dea) * 2
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        # BB
        df['BB_Middle'] = close.rolling(window=20).mean()
        std_dev = close.rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (2 * std_dev)
        df['BB_Lower'] = df['BB_Middle'] - (2 * std_dev)
        return df
    except Exception as e:
        st.error(f"指标计算出错: {e}")
        return df

# --- 主界面 ---
with st.sidebar:
    if st.button("🔒 退出登录"):
        st.session_state.password_correct = False
        st.rerun()

st.title("☁️ 全球量化 V4 (云端稳定版)")
st.caption("数据源: Yahoo Finance (US Server Optimized)")

with st.sidebar:
    st.header("🔍 股票查询")
    stock_code = st.text_input("输入代码", value="00700", help="输入原始代码即可，系统会自动转换后缀")
    run_btn = st.button("🚀 生成报告", type="primary")

if run_btn:
    with st.spinner(f"正在连接雅虎财经 (US) 拉取 {stock_code}..."):
        df, msg = get_stock_data_v4(stock_code)

    if df is not None:
        st.success(f"✅ {msg}")
        
        df = calculate_indicators(df)
        if len(df) > 200: df = df.tail(200).reset_index(drop=True)
        curr = df.iloc[-1]
        
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 最新收盘", f"{curr['close']:.2f}")
        val_rsi = curr['RSI'] if not pd.isna(curr['RSI']) else 0
        c2.metric("📈 RSI 强度", f"{val_rsi:.2f}")
        
        val_macd = curr['MACD_Hist'] if not pd.isna(curr['MACD_Hist']) else 0
        trend = "多头 🔴" if val_macd > 0 else "空头 🟢"
        c3.metric("🌊 MACD 趋势", trend, f"{val_macd:.3f}")
        
        b_up, b_low = curr['BB_Upper'], curr['BB_Lower']
        if b_up != b_low and not pd.isna(b_up):
            b_pos = (curr['close'] - b_low) / (b_up - b_low) * 100
        else:
            b_pos = 50.0
        c4.metric("📊 布林带位置", f"{b_pos:.1f}%")

        # 绘图
        st.subheader("📉 股价走势")
        if 'BB_Upper' in df.columns:
            chart_cols = ['time_key', 'close', 'BB_Upper', 'BB_Lower']
            st.line_chart(df[chart_cols].set_index('time_key'), color=["#0000FF", "#FF0000", "#00FF00"])
        else:
            st.line_chart(df[['time_key', 'close']].set_index('time_key'))

        # 表格
        st.subheader("📜 详细数据")
        st.dataframe(df.sort_values(by='time_key', ascending=False).head(5), use_container_width=True)
        
    else:
        st.error(msg)

