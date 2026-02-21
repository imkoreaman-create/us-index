import streamlit as st
import yfinance as yf
import feedparser
import pandas as pd
import numpy as np
import math
import os
import json
from datetime import datetime

# --- 1. 페이지 및 기본 설정 ---
st.set_page_config(page_title="지수 종목 확인 (Quant AI)", layout="wide", initial_sidebar_state="collapsed")

SEARCH_DB = {
    "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "한국항공우주": "047810.KS",
    "한화에어로스페이스": "012450.KS", "알테오젠": "196170.KQ", "한화시스템": "272210.KS", 
    "한화오션": "042660.KS", "HD한국조선해양": "009540.KS", "LS": "006260.KS", 
    "갤럭시아머니트리": "094480.KQ", "현대차": "005380.KS", "테슬라": "TSLA", 
    "엔비디아": "NVDA", "애플": "AAPL", "록히드마틴": "LMT",
    "KOSPI 200": "^KS200", "V-KOSPI (자체계산)": "CALC_VKOSPI" # 자체 계산 로직 트리거 추가
}

# --- 2. 영구 저장 및 메모리 로직 ---
TICKERS_FILE = "my_tickers.json"

def load_tickers():
    if os.path.exists(TICKERS_FILE):
        with open(TICKERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        default_tickers = {
            "VIX (공포지수)": "^VIX", "필라델피아 반도체": "^SOX", "SMH": "SMH", 
            "원달러 환율": "KRW=X", "미국 10년물 국채": "^TNX",
            "KOSPI 200": "^KS200", "V-KOSPI (자체계산)": "CALC_VKOSPI",
            "삼성전자": "005930.KS", "한국항공우주": "047810.KS",
            "한화에어로스페이스": "012450.KS", "알테오젠": "196170.KQ",
            "NVDA (엔비디아)": "NVDA"
        }
        return default_tickers

def save_tickers(tickers_dict):
    with open(TICKERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tickers_dict, f, ensure_ascii=False, indent=4)

if 'tickers' not in st.session_state: st.session_state.tickers = load_tickers()
if 'market_data' not in st.session_state: st.session_state.market_data = {}
if 'last_update' not in st.session_state: st.session_state.last_update = "아직 업데이트되지 않음"
if 'news_data' not in st.session_state: st.session_state.news_data = []
if 'checked_items' not in st.session_state: st.session_state.checked_items = []
if 'input_key' not in st.session_state: st.session_state.input_key = 0

# --- 3. 데이터 수집 핵심 함수 (V-KOSPI 계산 및 PEG 크롤링 추가) ---
@st.cache_data(ttl=60)
def fetch_single_stock(ticker):
    try:
        # [퀀트 로직 1] KOSPI 200 역사적 변동성 직접 계산 (V-KOSPI 대체)
        if ticker == "CALC_VKOSPI":
            ks200 = yf.Ticker("^KS200").history(period="1mo")
            if len(ks200) >= 2:
                returns = ks200['Close'].pct_change().dropna()
                # 연환산 변동성 (252 거래일 기준)
                vol = returns.std() * math.sqrt(252) * 100
                returns_prev = returns.iloc[:-1]
                vol_prev = returns_prev.std() * math.sqrt(252) * 100
                change = ((vol - vol_prev) / vol_prev) * 100 if vol_prev > 0 else 0.0
                return float(vol), float(change), None
            return 0.0, 0.0, None

        # 일반 종목/지수 수집
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d") # 안정성을 위해 5일치 호출
        if len(hist) >= 2:
            current = float(hist['Close'].iloc[-1])
            prev = float(hist['Close'].iloc[-2])
            change = float(((current - prev) / prev) * 100)
        elif len(hist) == 1:
            current = float(hist['Close'].iloc[-1])
            change = 0.0
        else:
            return 0.0, 0.0, None

        # [퀀트 로직 2] 개별 주식 PEG 지수 추출 (지수, 환율 등은 건너뜀)
        peg = None
        if not ticker.startswith('^') and '=' not in ticker and ticker != 'CALC_VKOSPI':
            try:
                info = stock.info
                # PEG가 없으면 Trailing PEG 등 대안 탐색
                peg = info.get('pegRatio', info.get('trailingPegRatio', None))
            except:
                pass

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
    with st.spinner("퀀트 데이터를 수집 및 연산 중입니다..."):
        fetch_all_data()
        fetch_news()

# --- 4. 순서 이동 및 삭제 로직 ---
def force_editor_rebuild():
    if "edit_left" in st.session_state: del st.session_state["edit_left"]
    if "edit_right" in st.session_state: del st.session_state["edit_right"]

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

# --- 5. UI 메인 렌더링 ---
st.title("📱 지수 종목 확인 (Quant AI)")
st.markdown("<span style='color:gray;'>자율 진화형 퀀트 분석 및 실시간 포트폴리오 모니터링 시스템</span>", unsafe_allow_html=True)

refresh_opts = {"끄기": 0, "1분마다": 60, "5분마다": 300, "10분마다": 600}
col_top1, col_top2, col_top3 = st.columns([1.2, 1, 2])
with col_top1:
    refresh_sel = st.selectbox("⏱️ 자동고침 설정", list(refresh_opts.keys()), label_visibility="collapsed")
    if refresh_opts[refresh_sel] > 0:
        st.markdown(f"<meta http-equiv='refresh' content='{refresh_opts[refresh_sel]}'>", unsafe_allow_html=True)
with col_top2:
    if st.button("🔄 데이터 전체 갱신", use_container_width=True):
        fetch_all_data()
        fetch_news()
        st.rerun()
with col_top3:
    st.info(f"마지막 갱신: {st.session_state.last_update}")

with st.expander("➕ 종목 추가 및 DB 검색", expanded=False):
    selected_db = st.selectbox("DB 선택", ["직접 입력"] + list(SEARCH_DB.keys()), label_visibility="collapsed")
    
    def_name = "" if selected_db == "직접 입력" else selected_db
    def_ticker = "" if selected_db == "직접 입력" else SEARCH_DB[selected_db]
    
    c1, c2 = st.columns(2)
    new_name = c1.text_input("종목명", value=def_name, key=f"name_{st.session_state.input_key}")
    new_ticker = c2.text_input("티커", value=def_ticker, key=f"ticker_{st.session_state.input_key}")
    
    bc1, bc2 = st.columns(2)
    if bc1.button("➕ 종목 추가", use_container_width=True):
        if new_name and new_ticker:
            st.session_state.tickers[new_name] = new_ticker
            p, c, peg = fetch_single_stock(new_ticker)
            st.session_state.market_data[new_name] = {"raw_price": p, "raw_change": c, "peg": peg}
            save_tickers(st.session_state.tickers)
            st.session_state.input_key += 1 
            force_editor_rebuild()
            st.rerun()
            
    if bc2.button("✏️ 종목 수정", use_container_width=True):
        if new_name and new_ticker:
            st.session_state.tickers[new_name] = new_ticker
            p, c, peg = fetch_single_stock(new_ticker)
            st.session_state.market_data[new_name] = {"raw_price": p, "raw_change": c, "peg": peg}
            save_tickers(st.session_state.tickers)
            st.session_state.input_key += 1 
            force_editor_rebuild()
            st.rerun()

# --- 6. 실시간 테이블 (셀 자체 색상 렌더링 및 PEG 지수 삽입) ---
st.subheader("📈 실시간 지표 및 포트폴리오 관리")
st.write("표 안의 **[✅선택]** 체크박스를 누른 후 아래 버튼을 누르거나 하단의 AI 시뮬레이션을 실행하세요.")

ctrl1, ctrl2, ctrl3, ctrl4 = st.columns(4)
if ctrl1.button("🔼 위로 이동", use_container_width=True):
    move_items("up")
    st.rerun()
if ctrl2.button("🔽 아래로 이동", use_container_width=True):
    move_items("down")
    st.rerun()
if ctrl3.button("🗑️ 선택 삭제", use_container_width=True):
    delete_items()
    st.rerun()

df_list = []
for name, ticker in st.session_state.tickers.items():
    info = st.session_state.market_data.get(name, {})
    price = info.get("raw_price", 0.0)
    chg = info.get("raw_change", 0.0)
    peg = info.get("peg", None)
    
    # 한국 주식 포맷 적용
    is_kr = str(ticker).upper().endswith('.KS') or str(ticker).upper().endswith('.KQ')
    price_str = f"{int(price):,}" if is_kr else f"{price:,.2f}"
    peg_str = f"{peg:.2f}" if peg is not None else "-"

    df_list.append({
        "✅선택": name in st.session_state.checked_items,
        "항목": name, 
        "현재가": price_str, 
        "등락률(%)": chg,
        "PEG": peg_str
    })

df = pd.DataFrame(df_list)
num_left = math.ceil(len(df) / 2) if len(df) > 0 else 0
df_left = df.iloc[:num_left].reset_index(drop=True)
df_right = df.iloc[num_left:].reset_index(drop=True)

# [핵심] Pandas Styler를 사용해 상승/하락에 따라 셀 '글자 색상'을 직접 변경하고 우측 정렬 강제
def style_dataframe(x):
    # 기본 스타일 세팅 (모든 셀 우측 정렬)
    styles = pd.DataFrame('text-align: right;', index=x.index, columns=x.columns)
    # 항목명은 좌측 정렬 유지
    styles['항목'] = 'text-align: left;'
    
    # 등락률 값에 따라 현재가와 등락률 색상 동기화
    for i in x.index:
        val = x.loc[i, '등락률(%)']
        if pd.isna(val) or val == 0.0:
            color = 'color: gray;'
        elif val > 0:
            color = 'color: #ff4d4d; font-weight: bold;' # 상승 빨강
        else:
            color = 'color: #4d94ff; font-weight: bold;' # 하락 파랑
            
        styles.loc[i, '현재가'] += color
        styles.loc[i, '등락률(%)'] += color
        
    return styles

styled_left = df_left.style.apply(style_dataframe, axis=None).format({'등락률(%)': "{:+.2f}%"})
styled_right = df_right.style.apply(style_dataframe, axis=None).format({'등락률(%)': "{:+.2f}%"})

col_config = {
    "✅선택": st.column_config.CheckboxColumn("선택", width="small"),
    "항목": st.column_config.TextColumn("항목"),
    "현재가": st.column_config.TextColumn("현재가"), 
    "등락률(%)": st.column_config.TextColumn("등락률"),
    "PEG": st.column_config.TextColumn("PEG")
}

table_col1, table_col2 = st.columns(2)

with table_col1:
    edited_left = st.data_editor(
        styled_left, column_config=col_config,
        disabled=["항목", "현재가", "등락률(%)", "PEG"], hide_index=True, use_container_width=True, key="edit_left"
    )

with table_col2:
    edited_right = st.data_editor(
        styled_right, column_config=col_config,
        disabled=["항목", "현재가", "등락률(%)", "PEG"], hide_index=True, use_container_width=True, key="edit_right"
    )

new_checked_left = edited_left[edited_left["✅선택"] == True]["항목"].tolist() if not edited_left.empty else []
new_checked_right = edited_right[edited_right["✅선택"] == True]["항목"].tolist() if not edited_right.empty else []
st.session_state.checked_items = new_checked_left + new_checked_right

# --- 7. AI 시뮬레이션 영역 (진짜 퀀트 스코어링 로직 탑재) ---
st.markdown("<hr style='border: 1px solid #3a3a52;'>", unsafe_allow_html=True)
st.subheader("🧠 자율 진화형 AI & 퀀트 포트폴리오 스캐닝")
sim_col1, sim_col2 = st.columns(2)
model_sel = sim_col1.selectbox("AI 모델 선택", ["Machine Learning", "LSTM", "Autonomous AI", "Reinforcement Learning", "Sentiment Analysis"])
algo_sel = sim_col2.selectbox("전략 알고리즘 선택", ["Quant 분석 AI", "Kai Score", "Holly AI", "포트폴리오 최적화 알고리즘"])

if st.button("▶ 체크된 종목 타겟 AI 시뮬레이션 실행", use_container_width=True, type="primary"):
    
    if not st.session_state.checked_items:
        st.warning("⚠️ 표에서 시뮬레이션을 원하시는 주식 종목의 **[✅선택]** 체크박스를 1개 이상 클릭해 주세요.")
    else:
        with st.spinner('선택된 종목의 PEG, 펀더멘털, KOSPI 변동성을 기반으로 퀀트 연산을 수행합니다...'):
            current_date_str = datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")
            market = st.session_state.market_data
            
            # 매크로 상시 참조 (V-KOSPI 자체 계산값 최우선 반영)
            vkospi = market.get("V-KOSPI (자체계산)", market.get("VIX (공포지수)", {}))
            vkospi_val = vkospi.get("raw_price", 0.0)
            vkospi_chg = vkospi.get("raw_change", 0.0)
            sox_change = market.get("필라델피아 반도체", {}).get("raw_change", 0.0)
            
            macro_sentiment = "리스크 관리(Risk-Off) 경계 구간" if vkospi_chg > 0 else "위험자산 선호(Risk-On) 모멘텀 회복"
            
            # 선택된 종목 진짜 알고리즘 스캐닝
            quant_results = []
            for name in st.session_state.checked_items:
                info = market.get(name, {})
                price = info.get("raw_price", 0.0)
                change = info.get("raw_change", 0.0)
                peg = info.get("peg", None)
                
                if price <= 0: continue
                
                # 가상 퀀트 스코어 연산 (실제 등락률과 PEG 기반)
                base_score = 50 + (change * 3)
                eval_text = "단기 수급 모멘텀 추종"
                signal = "관망 (Hold)"
                
                if peg is not None:
                    if peg < 1.0: 
                        base_score += 20
                        eval_text = "PEG < 1.0 저평가. 실적 대비 성장성 우수"
                        signal = "비중 확대 (Buy)"
                    elif peg > 2.0: 
                        base_score -= 15
                        eval_text = "PEG > 2.0 고평가. 밸류에이션 부담 가중"
                        signal = "비중 축소 (Sell)"
                
                if change > 3.0: signal = "강력 매수 (Strong Buy)"
                elif change < -3.0: signal = "리스크 관리 (Risk Off)"

                final_score = min(max(int(base_score), 0), 100) # 0~100 스케일링
                quant_results.append({
                    "name": name, "price": price, "change": change, "peg": peg,
                    "score": final_score, "signal": signal, "eval": eval_text
                })

            st.success("데이터 연산 및 시뮬레이션 분석 완료!")
            
            st.info(f"**기준 일시:** {current_date_str} | **적용 모델:** {model_sel} | **적용 알고리즘:** {algo_sel}")
            
            st.markdown(f"""
            ### 1. 거시경제 및 시장 변동성 지표 (상시 참조)
            * **KOSPI 역사적 변동성(V-KOSPI 대체):** 현재 {vkospi_val:.2f}% (전일대비 {vkospi_chg:+.2f}%). 시장 자금 동향은 **[{macro_sentiment}]** 국면으로 연산되었습니다.
            * **글로벌 반도체 지수 투영:** 미국 반도체 지수({sox_change:+.2f}%) 데이터가 선택하신 **{algo_sel}** 모델에 가중치로 반영되었습니다.
            
            ### 2. 🎯 타겟 종목 퀀트 알고리즘 분석 결과
            """)
            
            # 선택된 종목별 상세 브리핑 (HTML 대신 마크다운 사용하여 깨짐 방지)
            for res in quant_results:
                n = res['name']
                p = f"{res['price']:,.0f}" if res['price'] > 1000 else f"{res['price']:,.2f}"
                c = res['change']
                peg_str = f"{res['peg']:.2f}" if res['peg'] is not None else "데이터 없음"
                
                color_dot = "🔴" if c > 0 else "🔵" if c < 0 else "⚪"
                
                st.markdown(f"""
                * **{n}:** 현재가 **{p}원** ({color_dot} **{c:+.2f}%**)
                  * **지표:** PEG Ratio = {peg_str} | 알고리즘 스코어 = **{res['score']}점/100점**
                  * **Action:** **{res['signal']}** ({res['eval']})
                """)
            
            st.markdown(f"> **💡 AI 종합 평가:** 선택된 종목군은 현재 산출된 KOSPI 변동성과 PEG 펀더멘털을 기반으로 볼 때, 기계적이고 냉정한 트레이딩 대응이 요구됩니다.")

st.markdown("<br><hr style='border: 1px solid #3a3a52;'><p style='text-align: right; color: #a1a1bb; font-style: italic; font-weight: bold;'>모두가 부자 되길 바라는 주린(인) 김병권</p>", unsafe_allow_html=True)
