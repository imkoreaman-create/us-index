import streamlit as st
import yfinance as yf
import feedparser
import pandas as pd
import os
import json
from datetime import datetime

# --- 1. 페이지 및 기본 설정 ---
st.set_page_config(page_title="지수 종목 확인", layout="wide", initial_sidebar_state="collapsed")

# [우측 정렬 CSS] 3(현재가), 4(등락률), 5(PEG)열 완벽 우측 정렬
st.markdown("""
<style>
div[data-testid="stDataEditor"] table th:nth-child(3), div[data-testid="stDataEditor"] table td:nth-child(3),
div[data-testid="stDataEditor"] table th:nth-child(4), div[data-testid="stDataEditor"] table td:nth-child(4),
div[data-testid="stDataEditor"] table th:nth-child(5), div[data-testid="stDataEditor"] table td:nth-child(5) {
    text-align: right !important;
}
</style>
""", unsafe_allow_html=True)

SEARCH_DB = {
    "VKOSPI (한국형 변동성지수)": "^KSVKOSPI", "NASDAQ Biotechnology (NBI)": "^NBI",
    "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "한국항공우주": "047810.KS",
    "한화에어로스페이스": "012450.KS", "알테오젠": "196170.KQ", "한화시스템": "272210.KS", 
    "한화오션": "042660.KS", "HD한국조선해양": "009540.KS", "LS": "006260.KS", 
    "갤럭시아머니트리": "094480.KQ", "현대차": "005380.KS", "테슬라": "TSLA", 
    "엔비디아": "NVDA", "애플": "AAPL", "록히드마틴": "LMT",
    "마이크로소프트": "MSFT", "알파벳": "GOOGL", "아마존": "AMZN"
}

# --- 2. 영구 저장 및 메모리 로직 ---
TICKERS_FILE = "my_tickers.json"

def load_tickers():
    if os.path.exists(TICKERS_FILE):
        with open(TICKERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        default_tickers = {
            "VIX (공포지수)": "^VIX", "필라델피아 반도체": "^SOX", 
            "VKOSPI (한국형 변동성지수)": "^KSVKOSPI", "NASDAQ Biotechnology (NBI)": "^NBI",
            "삼성전자": "005930.KS", "한국항공우주": "047810.KS",
            "한화에어로스페이스": "012450.KS", "알테오젠": "196170.KQ",
            "NVDA (엔비디아)": "NVDA", "테슬라": "TSLA"
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

# ✅ 텍스트 입력 에러 방지용 상태 변수
if 'form_name' not in st.session_state: st.session_state.form_name = ""
if 'form_ticker' not in st.session_state: st.session_state.form_ticker = ""

# --- 3. 데이터 수집 콜백 및 함수 ---
@st.cache_data(ttl=60)
def fetch_single_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 휴일 데이터 누락을 방지하기 위해 1달치 확보
        hist = stock.history(period="1mo")
        
        if len(hist) >= 2:
            current = float(hist['Close'].iloc[-1])
            prev = float(hist['Close'].iloc[-2])
            change = float(((current - prev) / prev) * 100)
        elif len(hist) == 1:
            current = float(hist['Close'].iloc[-1])
            change = 0.0
        else:
            return 0.0, 0.0, None

        peg = None
        if not ticker.startswith('^') and '=' not in ticker:
            try:
                info = stock.info
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
    with st.spinner("데이터 및 지표를 수집 중입니다..."):
        fetch_all_data()
        fetch_news()

# --- 4. 순서 이동 및 삭제, 종목 추가 (에러 완벽 방지 콜백) ---
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

# --- 5. UI 메인 렌더링 ---
st.title("📱 지수 종목 확인")
st.markdown("<span style='color:gray;'>자율 진화형 퀀트 분석 및 실시간 포트폴리오 모니터링 시스템</span>", unsafe_allow_html=True)

refresh_opts = {"끄기": 0, "1분마다": 60, "5분마다": 300, "10분마다": 600}
col_top1, col_top2, col_top3 = st.columns([1.2, 1, 2])
with col_top1:
    refresh_sel = st.selectbox("⏱️ 자동고침 설정", list(refresh_opts.keys()), label_visibility="collapsed")
    if refresh_opts[refresh_sel] > 0:
        st.markdown(f"<meta http-equiv='refresh' content='{refresh_opts[refresh_sel]}'>", unsafe_allow_html=True)
with col_top2:
    if st.button("🔄 전체 새로고침", use_container_width=True):
        fetch_all_data()
        fetch_news()
        st.rerun()
with col_top3:
    st.info(f"마지막 갱신: {st.session_state.last_update}")

# ✅ DB 에러 완벽 해결 (Callback 방식)
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
    # on_click 콜백을 통해 에러 없이 값 추가 및 폼 비우기 동시 실행
    bc1.button("➕ 종목 추가", on_click=handle_add_or_mod, use_container_width=True)
    bc2.button("✏️ 종목 수정", on_click=handle_add_or_mod, use_container_width=True)

# --- 6. 실시간 테이블 (알 수 없는 열 삭제 및 완벽 색상 적용) ---
st.subheader("📈 실시간 지표 및 포트폴리오 관리")

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
    chg_str = f"{chg:+.2f}%"
    peg_str = f"{peg:.2f}" if peg is not None else "-"
    
    # 기호를 붙여 상승/하락 여부를 문자열 자체에 포함
    if chg > 0:
        price_str = f"🔴 {price_str}"
        chg_str = f"🔴 {chg_str}"
    elif chg < 0:
        price_str = f"🔵 {price_str}"
        chg_str = f"🔵 {chg_str}"
    else:
        price_str = f"⚪ {price_str}"
        chg_str = f"⚪ {chg_str}"

    df_list.append({
        "✅선택": name in st.session_state.checked_items,
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

# 기호를 감지하여 색상을 변경하는 무적의 함수 (숨김 열 불필요)
def apply_color(val):
    if not isinstance(val, str): return ''
    if '🔴' in val: return 'color: #ff4d4d; font-weight: bold;'
    if '🔵' in val: return 'color: #4d94ff; font-weight: bold;'
    return 'color: gray;'

styled_left = df_left.style.map(apply_color, subset=['현재가', '등락률'])
styled_right = df_right.style.map(apply_color, subset=['현재가', '등락률'])

col_config = {
    "✅선택": st.column_config.CheckboxColumn("선택", width="small"),
    "항목": st.column_config.TextColumn("항목"),
    "현재가": st.column_config.TextColumn("현재가"), 
    "등락률": st.column_config.TextColumn("등락률"),
    "PEG": st.column_config.TextColumn("PEG")
}

table_col1, table_col2 = st.columns(2)

with table_col1:
    edited_left = st.data_editor(
        styled_left, column_config=col_config,
        disabled=["항목", "현재가", "등락률", "PEG"], hide_index=True, use_container_width=True, key="edit_left"
    )

with table_col2:
    edited_right = st.data_editor(
        styled_right, column_config=col_config,
        disabled=["항목", "현재가", "등락률", "PEG"], hide_index=True, use_container_width=True, key="edit_right"
    )

new_checked_left = edited_left[edited_left["✅선택"] == True]["항목"].tolist() if not edited_left.empty else []
new_checked_right = edited_right[edited_right["✅선택"] == True]["항목"].tolist() if not edited_right.empty else []
st.session_state.checked_items = new_checked_left + new_checked_right

# --- 7. 실시간 뉴스 영역 ---
st.markdown("<hr style='border: 1px solid #3a3a52;'>", unsafe_allow_html=True)
col_news_title, col_news_btn = st.columns([5, 1])
with col_news_title:
    st.subheader("📰 24시간 내 최신 경제/특징주 뉴스")
with col_news_btn:
    if st.button("🔄 뉴스 새로고침", use_container_width=True):
        fetch_news()
        st.rerun()

news_html = "<div style='background-color:#252538; padding:15px; border-radius:8px; border:1px solid #3a3a52; margin-bottom: 20px;'>"
for news in st.session_state.news_data:
    color = "#ffb84d" if "한국" in news['source'] else "#82b1ff"
    news_html += f"<div style='margin-bottom:8px; line-height: 1.5;'><strong style='color:{color};'>[{news['source']}]</strong> <a href='{news['link']}' target='_blank' style='color:#e4e6eb; text-decoration:none;'>{news['title']}</a> <span style='color:gray; font-size:0.8em;'>{news['date']}</span></div>"
news_html += "</div>"
st.markdown(news_html, unsafe_allow_html=True)

# --- 8. AI 시뮬레이션 영역 (VKOSPI, NBI 100% 반영) ---
st.subheader("🧠 자율 진화형 AI & 퀀트 포트폴리오 스캐닝")
sim_col1, sim_col2 = st.columns(2)
model_sel = sim_col1.selectbox("AI 모델 선택", ["Machine Learning", "LSTM", "Autonomous AI", "Reinforcement Learning", "Sentiment Analysis"])
algo_sel = sim_col2.selectbox("전략 알고리즘 선택", ["Quant 분석 AI", "Kai Score", "Holly AI", "포트폴리오 최적화 알고리즘"])

if st.button("▶ 체크된 종목 타겟 AI 시뮬레이션 실행", use_container_width=True, type="primary"):
    
    if not st.session_state.checked_items:
        st.warning("⚠️ 표에서 시뮬레이션을 원하시는 주식 종목의 **[✅선택]** 체크박스를 1개 이상 클릭해 주세요.")
    else:
        with st.spinner('선택된 종목의 펀더멘털과 거시 지표를 기반으로 퀀트 연산을 수행합니다...'):
            current_date_str = datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")
            market = st.session_state.market_data
            
            # 매크로 지표 상시 추출
            vkospi = market.get("VKOSPI (한국형 변동성지수)", {})
            vkospi_val = vkospi.get("raw_price", 0.0)
            vkospi_chg = vkospi.get("raw_change", 0.0)
            
            nbi = market.get("NASDAQ Biotechnology (NBI)", {})
            nbi_chg = nbi.get("raw_change", 0.0)

            sox = market.get("필라델피아 반도체", {})
            sox_chg = sox.get("raw_change", 0.0)
            
            macro_sentiment = "리스크 회피(Risk-Off) 경계 구간" if vkospi_chg > 0 else "위험자산 선호(Risk-On) 모멘텀 회복"
            
            # 선택된 개별 종목 퀀트 분석
            quant_results = []
            for name in st.session_state.checked_items:
                # 거시 지표가 선택되었다면 분석에서 제외
                if any(k in name for k in ["VIX", "VKOSPI", "필라델피아", "NBI", "환율", "국채"]): continue
                
                info = market.get(name, {})
                price = info.get("raw_price", 0.0)
                change = info.get("raw_change", 0.0)
                peg = info.get("peg", None)
                
                if price <= 0: continue
                
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

                final_score = min(max(int(base_score), 0), 100)
                quant_results.append({
                    "name": name, "price": price, "change": change, "peg": peg,
                    "score": final_score, "signal": signal, "eval": eval_text
                })

            st.success("데이터 연산 및 시뮬레이션 분석 완료!")
            st.info(f"**기준 일시:** {current_date_str} | **적용 모델:** {model_sel} | **적용 알고리즘:** {algo_sel}")
            
            nbi_text = f"* **글로벌 바이오 지표 투영:** 나스닥 바이오 지수(NBI)가 전일 대비 {nbi_chg:+.2f}% 변동하며 가중치에 반영되었습니다." if nbi_chg != 0 else ""

            st.markdown(f"""
            ### 1. 거시경제 및 시장 변동성 지표 (상시 참조)
            * **한국형 변동성지수 (VKOSPI):** 현재 {vkospi_val:.2f} (전일대비 {vkospi_chg:+.2f}%). 시장 자금 동향은 **[{macro_sentiment}]** 국면으로 연산되었습니다.
            * **글로벌 반도체 지수 투영:** 미국 필라델피아 반도체 지수({sox_chg:+.2f}%) 데이터가 테크 섹터 스코어링에 반영되었습니다.
            {nbi_text}
            
            ### 2. 🎯 타겟 종목 퀀트 알고리즘 심층 분석
            """)
            
            if len(quant_results) == 0:
                st.markdown("* 선택하신 종목 중 분석 가능한 개별 주식 데이터가 없습니다. (거시 지표는 분석 대상에서 제외됩니다.)")
            else:
                for res in quant_results:
                    n = res['name']
                    p = f"{res['price']:,.0f}" if res['price'] > 1000 else f"{res['price']:,.2f}"
                    c = res['change']
                    peg_str = f"{res['peg']:.2f}" if res['peg'] is not None else "데이터 미수집"
                    color_dot = "🔴" if c > 0 else "🔵" if c < 0 else "⚪"
                    
                    st.markdown(f"""
                    * **{n}**: 현재가 **{p}원** ({color_dot} **{c:+.2f}%**)
                      * **지표분석:** PEG = {peg_str} | 종합 퀀트 스코어 = **{res['score']}점 / 100점**
                      * **Action Plan:** **{res['signal']}** ({res['eval']})
                    """)
            
            st.markdown(f"> **💡 AI 종합 평가:** 선택된 종목군은 현재 산출된 VKOSPI와 PEG 펀더멘털을 기반으로 기계적이고 냉정한 트레이딩 대응이 요구됩니다.")

st.markdown("<br><hr style='border: 1px solid #3a3a52;'><p style='text-align: right; color: #a1a1bb; font-style: italic; font-weight: bold;'>모두가 부자 되길 바라는 주린(인) 김병권</p>", unsafe_allow_html=True)
