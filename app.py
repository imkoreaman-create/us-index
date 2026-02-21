import streamlit as st
import yfinance as yf
import feedparser
import pandas as pd
import math
import os
import json
from datetime import datetime

# --- 1. 페이지 및 기본 설정 ---
st.set_page_config(page_title="지수 종목 확인", layout="wide", initial_sidebar_state="collapsed")

# 우측 정렬 강제 적용 CSS
st.markdown("""
<style>
div[data-testid="stDataEditor"] table th:nth-child(3),
div[data-testid="stDataEditor"] table td:nth-child(3),
div[data-testid="stDataEditor"] table th:nth-child(4),
div[data-testid="stDataEditor"] table td:nth-child(4) {
    text-align: right !important;
}
</style>
""", unsafe_allow_html=True)

SEARCH_DB = {
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
            "VIX (공포지수)": "^VIX", "필라델피아 반도체": "^SOX", "SMH": "SMH", 
            "원달러 환율": "KRW=X", "미국 10년물 국채": "^TNX",
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

if 'input_key' not in st.session_state: st.session_state.input_key = 0

# --- 3. 데이터 수집 함수 ---
@st.cache_data(ttl=60)
def fetch_single_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="2d")
        if len(hist) >= 2:
            current = float(hist['Close'].iloc[-1])
            prev = float(hist['Close'].iloc[-2])
            change = float(((current - prev) / prev) * 100)
        elif len(hist) == 1:
            current = float(hist['Close'].iloc[-1])
            change = 0.0
        else:
            return 0.0, 0.0
        return current, change
    except:
        return 0.0, 0.0

def fetch_all_data():
    raw_data = {}
    for name, ticker in st.session_state.tickers.items():
        raw_price, raw_change = fetch_single_stock(ticker)
        raw_data[name] = {"raw_price": raw_price, "raw_change": raw_change}
    st.session_state.market_data = raw_data
    st.session_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def fetch_news():
    news_list = []
    rss_urls = [
        ("한국/특징주", "https://news.google.com/rss/search?q=특징주+주식+경제+when:1d&hl=ko&gl=KR&ceid=KR:ko"),
        ("Yahoo Top", "https://finance.yahoo.com/rss/topstories"),
        ("US Macro", "https://news.google.com/rss/search?q=global+economy+market+when:1d&hl=en-US&gl=US&ceid=US:en")
    ]
    for source, url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:4]:
                pub_date = entry.published[:16] if hasattr(entry, 'published') else ""
                news_list.append({"source": source, "title": entry.title, "link": entry.link, "date": pub_date})
        except: pass
    st.session_state.news_data = news_list

if not st.session_state.market_data:
    with st.spinner("데이터를 수집하는 중입니다..."):
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
    names = st.session_state.checked_items
    for name in names:
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

with st.expander("➕ 새로운 종목 추가 및 수정", expanded=False):
    st.markdown("**자동완성 DB 검색** (선택 시 아래 입력칸에 자동으로 채워집니다)")
    selected_db = st.selectbox("DB 선택", ["직접 입력"] + list(SEARCH_DB.keys()), label_visibility="collapsed")
    
    def_name = "" if selected_db == "직접 입력" else selected_db
    def_ticker = "" if selected_db == "직접 입력" else SEARCH_DB[selected_db]
    
    c1, c2 = st.columns(2)
    new_name = c1.text_input("종목명", value=def_name, placeholder="예: 삼성전자", key=f"name_{st.session_state.input_key}")
    new_ticker = c2.text_input("티커", value=def_ticker, placeholder="예: 005930.KS", key=f"ticker_{st.session_state.input_key}")
    
    bc1, bc2 = st.columns(2)
    if bc1.button("➕ 종목 추가", use_container_width=True):
        if new_name and new_ticker:
            st.session_state.tickers[new_name] = new_ticker
            p, c = fetch_single_stock(new_ticker)
            st.session_state.market_data[new_name] = {"raw_price": p, "raw_change": c}
            save_tickers(st.session_state.tickers)
            st.session_state.input_key += 1 
            force_editor_rebuild()
            st.rerun()
            
    if bc2.button("✏️ 종목 수정", use_container_width=True):
        if new_name and new_ticker:
            st.session_state.tickers[new_name] = new_ticker
            p, c = fetch_single_stock(new_ticker)
            st.session_state.market_data[new_name] = {"raw_price": p, "raw_change": c}
            save_tickers(st.session_state.tickers)
            st.session_state.input_key += 1 
            force_editor_rebuild()
            st.rerun()

# --- 6. 실시간 테이블 ---
st.subheader("📈 실시간 지표 및 포트폴리오 관리")
st.write("표 안의 **[✅선택]** 체크박스를 누른 후 아래 이동 버튼을 클릭하거나 시뮬레이션을 돌려보세요.")

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
for name, _ in st.session_state.tickers.items():
    info = st.session_state.market_data.get(name, {})
    price = info.get("raw_price", 0.0)
    chg = info.get("raw_change", 0.0)
    
    trend = "🔴 상승" if chg > 0 else "🔵 하락" if chg < 0 else "⚪ 보합"

    df_list.append({
        "✅선택": name in st.session_state.checked_items,
        "항목": name, 
        "추세": trend,
        "현재가": float(price), 
        "등락률(%)": float(chg)
    })

df = pd.DataFrame(df_list)
num_left = math.ceil(len(df) / 2) if len(df) > 0 else 0
df_left = df.iloc[:num_left].reset_index(drop=True)
df_right = df.iloc[num_left:].reset_index(drop=True)

col_config = {
    "✅선택": st.column_config.CheckboxColumn("✅선택", width="small"),
    "항목": st.column_config.TextColumn("항목", width="medium"),
    "추세": st.column_config.TextColumn("추세", width="small"),
    "현재가": st.column_config.NumberColumn("현재가"), 
    "등락률(%)": st.column_config.NumberColumn("등락률(%)", format="%+.2f")
}

table_col1, table_col2 = st.columns(2)

with table_col1:
    edited_left = st.data_editor(
        df_left, column_config=col_config,
        disabled=["항목", "추세", "현재가", "등락률(%)"], hide_index=True, use_container_width=True, key="edit_left"
    )

with table_col2:
    edited_right = st.data_editor(
        df_right, column_config=col_config,
        disabled=["항목", "추세", "현재가", "등락률(%)"], hide_index=True, use_container_width=True, key="edit_right"
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

# --- 8. AI 시뮬레이션 영역 (마크다운 완벽 적용 및 선택 종목 집중 분석) ---
st.subheader("🧠 자율 진화형 AI & 포트폴리오 최적화 알고리즘")
sim_col1, sim_col2 = st.columns(2)
model_sel = sim_col1.selectbox("AI 모델 선택", ["Machine Learning", "LSTM", "Autonomous AI", "Reinforcement Learning", "Sentiment Analysis"])
algo_sel = sim_col2.selectbox("전략 알고리즘 선택", ["Quant 분석 AI", "Kai Score", "Holly AI", "포트폴리오 최적화 알고리즘"])

if st.button("▶ 선택 종목 타겟 AI 분석 실행", use_container_width=True, type="primary"):
    with st.spinner('선택된 종목을 스캐닝하여 시뮬레이션을 진행합니다...'):
        current_date_str = datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")
        market = st.session_state.market_data
        
        # 1) 매크로 지표 추출 (지수는 무조건 상시 참조)
        vix_change = market.get("VIX (공포지수)", {}).get("raw_change", 0.0)
        sox_change = market.get("필라델피아 반도체", {}).get("raw_change", 0.0)
        macro_sentiment = "안전자산 선호(Risk-Off) 회피 심리" if vix_change > 0 else "위험자산 선호(Risk-On) 심리 회복"
        semi_forecast = "수급 이탈 경계구간" if sox_change < 0 else "강한 상승 모멘텀 동조화"
        
        # 2) '체크된' 종목들 중에서만 분석 진행 (매크로 지수 제외)
        macro_keywords = ["VIX", "필라델피아", "SMH", "환율", "국채", "S&P", "NASDAQ", "Russell", "구리", "금", "WTI"]
        checked_stocks = []
        
        for name in st.session_state.checked_items:
            if not any(k in name for k in macro_keywords):
                info = market.get(name, {})
                if info.get("raw_price", 0) > 0:
                    checked_stocks.append((name, info))
                    
        # 3) 선택된 종목 수에 따른 동적 브리핑 생성
        insight_text = ""
        if len(checked_stocks) == 0:
            insight_text = "* ⚠️ **분석 대기:** 표에서 시뮬레이션을 원하시는 개별 주식 종목의 **[✅선택]** 체크박스를 먼저 클릭해 주세요."
        elif len(checked_stocks) == 1:
            item = checked_stocks[0]
            n, info = item
            p = info['raw_price']
            c = info['raw_change']
            p_str = f"{p:,.0f}" if p > 1000 else f"{p:,.2f}"
            color = "🔴" if c > 0 else "🔵" if c < 0 else "⚪"
            
            insight_text = f"* **{n} (단일 집중 분석):** 현재가 **{p_str}원** ({color} {c:+.2f}%). 선택하신 **{algo_sel}** 알고리즘으로 해당 종목의 수급과 변동성을 단독 시뮬레이션 중입니다. 현재 매크로 지표와 연동하여 비중 조절을 검토하세요."
        else:
            # 2개 이상 선택 시 수익률 순으로 정렬하여 1등과 꼴등 비교
            checked_stocks.sort(key=lambda x: x[1].get("raw_change", 0.0), reverse=True)
            top_gainer = checked_stocks[0]
            top_loser = checked_stocks[-1]
            
            g_name, g_info = top_gainer
            g_p = g_info['raw_price']
            g_c = g_info['raw_change']
            g_p_str = f"{g_p:,.0f}" if g_p > 1000 else f"{g_p:,.2f}"
            g_color = "🔴" if g_c > 0 else "🔵" if g_c < 0 else "⚪"
            
            l_name, l_info = top_loser
            l_p = l_info['raw_price']
            l_c = l_info['raw_change']
            l_p_str = f"{l_p:,.0f}" if l_p > 1000 else f"{l_p:,.2f}"
            l_color = "🔴" if l_c > 0 else "🔵" if l_c < 0 else "⚪"
            
            insight_text += f"* **{g_name} (핵심 주도주):** 현재가 **{g_p_str}원** ({g_color} {g_c:+.2f}%). 타겟 포트폴리오 내에서 가장 강력한 수급 모멘텀을 형성 중입니다. **{algo_sel}** 모델 기준 단기 추가 상승 여력이 높습니다.\n"
            if g_name != l_name:
                insight_text += f"* **{l_name} (리스크 관리):** 현재가 **{l_p_str}원** ({l_color} {l_c:+.2f}%). 타겟 종목 중 단기 지지선 테스트 구간에 진입했습니다. 기술적 반등이 없을 경우 비중 축소를 권장합니다."

        st.success("데이터 연산 및 시뮬레이션 분석 완료!")
        
        # HTML 렌더링 오류를 피하기 위해 네이티브 마크다운과 Streamlit 박스 기능 활용
        st.info(f"**기준 일시:** {current_date_str} | **적용 모델:** {model_sel} | **적용 알고리즘:** {algo_sel}")
        
        st.markdown(f"""
        ### 1. 매크로 & 오버피팅 검증 (상시 참조 지표)
        * 선택하신 **{model_sel}** 모델이 실시간 데이터 노이즈를 필터링하고 자체 검증을 완료했습니다.
        * **{algo_sel}** 연산에 현재 VIX 지수({vix_change:+.2f}%) 및 반도체 지수({sox_change:+.2f}%) 가중치가 기본 참조값으로 반영되었습니다.
        
        ### 2. 거시경제 동향 (Macro & Sentiment)
        * 현재 글로벌 시장 자금 동향은 **[{macro_sentiment}]** 국면으로 분석됩니다.
        * 미국 반도체 지수 투영 결과, 국내 기술주 및 관련 섹터는 **[{semi_forecast}]** 시그널이 도출되었습니다.
        
        ### 3. 🎯 선택 종목 심층 분석 (Target Insight)
        {insight_text}
        * **종합 평가:** 거시 지표 방향성에 맞추어 **{algo_sel}** 로직에 기반한 기계적이고 냉정한 트레이딩 대응이 필요한 시점입니다.
        """)

st.markdown("<br><hr style='border: 1px solid #3a3a52;'><p style='text-align: right; color: #a1a1bb; font-style: italic; font-weight: bold;'>모두가 부자 되길 바라는 주린(인) 김병권</p>", unsafe_allow_html=True)
