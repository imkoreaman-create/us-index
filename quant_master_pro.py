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
warnings.filterwarnings('ignore')

# ==========================================
# 🛡️ 0. 글로벌 상태 초기화 
# ==========================================
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame({
        "종목명": ["SK하이닉스", "삼성전자", "두산에너빌리티", "현대오토에버", "PLUS K방산", "💡 커스텀 종목"],
        "평단가(원)": [0, 0, 0, 0, 0, 0],
        "수량(주)": [0, 0, 0, 0, 0, 0]
    })
if 'spot_qty' not in st.session_state: st.session_state.spot_qty = 0
if 'fut_cont' not in st.session_state: st.session_state.fut_cont = 0
if 'cash' not in st.session_state: st.session_state.cash = 50000000
if 'mdd' not in st.session_state: st.session_state.mdd = 2.0

# ==========================================
# ⚙️ 1. Streamlit GUI & CSS (V23 4-TAB UI)
# ==========================================
st.set_page_config(page_title="Quantum Pro - V23 Masterpiece", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    .stApp { background-color: #050507; color: #e2e8f0; }
    h2, h3 { color: #fff; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 0px; }
    .highlight { color: #00ffcc; text-shadow: 0 0 12px rgba(0,255,204,0.6); }
    
    /* 4-TAB 모바일 최적화 */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { padding: 10px 15px; background-color: #111216; border-radius: 8px; border: 1px solid #2d3748; font-weight: bold;}
    .stTabs [aria-selected="true"] { background-color: #1a202c; border-bottom: 3px solid #00ffcc !important; color: #00ffcc !important;}
    
    .metric-card { background: linear-gradient(145deg, #111216, #1a1c23); border: 1px solid #2d3748; padding: 15px; border-radius: 10px; border-left: 4px solid #00ffcc; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    .metric-title { font-size: 0.8rem; color: #a0aec0; margin-bottom: 4px; font-weight: 600; }
    .metric-value { font-size: 1.15rem; font-weight: 800; letter-spacing: -0.5px; }
    
    .alert-card { background: linear-gradient(145deg, #1a0f14, #241419); border: 1px solid #ff3366; padding: 15px; border-radius: 10px; border-left: 4px solid #ff3366; font-size: 0.9rem;}
    .open-briefing { background: linear-gradient(145deg, #0f172a, #1a202c); border: 1px solid #3182ce; padding: 15px; border-radius: 10px; border-left: 4px solid #3182ce; margin-bottom: 15px; font-size: 0.9rem;}
    .time-machine { background: linear-gradient(145deg, #1a1a0a, #2a2a11); border: 1px solid #ffdd00; padding: 15px; border-radius: 10px; border-left: 4px solid #ffdd00; margin-bottom: 15px;}
    
    .badge-bull { background: rgba(0,255,204,0.15); color: #00ffcc; padding: 3px 6px; border-radius: 4px; font-size: 0.75rem; border: 1px solid rgba(0,255,204,0.3); font-weight: bold;}
    .badge-bear { background: rgba(255,68,68,0.15); color: #ff4444; padding: 3px 6px; border-radius: 4px; font-size: 0.75rem; border: 1px solid rgba(255,68,68,0.3); font-weight: bold;}
    .badge-neutral { background: rgba(160,174,192,0.15); color: #a0aec0; padding: 3px 6px; border-radius: 4px; font-size: 0.75rem; border: 1px solid rgba(160,174,192,0.3); font-weight: bold;}
    
    [data-testid="stNumberInputContainer"] button { display: none !important; }
    input[type="number"] { -moz-appearance: textfield; font-weight: bold; color: #ffdd00 !important; text-align: center !important; font-size: 1rem !important;}
    
    .data-table { width: 100%; border-collapse: collapse; background: #111216; border-radius: 10px; overflow: hidden; margin-bottom: 20px; font-size: 0.85rem;}
    .data-table th, .data-table td { padding: 10px 8px; text-align: right; border-bottom: 1px solid #2d3748; }
    .data-table th { background: #0a0a0c; color: #ff9900; font-weight: 600; text-align: center; }
    .data-table td:first-child, .data-table th:first-child { text-align: left; background: #16181d; font-weight: bold; border-right: 1px solid #2d3748;}
    .data-table tr:hover { background-color: rgba(255,255,255,0.03); }
    .curr-price { color: #ffdd00; font-size: 1.05rem; font-weight: 800; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 📡 2. 한계 돌파 데이터 파이프라인 (3중 폴백 엔진)
# ==========================================
@st.cache_data(ttl=600)
def fetch_auto_sentiment():
    try:
        url = "https://m.stock.naver.com/api/news/list?category=mainnews&pageSize=15"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=3).read().decode('utf-8')
        news_data = json.loads(res)
        
        bull_words = ['상승', '급등', '호조', '수주', '돌파', '흑자', '기대', '상회', '협력']
        bear_words = ['하락', '급락', '우려', '봉쇄', '전쟁', '위기', '쇼크', '인플레이션', '매도', '외인']
        
        score = 0.5
        for item in news_data:
            title = item.get('title', '')
            for w in bull_words:
                if w in title: score += 0.05
            for w in bear_words:
                if w in title: score -= 0.05
        return max(0.0, min(1.0, score))
    except: return 0.5

def get_investing_vkospi():
    try:
        url = "https://kr.investing.com/indices/kospi-volatility"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=3).read().decode('utf-8')
        p_match = re.search(r'data-test="instrument-price-last">([0-9\.,]+)<', html)
        pct_match = re.search(r'data-test="instrument-price-change-percent">[^<]*\(([+-]?[0-9\.,]+)%\)<', html)
        if not p_match:
            p_match = re.search(r'class="text-2xl[^>]*>([0-9\.,]+)<', html)
            pct_match = re.search(r'class="instrument-price_change-percent[^>]*>[^<]*\(([+-]?[0-9\.,]+)%\)<', html)
        price = float(p_match.group(1).replace(',', '')) if p_match else None
        pct = float(pct_match.group(1).replace(',', '')) if pct_match else 0.0
        return price, pct
    except: return None, None

def get_naver_finance_fallback(ticker):
    code = ticker.split('.')[0]
    try:
        url = f"https://m.stock.naver.com/api/stock/{code}/integration"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=3).read().decode('utf-8')
        data = json.loads(res)
        return float(data['recentPrice'].replace(',', '')), float(data['fluctuationsRatio'])
    except: return None, None

@st.cache_data(ttl=300)
def fetch_quant_data(tickers_dict):
    data_store = {}
    tickers = list(tickers_dict.keys())
    
    f = open(os.devnull, 'w')
    old_stderr = sys.stderr
    sys.stderr = f
    try:
        # yfinance 병목을 막기 위해 15일치 강제 확보
        df_raw = yf.download(tickers, period="15d", progress=False)
        df = df_raw['Close'] if isinstance(df_raw.columns, pd.MultiIndex) else df_raw
    except: df = pd.DataFrame()
    finally:
        sys.stderr = old_stderr
        f.close()

    for t in tickers:
        try:
            # 1. yfinance 우선 시도 (개별 종목 ffill)
            if not df.empty and t in df.columns:
                series = df[t].ffill().dropna()
                if series.empty: raise ValueError
            else: raise ValueError
            
            if len(series) < 10: raise ValueError
            
            curr_p = series.iloc[-1]
            pct = ((curr_p - series.iloc[-2]) / series.iloc[-2]) * 100
            
            delta = series.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))
            
            ema12 = series.ewm(span=12, adjust=False).mean()
            ema26 = series.ewm(span=26, adjust=False).mean()
            macd_val = ema12 - ema26
            if isinstance(macd_val, pd.Series): macd_val = macd_val.iloc[-1]
            
            sma20 = series.rolling(20).mean().iloc[-1]
            std20 = series.rolling(20).std().iloc[-1]
            bb_position = (curr_p - (sma20 - 2*std20)) / (4*std20) if std20 != 0 else 0.5
            
            data_store[t] = {"price": curr_p, "pct_change": pct, "rsi": rsi, "macd_hist": macd_val, "bb_pos": bb_position}
        except:
            # 2. 실패 시 네이버 fchart 우회 스크래핑
            try:
                if ".KS" in t or ".KQ" in t:
                    code = t.split('.')[0]
                    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=60&requestType=0"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    res = urllib.request.urlopen(req, timeout=3).read().decode('euc-kr')
                    root = ET.fromstring(res)
                    closes = [float(item.attrib['data'].split('|')[4]) for item in root.findall('.//item')]
                    series = pd.Series(closes)
                    curr_p = series.iloc[-1]
                    pct = ((curr_p - series.iloc[-2]) / series.iloc[-2]) * 100
                    rsi = 50.0 # 간략화
                    data_store[t] = {"price": curr_p, "pct_change": pct, "rsi": rsi, "macd_hist": 0, "bb_pos": 0.5}
                else:
                    data_store[t] = {"price": 0.001, "pct_change": 0, "rsi": 50, "macd_hist": 0, "bb_pos": 0.5}
            except:
                data_store[t] = {"price": 0.001, "pct_change": 0, "rsi": 50, "macd_hist": 0, "bb_pos": 0.5}

    if "^VKOSPI" in tickers:
        vk_p, vk_pct = get_investing_vkospi()
        if vk_p is not None: data_store["^VKOSPI"] = {"price": vk_p, "pct_change": vk_pct, "rsi": 50, "macd_hist": 0, "bb_pos": 0.5}
        elif data_store["^VKOSPI"]["price"] == 0.001:
            vix_p = data_store.get("^VIX", {}).get("price", 15.0)
            data_store["^VKOSPI"] = {"price": vix_p * 1.05, "pct_change": 0, "rsi": 50, "macd_hist": 0, "bb_pos": 0.5}

    return data_store

@st.cache_data(ttl=60)
def fetch_live_prices():
    tickers = ["000660.KS", "005930.KS", "034020.KS", "307950.KS", "449450.KS"]
    prices = {t: 0 for t in tickers}
    for t in tickers:
        # 1. YF 최우선 시도 (기간 5일로 넓게 잡아 휴장일 대응)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = yf.Ticker(t).history(period="5d")
                if not df.empty: 
                    prices[t] = int(df['Close'].iloc[-1])
                    continue
        except: pass
        
        # 2. 실패 시 네이버 모바일 API 2차 시도
        fallback_p, _ = get_naver_finance_fallback(t)
        if fallback_p: prices[t] = int(fallback_p)
    return prices

def get_ai_ensemble_score(d, is_inverse=False):
    pct, rsi, macd, bb = d["pct_change"], d["rsi"], d["macd_hist"], d["bb_pos"]
    if pct >= 1.5: base = 0.9
    elif pct >= 0.3: base = 0.7
    elif pct > -0.3: base = 0.5
    elif pct > -1.5: base = 0.3
    else: base = 0.1
    if not is_inverse:
        if macd > 0: base += 0.15
        else: base -= 0.1
        if rsi > 75: base -= 0.2
        elif rsi < 30: base += 0.2
        if bb <= 0.1: base += 0.2
        elif bb >= 0.9: base -= 0.15
    return max(0.0, min(1.0, (1.0 - base) if is_inverse else base))

def sigmoid(x): return 1 / (1 + math.exp(-x))

# ==========================================
# 🖥️ 3. 메인 레이아웃 (V23 4-TAB UI)
# ==========================================
st.markdown("<h2 style='margin-bottom:5px;'>Quantum <span class='highlight'>V23 Masterpiece</span></h2>", unsafe_allow_html=True)
st.caption(f"최종 스캔: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | NXT 브리핑 & 4-TAB 레이아웃")

# 🔥 모바일 최적화 4-TAB 구조
tab1, tab2, tab3, tab4 = st.tabs(["📊 실전 타점", "⚙️ 세팅", "🌐 매크로", "💎 AI 레이더"])

# ----------------------------------------------------
# ⚙️ [TAB 2] 수급 및 포트폴리오 세팅 
# ----------------------------------------------------
with tab2:
    st.markdown("### ⚙️ 시스템 기본 설정")
    c1, c2 = st.columns(2)
    st.session_state.cash = c1.number_input("💰 가용 현금 (원)", value=st.session_state.cash, step=1000000, format="%d")
    st.session_state.mdd = c2.slider("🔒 MDD 손실 한도 (%)", 0.5, 10.0, st.session_state.mdd, 0.1)
    
    st.markdown("### 🌐 KOSPI 외국인 수급 입력")
    c3, c4 = st.columns(2)
    st.session_state.spot_qty = c3.number_input("현물 순매수 (천주)", value=st.session_state.spot_qty, step=100, format="%d")
    st.session_state.fut_cont = c4.number_input("선물 순매수 (계약)", value=st.session_state.fut_cont, step=500, format="%d")
    
    st.markdown("### 📊 나의 포트폴리오 에디터")
    st.info("셀을 더블클릭하여 평단가와 수량을 입력하세요.")
    
    edited_portfolio = st.data_editor(
        st.session_state.portfolio,
        column_config={
            "종목명": st.column_config.TextColumn("종목명", disabled=False),
            "평단가(원)": st.column_config.NumberColumn("평단가(원)", min_value=0, step=100, format="%d"),
            "수량(주)": st.column_config.NumberColumn("수량(주)", min_value=0, step=1, format="%d")
        },
        hide_index=True,
        width="stretch"
    )
    st.session_state.portfolio = edited_portfolio
    p_data = edited_portfolio.to_dict(orient='list')
    
    pC_live = st.number_input("💡 커스텀 종목 현재가 (수동입력)", value=0, format="%d")

# ----------------------------------------------------
# 📊 [TAB 1] 코어 연산 및 실전 타점 (타임머신 탑재)
# ----------------------------------------------------
with tab1:
    with st.expander("⏳ 타임머신 시뮬레이터 (NXT 대응 루틴 미리보기)"):
        st.markdown("<div class='time-machine'>지정한 시간대의 봇 대응 전략(NXT 프리/애프터마켓 포함)을 미리 확인합니다.</div>", unsafe_allow_html=True)
        use_time_machine = st.checkbox("타임머신 모드 가동")
        sim_time = st.slider("가상 시각 설정", min_value=700, max_value=2100, value=900, step=10, format="%d")

    # 🔥 필수 글로벌 지표 추가 (러셀2000, 코스닥)
    UNIVERSE = {
        "^SOX": "필라델피아반도체", "NVDA": "엔비디아", "TSM": "TSMC", "MU": "마이크론", "AVGO": "브로드컴", "AMD": "AMD",
        "QQQ": "나스닥ETF", "NQ=F": "나스닥선물", "ES=F": "S&P500선물", "RTY=F": "러셀2000선물", "AAPL": "애플", 
        "BTC-USD": "비트코인", "USDKRW=X": "원달러환율", "^TNX": "미10년금리", "DX-Y.NYB": "달러인덱스", "GC=F": "금(Gold)", 
        "CL=F": "WTI유가", "HG=F": "구리(Copper)", "^VIX": "VIX", "^VKOSPI": "VKOSPI(공포)", "HYG": "하이일드",
        "EWY": "MSCI한국", "^KQ11": "KOSDAQ지수", "ETN": "이튼(전력)", "URA": "우라늄ETF", "TSLA": "테슬라", "ITA": "미 방산ETF"
    }

    with st.spinner("🤖 V23 코어 네트워크 연산 중..."):
        market_data = fetch_quant_data(UNIVERSE)
        AUTO_NEWS_SCORE = fetch_auto_sentiment() 

    scores = {}
    inverse_tickers = ["USDKRW=X", "^TNX", "CL=F", "^VIX", "^VKOSPI", "DX-Y.NYB"] 
    for t in UNIVERSE.keys():
        scores[t] = get_ai_ensemble_score(market_data.get(t, {"pct_change":0, "rsi":50, "macd_hist":0, "bb_pos":0.5}), is_inverse=(t in inverse_tickers))

    KOR_SPOT_SCORE = max(0.0, min(1.0, (st.session_state.spot_qty + 5000) / 10000))
    KOR_FUT_SCORE = max(0.0, min(1.0, (st.session_state.fut_cont + 10000) / 20000))

    semi_score = scores["^SOX"] + scores["NVDA"] + scores["TSM"] + scores["MU"] + scores["AVGO"] + scores["AMD"] + (AUTO_NEWS_SCORE * 0.5)
    macro_score = scores["USDKRW=X"] + scores["^TNX"] + scores["DX-Y.NYB"] + scores["GC=F"] + scores["HYG"] + scores["HG=F"]
    fear_score = scores["^VIX"] * 1.5 + scores["^VKOSPI"] * 1.0 
    korea_score = scores["EWY"] + scores.get("^KQ11", 0.5) + KOR_SPOT_SCORE + KOR_FUT_SCORE 
    dusan_score = scores["ETN"] + scores["URA"] + (AUTO_NEWS_SCORE * 1.5)
    auto_score = scores["TSLA"] + (AUTO_NEWS_SCORE * 1.0)
    defense_score = scores["ITA"] + scores["^VIX"] + (AUTO_NEWS_SCORE * 0.5)

    node_semi = (semi_score / 6.5) * 2 - 1
    node_macro = ((macro_score + fear_score) / 8.5) * 2 - 1
    node_infra = (dusan_score / 3.5) * 2 - 1
    node_kor = (korea_score / 4) * 2 - 1

    prob_bull = sigmoid(node_semi*1.5 + node_macro*1.0 + node_kor*1.0) * 100
    prob_rotation = sigmoid(-node_semi*1.0 + node_infra*1.5 + node_macro*0.5) * 100
    prob_panic = sigmoid(-node_macro*2.0 - node_kor*1.0) * 100

    tot_p = prob_bull + prob_rotation + prob_panic + 20
    prob_bull, prob_rotation, prob_panic = (prob_bull/tot_p)*100, (prob_rotation/tot_p)*100, (prob_panic/tot_p)*100

    max_prob = max(prob_bull, prob_rotation, prob_panic)
    kelly_factor = max(0, (max_prob/100) - ((1 - (max_prob/100)) / 1.5))
    kelly_factor = min(1.0, kelly_factor * 1.5) 

    if prob_panic > 40 or fear_score >= 1.8: regime, reg_color = "PANIC (매크로 붕괴)", "#ff4444"
    elif prob_bull > prob_rotation and prob_bull > 35: regime, reg_color = "BULL (테크 상승)", "#00ffcc"
    elif prob_rotation > 35 or defense_score >= 3.5: regime, reg_color = "ROTATION (순환매)", "#ffaa00"
    else: regime, reg_color = "NEUTRAL (관망 혼조)", "#a0aec0"

    # 타임라인 브리핑
    if use_time_machine: time_val = sim_time
    else: time_val = datetime.now().hour * 100 + datetime.now().minute
        
    us_tech_trend = market_data.get('^SOX', {}).get('pct_change', 0)
    fc = st.session_state.fut_cont
    fut_trend_txt = f"<span style='color:#00ffcc;'>{fc:,}계약 매수</span>" if fc > 0 else (f"<span style='color:#ff4444;'>{fc:,}계약 매도</span>" if fc < 0 else "중립")

    briefing_msg = ""
    if 800 <= time_val < 850:
        briefing_msg = f"🌅 **[08:00~08:50 NXT 프리마켓]** 반도체 **{us_tech_trend:+.2f}%**. 대체거래소(NXT) 장전 호가 탐색 및 켈리 비중({kelly_factor:.2f}x) 점검."
    elif 850 <= time_val < 900:
        briefing_msg = f"🔔 **[08:50~09:00 KRX 장전 동시호가]** 정규장 개장 임박. 시초가 갭 시나리오 점검 및 타점 호가창 세팅."
    elif 900 <= time_val < 930:
        if us_tech_trend > 1.0 and fc > 1000: briefing_msg = f"🟢 **[09:00~09:30 본장 초반] 돌파 매매:** 외인 선물 **{fut_trend_txt}**. 시초가 추격 매수 유효."
        elif us_tech_trend < -1.0 and fc < -1000: briefing_msg = f"🔴 **[09:00~09:30 본장 초반] 투매 주의:** 외인 선물 **{fut_trend_txt}**. 물타기 절대 금지 및 관망."
        else: briefing_msg = f"➖ **[09:00~09:30 본장 초반] 수급 탐색:** 뚜렷한 방향성 부재. 테마별 수급 이동 관망."
    elif 930 <= time_val < 1520:
        briefing_msg = f"☀️ **[09:30~15:20 정규장]** 장세는 **{regime}**. 밴드 하단에 도달한 종목 위주 분할 매수."
    elif 1520 <= time_val < 1530:
        briefing_msg = f"🌇 **[15:20~15:30 KRX 종가 동시호가]** 수급 방향성 확정. 목표 비중 미달 주도주 종가 오버나잇 집행."
    elif 1530 <= time_val <= 2000:
        briefing_msg = f"🌙 **[15:30~20:00 NXT 애프터마켓]** 시간외 단일가 및 대체거래소(NXT) 애프터마켓 가동. 장 마감 공시 반영."
    else:
        briefing_msg = f"🌌 **[20:00 이후]** 모든 거래소 마감. 계좌 복기 및 글로벌 야간 선물 모니터링."

    sim_badge = " <span class='badge-bear'>가상 시뮬레이션 중</span>" if use_time_machine else ""
    st.markdown(f"<div class='open-briefing'>🕒 <b>AI 알고리즘 대응{sim_badge}:</b> {briefing_msg}</div>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"<div class='metric-card' style='border-color:{reg_color};'><div class='metric-title'>시장 국면</div><div class='metric-value' style='color:{reg_color};'>{regime}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><div class='metric-title'>상승(Bull) 확률</div><div class='metric-value' style='color:#00ffcc;'>{prob_bull:.1f}%</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card'><div class='metric-title'>켈리 비중 (f*)</div><div class='metric-value' style='color:#ffdd00;'>{kelly_factor:.2f}x</div></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='metric-card'><div class='metric-title'>뉴스 센티멘탈</div><div class='metric-value' style='color:#00ffcc;'>{AUTO_NEWS_SCORE:.2f}</div></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader(f"🎯 실시간 리밸런싱 (MDD {st.session_state.mdd}% 방어)")
    
    alloc = kelly_factor * 100
    w = [0,0,0,0,0]
    if "PANIC" in regime: w = [0, 0, 0, 0, alloc*0.6]
    elif "BULL" in regime: w = [alloc*0.4, alloc*0.2, alloc*0.2, alloc*0.2, 0]
    elif "ROTATION" in regime: w = [alloc*0.1, alloc*0.1, alloc*0.3, alloc*0.2, alloc*0.3]
    else: w = [alloc*0.2, alloc*0.2, alloc*0.2, alloc*0.2, alloc*0.2]

    live_p = fetch_live_prices()
    prices = [live_p.get("000660.KS",0), live_p.get("005930.KS",0), live_p.get("034020.KS",0), live_p.get("307950.KS",0), live_p.get("449450.KS",0), pC_live]
    final_weights = w + [0]

    names = p_data["종목명"]
    avgs = p_data["평단가(원)"]
    holds = p_data["수량(주)"]
    custom_name = names[5] if names[5] != "💡 커스텀 종목" else ""

    total_asset = st.session_state.cash
    for i in range(6):
        if prices[i] > 0: total_asset += (prices[i] * holds[i])

    if custom_name != "" and "PANIC" not in regime:
        final_weights[5] = alloc * 0.15
        for i in range(5): final_weights[i] *= 0.85

    vol_mult = 1.0 + (market_data.get('^VIX', {}).get('price', 15) / 100) 
    t_arr = [1 + (0.04 * vol_mult), 1 + (0.03 * vol_mult), 1 + (0.05 * vol_mult), 1 + (0.045 * vol_mult), 1 + (0.03 * vol_mult), 1 + (0.05 * vol_mult)]
    s_arr = [1 - (0.02 * vol_mult), 1 - (0.015 * vol_mult), 1 - (0.025 * vol_mult), 1 - (0.025 * vol_mult), 1 - (0.015 * vol_mult), 1 - (0.03 * vol_mult)]
    if "PANIC" in regime: t_arr = [0,0,0,0,1+(0.08*vol_mult),0]; s_arr = [0,0,0,0,1-(0.04*vol_mult),0]

    FEE = 0.0023
    pre_loss = 0
    for i in range(6):
        if prices[i] > 0 and final_weights[i] > 0:
            t_qty = math.floor((total_asset * (final_weights[i]/100)) / prices[i])
            if t_qty > 0:
                pre_loss += ((t_qty * prices[i]) - (math.floor(prices[i]*s_arr[i]) * t_qty)) * (1 + FEE)

    shrink = 1.0
    max_loss = total_asset * (st.session_state.mdd / 100)
    if pre_loss > max_loss and pre_loss > 0:
        shrink = max_loss / pre_loss
        st.markdown(f"<div class='alert-card'>⚠️ <b>[MDD 방어]</b> 한도 초과! 비중을 {shrink*100:.1f}%로 축소.</div><br>", unsafe_allow_html=True)

    res_html = "<table class='data-table'><tr><th>종목명 (현재가)</th><th>평단가 (수익률)</th><th>비중</th><th>AI 판단</th><th>목표/손절</th><th>리밸런싱</th></tr>"
    tot_profit, tot_loss, tot_invest = 0, 0, 0

    for i in range(6):
        if i == 5 and custom_name == "": continue 
        
        p, avg, h = prices[i], avgs[i], holds[i]
        fw = final_weights[i] * shrink
        
        ret_pct = ((p - avg) / avg * 100) if avg > 0 else 0.0
        ret_str = f"<span style='color: #00ffcc;'>{ret_pct:+.2f}%</span>" if ret_pct > 0 else (f"<span style='color: #ff4444;'>{ret_pct:+.2f}%</span>" if ret_pct < 0 else "-")
        avg_disp = f"{avg:,.0f}원<br>({ret_str})" if avg > 0 else "-"
        
        # 0원 출력 버그 방어 텍스트 적용
        price_str = f"<span class='curr-price'>{p:,.0f}원</span>" if p > 0 else "<span style='color:#ff4444; font-size:0.85rem;'>통신대기</span>"
        
        if fw <= 0 or p <= 0:
            if h > 0 and fw == 0: act_badge = "<span class='badge-bull'>💰 익절</span>" if ret_pct > 0 else "<span class='badge-bear'>✂️ 손절</span>"; a_qty = -h
            else: act_badge = "<span class='badge-neutral'>관망</span>"; a_qty = 0
            res_html += f"<tr><td><b>{names[i]}</b><br>{price_str}</td><td>{avg_disp}</td><td>0.0%</td><td>{act_badge}</td><td>-</td><td>{f'<span class=badge-bear>매도 {a_qty}</span>' if a_qty<0 else '-'}</td></tr>"
            continue
        
        t_qty = math.floor((total_asset * (fw/100)) / p)
        a_qty = t_qty - h
        tgt_p = math.floor(p * t_arr[i])
        stp_p = math.floor(p * s_arr[i])
        
        if t_qty > 0:
            tot_invest += (t_qty * p)
            tot_profit += (tgt_p - p) * t_qty * (1 - FEE)
            tot_loss += (p - stp_p) * t_qty * (1 + FEE)
            
        if a_qty > 0:
            if avg > 0 and ret_pct > 0: act_badge = "<span class='badge-bull'>🔥 불타기</span>"
            elif avg > 0 and ret_pct < 0: act_badge = "<span class='badge-neutral'>💧 저점매수</span>"
            else: act_badge = "<span class='badge-bull'>🟢 신규진입</span>"
            action_str = f"<span style='color:#00ffcc; font-weight:bold;'>매수 +{a_qty}</span>"
        elif a_qty < 0:
            if avg > 0 and ret_pct > 0: act_badge = "<span class='badge-bull'>💰 부분익절</span>"
            else: act_badge = "<span class='badge-bear'>✂️ 손절</span>"
            action_str = f"<span style='color:#ff4444; font-weight:bold;'>매도 {a_qty}</span>"
        else:
            act_badge = "<span class='badge-neutral'>유지</span>"
            action_str = "-"
            
        res_html += f"<tr><td><b>{names[i]}</b><br>{price_str}</td><td>{avg_disp}</td><td>{fw:.0f}%</td><td>{act_badge}</td><td>🎯 {tgt_p:,.0f}<br>🛡️ {stp_p:,.0f}</td><td>{action_str}</td></tr>"

    res_html += "</table>"
    st.markdown(res_html, unsafe_allow_html=True)
    rrr = (tot_profit / tot_loss) if tot_loss > 0 else 0
    st.markdown(f"**💰 집행 금액:** {tot_invest:,.0f} 원 | **예상 잔여 현금:** {total_asset - tot_invest:,.0f} 원 | **⚖️ 예상 손익비:** {rrr:.2f}배")

# ----------------------------------------------------
# 🌐 [TAB 3] 글로벌 전광판 
# ----------------------------------------------------
with tab3:
    st.subheader("🌐 글로벌 매크로 & 섹터 실시간")
    df_display = []
    for t, name in UNIVERSE.items():
        d = market_data.get(t, {"price":0, "pct_change":0, "rsi":50, "macd_hist":0, "bb_pos":0.5})
        macd_badge = "<span class='badge-bull'>UP</span>" if d['macd_hist'] > 0 else "<span class='badge-bear'>DN</span>"
        if d['bb_pos'] < 0.1: bb_badge = "<span class='badge-bull'>하단</span>"
        elif d['bb_pos'] > 0.9: bb_badge = "<span class='badge-bear'>상단</span>"
        else: bb_badge = "<span class='badge-neutral'>횡보</span>"
        if d['rsi'] > 70: rsi_badge = f"<span class='badge-bear'>{d['rsi']:.0f}</span>"
        elif d['rsi'] < 30: rsi_badge = f"<span class='badge-bull'>{d['rsi']:.0f}</span>"
        else: rsi_badge = f"<span class='badge-neutral'>{d['rsi']:.0f}</span>"

        df_display.append({
            "지표명": f"<b>{name}</b>", "현재가": f"{d['price']:,.2f}",
            "변동률": f"<span style='color:{'#00ffcc' if d['pct_change']>0 else '#ff4444'};'>{d['pct_change']:+.2f}%</span>",
            "RSI": rsi_badge, "추세": macd_badge, "위치": bb_badge, "AI": f"<b style='color:#ebd197;'>{scores.get(t, 0.5):.2f}</b>"
        })
    matrix_html = "<table class='data-table'><tr>" + "".join([f"<th>{col}</th>" for col in df_display[0].keys()]) + "</tr>"
    for row in df_display: matrix_html += "<tr>" + "".join([f"<td>{val}</td>" for val in row.values()]) + "</tr>"
    matrix_html += "</table>"
    st.markdown(matrix_html, unsafe_allow_html=True)

# ----------------------------------------------------
# 💎 [TAB 4] AI 주도주 스캔 레이더 (별도 탭으로 완벽 분리)
# ----------------------------------------------------
with tab4:
    st.subheader("💎 AI 딥러닝 주도주 스캔 레이더")
    st.caption("AI가 한국 증시 전체를 스캔하여 주도주와 낙폭과대주를 발굴합니다.")

    KR_UNIVERSE = {
        "000660.KS": "SK하이닉스(HBM)", "042700.KS": "한미반도체(장비)", "064350.KS": "현대로템(방산)", 
        "079550.KS": "LIG넥스원(유도)", "034020.KS": "두산에너빌리티", "267260.KS": "HD현대일렉(전력)", 
        "307950.KS": "현대오토에버", "000270.KS": "기아(모빌리티)", "196170.KQ": "알테오젠(바이오)", 
        "207940.KS": "삼성바이오로직스"
    }

    with st.spinner("🔍 딥러닝 스캔 중..."):
        kr_data = fetch_quant_data(KR_UNIVERSE)

    if kr_data:
        rankings = []
        for t, name in KR_UNIVERSE.items():
            d = kr_data.get(t)
            if not d or d['price'] == 0: continue
            s = get_ai_ensemble_score(d)
            if "반도체" in name and prob_bull > 40: s += 0.2
            if ("방산" in name or "전력" in name) and prob_rotation > 30: s += 0.2
            if "바이오" in name and prob_panic > 30: s += 0.2
            rankings.append({"name": name, "price": d['price'], "score": s, "rsi": d['rsi'], "bb": d['bb_pos']})
        
        rankings.sort(key=lambda x: x['score'], reverse=True)
        
        st.markdown("<div style='padding: 10px; border:1px solid #cc33ff; border-radius:10px; background-color:#1a0a1a;'>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🔥 오늘 담아야 할 주도주 Top 3")
            for i in range(min(3, len(rankings))):
                r = rankings[i]
                st.markdown(f"**{i+1}. {r['name']}** ({r['price']:,.0f}원) <br><span style='color:#a0aec0; font-size:0.8rem;'>AI 스코어: {r['score']:.2f} | RSI: {r['rsi']:.1f}</span>", unsafe_allow_html=True)
                
        with c2:
            st.markdown("#### 🔄 턴어라운드 낙폭과대주")
            turnaround = [r for r in rankings if r['rsi'] < 50 and r['bb'] < 0.3]
            turnaround.sort(key=lambda x: x['rsi']) 
            if not turnaround: st.write("뚜렷한 종목이 없습니다.")
            else:
                for i in range(min(2, len(turnaround))):
                    r = turnaround[i]
                    st.markdown(f"**{i+1}. {r['name']}** ({r['price']:,.0f}원) <br><span style='color:#00ffcc; font-size:0.8rem;'>RSI: {r['rsi']:.1f} (반등 시그널)</span>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
