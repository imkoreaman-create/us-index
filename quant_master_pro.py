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
import warnings
warnings.filterwarnings('ignore')

# ==========================================
# 🛡️ 0. 글로벌 상태 초기화 (오토에버 티커 307950 복구)
# ==========================================
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame({
        "종목명": ["SK하이닉스", "삼성전자", "두산에너빌리티", "현대오토에버", "PLUS K방산", "💡 커스텀 종목"],
        "평단가(원)": [0, 0, 0, 0, 0, 0],
        "수량(주)": [0, 0, 0, 0, 0, 0]
    })

# ==========================================
# ⚙️ 1. Streamlit GUI 세팅 및 CSS
# ==========================================
st.set_page_config(page_title="Quantum Pro - V19 Ultimate AI", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #050507; color: #e2e8f0; }
    h2, h3 { color: #fff; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 0px; }
    .highlight { color: #00ffcc; text-shadow: 0 0 12px rgba(0,255,204,0.6); }
    
    .metric-card { background: linear-gradient(145deg, #111216, #1a1c23); border: 1px solid #2d3748; padding: 15px; border-radius: 10px; border-left: 4px solid #00ffcc; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    .metric-title { font-size: 0.8rem; color: #a0aec0; margin-bottom: 4px; font-weight: 600; }
    .metric-value { font-size: 1.1rem; font-weight: 800; letter-spacing: -0.5px; }
    
    .alert-card { background: linear-gradient(145deg, #1a0f14, #241419); border: 1px solid #ff3366; padding: 15px; border-radius: 10px; border-left: 4px solid #ff3366; font-size: 0.9rem;}
    .open-briefing { background: linear-gradient(145deg, #0f172a, #1a202c); border: 1px solid #3182ce; padding: 15px; border-radius: 10px; border-left: 4px solid #3182ce; margin-bottom: 15px; font-size: 0.9rem;}
    .creator-mark { font-size: 0.75rem; color: #ebd197; text-align: right; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 10px;}
    
    .badge-bull { background: rgba(0,255,204,0.15); color: #00ffcc; padding: 3px 6px; border-radius: 4px; font-size: 0.75rem; border: 1px solid rgba(0,255,204,0.3); font-weight: bold;}
    .badge-bear { background: rgba(255,68,68,0.15); color: #ff4444; padding: 3px 6px; border-radius: 4px; font-size: 0.75rem; border: 1px solid rgba(255,68,68,0.3); font-weight: bold;}
    .badge-neutral { background: rgba(160,174,192,0.15); color: #a0aec0; padding: 3px 6px; border-radius: 4px; font-size: 0.75rem; border: 1px solid rgba(160,174,192,0.3); font-weight: bold;}
    
    [data-testid="stNumberInputContainer"] button { display: none !important; }
    input[type="number"] { -moz-appearance: textfield; font-weight: bold; color: #ffdd00 !important; text-align: center !important; font-size: 0.9rem !important;}
    
    .data-table { width: 100%; border-collapse: collapse; background: #111216; border-radius: 10px; overflow: hidden; margin-bottom: 20px; font-size: 0.8rem;}
    .data-table th, .data-table td { padding: 10px 8px; text-align: right; border-bottom: 1px solid #2d3748; }
    .data-table th { background: #0a0a0c; color: #ff9900; font-weight: 600; text-align: center; }
    .data-table td:first-child, .data-table th:first-child { text-align: left; background: #16181d; font-weight: bold; border-right: 1px solid #2d3748;}
    .data-table tr:hover { background-color: rgba(255,255,255,0.03); }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 📡 2. 데이터 파이프라인 (네이버 펄백 엔진)
# ==========================================
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
        us_tickers = [t for t in tickers if not (".KS" in t or ".KQ" in t)]
        df_raw = yf.download(us_tickers, period="3mo", progress=False)
        df = df_raw['Close'] if isinstance(df_raw.columns, pd.MultiIndex) else df_raw
    except: 
        df = pd.DataFrame()
    finally:
        sys.stderr = old_stderr
        f.close()

    for t in tickers:
        try:
            if ".KS" in t or ".KQ" in t:
                code = t.split('.')[0]
                url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=60&requestType=0"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                res = urllib.request.urlopen(req, timeout=3).read().decode('euc-kr')
                root = ET.fromstring(res)
                closes = [float(item.attrib['data'].split('|')[4]) for item in root.findall('.//item')]
                series = pd.Series(closes)
            else:
                if not df.empty and t in df.columns and not df[t].dropna().empty:
                    series = df[t].dropna()
                else: raise ValueError
                    
            if len(series) < 14: raise ValueError
            
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
            vol = series.pct_change().std() * math.sqrt(252) * 100
            
            data_store[t] = {"price": curr_p, "pct_change": pct, "rsi": rsi, "macd_hist": macd_val, "bb_pos": bb_position, "vol": vol}
        except:
            data_store[t] = {"price": 0, "pct_change": 0, "rsi": 50, "macd_hist": 0, "bb_pos": 0.5, "vol": 20.0}

    if "^VKOSPI" in tickers and data_store["^VKOSPI"]["price"] == 0:
        vix_p = data_store.get("^VIX", {}).get("price", 15.0)
        data_store["^VKOSPI"] = {"price": vix_p * 1.05, "pct_change": 0, "rsi": 50, "macd_hist": 0, "bb_pos": 0.5, "vol": 20.0}

    return data_store

@st.cache_data(ttl=60)
def fetch_live_prices():
    # 🔥 오토에버 307950 완벽 복구
    tickers = ["000660.KS", "005930.KS", "034020.KS", "307950.KS", "449450.KS"]
    prices = {t: 0 for t in tickers}
    for t in tickers:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                data = yf.Ticker(t).history(period="5d")
                if not data.empty: prices[t] = int(data['Close'].iloc[-1])
                else: raise ValueError
        except:
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
# 🖥️ 3. 스트림릿 사이드바 (센티멘탈 감성 분석 입력)
# ==========================================
st.sidebar.markdown("<div class='creator-mark'>✨ 모두가 부자 되길 바라는 주린(인)님 병권</div>", unsafe_allow_html=True)

st.sidebar.header("🌐 KOSPI 외국인 수급")
spot_qty = st.sidebar.number_input("현물 순매수 (천주)", value=0, step=100, format="%d")
fut_cont = st.sidebar.number_input("선물 순매수 (계약)", value=0, step=500, format="%d")
KOR_SPOT_SCORE = max(0.0, min(1.0, (spot_qty + 5000) / 10000))
KOR_FUT_SCORE = max(0.0, min(1.0, (fut_cont + 10000) / 20000))

st.sidebar.markdown("---")
st.sidebar.header("💼 계좌 및 리스크 설정")
TOTAL_CASH = st.sidebar.number_input("가용 현금 (원)", value=50000000, step=1000000, format="%d")
RISK_LIMIT_PCT = st.sidebar.slider("MDD 손실 한도 (%)", 0.5, 10.0, 2.0, 0.1)
DDAY_HEDGE = st.sidebar.checkbox("⚠️ D-Day 헷지 (비중 50% 삭감)")

st.sidebar.markdown("---")
st.sidebar.subheader("🧠 정성/감성 분석 팩터 (AI 보정용)")
NEWS_AI_INFRA = st.sidebar.slider("AI 인프라 뉴스 (1:극호재, 0:극악재)", 0.0, 1.0, 0.5, 0.25)
NEWS_EXPORT = st.sidebar.slider("방산/원전 수주 뉴스 감성", 0.0, 1.0, 0.5, 0.25)

st.sidebar.markdown("---")
st.sidebar.subheader("📊 나의 포트폴리오 에디터")
edited_portfolio = st.sidebar.data_editor(
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
names = p_data["종목명"]
avgs = p_data["평단가(원)"]
holds = p_data["수량(주)"]

custom_name = names[5] if names[5] != "💡 커스텀 종목" else ""
pC_live = st.sidebar.number_input("커스텀 종목 현재가", value=0, format="%d")

# ==========================================
# 📊 4. 딥러닝 앙상블 코어 연산 및 대시보드
# ==========================================
st.markdown("<h2 style='margin-bottom:5px;'>Quantum <span class='highlight'>V19 Ultimate AI</span></h2>", unsafe_allow_html=True)
st.caption(f"최종 스캔 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 정량/정성 딥러닝 융합 모드 가동 중")

UNIVERSE = {
    "^SOX": "필라델피아반도체", "NVDA": "엔비디아", "TSM": "TSMC", "MU": "마이크론", "AVGO": "브로드컴", "AMD": "AMD",
    "QQQ": "나스닥ETF", "NQ=F": "나스닥선물(NQ)", "ES=F": "S&P500선물(ES)", "AAPL": "애플", 
    "BTC-USD": "비트코인", "USDKRW=X": "원달러환율", "^TNX": "미10년금리", "DX-Y.NYB": "달러인덱스(DXY)", "GC=F": "금(Gold)", 
    "CL=F": "WTI유가", "HG=F": "구리(Copper)", "^VIX": "VIX", "^VKOSPI": "VKOSPI(국내공포)", "HYG": "하이일드(리스크)",
    "EWY": "MSCI한국", "ETN": "이튼(미 전력)", "URA": "우라늄ETF", "TSLA": "테슬라", "ITA": "미 방산ETF"
}

with st.spinner("🤖 V19 신경망이 정량적 데이터와 정성적 뉴스 팩터를 융합 중입니다..."):
    market_data = fetch_quant_data(UNIVERSE)

scores = {}
inverse_tickers = ["USDKRW=X", "^TNX", "CL=F", "^VIX", "^VKOSPI", "DX-Y.NYB"] 
for t in UNIVERSE.keys():
    scores[t] = get_ai_ensemble_score(market_data.get(t, {"pct_change":0, "rsi":50, "macd_hist":0, "bb_pos":0.5}), is_inverse=(t in inverse_tickers))

# 🔥 딥러닝 시그모이드 노드 연산 (뉴스 감성 분석 가중치 강화)
semi_score = scores["^SOX"] + scores["NVDA"] + scores["TSM"] + scores["MU"] + scores["AVGO"] + scores["AMD"] + (NEWS_AI_INFRA * 1.5)
macro_score = scores["USDKRW=X"] + scores["^TNX"] + scores["DX-Y.NYB"] + scores["GC=F"] + scores["HYG"] + scores["HG=F"]
fear_score = scores["^VIX"] * 1.5 + scores["^VKOSPI"] * 1.0 
korea_score = scores["EWY"] + KOR_SPOT_SCORE + KOR_FUT_SCORE 
dusan_score = scores["ETN"] + scores["URA"] + (NEWS_AI_INFRA * 2.0) + (NEWS_EXPORT * 1.5)
auto_score = scores["TSLA"] + (NEWS_AI_INFRA * 1.0)
defense_score = scores["ITA"] + scores["^VIX"] + (NEWS_EXPORT * 2.5) # 방산은 뉴스 민감도 극대화

node_semi = (semi_score / 7.5) * 2 - 1
node_macro = ((macro_score + fear_score) / 8.5) * 2 - 1
node_infra = (dusan_score / 5.5) * 2 - 1
node_kor = (korea_score / 3) * 2 - 1

prob_bull = sigmoid(node_semi*1.5 + node_macro*1.0 + node_kor*1.0) * 100
prob_rotation = sigmoid(-node_semi*1.0 + node_infra*1.5 + node_macro*0.5) * 100
prob_panic = sigmoid(-node_macro*2.0 - node_kor*1.0) * 100

tot_p = prob_bull + prob_rotation + prob_panic + 20
prob_bull, prob_rotation, prob_panic = (prob_bull/tot_p)*100, (prob_rotation/tot_p)*100, (prob_panic/tot_p)*100

max_prob = max(prob_bull, prob_rotation, prob_panic)
confidence = max(0, max_prob - ((100 - max_prob)/2))

R = 1.5 
W = max_prob / 100
kelly_factor = max(0, W - ((1 - W) / R))
kelly_factor = min(1.0, kelly_factor * 1.5) 
if DDAY_HEDGE: kelly_factor *= 0.5

if prob_panic > 40 or fear_score >= 1.8: regime, reg_color = "PANIC (매크로 붕괴)", "#ff4444"
elif prob_bull > prob_rotation and prob_bull > 35: regime, reg_color = "BULL (테크 주도)", "#00ffcc"
elif prob_rotation > 35 or defense_score >= 3.5: regime, reg_color = "ROTATION (순환매)", "#ffaa00"
else: regime, reg_color = "NEUTRAL (관망/혼조)", "#a0aec0"

# ==========================================
# 🔥 5. K-Market 타임라인 루틴
# ==========================================
now_hour = datetime.now().hour
now_minute = datetime.now().minute
time_val = now_hour * 100 + now_minute

us_tech_trend = market_data.get('^SOX', {}).get('pct_change', 0)
fut_trend_txt = f"<span style='color:#00ffcc;'>{fut_cont:,}계약 매수</span>" if fut_cont > 0 else (f"<span style='color:#ff4444;'>{fut_cont:,}계약 매도</span>" if fut_cont < 0 else "중립")

briefing_msg = ""
if 800 <= time_val < 900:
    briefing_msg = f"🌅 **[08:00~09:00 장전 동시호가]** 간밤 반도체 지수 **{us_tech_trend:+.2f}%**. 오늘의 켈리 비중({kelly_factor:.2f}x)에 맞춰 호가창 세팅 요망."
elif 900 <= time_val < 930:
    if us_tech_trend > 1.0 and fut_cont > 1000: briefing_msg = f"🟢 **[오전 변동성] 돌파 매매:** 외인 선물 **{fut_trend_txt}** 포착. 주도주 추격 매수 유효."
    elif us_tech_trend < -1.0 and fut_cont < -1000: briefing_msg = f"🔴 **[오전 변동성] 투매 주의:** 외인 선물 **{fut_trend_txt}** 포착. 물타기 금지 및 관망."
    else: briefing_msg = f"➖ **[오전 변동성] 수급 탐색:** 뚜렷한 방향성 부재. 테마별 수급 이동 관망."
elif 930 <= time_val < 1520:
    briefing_msg = f"☀️ **[정규장] 추세 확인:** 장세는 **{regime}** 국면. AI 스코어가 높고 밴드 하단에 위치한 종목 분할 매수."
elif 1520 <= time_val < 1530:
    briefing_msg = f"🌇 **[종가 베팅]** 당일 수급 방향성 확정. 목표 비중 미달 주도주 종가 오버나잇 집행."
else:
    briefing_msg = f"🌙 **[장 마감 / 야간]** 계좌 복기 및 글로벌 매크로 지표 변동성 모니터링."

st.markdown(f"<div class='open-briefing'>🕒 <b>K-Market 알고리즘 대응:</b> {briefing_msg}</div>", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
col1.markdown(f"<div class='metric-card' style='border-color:{reg_color};'><div class='metric-title'>시장 국면 (AI 융합 판독)</div><div class='metric-value' style='color:{reg_color};'>{regime}</div></div>", unsafe_allow_html=True)
col2.markdown(f"<div class='metric-card'><div class='metric-title'>주도장(Bull/Rot) 확률</div><div class='metric-value' style='color:#00ffcc;'>{max(prob_bull, prob_rotation):.1f}%</div></div>", unsafe_allow_html=True)
col3.markdown(f"<div class='metric-card'><div class='metric-title'>동적 켈리 비중 (f*)</div><div class='metric-value' style='color:#ffdd00;'>{kelly_factor:.2f}x</div></div>", unsafe_allow_html=True)
col4.markdown(f"<div class='metric-card'><div class='metric-title'>AI 공포 (VKOSPI/VIX)</div><div class='metric-value' style='color:#ff4444;'>{fear_score:.2f} / 2.5</div></div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
st.subheader("🌐 글로벌 매크로 & 섹터 실시간 전광판")

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
        "RSI": rsi_badge, "추세": macd_badge, "위치": bb_badge, "AI 스코어": f"<b style='color:#ebd197;'>{scores.get(t, 0.5):.2f}</b>"
    })

matrix_html = "<table class='data-table'><tr>" + "".join([f"<th>{col}</th>" for col in df_display[0].keys()]) + "</tr>"
for row in df_display: matrix_html += "<tr>" + "".join([f"<td>{val}</td>" for val in row.values()]) + "</tr>"
matrix_html += "</table>"
st.markdown(matrix_html, unsafe_allow_html=True)

# ==========================================
# 🛡️ 6. 실전 계좌 리밸런싱 (오토에버 적용 완료)
# ==========================================
st.markdown("---")
st.subheader(f"🎯 딥러닝 타점 분석 (MDD {RISK_LIMIT_PCT}% 방어)")

alloc = kelly_factor * 100
w = [0,0,0,0,0]
if "PANIC" in regime: w = [0, 0, 0, 0, alloc*0.6]
elif "BULL" in regime: w = [alloc*0.4, alloc*0.2, alloc*0.2, alloc*0.2, 0]
elif "ROTATION" in regime: w = [alloc*0.1, alloc*0.1, alloc*0.3, alloc*0.2, alloc*0.3]
else: w = [alloc*0.2, alloc*0.2, alloc*0.2, alloc*0.2, alloc*0.2]

live_p = fetch_live_prices()
prices = [live_p.get("000660.KS",0), live_p.get("005930.KS",0), live_p.get("034020.KS",0), live_p.get("307950.KS",0), live_p.get("449450.KS",0), pC_live]
final_weights = w + [0]

total_asset = TOTAL_CASH
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

if total_asset > 0:
    for i in range(6):
        if prices[i] > 0 and final_weights[i] > 0:
            t_qty = math.floor((total_asset * (final_weights[i]/100)) / prices[i])
            if t_qty > 0:
                pre_loss += ((t_qty * prices[i]) - (math.floor(prices[i]*s_arr[i]) * t_qty)) * (1 + FEE)

shrink = 1.0
max_loss = total_asset * (RISK_LIMIT_PCT / 100)
if pre_loss > max_loss and pre_loss > 0:
    shrink = max_loss / pre_loss
    st.markdown(f"<div class='alert-card'>⚠️ <b>[MDD 방어 가동]</b> 예상 손실({pre_loss:,.0f}원) 한도 초과! 비중을 {shrink*100:.1f}%로 축소합니다.</div><br>", unsafe_allow_html=True)

res_html = "<table class='data-table'><tr><th>종목명 (현재가)</th><th>평단가 (수익률)</th><th>비중</th><th>AI 판단</th><th>목표/손절</th><th>리밸런싱</th></tr>"

tot_profit, tot_loss, tot_invest = 0, 0, 0

for i in range(6):
    if i == 5 and custom_name == "": continue 
    
    p, avg, h = prices[i], avgs[i], holds[i]
    fw = final_weights[i] * shrink
    
    ret_pct = ((p - avg) / avg * 100) if avg > 0 else 0.0
    ret_str = f"<span style='color: #00ffcc;'>{ret_pct:+.2f}%</span>" if ret_pct > 0 else (f"<span style='color: #ff4444;'>{ret_pct:+.2f}%</span>" if ret_pct < 0 else "-")
    avg_disp = f"{avg:,.0f}원<br>({ret_str})" if avg > 0 else "-"
    
    if fw <= 0 or p <= 0:
        if h > 0 and fw == 0:
            act_badge = "<span class='badge-bull'>💰 익절</span>" if ret_pct > 0 else "<span class='badge-bear'>✂️ 손절</span>"
            a_qty = -h
        else:
            act_badge = "<span class='badge-neutral'>관망</span>"
            a_qty = 0
            
        res_html += f"<tr><td><b>{names[i]}</b><br><span style='color:#a0aec0;'>{p:,.0f}원</span></td><td>{avg_disp}</td><td>0.0%</td><td>{act_badge}</td><td>-</td><td>{f'<span class=badge-bear>매도 {a_qty}주</span>' if a_qty<0 else '-'}</td></tr>"
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
        action_str = f"<span style='color:#00ffcc; font-weight:bold;'>매수 +{a_qty}주</span>"
    elif a_qty < 0:
        if avg > 0 and ret_pct > 0: act_badge = "<span class='badge-bull'>💰 부분 익절</span>"
        else: act_badge = "<span class='badge-bear'>✂️ 리스크 축소</span>"
        action_str = f"<span style='color:#ff4444; font-weight:bold;'>매도 {a_qty}주</span>"
    else:
        act_badge = "<span class='badge-neutral'>유지</span>"
        action_str = "-"
        
    res_html += f"<tr><td><b>{names[i]}</b><br><span style='color:#a0aec0;'>{p:,.0f}원</span></td><td>{avg_disp}</td><td>{fw:.0f}%</td><td>{act_badge}</td><td>🎯 {tgt_p:,.0f}<br>🛡️ {stp_p:,.0f}</td><td>{action_str}</td></tr>"

res_html += "</table>"
st.markdown(res_html, unsafe_allow_html=True)

rrr = (tot_profit / tot_loss) if tot_loss > 0 else 0
st.markdown(f"**💰 집행 금액:** {tot_invest:,.0f} 원 | **예상 잔여 현금:** {total_asset - tot_invest:,.0f} 원 | **⚖️ 손익비:** {rrr:.2f}배")

# ==========================================
# 💎 7. AI 주도주 스캔 레이더 (정성/감성 딥러닝 편입)
# ==========================================
st.markdown("---")
st.markdown("### 💎 [AI 주도주 스캔 레이더]")

KR_UNIVERSE = {
    "000660.KS": "SK하이닉스 (HBM 대장)", "042700.KS": "한미반도체 (장비 대장)", "064350.KS": "현대로템 (방산 수출)", 
    "079550.KS": "LIG넥스원 (유도무기)", "034020.KS": "두산에너빌리티 (원전/SMR)", "267260.KS": "HD현대일렉트릭 (전력망)", 
    "307950.KS": "현대오토에버 (SDV)", "000270.KS": "기아 (모빌리티)", "196170.KQ": "알테오젠 (바이오)", 
    "207940.KS": "삼성바이오로직스 (CDMO)"
}

with st.spinner("🔍 한국 증시 딥러닝 스캔 중..."):
    kr_data = fetch_quant_data(KR_UNIVERSE)

if kr_data:
    rankings = []
    for t, name in KR_UNIVERSE.items():
        d = kr_data.get(t)
        if not d or d['price'] == 0: continue
        
        # 🧠 감성 분석 가중치 부스팅
        s = get_ai_ensemble_score(d)
        if "반도체" in name: s += (NEWS_AI_INFRA * 0.2)
        if ("방산" in name or "전력" in name): s += (NEWS_EXPORT * 0.2)
        
        rankings.append({"name": name, "price": d['price'], "score": s, "rsi": d['rsi'], "bb": d['bb_pos']})
    
    rankings.sort(key=lambda x: x['score'], reverse=True)
    
    st.markdown("<div class='ai-radar'>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🔥 오늘 반드시 담아야 할 주도주 Top 3")
        for i in range(min(3, len(rankings))):
            r = rankings[i]
            st.markdown(f"**{i+1}. {r['name']}** (현재가: {r['price']:,.0f}원) <br><span style='color:#a0aec0; font-size:0.8rem;'>AI 감성스코어: {r['score']:.2f} | RSI: {r['rsi']:.1f}</span>", unsafe_allow_html=True)
            
    with c2:
        st.markdown("#### 🔄 턴어라운드 유망주 (낙폭과대/지지선)")
        turnaround = [r for r in rankings if r['rsi'] < 50 and r['bb'] < 0.3]
        turnaround.sort(key=lambda x: x['rsi']) 
        if not turnaround:
            st.write("현재 뚜렷한 낙폭과대 턴어라운드 종목이 없습니다.")
        else:
            for i in range(min(2, len(turnaround))):
                r = turnaround[i]
                st.markdown(f"**{i+1}. {r['name']}** (현재가: {r['price']:,.0f}원) <br><span style='color:#00ffcc; font-size:0.8rem;'>반등 시그널 포착 (RSI: {r['rsi']:.1f})</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
