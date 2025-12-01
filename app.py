#!/usr/bin/env python3
"""
Streamlit app: SoccerBot

Features:
- Detects soccer-related prompts and applies a SoccerBot system instruction
- Mock local tools: get_match_summary, get_player_stats (JSON strings)
- If prompt contains '경기 요약:' or '선수 통계:' it will call local tools and then ask the model to expand the result

Before running:
- create a `.env` with `AZURE_OAI_KEY` and `AZURE_OAI_ENDPOINT` (and optionally `AZURE_OAI_DEPLOYMENT`)
- install: `pip install streamlit python-dotenv openai requests`

Run:
    streamlit run app.py
"""

import os
import json
import re
import streamlit as st
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="SoccerBot ⚽",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 축구 테마 CSS 스타일
st.markdown("""
    <style>
    /* 메인 컨테이너 스타일 */
    .main {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    }
    
    /* 헤더 스타일 */
    .soccer-header {
        background: linear-gradient(90deg, #00a859 0%, #00d4aa 100%);
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        color: white;
        box-shadow: 0 4px 15px rgba(0, 168, 89, 0.3);
        margin-bottom: 2rem;
    }
    
    .soccer-header h1 {
        color: white;
        margin: 0;
        font-size: 2.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    /* 사이드바 스타일 */
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #f0f8f5 0%, #ffffff 100%);
    }
    
    /* 버튼 스타일 */
    .stButton>button {
        background: linear-gradient(90deg, #00a859 0%, #00d4aa 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 0.5rem 2rem;
        font-weight: bold;
        transition: all 0.3s;
        box-shadow: 0 4px 10px rgba(0, 168, 89, 0.3);
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 15px rgba(0, 168, 89, 0.5);
    }
    
    /* 입력 필드 스타일 */
    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea {
        border-radius: 10px;
        border: 2px solid #00a859;
    }
    
    /* 채팅 메시지 스타일 */
    .user-message {
        background: linear-gradient(90deg, #00a859 0%, #00d4aa 100%);
        color: white;
        padding: 1rem;
        border-radius: 15px;
        margin: 0.5rem 0;
        box-shadow: 0 2px 8px rgba(0, 168, 89, 0.2);
    }
    
    .assistant-message {
        background: #f0f8f5;
        padding: 1rem;
        border-radius: 15px;
        margin: 0.5rem 0;
        border-left: 4px solid #00a859;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    /* 카드 스타일 */
    .info-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin: 1rem 0;
        border-top: 4px solid #00a859;
    }
    
    /* 스크롤바 스타일 */
    .element-container {
        max-height: 600px;
        overflow-y: auto;
    }
    
    /* 스크롤바 커스텀 */
    .element-container::-webkit-scrollbar {
        width: 8px;
    }
    
    .element-container::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    
    .element-container::-webkit-scrollbar-thumb {
        background: #00a859;
        border-radius: 10px;
    }
    
    .element-container::-webkit-scrollbar-thumb:hover {
        background: #00d4aa;
    }
    </style>
""", unsafe_allow_html=True)

# 헤더
st.markdown("""
    <div class="soccer-header">
        <h1>⚽ SoccerBot — 축구 전문 챗봇</h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.1rem;">축구 경기, 선수 통계, 전술 분석을 제공하는 AI 어시스턴트</p>
    </div>
""", unsafe_allow_html=True)

# Azure OpenAI 클라이언트 초기화
AZURE_ENDPOINT = os.getenv("AZURE_OAI_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_OAI_KEY")
DEPLOYMENT = os.getenv("AZURE_OAI_DEPLOYMENT", "gpt-4o-mini")

if not AZURE_KEY or not AZURE_ENDPOINT:
    st.error("⚠️ 환경변수 `AZURE_OAI_KEY` 또는 `AZURE_OAI_ENDPOINT`가 설정되어 있지 않습니다. .env 파일을 확인하세요.")
    st.stop()

try:
    client = AzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=AZURE_KEY,
        api_version="2024-05-01-preview"
    )
except Exception as e:
    st.error(f"❌ AzureOpenAI 클라이언트 초기화 실패: {e}")
    st.stop()

# 축구 키워드
SOCCER_KEYWORDS = [
    "축구", "선수", "경기", "골", "리그", "득점", "어시스트", 
    "포메이션", "전술", "맨유", "리버풀", "손흥민", "프리미어리그",
    "월드컵", "챔피언스리그", "라리가", "분데스리가", "세리에A"
]

# 도구 함수들
def get_match_summary(home: str, away: str) -> str:
    """모의 경기 요약을 JSON 문자열로 반환합니다."""
    summary = {
        "home": home,
        "away": away,
        "score": "2-1",
        "events": [
            {"minute": 12, "team": home, "type": "goal", "player": "A. Kim"},
            {"minute": 45, "team": away, "type": "goal", "player": "J. Lee"},
            {"minute": 78, "team": home, "type": "goal", "player": "B. Park"},
        ],
        "summary_text": f"{home}이(가) {away}를 상대로 역전승을 거두었습니다. 전반에는 팽팽했으나 후반에 흐름을 바꿨습니다."
    }
    return json.dumps(summary, ensure_ascii=False)

def get_player_stats(player_name: str) -> str:
    """모의 선수 통계를 JSON 문자열로 반환합니다."""
    stats = {
        "player": player_name,
        "appearances": 24,
        "goals": 9,
        "assists": 6,
        "rating": 7.4,
        "notes": f"{player_name}은(는) 이번 시즌 핵심 공격수로 활약 중입니다."
    }
    return json.dumps(stats, ensure_ascii=False)

def call_model(messages, temperature=0.5, max_tokens=1000):
    """모델 호출 함수"""
    if client is None:
        return "❌ 모델 호출 불가 — Azure 클라이언트 초기화 실패"
    try:
        resp = client.chat.completions.create(
            model=DEPLOYMENT,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"❌ 모델 호출 중 오류: {e}"

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 사이드바 설정
with st.sidebar:
    st.markdown("### ⚙️ 설정")
    
    mode = st.radio(
        "모드 선택",
        ["Auto", "Soccer", "General"],
        index=0,
        help="Auto: 자동 감지, Soccer: 항상 축구 모드, General: 일반 모드"
    )
    
    temp = st.slider(
        "창의성 (Temperature)",
        0.0, 1.0, 0.3,
        help="값이 높을수록 더 창의적인 응답을 생성합니다"
    )
    
    max_tokens = st.slider(
        "최대 토큰 수",
        100, 2000, 1000,
        help="응답의 최대 길이를 설정합니다"
    )
    
    st.markdown("---")
    st.markdown("### 🛠️ 도구 테스트")
    
    with st.expander("경기 요약 테스트", expanded=False):
        t_home = st.text_input("홈 팀", "Manchester United", key="test_home")
        t_away = st.text_input("원정 팀", "Liverpool", key="test_away")
        if st.button("모의 경기 요약 생성", key="test_match"):
            summary = json.loads(get_match_summary(t_home, t_away))
            st.json(summary)
    
    with st.expander("선수 통계 테스트", expanded=False):
        p_name = st.text_input("선수 이름", "Son Heung-min", key="test_player")
        if st.button("모의 선수 통계 생성", key="test_stats"):
            stats = json.loads(get_player_stats(p_name))
            st.json(stats)
    
    st.markdown("---")
    if st.button("🗑️ 대화 기록 삭제", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# 메인 채팅 영역
st.markdown("### 💬 대화")

# 대화 기록 표시
chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# 사용자 입력
if prompt := st.chat_input("축구에 대해 물어보세요! 예: '맨유 vs 리버풀 경기 요약해줘' 또는 '선수 통계: 손흥민'"):
    # 사용자 메시지 표시 및 저장
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 축구 의도 감지
    is_soccer = mode == "Soccer" or (mode == "Auto" and any(k in prompt for k in SOCCER_KEYWORDS))
    
    # 응답 생성
    with st.chat_message("assistant"):
        with st.spinner("⚽ 축구 데이터를 분석 중입니다..."):
            if is_soccer:
                system = {
                    "role": "system",
                    "content": (
                        "당신은 SoccerBot입니다. 축구에 관해 전문적이고 상세하게 한국어로 설명합니다. "
                        "경기 요약, 전술 분석, 선수 통계 및 추천을 제공하세요. 사실 기반과 의견을 구분하고, "
                        "필요한 경우 예상 라인업이나 전술도 제안하세요. 친근하고 열정적인 톤으로 답변하세요."
                    )
                }
                
                # 경기 요약 패턴 처리
                match_pattern = re.search(r"경기 요약[:：]?\s*(.+?)\s+vs\s+(.+)", prompt, re.IGNORECASE)
                if match_pattern:
                    home, away = match_pattern.group(1).strip(), match_pattern.group(2).strip()
                    tool_out = get_match_summary(home, away)
                    messages = [
                        system,
                        {"role": "user", "content": prompt},
                        {"role": "tool", "name": "get_match_summary", "content": tool_out}
                    ]
                    assistant_reply = call_model(messages, temperature=temp, max_tokens=max_tokens)
                else:
                    # 선수 통계 패턴 처리
                    player_pattern = re.search(r"선수 통계[:：]?\s*(.+)", prompt, re.IGNORECASE)
                    if player_pattern:
                        player = player_pattern.group(1).strip()
                        tool_out = get_player_stats(player)
                        messages = [
                            system,
                            {"role": "user", "content": prompt},
                            {"role": "tool", "name": "get_player_stats", "content": tool_out}
                        ]
                        assistant_reply = call_model(messages, temperature=temp, max_tokens=max_tokens)
                    else:
                        # 일반 축구 질문
                        messages = [system, {"role": "user", "content": prompt}]
                        assistant_reply = call_model(messages, temperature=temp, max_tokens=max_tokens)
            else:
                # 일반 모드
                messages = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ]
                assistant_reply = call_model(messages, temperature=temp, max_tokens=max_tokens)
        
        st.markdown(assistant_reply)
    
    # 어시스턴트 응답 저장
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})

# 하단 안내
st.markdown("---")
st.markdown("""
    <div style="text-align: center; color: #666; padding: 1rem;">
        <p>💡 <strong>팁:</strong> 축구 전문 응답을 원하면 '선수 통계: 손흥민' 또는 '경기 요약: 맨유 vs 리버풀'처럼 구체적으로 입력하세요.</p>
        <p>⚽ SoccerBot은 경기 요약, 선수 통계, 전술 분석을 제공합니다.</p>
    </div>
""", unsafe_allow_html=True)
