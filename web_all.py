import streamlit as st
import akshare as ak
import talib
import numpy as np
import pandas as pd
import datetime

# --- 🛠️ 核心功能：智能获取数据 (东财源 - 稳定版) ---
def get_stock_data(code):
    code = code.strip().upper()
    df = pd.DataFrame()
    market_type = ""
    
    end_date = datetime.datetime.now().strftime("%Y%m%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime("%Y%m%d")

    try:
        # 1. 美股
        if code.isalpha() and len(code) <= 5:
            market_type = "🇺🇸 美股 (东财源)"
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
            market_type = "🇭🇰 港股 (东财源)"
            try:
                df = ak.stock_hk_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
                df = df.rename(columns={'日期': 'time_key', '开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'volume'})
            except: pass

        # 3. A股
        elif code.isdigit() and len(code) == 6:
            market_type = "🇨🇳 A股 (东财源)"
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

# --- 🎨 网页界面 ---
st.set_page_config(page_title="全球量化 V3", page_icon="📊", layout="wide")
st.title("📊 全球股市多因子分析 (V3 增强版)")
st.markdown("集成 **MACD + RSI + 布林带** 深度体检报告")

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
        
        # 数据计算
        if len(df) > 200:
            df = df.tail(200).reset_index(drop=True)
        else:
            df = df.reset_index(drop=True)
            
        close = np.array(df['close'], dtype=np.float64)
        
        # 1. MACD
        diff, dea, macd = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
        df['MACD_Hist'] = macd * 2
        
        # 2. RSI
        df['RSI'] = talib.RSI(close, timeperiod=14)
        
        # 3. 布林带
        upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        df['BB_Upper'] = upper
        df['BB_Lower'] = lower
        
        # 取最新一天
        curr = df.iloc[-1]
        
        # --- 🟢 第一部分：核心指标卡片 ---
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 最新收盘", f"{curr['close']:.2f}")
        c2.metric("📈 RSI 强度", f"{curr['RSI']:.2f}")
        
        trend = "多头 🔴" if curr['MACD_Hist'] > 0 else "空头 🟢"
        c3.metric("🌊 MACD 趋势", trend, f"{curr['MACD_Hist']:.3f}")
        
        bb_pos = (curr['close'] - curr['BB_Lower']) / (curr['BB_Upper'] - curr['BB_Lower']) * 100
        c4.metric("📊 布林带位置", f"{bb_pos:.1f}%")

        # --- 🟡 第二部分：深度分析报告 (还原控制台风格) ---
        st.subheader("📝 深度体检报告")
        
        # 准备文案
        macd_text = "处于上升趋势中 (红柱区域)" if curr['MACD_Hist'] > 0 else "处于下跌趋势中 (绿柱区域)"
        
        bb_status = "通道内震荡"
        if curr['close'] < curr['BB_Lower']: bb_status = "⚠️ 跌破下轨 (超卖)"
        elif curr['close'] > curr['BB_Upper']: bb_status = "⚠️ 突破上轨 (超买)"
            
        rsi_status = "中性"
        if curr['RSI'] < 30: rsi_status = "🟢 超卖 (反弹概率大)"
        elif curr['RSI'] > 70: rsi_status = "🔴 超买 (回调风险大)"
            
        # 综合信号
        final_signal = "⏸️ 暂无特殊信号，建议观望"
        signal_color = "blue"
        if curr['close'] < curr['BB_Lower'] and curr['RSI'] < 30:
            final_signal = "🚀 【强烈买入信号】股价破下轨 + RSI超卖！"
            signal_color = "green"
        elif curr['RSI'] > 70:
            final_signal = "⚠️ 【风险提示】RSI超买，注意止盈！"
            signal_color = "red"

        # 使用 Markdown 展示详细报告
        st.info(f"""
        **1️⃣ MACD 分析**：{macd_text}  
        **2️⃣ 布林带分析**：股价处于通道的 **{bb_pos:.1f}%** 位置，状态为：**{bb_status}** **3️⃣ RSI 分析**：当前值为 {curr['RSI']:.2f}，判定为：**{rsi_status}** ---
        **🤖 综合决策建议**： :{signal_color}[**{final_signal}**]
        """)

        # --- 🔵 第三部分：走势图 ---
        st.subheader("📉 股价走势图")
        chart_data = df[['time_key', 'close', 'BB_Upper', 'BB_Lower']].set_index('time_key')
        st.line_chart(chart_data, color=["#0000FF", "#FF0000", "#00FF00"])

        # --- 🟣 第四部分：最近5天详细数据 (你想要的数据表！) ---
        st.subheader("📜 近 5 个交易日详细数据")
        
        # 整理一个漂亮的表格，只显示关键列
        history_df = df[['time_key', 'close', 'RSI', 'BB_Lower', 'MACD_Hist']].tail(5).copy()
        # 格式化一下数字，保留2位小数
        history_df['close'] = history_df['close'].apply(lambda x: f"{x:.2f}")
        history_df['RSI'] = history_df['RSI'].apply(lambda x: f"{x:.2f}")
        history_df['BB_Lower'] = history_df['BB_Lower'].apply(lambda x: f"{x:.2f}")
        history_df['MACD_Hist'] = history_df['MACD_Hist'].apply(lambda x: f"{x:.3f}")
        
        # 按照日期倒序排列（最新的在最上面），符合看盘习惯
        history_df = history_df.sort_values(by='time_key', ascending=False)
        
        st.dataframe(history_df, use_container_width=True)

    else:
        st.error(msg)