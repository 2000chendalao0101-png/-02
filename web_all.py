import streamlit as st
import akshare as ak
import numpy as np
import pandas as pd
import datetime

# --- 🔐 第一步：密码保护功能 ---
def check_password():
    """Returns `True` if the user had the correct password."""

    # 这里设置你的密码 👇
    actual_password = st.secrets["app_password"]

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == actual_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "🔑 请输入访问密码", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input(
            "🔑 请输入访问密码", type="password", on_change=password_entered, key="password"
        )
        st.error("❌ 密码错误，请重试")
        return False
    else:
        # Password correct.
        return True

# --- 🚨 只有密码正确才会执行下面的代码 ---
if not check_password():
    st.stop()  # 停止运行，不显示后面的内容

# ==========================================
#      👇 下面是原本的核心功能代码 👇
# ==========================================

# --- 🛠️ 核心功能：智能获取数据 (东财源) ---
def get_stock_data(code):
    code = code.strip().upper()
    df = pd.DataFrame()
    market_type = ""
    
    end_date = datetime.datetime.now().strftime("%Y%m%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime("%Y%m%d")

    try:
        # 1. 美股
        if code.isalpha() and len(code) <= 5:
            market_type = "🇺🇸 美股"
            prefixes = ["105", "106", "107"] 
            for pre in prefixes:
                try:
                    em_code = f"{pre}.{code}"
                    df = ak.stock_us_hist(symbol=em_code, start_date=start_date, end_date=end_date, adjust="qfq")
                    if not df.empty: break
                except: continue
            if not df.empty:
                df = df.rename(columns={'日期': 'time_key', '开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'volume'})

        # 2. 港股
        elif code.isdigit() and len(code) == 5:
            market_type = "🇭🇰 港股"
            try:
                df = ak.stock_hk_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
                df = df.rename(columns={'日期': 'time_key', '开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'volume'})
            except: pass

        # 3. A股
        elif code.isdigit() and len(code) == 6:
            market_type = "🇨🇳 A股"
            try:
                df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
                df = df.rename(columns={'日期': 'time_key', '开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'volume'})
            except: pass

        else:
            return None, "❌ 代码格式无法识别"

        if df.empty: return None, f"⚠️ 未找到 {code} 数据"
        return df, market_type

    except Exception as e:
        return None, f"错误: {str(e)}"

# --- 🧮 纯 Pandas 计算指标 ---
def calculate_indicators(df):
    close = df['close'].astype(float)
    
    # 1. MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = (dif - dea) * 2
    
    # 2. RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 3. 布林带
    df['BB_Middle'] = close.rolling(window=20).mean()
    std_dev = close.rolling(window=20).std()
    df['BB_Upper'] = df['BB_Middle'] + (2 * std_dev)
    df['BB_Lower'] = df['BB_Middle'] - (2 * std_dev)
    
    return df

# --- 🎨 网页界面 ---
st.set_page_config(page_title="全球量化 V3 (加密版)", page_icon="🔐", layout="wide")
# --- 🚫 隐藏 Streamlit 默认的菜单和页脚 ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# 侧边栏登出按钮
with st.sidebar:
    if st.button("🔒 退出登录"):
        del st.session_state["password_correct"]
        st.rerun()

st.title("📈 全球股市多因子分析 (内部专用)")
st.markdown("无需复杂依赖，集成 **MACD + RSI + 布林带**")

# --- 侧边栏 ---
with st.sidebar:
    st.header("🔍 股票查询")
    stock_code = st.text_input("输入代码", value="00700", help="美股(NVDA), 港股(00700), A股(600519)")
    run_btn = st.button("🚀 生成报告", type="primary")

# --- 主逻辑 ---
if run_btn:
    with st.spinner(f"正在拉取 {stock_code} 数据..."):
        df, msg = get_stock_data(stock_code)

    if df is not None:
        st.success(f"✅ 成功获取 {msg} 数据！")
        
        df = df.reset_index(drop=True)
        df = calculate_indicators(df)
        
        if len(df) > 200:
            df = df.tail(200).reset_index(drop=True)
            
        curr = df.iloc[-1]
        
        # --- 🟢 指标卡片 ---
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 最新收盘", f"{curr['close']:.2f}")
        c2.metric("📈 RSI 强度", f"{curr['RSI']:.2f}")
        
        trend = "多头 🔴" if curr['MACD_Hist'] > 0 else "空头 🟢"
        c3.metric("🌊 MACD 趋势", trend, f"{curr['MACD_Hist']:.3f}")
        
        bb_upper = curr['BB_Upper']
        bb_lower = curr['BB_Lower']
        if bb_upper != bb_lower:
            bb_pos = (curr['close'] - bb_lower) / (bb_upper - bb_lower) * 100
        else:
            bb_pos = 50.0
            
        c4.metric("📊 布林带位置", f"{bb_pos:.1f}%")

        # --- 🟡 深度报告 ---
        st.subheader("📝 深度体检报告")
        
        macd_text = "处于上升趋势中 (红柱区域)" if curr['MACD_Hist'] > 0 else "处于下跌趋势中 (绿柱区域)"
        
        bb_status = "通道内震荡"
        if curr['close'] < bb_lower: bb_status = "⚠️ 跌破下轨 (超卖)"
        elif curr['close'] > bb_upper: bb_status = "⚠️ 突破上轨 (超买)"
            
        rsi_status = "中性"
        if curr['RSI'] < 30: rsi_status = "🟢 超卖 (反弹概率大)"
        elif curr['RSI'] > 70: rsi_status = "🔴 超买 (回调风险大)"
            
        final_signal = "⏸️ 暂无特殊信号，建议观望"
        signal_color = "blue"
        if curr['close'] < bb_lower and curr['RSI'] < 30:
            final_signal = "🚀 【强烈买入信号】股价破下轨 + RSI超卖！"
            signal_color = "green"
        elif curr['RSI'] > 70:
            final_signal = "⚠️ 【风险提示】RSI超买，注意止盈！"
            signal_color = "red"

        st.info(f"""
        **1️⃣ MACD 分析**：{macd_text}  
        **2️⃣ 布林带分析**：股价处于通道的 **{bb_pos:.1f}%** 位置，状态为：**{bb_status}** **3️⃣ RSI 分析**：当前值为 {curr['RSI']:.2f}，判定为：**{rsi_status}** ---
        **🤖 综合决策建议**： :{signal_color}[**{final_signal}**]
        """)

        # --- 🔵 走势图 ---
        st.subheader("📉 股价走势图")
        chart_data = df[['time_key', 'close', 'BB_Upper', 'BB_Lower']].set_index('time_key')
        st.line_chart(chart_data, color=["#0000FF", "#FF0000", "#00FF00"])

        # --- 🟣 详细表格 ---
        st.subheader("📜 近 5 个交易日详细数据")
        history_df = df[['time_key', 'close', 'RSI', 'BB_Lower', 'MACD_Hist']].tail(5).copy()
        for col in ['close', 'RSI', 'BB_Lower']:
            history_df[col] = history_df[col].apply(lambda x: f"{x:.2f}")
        history_df['MACD_Hist'] = history_df['MACD_Hist'].apply(lambda x: f"{x:.3f}")
        history_df = history_df.sort_values(by='time_key', ascending=False)
        st.dataframe(history_df, use_container_width=True)

    else:
        st.error(msg)



