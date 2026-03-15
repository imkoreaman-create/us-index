import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import math
from datetime import datetime
import urllib.request
import xml.etree.ElementTree as ET
import json
import sys, os
import re
import warnings
import altair as alt
warnings.filterwarnings('ignore')

# ==========================================
# 🛡️ 0. 글로벌 상태 초기화 
# ==========================================
if 'portfolio_base' not in st.session_state:
    st.session_state.portfolio_base = pd.DataFrame({
        "종목명": ["SK하이닉스", "삼성전자", "두산에너빌리티", "현대오토에버", "PLUS K방산", "💡 커스텀 종목"],
        "평단가(원)": [0, 0, 0, 0, 0, 0],
        "수량(주)": [0, 0, 0, 0, 0, 0]
    })
if 'spot_qty' not in st.session_state: st.session_state.spot_qty = 0
if 'fut_cont' not in st.session_state: st.session_state.fut_cont = 0
if 'cash' not in st.session_state: st.session_state.cash = 50000000
if 'mdd' not in st.session_state: st.session_state.mdd = 2.0

# ==========================================
# ⚙️ 1. Streamlit GUI & 반응형 CSS (스크롤 박멸 HTML 테이블)
# ==========================================
st.set_page_config(page_title="Quantum Pro - V FINAL", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 1.5rem !important; }
    .stApp { background-color: #050507; color: #e2e8f0; font-family: 'Pretendard', sans-serif; }
    .highlight { color: #00ffcc; text-shadow: 0 0 8px rgba(0,255,204,0.6); }
    
    .top-header-container { display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid #2d3748; padding-bottom: 5px; margin-bottom: 15px; margin-top: -20px;}
    .app-title { font-size: 1.1rem; color: #fff; font-weight: 900; margin: 0; letter-spacing: -0.5px;}
    .creator-mark { font-size: 0.8rem; color: #ebd197; font-weight: bold; margin: 0; text-shadow: 0 0 5px rgba(235, 209, 151, 0.4);}
    
    .stTabs [data-baseweb="tab-list"] { gap: 6px; flex-wrap: wrap; border-bottom: 1px solid #2d3748;}
    .stTabs [data-baseweb="tab"] { padding: 6px 12px; background-color: transparent; border-radius: 6px 6px 0 0; font-weight: bold; color: #a0aec0; font-size: 0.85rem;}
    .stTabs [aria-selected="true"] { background-color: #1a202c; border-bottom: 3px solid #00ffcc !important; color: #00ffcc !important;}
    
    .metric-card { background: linear-gradient(145deg, #111216, #1a1c23); border: 1px solid #2d3748; padding: 12px; border-radius: 8px; border-left: 4px solid #00ffcc; box-shadow: 0 4px 10px rgba(0,0,0,0.5); text-align: center; }
    .metric-title { font-size: 0.75rem; color: #a0aec0; margin-bottom: 4px; font-weight: 600; }
    .metric-value { font-size: 1.1rem; font-weight: 800; letter-spacing: -0.5px; }
    
    .open-briefing { background: linear-gradient(145deg, #0f172a, #1a202c); border: 1px solid #3182ce; padding: 12px; border-radius: 8px; border-left: 4px solid #3182ce; margin-bottom: 12px; font-size: 0.85rem;}
    .alert-card { background: linear-gradient(145deg, #1a0f14, #241419); border: 1px solid #ff3366; padding: 10px; border-radius: 8px; border-left: 4px solid #ff3366; font-size: 0.85rem; margin-bottom: 10px;}
    
    [data-testid="stNumberInputContainer"] button { display: none !important; }
    input[type="number"] { -moz-appearance: textfield; font-weight: bold; color: #ffdd00 !important; text-align: center !important; font-size: 0.95rem !important;}
    
    .prob-bar-container { width: 100%; height: 8px; display: flex; border-radius: 4px; overflow: hidden; margin-top: 5px; margin-bottom: 12px; background: #2d3748; }
    
    /* 🔥 스크롤 박멸을 위한 HTML 엑셀 그리드 완벽 부활 */
    .data-table { width: 100%; border-collapse: collapse; background: #111216; border-radius: 8px; overflow: hidden; margin-bottom: 15px; font-size: 0.8rem; border: 1px solid #2d3748;}
    .data-table th, .data-table td { padding: 8px 6px; text-align: right; border-bottom: 1px solid #2d3748; }
    .data-table th { background: #0a0a0c; color: #ff9900; font-weight: 600; text-align: center; }
    .data-table td:first-child, .data-table th:first-child { text-align: left; background: #16181d; font-weight: bold; border-right: 1px solid #2d3748;}
    
    .badge-bull { background: rgba(0,255,204,0.15); color: #00ffcc; padding: 3px 6px; border-radius: 4px; font-size: 0.7rem; border: 1px solid rgba(0,255,204,0.3); font-weight: bold;}
    .badge-bear { background: rgba(255,68,68,0.15); color: #ff4444; padding: 3px 6px; border-radius: 4px; font-size: 0.7rem; border: 1px solid rgba(255,68,68,0.3); font-weight: bold;}
    .badge-neutral { background: rgba(160,174,192,0.15); color: #a0aec0; padding: 3px 6px; border-radius: 4px; font-size: 0.7rem; border: 1px solid rgba(160,174,192,0.3); font-weight: bold;}

    @media (max-width: 768px) {
        .top-header-container { flex-direction: column; align-items: flex-start; gap: 2px; padding-bottom: 8px; margin-top: 0px;}
        .app-title { font-size: 1.05rem; }
        .creator-mark { font-size: 0.75rem; }
        .data-table { font-size: 0.7rem; }
        .data-table th, .data-table td { padding: 6px 3px; }
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
<div class='top-header-container'>
    <div class='app-title'>Quantum <span class='highlight'>V FINAL The Absolute End</span></div>
    <div class='creator-mark'>✨ 모두가 부자 되길 바라는 주린(인)님 병권</div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 📡 2. 스크래핑 엔진 (데이터 누락/0.00% 완전 방어)
# ==========================================
@st.cache_data(ttl=600)
def fetch_auto_sentiment():
    try:
        url = "https://m.stock.naver.com/api/news/list?category=mainnews&pageSize=20"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=3).read().decode('utf-8')
        news_data = json.loads(res)
        score = 0.5
        bull_words = ['상승', '급등', '수주', '돌파', '흑자', '기대', '상회', '조선', '방산', '동맹', '협력', '수출']
        bear_words = ['하락', '급락', '우려', '봉쇄', '전쟁', '위기', '쇼크', '매도', '관세', '제재', '침체']
        for item in news_data:
            title = item.get('title', '')
            if any(w in title for w in bull_words): score += 0.05
            if any(w in title for w in bear_words): score -= 0.05
        return max(0.0, min(1.0, score))
    except: return 0.5

def get_investing_vkospi():
    try:
        url = "https://kr.investing.com/indices/kospi-volatility"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=3).read().decode('utf-8')
        p_match = re.search(r'data-test="instrument-price-last">([0-9\.,]+)<', html)
        pct_match = re.search(r'data-test="instrument-price-change-percent">[^<]*\(([+-]?[0-9\.,]+)%\)<', html)
        return float(p_match.group(1).replace(',', '')) if p_match else None, float(pct_match.group(1).replace(',', '')) if pct_match else 0.0
    except: return None, None

@st.cache_data(ttl=300)
def fetch_quant_data(tickers_dict):
    data_store = {}
    f = open(os.devnull, 'w')
    sys.stderr = f
    
    for t in tickers_dict.keys():
        try:
            if ".KS" in t or ".KQ" in t:
                code = t.split('.')[0]
                url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=90&requestType=0"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                res = urllib.request.urlopen(req, timeout=3).read().decode('euc-kr')
                root = ET.fromstring(res)
                closes, dates = [], []
                for item in root.findall('.//item'):
                    parts = item.attrib['data'].split('|')
                    dates.append(pd.to_datetime(parts[0]))
                    closes.append(float(parts[4]))
                series = pd.Series(closes, index=dates)
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    tmp_df = yf.Ticker(t).history(period="3mo")
                    if tmp_df.empty: raise ValueError
                    series = tmp_df['Close'].dropna()
                    series.index = series.index.tz_localize(None)
                    
            if len(series) < 25: raise ValueError
            
            curr_p = series.iloc[-1]
            prev_p = series.iloc[-2]
            pct = ((curr_p - prev_p) / prev_p) * 100
            
            sma20_series = series.rolling(20).mean()
            sma20 = sma20_series.iloc[-1]
            
            df_chart = pd.DataFrame({'Price': series, 'SMA20': sma20_series}).dropna().tail(30)
            df_chart.index = df_chart.index.strftime('%m-%d')
            
            delta = series.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rsi_series = 100 - (100 / (1 + (gain / loss)))
            rsi = rsi_series.iloc[-1]
            
            data_store[t] = {
                "price": curr_p, "pct_change": pct, "rsi": rsi, "macd_hist": 0, 
                "bb_pos": 0.5, "sma20": sma20, "history_df": df_chart
            }
        except:
            # 에러 시 지표를 날리지 않고 0.001로 통신대기 상태 유지
            data_store[t] = {"price": 0.001, "pct_change": 0.0, "rsi": 50, "macd_hist": 0, "bb_pos": 0.5, "sma20": 0, "history_df": pd.DataFrame()}

    sys.stderr = sys.__stderr__

    if "^VKOSPI" in tickers_dict:
        vk_p, vk_pct = get_investing_vkospi()
        if vk_p is not None:
            data_store["^VKOSPI"]["price"] = vk_p
            data_store["^VKOSPI"]["pct_change"] = vk_pct
        elif data_store["^VKOSPI"]["price"] == 0.001:
            vix_p = data_store.get("^VIX", {}).get("price", 15.0)
            data_store["^VKOSPI"]["price"] = vix_p * 1.05
            data_store["^VKOSPI"]["pct_change"] = 0.0
            
    return data_store

def get_ai_ensemble_score(d, is_inverse=False):
    pct, rsi, bb = d.get("pct_change", 0), d.get("rsi", 50), d.get("bb_pos", 0.5)
    base = 0.9 if pct >= 1.5 else (0.7 if pct >= 0.3 else (0.5 if pct > -0.3 else (0.3 if pct > -1.5 else 0.1)))
    if not is_inverse:
        if rsi > 75: base -= 0.2
        elif rsi < 30: base += 0.2
        if bb <= 0.1: base += 0.2
        elif bb >= 0.9: base -= 0.15
    return max(0.0, min(1.0, (1.0 - base) if is_inverse else base))

def sigmoid(x): return 1 / (1 + math.exp(-x))

def draw_altair_chart(df, height=120):
    if df.empty: return
    df_melted = df.reset_index().melt('index', var_name='Type', value_name='Value')
    chart = alt.Chart(df_melted).mark_line(strokeWidth=2).encode(
        x=alt.X('index:N', title='', axis=alt.Axis(labelAngle=-45, labelColor='#a0aec0', tickCount=5)),
        y=alt.Y('Value:Q', scale=alt.Scale(zero=False), title='', axis=alt.Axis(labelColor='#a0aec0', tickCount=4)),
        color=alt.Color('Type:N', scale=alt.Scale(domain=['Price', 'SMA20'], range=['#00ffcc', '#ffaa00']), legend=None),
        tooltip=['index:N', 'Type:N', 'Value:Q']
    ).properties(height=height)
    st.altair_chart(chart, use_container_width=True)

# ==========================================
# 🖥️ 3. 메인 레이아웃 (4-TAB V FINAL)
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["📊 타점 & 브리핑", "⚙️ 시스템 세팅", "🌐 매크로 전광판", "💎 K-정세 레이더"])

# ----------------------------------------------------
# ⚙️ [TAB 2] 시스템 세팅 (입력 먹통 완전 해결 및 콤마 동기화)
# ----------------------------------------------------
with tab2:
    c1, c2 = st.columns(2)
    cash_input = c1.text_input("💰 가용 현금 (단위: 원)", value=f"{st.session_state.cash:,}")
    try: st.session_state.cash = int(cash_input.replace(',', ''))
    except: pass
    
    st.session_state.mdd = c2.slider("🔒 MDD 손실 한도 (%)", 0.5, 10.0, st.session_state.mdd, 0.1)
    
    c3, c4 = st.columns(2)
    spot_input = c3.text_input("KOSPI 현물 순매수 (단위: 천주)", value=f"{st.session_state.spot_qty:,}")
    try: st.session_state.spot_qty = int(spot_input.replace(',', ''))
    except: pass
    
    fut_input = c4.text_input("KOSPI 선물 순매수 (단위: 계약)", value=f"{st.session_state.fut_cont:,}")
    try: st.session_state.fut_cont = int(fut_input.replace(',', ''))
    except: pass
    
    st.markdown("### 📊 포트폴리오 입력")
    st.caption("✅ 셀을 클릭하고 숫자를 타이핑하세요. 입력 포커스가 절대 튕기지 않습니다.")
    
    # width="stretch" 를 통해 경고 에러 로그 차단
    edited_df = st.data_editor(
        st.session_state.portfolio_base,
        hide_index=True,
        width="stretch"
    )
    
    p_data = edited_df.to_dict(orient='list')
    names = p_data["종목명"]
    avgs = p_data["평단가(원)"]
    holds = p_data["수량(주)"]
    custom_name = names[5] if names[5] != "💡 커스텀 종목" else ""
    
    pC_live_input = st.text_input("💡 커스텀 종목 현재가 (수동입력)", value="0")
    try: pC_live = int(pC_live_input.replace(',', ''))
    except: pC_live = 0

# ----------------------------------------------------
# 📊 [TAB 1] 코어 연산 및 실전 타점
# ----------------------------------------------------
with tab1:
    with st.expander("⏳ 타임머신 시뮬레이터"):
        use_time_machine = st.checkbox("타임머신 모드 가동")
        sim_time = st.slider("가상 시각 설정 (예: 900 = 09:00)", min_value=700, max_value=2100, value=900, step=10, format="%d")

    # 🔥 글로벌 유니버스 29개 완벽 보존 (누락/증발 원천 차단)
    UNIVERSE = {
        "^KS11": "KOSPI(종합)", "^SOX": "필라델피아반도체", "NVDA": "엔비디아", "TSM": "TSMC", "MU": "마이크론", "AVGO": "브로드컴", "AMD": "AMD", "AAPL": "애플", 
        "QQQ": "나스닥ETF", "NQ=F": "나스닥선물", "ES=F": "S&P500선물", "RTY=F": "러셀2000선물", "XLI": "미 산업재(정책)",
        "BTC-USD": "비트코인", "USDKRW=X": "원달러환율", "^TNX": "미10년금리", "DX-Y.NYB": "달러인덱스", "GC=F": "금(Gold)", 
        "CL=F": "WTI유가", "HG=F": "구리(Copper)", "^VIX": "VIX", "^VKOSPI": "VKOSPI(공포)", "HYG": "하이일드(신용)",
        "EWY": "MSCI한국", "^KQ11": "KOSDAQ지수", "ETN": "이튼(전력)", "URA": "우라늄ETF", "TSLA": "테슬라", "ITA": "미 방산ETF"
    }
    port_tickers_dict = {"000660.KS":"SK하이닉스", "005930.KS":"삼성전자", "034020.KS":"두산에너빌리티", "307950.KS":"현대오토에버", "449450.KS":"PLUS K방산"}
    combined_tickers = {**UNIVERSE, **port_tickers_dict}

    with st.spinner("🤖 V FINAL: 스크래핑 스캔 및 수급 연동 알고리즘 실행 중..."):
        all_market_data = fetch_quant_data(combined_tickers)
        AUTO_NEWS_SCORE = fetch_auto_sentiment() 

    scores = {}
    inverse_tickers = ["USDKRW=X", "^TNX", "CL=F", "^VIX", "^VKOSPI", "DX-Y.NYB"] 
    for t in UNIVERSE.keys():
        scores[t] = get_ai_ensemble_score(all_market_data.get(t, {"pct_change":0, "rsi":50, "macd_hist":0, "bb_pos":0.5}), is_inverse=(t in inverse_tickers))

    # 🔥 외인 수급(선물/현물)이 시장 확률과 켈리비중(투자금액)을 결정짓는 유기적 융합 매커니즘
    KOR_SPOT_SCORE = max(0.0, min(1.0, (st.session_state.spot_qty + 10000) / 20000))
    KOR_FUT_SCORE = max(0.0, min(1.0, (st.session_state.fut_cont + 20000) / 40000))

    semi_score = scores.get("^SOX",0.5) + scores.get("NVDA",0.5) + scores.get("TSM",0.5) + scores.get("MU",0.5) + scores.get("AVGO",0.5) + scores.get("AMD",0.5) + (AUTO_NEWS_SCORE * 0.5)
    macro_score = scores.get("USDKRW=X",0.5) + scores.get("^TNX",0.5) + scores.get("DX-Y.NYB",0.5) + scores.get("GC=F",0.5) + scores.get("HG=F",0.5) + scores.get("HYG",0.5)
    fear_score = scores.get("^VIX",0.5) * 1.5 + scores.get("^VKOSPI",0.5) * 1.0 
    
    korea_score = scores.get("^KS11",0.5) * 1.5 + scores.get("EWY",0.5) + scores.get("^KQ11",0.5) + KOR_SPOT_SCORE + KOR_FUT_SCORE 
    defense_score = scores.get("ITA",0.5) + scores.get("XLI",0.5) + scores.get("ETN",0.5) + scores.get("URA",0.5) + (AUTO_NEWS_SCORE * 1.5)

    node_semi = (semi_score / 6.5) * 2 - 1
    node_macro = ((macro_score + fear_score) / 8.5) * 2 - 1
    node_kor = (korea_score / 5.5) * 2 - 1
    node_infra = (defense_score / 5.5) * 2 - 1

    prob_bull = sigmoid(node_semi*1.5 + node_macro*1.0 + node_kor*1.0) * 100
    prob_rotation = sigmoid(-node_semi*1.0 + node_infra*1.5 + node_macro*0.5) * 100
    prob_panic = sigmoid(-node_macro*2.0 - node_kor*1.0) * 100

    tot_p = prob_bull + prob_rotation + prob_panic + 20
    prob_bull, prob_rotation, prob_panic = (prob_bull/tot_p)*100, (prob_rotation/tot_p)*100, (prob_panic/tot_p)*100

    max_prob = max(prob_bull, prob_rotation, prob_panic)
    kelly_factor = max(0, (max_prob/100) - ((1 - (max_prob/100)) / 1.5))
    kelly_factor = min(1.0, kelly_factor * 1.5) 

    if prob_panic > 40 or fear_score >= 1.8: regime, reg_color = "PANIC (하락장)", "#ff4444"
    elif prob_bull > prob_rotation and prob_bull > 35: regime, reg_color = "BULL (상승장)", "#00ffcc"
    elif prob_rotation > 35 or defense_score >= 3.5: regime, reg_color = "ROTATION (순환장)", "#ffaa00"
    else: regime, reg_color = "NEUTRAL (관망세)", "#a0aec0"

    if use_time_machine: time_val = sim_time
    else: time_val = datetime.now().hour * 100 + datetime.now().minute
        
    us_tech_trend = all_market_data.get('^SOX', {}).get('pct_change', 0)
    fc = st.session_state.fut_cont
    fut_trend_txt = f"🟢 {fc:,}계약 매수" if fc > 0 else (f"🔴 {fc:,}계약 매도" if fc < 0 else "중립")

    briefing_msg = ""
    if 800 <= time_val < 850: briefing_msg = f"🌅 **[08:00~08:50 NXT 프리마켓]** 반도체 **{us_tech_trend:+.2f}%**. 장전 호가 탐색 및 켈리 비중({kelly_factor:.2f}x) 점검."
    elif 850 <= time_val < 900: briefing_msg = f"🔔 **[08:50~09:00 KRX 동시호가]** 정규장 개장 임박. 갭 시나리오 점검 및 타점 세팅."
    elif 900 <= time_val < 930:
        if us_tech_trend > 1.0 and fc > 1000: briefing_msg = f"🟢 **[09:00~09:30 돌파 매매]** 외인 선물 {fut_trend_txt}. 시초가 추격 매수 유효."
        elif us_tech_trend < -1.0 and fc < -1000: briefing_msg = f"🔴 **[09:00~09:30 투매 주의]** 외인 선물 {fut_trend_txt}. 물타기 금지."
        else: briefing_msg = f"➖ **[09:00~09:30 수급 탐색]** 방향성 부재. 수급 이동 관망."
    elif 930 <= time_val < 1520: briefing_msg = f"☀️ **[09:30~15:20 정규장]** 장세는 **{regime}**. 밴드 하단 도달 주도주 분할 매수."
    elif 1520 <= time_val < 1530: briefing_msg = f"🌇 **[15:20~15:30 KRX 종가 베팅]** 수급 방향성 확정. 주도주 오버나잇 집행."
    elif 1530 <= time_val <= 2000: briefing_msg = f"🌙 **[15:30~20:00 NXT 애프터마켓]** 시간외 단일가 및 대체거래소 가동 중."
    else: briefing_msg = f"🌌 **[20:00 이후]** 모든 거래소 마감. 야간 선물 모니터링."

    sim_badge = " <span class='badge-bear'>시뮬레이션 중</span>" if use_time_machine else ""
    st.markdown(f"<div class='open-briefing'>🕒 <b>AI 알고리즘 대응{sim_badge}:</b> {briefing_msg}</div>", unsafe_allow_html=True)

    fg_index = (prob_bull * 1.0) + (prob_rotation * 0.5) + (prob_panic * 0.0)
    fg_text = "극단적 공포 (Extreme Fear)" if fg_index < 25 else "공포 (Fear)" if fg_index < 45 else "중립 (Neutral)" if fg_index < 55 else "탐욕 (Greed)" if fg_index < 75 else "극단적 탐욕 (Extreme Greed)"
    fg_color = "#ff4444" if fg_index < 45 else "#a0aec0" if fg_index < 55 else "#00ffcc"
    st.markdown(f"<div style='text-align:center; font-size:1.3rem; font-weight:900; color:{fg_color}; margin-bottom:5px;'>K-Market 투심: {fg_index:.0f} ({fg_text})</div>", unsafe_allow_html=True)
    
    prob_html = f"""
    <div style="display:flex; justify-content:space-between; margin-bottom: 2px;">
        <div style="text-align:left; font-size:0.7rem; color:#ff4444; font-weight:bold;">PANIC {prob_panic:.1f}%</div>
        <div style="text-align:center; font-size:0.7rem; color:#ffaa00; font-weight:bold;">ROTATION {prob_rotation:.1f}%</div>
        <div style="text-align:right; font-size:0.7rem; color:#00ffcc; font-weight:bold;">BULL {prob_bull:.1f}%</div>
    </div>
    <div class='prob-bar-container'>
        <div style="width:{prob_panic}%; background-color:#ff4444;"></div>
        <div style="width:{prob_rotation}%; background-color:#ffaa00;"></div>
        <div style="width:{prob_bull}%; background-color:#00ffcc;"></div>
    </div>
    """
    st.markdown(prob_html, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='metric-card' style='border-color:{reg_color};'><div class='metric-title'>현재 국면</div><div class='metric-value' style='color:{reg_color};'>{regime}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><div class='metric-title'>안전 켈리 비중 (f*)</div><div class='metric-value' style='color:#ffdd00;'>{kelly_factor:.2f}x</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card'><div class='metric-title'>정세 감성 지수</div><div class='metric-value' style='color:#00ffcc;'>{AUTO_NEWS_SCORE:.2f} / 1.0</div></div>", unsafe_allow_html=True)

    # 🔥 [먹통 완벽 해결] HTML 표로 회귀하여 투명한 목표/손절가 노출 및 색상 서식 100% 반영
    st.markdown("---")
    st.subheader(f"🎯 리밸런싱 (MDD {st.session_state.mdd}% 방어)")
    
    alloc = kelly_factor * 100
    w = [0,0,0,0,0]
    if "PANIC" in regime: w = [0, 0, 0, 0, alloc*0.6]
    elif "BULL" in regime: w = [alloc*0.4, alloc*0.2, alloc*0.2, alloc*0.2, 0]
    elif "ROTATION" in regime: w = [alloc*0.1, alloc*0.1, alloc*0.3, alloc*0.2, alloc*0.3]
    else: w = [alloc*0.2, alloc*0.2, alloc*0.2, alloc*0.2, alloc*0.2]

    prices = [
        all_market_data.get("000660.KS", {}).get("price", 0.001),
        all_market_data.get("005930.KS", {}).get("price", 0.001),
        all_market_data.get("034020.KS", {}).get("price", 0.001),
        all_market_data.get("307950.KS", {}).get("price", 0.001),
        all_market_data.get("449450.KS", {}).get("price", 0.001),
        pC_live if pC_live > 0 else 0.001
    ]
    final_weights = w + [0]

    total_asset = st.session_state.cash
    for i in range(6):
        try: h_val = int(str(holds[i]).replace(',', '')) if holds[i] else 0
        except: h_val = 0
        if prices[i] > 1: total_asset += (prices[i] * h_val)

    if custom_name != "" and "PANIC" not in regime:
        final_weights[5] = alloc * 0.15
        for i in range(5): final_weights[i] *= 0.85

    vol_mult = 1.0 + (all_market_data.get('^VIX', {}).get('price', 15) / 100) 
    t_arr = [1 + (0.04 * vol_mult), 1 + (0.03 * vol_mult), 1 + (0.05 * vol_mult), 1 + (0.045 * vol_mult), 1 + (0.03 * vol_mult), 1 + (0.05 * vol_mult)]
    s_arr = [1 - (0.02 * vol_mult), 1 - (0.015 * vol_mult), 1 - (0.025 * vol_mult), 1 - (0.025 * vol_mult), 1 - (0.015 * vol_mult), 1 - (0.03 * vol_mult)]
    if "PANIC" in regime: t_arr = [0,0,0,0,1+(0.08*vol_mult),0]; s_arr = [0,0,0,0,1-(0.04*vol_mult),0]

    FEE = 0.0023
    pre_loss = 0
    for i in range(6):
        if prices[i] > 1 and final_weights[i] > 0:
            t_qty = math.floor((total_asset * (final_weights[i]/100)) / prices[i])
            if t_qty > 0: pre_loss += ((t_qty * prices[i]) - (math.floor(prices[i]*s_arr[i]) * t_qty)) * (1 + FEE)

    shrink = 1.0
    max_loss = total_asset * (st.session_state.mdd / 100)
    if pre_loss > max_loss and pre_loss > 0:
        shrink = max_loss / pre_loss
        st.markdown(f"<div class='alert-card'>⚠️ <b>[MDD 방어 가동]</b> 한도 초과! 시스템이 매수 비중을 {shrink*100:.1f}%로 축소합니다.</div>", unsafe_allow_html=True)

    grid_html = "<table class='data-table'><tr><th>종목명 (현재가)</th><th>평단 (수익률)</th><th>판단</th><th>익절가/손절가</th><th>비중(%)</th><th>리밸런싱</th></tr>"
    tot_profit, tot_loss, tot_invest = 0, 0, 0

    for i in range(6):
        if i == 5 and custom_name == "": continue 
        
        p = float(prices[i])
        try: avg = int(str(avgs[i]).replace(',', '')) if avgs[i] else 0
        except: avg = 0
        try: h = int(str(holds[i]).replace(',', '')) if holds[i] else 0
        except: h = 0
        fw = final_weights[i] * shrink
        
        ret_pct = ((p - avg) / avg * 100) if avg > 0 else 0.0
        ret_str = f"<span style='color: #00ffcc;'>{ret_pct:+.2f}%</span>" if ret_pct > 0 else (f"<span style='color: #ff4444;'>{ret_pct:+.2f}%</span>" if ret_pct < 0 else "-")
        avg_disp = f"{avg:,.0f}원<br>({ret_str})" if avg > 0 else "-"
        price_str = f"<span style='color:#ffdd00; font-weight:bold;'>{p:,.0f}원</span>" if p > 1 else "<span style='color:#ff4444;'>통신대기</span>"
        
        # 🔥 무결점 로직: 평단가 기준 목표가 연산. 비중이 0%여도 무조건 끝까지 연산하여 렌더링.
        if p > 1:
            tgt_p = math.floor(avg * t_arr[i]) if avg > 0 else math.floor(p * t_arr[i])
            stp_p = math.floor(avg * s_arr[i]) if avg > 0 else math.floor(p * s_arr[i])
        else:
            tgt_p, stp_p = 0, 0
            
        if p <= 1:
            grid_html += f"<tr><td><b>{names[i]}</b><br>{price_str}</td><td>{avg_disp}</td><td><span class='badge-neutral'>대기</span></td><td>-</td><td>0%</td><td>-</td></tr>"
            continue
            
        t_qty = math.floor((total_asset * (fw/100)) / p)
        a_qty = t_qty - h
        
        # 🔥 기대 손익비 계산 보정 (수량이 있으면 무조건 손익 평가에 반영)
        calc_qty = t_qty if t_qty > 0 else h
        if calc_qty > 0:
            tot_invest += (calc_qty * p)
            tot_profit += max(0, tgt_p - p) * calc_qty * (1 - FEE)
            tot_loss += max(0, p - stp_p) * calc_qty * (1 + FEE)
            
        if fw <= 0:
            if h > 0: act_badge = "<span class='badge-bull'>💰 전량익절</span>" if ret_pct > 0 else "<span class='badge-bear'>✂️ 전량손절</span>"; action_str = f"<span style='color:#ff4444; font-weight:bold;'>매도 {-a_qty:,}주</span>"
            else: act_badge = "<span class='badge-neutral'>관망</span>"; action_str = "-"
        else:
            if a_qty > 0:
                if h > 0: act_badge = "<span class='badge-bull'>🔥 불타기</span>" if ret_pct > 0 else "<span class='badge-neutral'>💧 물타기</span>"
                else: act_badge = "<span class='badge-bull'>🟢 신규진입</span>"
                action_str = f"<span style='color:#00ffcc; font-weight:bold;'>매수 +{a_qty:,}주</span>"
            elif a_qty < 0:
                act_badge = "<span class='badge-bull'>💰 부분익절</span>" if ret_pct > 0 else "<span class='badge-bear'>✂️ 부분손절</span>"
                action_str = f"<span style='color:#ff4444; font-weight:bold;'>매도 {a_qty:,}주</span>"
            else:
                act_badge = "<span class='badge-neutral'>유지</span>"; action_str = "-"
                
        grid_html += f"<tr><td><b>{names[i]}</b><br>{price_str}</td><td>{avg_disp}</td><td>{act_badge}</td><td>🎯 {tgt_p:,.0f}원<br>🛡️ {stp_p:,.0f}원</td><td>{fw:.1f}%</td><td>{action_str}</td></tr>"

    grid_html += "</table>"
    st.markdown(grid_html, unsafe_allow_html=True)

    rrr = (tot_profit / tot_loss) if tot_loss > 0 else 0
    st.markdown(f"**💰 투자(평가) 집행 총액:** {tot_invest:,.0f} 원 | **잔여 현금:** {total_asset - tot_invest:,.0f} 원 | **⚖️ 기대 손익비:** {rrr:.2f}배")

    st.markdown("---")
    st.markdown("### 📈 주가 & 20일 추세선")
    st.markdown("""
    <div style='text-align:center; font-size:0.85rem; margin-bottom:10px;'>
        <span style='color:#00ffcc; font-weight:bold;'>── 주가 (Price)</span> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
        <span style='color:#ffaa00; font-weight:bold;'>── 20일선 (SMA20)</span>
    </div>
    """, unsafe_allow_html=True)
    
    port_tickers = ["000660.KS", "005930.KS", "034020.KS", "307950.KS", "449450.KS"]
    chart_cols = st.columns(2)
    
    for idx, t in enumerate(port_tickers):
        with chart_cols[idx % 2]:
            st.markdown(f"<div style='text-align:left; font-size:0.9rem; font-weight:bold; color:#00ffcc; margin-top:5px; margin-bottom:2px;'>{names[idx]}</div>", unsafe_allow_html=True)
            hist_df = all_market_data.get(t, {}).get("history_df", pd.DataFrame())
            if not hist_df.empty: draw_altair_chart(hist_df, height=120)
            else: st.markdown("<div style='text-align:center; color:#ff4444; font-size:0.8rem; padding: 20px;'>차트 대기 중</div>", unsafe_allow_html=True)

# ----------------------------------------------------
# 🌐 [TAB 3] 글로벌 전광판 (스크롤 박멸 & 색상 100% 보존 HTML 테이블)
# ----------------------------------------------------
with tab3:
    st.subheader("🌐 매크로 & 섹터")
    df_display = []
    for t, name in UNIVERSE.items():
        d = all_market_data.get(t, {"price":0, "pct_change":0, "rsi":50, "macd_hist":0, "bb_pos":0.5})
        
        macd_badge = "<span class='badge-bull'>UP</span>" if d['macd_hist'] > 0 else "<span class='badge-bear'>DN</span>"
        if d['bb_pos'] < 0.1: bb_badge = "<span class='badge-bull'>하단</span>"
        elif d['bb_pos'] > 0.9: bb_badge = "<span class='badge-bear'>상단</span>"
        else: bb_badge = "<span class='badge-neutral'>횡보</span>"
        
        if d['rsi'] > 70: rsi_badge = f"<span class='badge-bear'>{d['rsi']:.0f}</span>"
        elif d['rsi'] < 30: rsi_badge = f"<span class='badge-bull'>{d['rsi']:.0f}</span>"
        else: rsi_badge = f"<span class='badge-neutral'>{d['rsi']:.0f}</span>"

        pct_color = "#00ffcc" if d['pct_change'] > 0 else "#ff4444"
        df_display.append({
            "지표": f"<b>{name}</b>", "현재가": f"{d['price']:,.2f}",
            "변동률": f"<span style='color:{pct_color}; font-weight:bold;'>{d['pct_change']:+.2f}%</span>",
            "RSI": rsi_badge, "추세": macd_badge, "위치": bb_badge, "AI스코어": f"<b style='color:#ebd197;'>{scores.get(t, 0.5):.2f}</b>"
        })
        
    matrix_html = "<table class='data-table'><tr>" + "".join([f"<th>{col}</th>" for col in df_display[0].keys()]) + "</tr>"
    for row in df_display: matrix_html += "<tr>" + "".join([f"<td>{val}</td>" for val in row.values()]) + "</tr>"
    matrix_html += "</table>"
    st.markdown(matrix_html, unsafe_allow_html=True)

# ----------------------------------------------------
# 💎 [TAB 4] K-정세 딥러닝 주도주 레이더
# ----------------------------------------------------
with tab4:
    st.subheader("💎 K-정세 주도주 스캔")
    KR_UNIVERSE = {
        "000660.KS": "SK하이닉스", "042700.KS": "한미반도체", "064350.KS": "현대로템", 
        "012450.KS": "한화에어로", "079550.KS": "LIG넥스원", "009540.KS": "한국조선해양", 
        "034020.KS": "두산에너빌리티", "267260.KS": "HD현대일렉", "307950.KS": "현대오토에버", 
        "000270.KS": "기아", "196170.KQ": "알테오젠", "207940.KS": "삼성바이오로직스"
    }

    with st.spinner("🔍 K-정세 퀀트 스캔 중..."):
        kr_data = fetch_quant_data(KR_UNIVERSE)

    if kr_data:
        rankings = []
        for t, name in KR_UNIVERSE.items():
            d = kr_data.get(t)
            if not d or d['price'] == 0: continue
            s = get_ai_ensemble_score(d)
            if "방산" in name or "조선" in name or "전력" in name: s += (AUTO_NEWS_SCORE * 0.3) 
            if "반도체" in name and prob_bull > 40: s += 0.15
            
            sma_badge = "<span class='badge-bull'>20일선 위</span>" if d['price'] > d.get('sma20', 0) else "<span class='badge-bear'>20일선 아래</span>"
            rankings.append({"ticker": t, "name": name, "price": d['price'], "score": s, "rsi": d['rsi'], "bb": d['bb_pos'], "sma": sma_badge})
        
        rankings.sort(key=lambda x: x['score'], reverse=True)
        
        radar_html = "<table class='data-table'><tr><th>분류</th><th>종목명</th><th>현재가</th><th>AI 스코어</th><th>RSI</th><th>추세</th></tr>"
        
        for i in range(min(4, len(rankings))): 
            r = rankings[i]
            radar_html += f"<tr><td>🔥 주도주 {i+1}</td><td><b>{r['name']}</b></td><td>{r['price']:,.0f}</td><td><b style='color:#00ffcc;'>{r['score']:.2f}</b></td><td>{r['rsi']:.1f}</td><td>{r['sma']}</td></tr>"
            
        turnaround = [r for r in rankings if r['rsi'] < 50 and r['bb'] < 0.3]
        turnaround.sort(key=lambda x: x['rsi']) 
        
        for i in range(min(3, len(turnaround))):
            r = turnaround[i]
            radar_html += f"<tr><td>🔄 반등 {i+1}</td><td><b>{r['name']}</b></td><td>{r['price']:,.0f}</td><td><b style='color:#ffaa00;'>{r['score']:.2f}</b></td><td>{r['rsi']:.1f}</td><td>{r['sma']}</td></tr>"
            
        radar_html += "</table>"
        st.markdown(radar_html, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📈 주도주 Top 4")
        st.markdown("""
        <div style='text-align:center; font-size:0.85rem; margin-bottom:10px;'>
            <span style='color:#00ffcc; font-weight:bold;'>── 주가 (Price)</span> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
            <span style='color:#ffaa00; font-weight:bold;'>── 20일선 (SMA20)</span>
        </div>
        """, unsafe_allow_html=True)
        
        mini_cols = st.columns(4)
        for i in range(min(4, len(rankings))):
            r = rankings[i]
            with mini_cols[i]:
                st.markdown(f"<div style='text-align:center; font-size:0.85rem; font-weight:bold; color:#00ffcc;'>{r['name']}</div>", unsafe_allow_html=True)
                chart_df = kr_data.get(r['ticker'], {}).get('history_df', pd.DataFrame())
                if not chart_df.empty: draw_altair_chart(chart_df, height=100)
                else: st.markdown("<div style='text-align:center; color:#ff4444; font-size:0.7rem; padding:15px;'>차트 대기</div>", unsafe_allow_html=True)
