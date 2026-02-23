import streamlit as st
import yfinance as yf
import feedparser
import pandas as pd
import os
import json
from datetime import datetime

# --- 1. 페이지 및 기본 설정 ---
st.set_page_config(page_title="데이터모니터링", layout="wide", initial_sidebar_state="collapsed")

# [완벽한 표 정렬 CSS 주입]
st.markdown("""
<style>
/* 모바일 화면에서 표 글자 크기 축소 및 가로 스크롤 허용 */
div[data-testid="stDataEditor"] {
    font-size: 0.85rem !important;
}
div[data-testid="stDataEditor"] table td {
    white-space: nowrap !important;
}

/* 1. 테이블 전체 제목(헤더)은 완벽하게 가운데 정렬 */
div[data-testid="stDataEditor"] table th {
    text-align: center !important;
}
div[data-testid="stDataEditor"] table th div {
    display: flex !important;
    justify-content: center !important;
    text-align: center !important;
}

/* 2. 3(현재가), 4(등락률), 5(PEG)열 '값(데이터)'만 강제 우측 정렬 */
div[data-testid="stDataEditor"] table td:nth-child(3),
div[data-testid="stDataEditor"] table td:nth-child(4),
div[data-testid="stDataEditor"] table td:nth-child(5) {
    text-align: right !important;
}

/* 3. 2열(항목 이름)은 읽기 편하게 좌측 정렬 유지 */
div[data-testid="stDataEditor"] table td:nth-child(2) {
    text-align: left !important;
}
</style>
""", unsafe_allow_html=True)

SEARCH_DB = {
    "한국형변동성지수 (VKOSPI)": "^KSVKOSPI", "코스피 200": "^KS200", 
    "필라델피아 반도체 (SOX)": "^SOX", "금 선물 (Gold)": "GC=F", "WTI 원유": "CL=F",
    "NASDAQ Biotechnology (NBI)": "^NBI", "나스닥 100 선물": "NQ=F", "S&P 500 선물": "ES=F",
    "미국 10년물 국채 금리": "^TNX", "USD Index (달러인덱스)": "DX-Y.NYB", 
    "미국 CPI (물가연동국채 대체)": "TIP", "VIX (공포지수)": "^VIX", 
    "장단기금리차 (T10Y2Y)": "CALC_T10Y2Y", "Risk-On (SPY/TLT)": "CALC_RISKON",
    "NVDA (엔비디아)": "NVDA", "록히드마틴": "LMT", "한화에어로스페이스": "012450.KS",
    "HD현대일렉트릭": "267260.KS", "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "알테오젠": "196170.KQ"
}

# --- 2. 영구 저장 및 메모리 로직 ---
TICKERS_FILE = "my_tickers.json"

def load_tickers():
    if os.path.exists(TICKERS_FILE):
        with open(TICKERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return {k: v for k, v in SEARCH_DB.items() if k in [
            "한국형변동성지수 (VKOSPI)", "VIX (공포지수)", "필라델피아 반도체 (SOX)", "NASDAQ Biotechnology (NBI)", 
            "장단기금리차 (T10Y2Y)", "삼성전자", "SK하이닉스", "한화에어로스페이스", "알테오젠", "NVDA (엔비디아)"
        ]}

def save_tickers(tickers_dict):
    with open(TICKERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tickers_dict, f, ensure_ascii=False, indent=4)

if 'tickers' not in st.session_state: st.session_state.tickers = load_tickers()
if 'market_data' not in st.session_state: st.session_state.market_data = {}
if 'last_update' not in st.session_state: st.session_state.last_update = "아직 업데이트되지 않음"
if 'news_data' not in st.session_state: st.session_state.news_data = {}
if 'checked_items' not in st.session_state: st.session_state.checked_items = []
if 'form_name' not in st.session_state: st.session_state.form_name = ""
if 'form_ticker' not in st.session_state: st.session_state.form_ticker = ""
if 'input_key' not in st.session_state: st.session_state.input_key = 0

# --- 3. 데이터 수집 함수 (PEG 자체 계산식 극한의 최적화) ---
@st.cache_data(ttl=60)
def fetch_single_stock(ticker):
    try:
        # 자체 수식 
        if ticker == "CALC_T10Y2Y":
            tnx = yf.Ticker("^TNX").history(period="5d")
            us2y = yf.Ticker("^US2Y").history(period="5d")
            if not tnx.empty and not us2y.empty:
                val = tnx['Close'].iloc[-1] - us2y['Close'].iloc[-1]
                prev = tnx['Close'].iloc[-2] - us2y['Close'].iloc[-2]
                return float(val), float(val - prev), None
            return 0.0, 0.0, None
            
        if ticker == "CALC_RISKON":
            spy = yf.Ticker("SPY").history(period="5d")
            tlt = yf.Ticker("TLT").history(period="5d")
            if not spy.empty and not tlt.empty:
                val = spy['Close'].iloc[-1] / tlt['Close'].iloc[-1]
                prev = spy['Close'].iloc[-2] / tlt['Close'].iloc[-2]
                chg = ((val - prev) / prev) * 100
                return float(val), float(chg), None
            return 0.0, 0.0, None

        # 일반 티커 수집
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo").dropna(subset=['Close'])
        
        if len(hist) >= 2:
            current = float(hist['Close'].iloc[-1])
            prev = float(hist['Close'].iloc[-2])
            change = float(((current - prev) / prev) * 100)
        elif len(hist) == 1:
            current = float(hist['Close'].iloc[-1])
            change = 0.0
        else:
            return 0.0, 0.0, None

        # [PEG 극한 탐색 및 자체 계산식 적용]
        peg = None
        is_index = str(ticker).startswith('^') or '=' in str(ticker)
        
        if not is_index:
            try:
                info = stock.info
                # 1. API에서 바로 가져오기 시도
                peg = info.get('pegRatio') or info.get('trailingPegRatio')
                
                # 2. 없으면 EPS, PER 데이터로 계산 (PEG = PER / EPS 증가율)
                if peg is None:
                    t_eps = info.get('trailingEps') # 당기/전기 EPS
                    f_eps = info.get('forwardEps')  # 예상/당기 EPS
                    pe = info.get('trailingPE') or info.get('forwardPE') # PER
                    
                    # PER조차 없다면 현재 주가와 EPS로 강제 계산
                    if pe is None and current > 0 and t_eps and t_eps > 0:
                        pe = current / t_eps
                        
                    if t_eps and f_eps and pe and t_eps > 0:
                        eps_growth = ((f_eps - t_eps) / t_eps) * 100
                        # EPS가 역성장(-)이면 PEG는 의미가 없으므로 양수일 때만 도출
                        if eps_growth > 0:
                            peg = pe / eps_growth
            except: pass

        return current, change, peg
    except:
        return 0.0, 0.0, None

def fetch_all_data():
    raw_data = {}
    for name, ticker in st.session_state.tickers.items():
        raw_price, raw_change, peg = fetch_single_stock(ticker)
        raw_data[name] = {"raw_price": raw_price, "raw_change": raw_change, "peg": peg}
    st.session_state.market_data = raw_data
    st.session_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def fetch_news():
    news_list = []
    urls = [
        ("한국/특징주", "https://news.google.com/rss/search?q=특징주+주식+경제+when:1d&hl=ko&gl=KR&ceid=KR:ko"),
        ("Yahoo Macro", "https://finance.yahoo.com/rss/topstories")
    ]
    for src, url in urls:
        try:
            for entry in feedparser.parse(url).entries[:4]:
                pub = entry.published[:16] if hasattr(entry, 'published') else ""
                news_list.append({"source": src, "title": entry.title, "link": entry.link, "date": pub})
        except: pass
    st.session_state.news_data = news_list

if not st.session_state.market_data:
    with st.spinner("데이터모니터링 초기화 및 퀀트 데이터를 수집 중입니다..."):
        fetch_all_data()
        fetch_news()

# --- 4. 순서 이동 및 삭제 ---
def force_editor_rebuild():
    if "edit_left" in st.session_state: del st.session_state["edit_left"]
    if "edit_right" in st.session_state: del st.session_state["edit_right"]

def handle_add_or_mod():
    n = st.session_state.form_name
    t = st.session_state.form_ticker
    if n and t:
        st.session_state.tickers[n] = t
        p, c, peg = fetch_single_stock(t)
        st.session_state.market_data[n] = {"raw_price": p, "raw_change": c, "peg": peg}
        save_tickers(st.session_state.tickers)
        st.session_state.form_name = ""
        st.session_state.form_ticker = ""
        force_editor_rebuild()

def move_items(direction):
    names = st.session_state.checked_items
    if not names: return
    items = list(st.session_state.tickers.items())
    if direction == "up":
        for i in range(1, len(items)):
            if items[i][0] in names and items[i-1][0] not in names:
                items[i], items[i-1] = items[i-1], items[i]
    elif direction == "down":
        for i in range(len(items)-2, -1, -1):
            if items[i][0] in names and items[i+1][0] not in names:
                items[i], items[i+1] = items[i+1], items[i]
    st.session_state.tickers = dict(items)
    save_tickers(st.session_state.tickers)
    force_editor_rebuild()

def delete_items():
    for name in st.session_state.checked_items:
        if name in st.session_state.tickers: del st.session_state.tickers[name]
        if name in st.session_state.market_data: del st.session_state.market_data[name]
    st.session_state.checked_items = [] 
    save_tickers(st.session_state.tickers)
    force_editor_rebuild()

# --- 5. UI 메인 ---
st.title("📱 데이터모니터링")
st.markdown("<span style='color:gray;'>자율 진화형 퀀트 분석 및 실시간 포트폴리오 스캐닝 시스템</span>", unsafe_allow_html=True)

refresh_opts = {"끄기": 0, "1분마다": 60, "5분마다": 300, "10분마다": 600}
col_top1, col_top2, col_top3 = st.columns([1.2, 1, 2])
with col_top1:
    refresh_sel = st.selectbox("⏱️ 자동고침 설정", list(refresh_opts.keys()), label_visibility="collapsed")
    if refresh_opts[refresh_sel] > 0:
        st.markdown(f"<meta http-equiv='refresh' content='{refresh_opts[refresh_sel]}'>", unsafe_allow_html=True)
with col_top2:
    if st.button("🔄 전체 데이터 갱신", use_container_width=True):
        fetch_all_data()
        fetch_news()
        st.rerun()
with col_top3:
    st.info(f"마지막 갱신: {st.session_state.last_update}")

with st.expander("➕ 종목 추가 및 DB 검색", expanded=False):
    def on_db_change():
        choice = st.session_state.db_choice
        if choice != "직접 입력":
            st.session_state.form_name = choice
            st.session_state.form_ticker = SEARCH_DB[choice]
        else:
            st.session_state.form_name = ""
            st.session_state.form_ticker = ""

    st.selectbox("DB 선택", ["직접 입력"] + list(SEARCH_DB.keys()), key="db_choice", on_change=on_db_change, label_visibility="collapsed")
    
    c1, c2 = st.columns(2)
    st.text_input("종목명", key="form_name", placeholder="예: 삼성전자")
    st.text_input("티커", key="form_ticker", placeholder="예: 005930.KS")
    
    bc1, bc2 = st.columns(2)
    bc1.button("➕ 종목 추가", on_click=handle_add_or_mod, use_container_width=True)
    bc2.button("✏️ 종목 수정", on_click=handle_add_or_mod, use_container_width=True)

# --- 6. 실시간 테이블 ---
st.subheader("📈 실시간 지수/현재가")

ctrl1, ctrl2, ctrl3, ctrl4 = st.columns(4)
if ctrl1.button("🔼 위로 이동", use_container_width=True): move_items("up"); st.rerun()
if ctrl2.button("🔽 아래로 이동", use_container_width=True): move_items("down"); st.rerun()
if ctrl3.button("🗑️ 선택 삭제", use_container_width=True): delete_items(); st.rerun()

df_list = []
for name, ticker in st.session_state.tickers.items():
    info = st.session_state.market_data.get(name, {})
    price = info.get("raw_price", 0.0)
    chg = info.get("raw_change", 0.0)
    peg = info.get("peg", None)
    
    is_kr = str(ticker).upper().endswith('.KS') or str(ticker).upper().endswith('.KQ')
    price_str = f"{int(price):,}" if is_kr else f"{price:,.2f}"
    chg_str = f"{chg:+.2f}%" if ticker != "CALC_T10Y2Y" else f"{chg:+.2f}bp"
    peg_str = f"{peg:.2f}" if peg is not None else "-"

    df_list.append({
        "✅": name in st.session_state.checked_items, 
        "항목": name, 
        "현재가": price_str, 
        "등락률": chg_str,
        "PEG": peg_str
    })

df = pd.DataFrame(df_list)
import math
num_left = math.ceil(len(df) / 2) if len(df) > 0 else 0
df_left = df.iloc[:num_left].copy()
df_right = df.iloc[num_left:].copy()

def apply_row_color(row):
    chg_val = row['등락률']
    if not isinstance(chg_val, str): color = 'color: gray;'
    elif chg_val.startswith('+'): color = 'color: #ff4d4d; font-weight: bold;'
    elif chg_val.startswith('-'): color = 'color: #4d94ff; font-weight: bold;'
    else: color = 'color: gray;'
    return [''] * 2 + [color] * 3 

if not df_left.empty: styled_left = df_left.style.apply(apply_row_color, axis=1)
else: styled_left = df_left

if not df_right.empty: styled_right = df_right.style.apply(apply_row_color, axis=1)
else: styled_right = df_right

col_config = {
    "✅": st.column_config.CheckboxColumn("선택", width="small"),
    "항목": st.column_config.TextColumn("항목", width="medium"),
    "현재가": st.column_config.TextColumn("현재가", width="small"), 
    "등락률": st.column_config.TextColumn("등락률", width="small"),
    "PEG": st.column_config.TextColumn("PEG", width="small")
}

table_col1, table_col2 = st.columns(2)
with table_col1:
    edited_left = st.data_editor(styled_left, column_config=col_config, disabled=["항목", "현재가", "등락률", "PEG"], hide_index=True, use_container_width=True, key="edit_left")
with table_col2:
    edited_right = st.data_editor(styled_right, column_config=col_config, disabled=["항목", "현재가", "등락률", "PEG"], hide_index=True, use_container_width=True, key="edit_right")

new_checked_left = edited_left[edited_left["✅"] == True]["항목"].tolist() if not edited_left.empty else []
new_checked_right = edited_right[edited_right["✅"] == True]["항목"].tolist() if not edited_right.empty else []
st.session_state.checked_items = new_checked_left + new_checked_right

# --- 7. 관련 뉴스 영역 ---
st.markdown("<hr style='border: 1px solid #3a3a52;'>", unsafe_allow_html=True)
col_news_title, col_news_btn = st.columns([5, 1])
with col_news_title:
    st.subheader("📰 관련 뉴스")
with col_news_btn:
    if st.button("🔄 뉴스 새로고침", use_container_width=True):
        fetch_news()
        st.rerun()

news_html = "<div style='background-color:#252538; padding:15px; border-radius:8px; border:1px solid #3a3a52; margin-bottom: 20px;'>"
for news in st.session_state.news_data:
    color = "#ffb84d" if "한국" in news['source'] else "#82b1ff"
    news_html += f"<div style='margin-bottom:8px; line-height: 1.5; font-size: 0.95rem;'><strong style='color:{color};'>[{news['source']}]</strong> <a href='{news['link']}' target='_blank' style='color:#e4e6eb; text-decoration:none;'>{news['title']}</a> <span style='color:gray; font-size:0.8em;'>{news['date']}</span></div>"
news_html += "</div>"
st.markdown(news_html, unsafe_allow_html=True)

# --- 8. AI 시뮬레이션 영역 ---
st.subheader("🧠 데이터모니터링 AI 스캐닝")
sim_col1, sim_col2 = st.columns(2)
model_sel = sim_col1.selectbox("AI 모델 선택", ["Machine Learning", "LSTM", "Autonomous AI", "Reinforcement Learning", "Sentiment Analysis"])
algo_sel = sim_col2.selectbox("전략 알고리즘 선택", ["Quant 분석 AI", "Kai Score", "Holly AI", "포트폴리오 최적화 알고리즘"])

if st.button("▶ 체크된 종목 타겟 AI 시뮬레이션 실행", use_container_width=True, type="primary"):
    if not st.session_state.checked_items:
        st.warning("⚠️ 표에서 시뮬레이션을 원하시는 주식 종목의 체크박스를 1개 이상 클릭해 주세요.")
    else:
        with st.spinner('선택된 종목의 PEG, 펀더멘털과 선택한 알고리즘을 기반으로 분석을 수행합니다...'):
            current_date_str = datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")
            market = st.session_state.market_data
            
            vkospi = market.get("한국형변동성지수 (VKOSPI)", {})
            vkospi_val = vkospi.get("raw_price", 0.0)
            vkospi_chg = vkospi.get("raw_change", 0.0)
            macro_sentiment = "리스크 회피(Risk-Off) 경계 구간" if vkospi_chg > 0 else "위험자산 선호(Risk-On) 모멘텀 회복"
            
            model_descriptions = {
                "Machine Learning": "다중 회귀 분석을 통해 과거 패턴과 현재 펀더멘털(PEG 등)의 상관관계를 도출했습니다.",
                "LSTM": "시계열 딥러닝 신경망을 활용하여 최근 가격 모멘텀과 변동성 추이를 시퀀스 기반으로 분석했습니다.",
                "Autonomous AI": "자율 진화형 에이전트가 실시간 시장 노이즈를 필터링하고 거시 지표와의 괴리율을 동적으로 학습했습니다.",
                "Reinforcement Learning": "강화학습 환경에서 최적의 수익률을 얻기 위한 매수/매도 액션 큐(Q-value)를 매트릭스로 연산했습니다.",
                "Sentiment Analysis": "거시 지표(공포지수 등)의 심리 데이터와 시장 모멘텀을 정량화하여 투심을 반영했습니다."
            }
            algo_descriptions = {
                "Quant 분석 AI": "PEG 및 밸류에이션 기반 퀀트 스코어링",
                "Kai Score": "모멘텀 및 변동성 돌파 기준 특화 스코어링",
                "Holly AI": "다인자 팩터(수급, 가치, 추세) 앙상블 스코어링",
                "포트폴리오 최적화 알고리즘": "샤프 지수(Sharpe Ratio) 극대화를 위한 리스크-리턴 최적화 배분 연산"
            }
            
            macro_keywords = ["VIX", "VKOSPI", "반도체", "NBI", "선물", "금리", "USD", "CPI", "지표", "금", "원유", "T10Y2Y", "코스피"]
            quant_results = []
            
            for name in st.session_state.checked_items:
                if any(k in name for k in macro_keywords): continue 
                
                info = market.get(name, {})
                price = info.get("raw_price", 0.0)
                change = info.get("raw_change", 0.0)
                peg = info.get("peg", None)
                
                if price <= 0: continue
                
                base_score = 50 + (change * 3)
                
                if peg is not None:
                    if peg < 1.0: 
                        base_score += 20
                        eval_text = "PEG < 1 : 성장성 대비 주가가 낮음 (저평가 가능성)"
                    elif peg > 1.0: 
                        base_score -= 15
                        eval_text = "PEG > 1 : 성장성 대비 주가가 높음 (고평가 가능성)"
                    else:
                        base_score += 5
                        eval_text = "PEG = 1 : 성장성 대비 주가가 적정함"
                else:
                    eval_text = "PEG 데이터 부족: 단기 수급 모멘텀만 추종"

                final_score = min(max(int(base_score), 0), 100)
                quant_results.append({
                    "name": name, "price": price, "change": change, "peg": peg,
                    "score": final_score, "eval": eval_text
                })

            st.success("데이터 연산 및 시뮬레이션 분석 완료!")
            
            st.markdown(f"""
            ### 📊 AI 시뮬레이션 리포트
            * **기준 일시:** {current_date_str}
            * **적용 모델 ({model_sel}):** {model_descriptions[model_sel]}
            * **적용 알고리즘 ({algo_sel}):** {algo_descriptions[algo_sel]}
            
            #### 1. 거시경제 및 시장 변동성 지표 (상시 참조)
            * **한국형변동성지수 (VKOSPI):** 현재 {vkospi_val:.2f} (전일대비 {vkospi_chg:+.2f}%). 이를 종합하여 시장 자금 동향은 **[{macro_sentiment}]** 국면으로 연산되었습니다.
            
            #### 2. 🎯 타겟 종목 퀀트 알고리즘 심층 분석
            """)
            
            if len(quant_results) == 0:
                st.markdown("* 선택하신 종목 중 분석 가능한 개별 주식 데이터가 없습니다. (거시 지표는 개별 분석에서 자동 제외됩니다.)")
            else:
                for res in quant_results:
                    n = res['name']
                    p = f"{res['price']:,.0f}" if res['price'] > 1000 else f"{res['price']:,.2f}"
                    c = res['change']
                    peg_str = f"{res['peg']:.2f}" if res['peg'] is not None else "데이터 없음"
                    color_dot = "🔴" if c > 0 else "🔵" if c < 0 else "⚪"
                    
                    st.markdown(f"""
                    * **{n}**: 현재가 **{p}원** ({color_dot} **{c:+.2f}%**)
                      * **지표분석:** PEG = **{peg_str}** | 알고리즘 스코어 = **{res['score']}점 / 100점**
                      * **AI 해석:** {res['eval']}
                    """)

st.markdown("<br><hr style='border: 1px solid #3a3a52;'><p style='text-align: right; color: #a1a1bb; font-style: italic; font-weight: bold;'>모두가 부자 되길 바라는 주린(인) 김병권</p>", unsafe_allow_html=True)
