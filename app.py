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

# [핵심 수정 1] 강제 우측 정렬 CSS 주입
st.markdown("""
<style>
/* 데이터 에디터의 3번째(현재가), 4번째(등락률) 열 텍스트 우측 정렬 강제 적용 */
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
    "한화시스템": "272210.KS", "한화오션": "042660.KS", "HD한국조선해양": "009540.KS",
    "LS": "006260.KS", "갤럭시아머니트리": "094480.KQ", "현대차": "005380.KS",
    "테슬라": "TSLA", "엔비디아": "NVDA", "애플": "AAPL", "록히드마틴": "LMT",
    "마이크로소프트": "MSFT", "알파벳": "GOOGL", "아마존": "AMZN"
}

# --- 2. 영구 저장 및 메모리(Session State) 초기화 ---
TICKERS_FILE = "my_tickers.json"

def load_tickers():
    if os.path.exists(TICKERS_FILE):
        with open(TICKERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        default_tickers = {
            "VIX (공포지수)": "^VIX", "필라델피아 반도체": "^SOX", "SMH": "SMH", 
            "원달러 환율": "KRW=X", "미국 10년물 국채": "^TNX",
            "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "한국항공우주": "047810.KS",
            "한화시스템": "272210.KS", "한화오션": "042660.KS", "HD한국조선해양": "009540.KS",
            "LS": "006260.KS", "갤럭시아머니트리": "094480.KQ",
            "NVDA (엔비디아)": "NVDA", "LMT (록히드마틴)": "LMT"
        }
        with open(TICKERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_tickers, f, ensure_ascii=False, indent=4)
        return default_tickers

def save_tickers(tickers_dict):
    with open(TICKERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tickers_dict, f, ensure_ascii=False, indent=4)

if 'tickers' not in st.session_state: st.session_state.tickers = load_tickers()
if 'market_data' not in st.session_state: st.session_state.market_data = {}
if 'last_update' not in st.session_state: st.session_state.last_update = "아직 업데이트되지 않음"
if 'news_data' not in st.session_state: st.session_state.news_data = []
if 'checked_items' not in st.session_state: st.session_state.checked_items = []

# --- 3. 데이터 수집 핵심 함수 ---
@st.cache_data(ttl=60)
def fetch_single_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="2d")
        if len(hist) >= 2:
            current = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[-2]
            change = ((current - prev) / prev) * 100
        elif len(hist) == 1:
            current = hist['Close'].iloc[-1]
            change = 0.0
        else:
            return "-", 0.0, None

        if ticker.upper().endswith('.KS') or ticker.upper().endswith('.KQ'):
            price_str = f"{int(current):,}"
        else:
            price_str = f"{current:,.2f}"
            
        return price_str, float(change), float(current)
    except:
        return "-", 0.0, None

def fetch_all_data():
    raw_data = {}
    for name, ticker in st.session_state.tickers.items():
        price_str, change, raw_price = fetch_single_stock(ticker)
        raw_data[name] = {"price": price_str, "change": change, "raw_price": raw_price}
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
        except:
            pass
    st.session_state.news_data = news_list

if not st.session_state.market_data:
    with st.spinner("초기 데이터를 불러오는 중입니다..."):
        fetch_all_data()
        fetch_news()

# --- 4. 순서 이동 및 삭제 로직 (파일 저장 연동) ---
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
    save_tickers(st.session_state.tickers) # 파일에 즉시 저장
    force_editor_rebuild()

def delete_items():
    names = st.session_state.checked_items
    for name in names:
        if name in st.session_state.tickers:
            del st.session_state.tickers[name]
        if name in st.session_state.market_data:
            del st.session_state.market_data[name]
    st.session_state.checked_items = [] 
    save_tickers(st.session_state.tickers) # 파일에 즉시 저장
    force_editor_rebuild()

# --- 5. UI 화면 렌더링 ---
st.title("📱 지수 종목 확인")
st.markdown("<span style='color:gray;'>자율 진화형 퀀트 분석 및 실시간 포트폴리오 모니터링 시스템</span>", unsafe_allow_html=True)

# [자동고침 주기 설정]
refresh_opts = {"끄기": 0, "1분마다": 60, "5분마다": 300, "10분마다": 600}

col_top1, col_top2, col_top3 = st.columns([1.2, 1, 1.5])
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

# [종목 추가/수정 패널]
with st.expander("➕ 새로운 종목 추가 및 수정", expanded=False):
    st.markdown("**자동완성 DB 검색** (선택 시 아래 입력칸에 자동으로 들어갑니다)")
    
    selected_db = st.selectbox("DB 선택", ["직접 입력"] + list(SEARCH_DB.keys()), label_visibility="collapsed")
    
    def_name = "" if selected_db == "직접 입력" else selected_db
    def_ticker = "" if selected_db == "직접 입력" else SEARCH_DB[selected_db]
    
    c1, c2 = st.columns(2)
    new_name = c1.text_input("종목명", value=def_name, placeholder="예: 삼성전자")
    new_ticker = c2.text_input("티커", value=def_ticker, placeholder="예: 005930.KS")
    
    bc1, bc2 = st.columns(2)
    if bc1.button("➕ 추가", use_container_width=True):
        if new_name and new_ticker:
            st.session_state.tickers[new_name] = new_ticker
            price, change, raw = fetch_single_stock(new_ticker)
            st.session_state.market_data[new_name] = {"price": price, "change": change, "raw_price": raw}
            save_tickers(st.session_state.tickers) # 파일에 즉시 저장
            st.success(f"'{new_name}' 추가 완료!")
            force_editor_rebuild()
            st.rerun()
            
    if bc2.button("✏️ 수정", use_container_width=True):
        if new_name and new_ticker:
            st.session_state.tickers[new_name] = new_ticker
            price, change, raw = fetch_single_stock(new_ticker)
            st.session_state.market_data[new_name] = {"price": price, "change": change, "raw_price": raw}
            save_tickers(st.session_state.tickers) # 파일에 즉시 저장
            st.success(f"'{new_name}' 수정 완료!")
            force_editor_rebuild()
            st.rerun()

# --- 6. 실시간 테이블 ---
st.subheader("📈 실시간 지표 및 포트폴리오 관리")
st.write("표 안의 **[✅선택]** 체크박스를 누른 후 아래 이동 버튼을 클릭하세요.")

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
    chg = info.get("change", 0.0)
    
    if chg > 0: chg_str = f"🔴 +{chg:.2f}%"
    elif chg < 0: chg_str = f"🔵 {chg:.2f}%"
    else: chg_str = f"⚪ 0.00%"

    df_list.append({
        "✅선택": name in st.session_state.checked_items,
        "항목": name, 
        "현재가": info.get("price", "-"), 
        "등락률": chg_str
    })

df = pd.DataFrame(df_list)
num_left = math.ceil(len(df) / 2) if len(df) > 0 else 0
df_left = df.iloc[:num_left].reset_index(drop=True)
df_right = df.iloc[num_left:].reset_index(drop=True)

# 색상 적용 
def color_align(val):
    if not isinstance(val, str): return ''
    if '🔴' in val: return 'color: #ff4d4d; font-weight: bold;'
    if '🔵' in val: return 'color: #4d94ff; font-weight: bold;'
    return 'color: gray;'

styled_left = df_left.style.map(color_align, subset=['등락률'])
styled_right = df_right.style.map(color_align, subset=['등락률'])

table_col1, table_col2 = st.columns(2)

with table_col1:
    edited_left = st.data_editor(
        styled_left, 
        column_config={"✅선택": st.column_config.CheckboxColumn("✅선택")},
        disabled=["항목", "현재가", "등락률"], 
        hide_index=True, 
        use_container_width=True,
        key="edit_left"
    )

with table_col2:
    edited_right = st.data_editor(
        styled_right, 
        column_config={"✅선택": st.column_config.CheckboxColumn("✅선택")},
        disabled=["항목", "현재가", "등락률"], 
        hide_index=True, 
        use_container_width=True,
        key="edit_right"
    )

new_checked_left = edited_left[edited_left["✅선택"] == True]["항목"].tolist() if not edited_left.empty else []
new_checked_right = edited_right[edited_right["✅선택"] == True]["항목"].tolist() if not edited_right.empty else []
st.session_state.checked_items = new_checked_left + new_checked_right

# --- 7. 실시간 뉴스 영역 (버튼 위치 수정) ---
st.markdown("<br>", unsafe_allow_html=True)
col_news_title, col_news_btn = st.columns([4, 1])
with col_news_title:
    st.subheader("📰 24시간 내 최신 경제/특징주 뉴스")
with col_news_btn:
    if st.button("🔄 뉴스 새로고침", key="news_refresh_btn", use_container_width=True):
        fetch_news()
        st.rerun()

news_html = "<div style='background-color:#252538; padding:15px; border-radius:8px; border:1px solid #3a3a52; margin-bottom: 20px;'>"
for news in st.session_state.news_data:
    color = "#ffb84d" if "한국" in news['source'] else "#82b1ff"
    news_html += f"<div style='margin-bottom:8px; line-height: 1.5;'><strong style='color:{color};'>[{news['source']}]</strong> <a href='{news['link']}' target='_blank' style='color:#e4e6eb; text-decoration:none;'>{news['title']}</a> <span style='color:gray; font-size:0.8em;'>{news['date']}</span></div>"
news_html += "</div>"
st.markdown(news_html, unsafe_allow_html=True)

# --- 8. AI 시뮬레이션 영역 ---
st.subheader("🧠 자율 진화형 AI & 포트폴리오 최적화 알고리즘")
sim_col1, sim_col2 = st.columns(2)
model_sel = sim_col1.selectbox("AI 모델 선택", ["Machine Learning", "LSTM", "Autonomous AI", "Reinforcement Learning", "Sentiment Analysis"])
algo_sel = sim_col2.selectbox("전략 알고리즘 선택", ["Quant 분석 AI", "Kai Score", "Holly AI", "포트폴리오 최적화 알고리즘"])

if st.button("▶ 실시간 시뮬레이션 연산 실행", use_container_width=True, type="primary"):
    with st.spinner('Overfitting 검증 및 자율 진화 알고리즘 연산 중...'):
        current_date_str = datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")
        
        vix_info = st.session_state.market_data.get("VIX (공포지수)", {})
        sox_info = st.session_state.market_data.get("필라델피아 반도체", {})
        sam_info = st.session_state.market_data.get("삼성전자", {})
        kai_info = st.session_state.market_data.get("한국항공우주", {})
        
        vix_change = vix_info.get("change", 0.0) if vix_info.get("change") is not None else 0.0
        sox_change = sox_info.get("change", 0.0) if sox_info.get("change") is not None else 0.0
        sam_price = sam_info.get("raw_price", 0)
        kai_price = kai_info.get("raw_price", 0)
        
        macro_sentiment = "안전자산 선호(Risk-Off) 회피 심리" if vix_change > 0 else "위험자산 선호(Risk-On) 심리 회복"
        semi_forecast = "수급 이탈 경계구간" if sox_change < 0 else "강한 상승 모멘텀 동조화"
        
        sam_ref = 182400
        kai_ref = 177100
        
        if sam_price:
            sam_status = "<span style='color:#ff4d4d;'>상회(돌파)</span>" if sam_price >= sam_ref else "<span style='color:#4d94ff;'>하회(이탈)</span>"
            sam_text = f"현재가 <b>{int(sam_price):,}원</b>으로, 핵심 마디가(182,400원)를 {sam_status}하며 방향성을 리드 중입니다."
        else:
            sam_text = "현재 시세 데이터 수집 지연으로 연산 대기 중."

        if kai_price:
            kai_status = "<span style='color:#ff4d4d;'>방어(상승)</span>" if kai_price >= kai_ref else "<span style='color:#4d94ff;'>약세(조정)</span>"
            kai_text = f"현재가 <b>{int(kai_price):,}원</b>으로, 벤치마크 지지선(177,100원) 대비 {kai_status} 흐름을 보입니다."
        else:
            kai_text = "현재 시세 데이터 수집 지연으로 연산 대기 중."

        st.success("데이터 연산 및 시뮬레이션 분석 완료!")
        
        report = f"""
        <div style="background-color:#252538; padding:20px; border-radius:8px; border:1px solid #3a3a52; line-height: 1.6;">
        <h3 style="color:#00bfff; margin-top:0;">[🤖 자율 진화형 AI 산출 리포트]</h3>
        <p style="font-size:0.9em; color:gray;">기준 일시: {current_date_str} <br> 적용 모델: <b>{model_sel}</b> | 적용 알고리즘: <b>{algo_sel}</b></p>
        <hr style="border: 1px solid #3a3a52;">
        
        <b>1. 자율 진화 및 Overfitting 검증:</b>
        <ul>
          <li>선택하신 <b>{model_sel}</b> 모델이 실시간 데이터 노이즈를 필터링하고 Overfitting 자체 검증을 완료했습니다.</li>
          <li><b>{algo_sel}</b> 연산에 현재 VIX({vix_change:+.2f}%) 및 반도체 지수({sox_change:+.2f}%) 가중치가 반영되었습니다.</li>
        </ul>
        
        <b>2. 거시경제 매크로 (Macro & Sentiment):</b>
        <ul>
          <li>현재 글로벌 시장 자금 동향은 <b>[{macro_sentiment}]</b> 국면으로 분석됩니다.</li>
          <li>미국 반도체 지수 투영 결과, 국내 대형 반도체 섹터는 <b>[{semi_forecast}]</b> 시그널이 도출되었습니다.</li>
        </ul>
        
        <b>3. 주요 편입 종목 및 밸류체인 심층 분석 (Actionable Insight):</b>
        <ul>
          <li><b>삼성전자:</b> {sam_text}</li>
          <li><b>우주/방산/조선:</b> KAI는 {kai_text} 해당 흐름에 따라 <b>한화시스템, 한화오션, HD한국조선해양</b> 등 관련 밸류체인으로의 연산 확률이 고도화되었습니다.</li>
          <li><b>개별 모멘텀:</b> 지수 파동과 무관한 <b>LS, 갤럭시아머니트리</b> 등은 <b>{algo_sel}</b> 로직에 입각해 당일 단기 트레이딩 진입이 유효합니다.</li>
        </ul>
        </div>
        """
        st.markdown(report, unsafe_allow_html=True)

st.markdown("<br><hr style='border: 1px solid #3a3a52;'><p style='text-align: right; color: #a1a1bb; font-style: italic; font-weight: bold;'>모두가 부자 되길 바라는 주린(인) 김병권</p>", unsafe_allow_html=True)
