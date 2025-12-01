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
import time
import streamlit as st
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

st.set_page_config(page_title="SoccerBot", layout="wide")
st.title("⚽ SoccerBot")

# Azure OpenAI client
AZURE_ENDPOINT = os.getenv("AZURE_OAI_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_OAI_KEY")
DEPLOYMENT = os.getenv("AZURE_OAI_DEPLOYMENT", "gpt-4o-mini")

if not AZURE_KEY or not AZURE_ENDPOINT:
    st.error("환경변수 `AZURE_OAI_KEY` 또는 `AZURE_OAI_ENDPOINT`가 설정되어 있지 않습니다. .env 파일을 확인하세요.")

try:
    client = AzureOpenAI(azure_endpoint=AZURE_ENDPOINT, api_key=AZURE_KEY, api_version="2024-05-01-preview")
except Exception as e:
    client = None
    st.warning(f"AzureOpenAI 클라이언트 초기화 실패: {e}")

# 간단한 축구 키워드 기반 감지
SOCCER_KEYWORDS = ["축구", "선수", "경기", "골", "리그", "득점", "어시스트", "포메이션", "전술", "맨유", "리버풀", "손흥민"]

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

def call_model(messages, temperature=0.5, max_tokens=700):
    if client is None:
        return "(모델 호출 불가 — Azure 클라이언트 초기화 실패)"
    try:
        resp = client.chat.completions.create(
            model=DEPLOYMENT,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"(모델 호출 중 오류: {e})"

# UI: left = controls, right = conversation
col1, col2 = st.columns([1, 2])

with col1:
    st.header("질문 입력")
    prompt = st.text_area("질문을 입력하세요.", height=120, placeholder="예: 지난 맨유 vs 리버풀 경기 요약해줘\n예: 선수 통계: 손흥민")
    mode = st.selectbox("모드", ["Auto", "Soccer", "General"], index=0)
    temp = st.slider("창의성 (temperature)", 0.0, 1.0, 0.3)
    send = st.button("전송")
    st.markdown("---")
    st.subheader("도구 테스트 (모의)")
    t_home = st.text_input("홈 팀", "Manchester United")
    t_away = st.text_input("원정 팀", "Liverpool")
    if st.button("모의 경기 요약 생성"):
        st.json(json.loads(get_match_summary(t_home, t_away)))
    st.text("")
    p_name = st.text_input("선수 이름 (테스트)", "Son Heung-min")
    if st.button("모의 선수 통계 생성"):
        st.json(json.loads(get_player_stats(p_name)))

with col2:
    st.header("대화 / 응답")
    if "history" not in st.session_state:
        st.session_state.history = []

    def append_history(role, text):
        st.session_state.history.append({"role": role, "content": text})

    # Display history
    for m in st.session_state.history:
        if m["role"] == "user":
            st.markdown(f"**사용자:** {m['content']}")
        else:
            st.markdown(f"**Assistant:** {m['content']}")

    # Action when send
    if send and prompt:
        append_history("user", prompt)

        # Detect soccer intent
        is_soccer = mode == "Soccer" or (mode == "Auto" and any(k in prompt for k in SOCCER_KEYWORDS))

        if is_soccer:
            system = {
                "role": "system",
                "content": (
                    "당신은 SoccerBot입니다. 축구에 관해 전문적이고 상세하게 한국어로 설명합니다. "
                    "경기 요약, 전술 분석, 선수 통계 및 추천을 제공하세요. 사실 기반과 의견을 구분하고, 필요한 경우 예상 라인업이나 전술도 제안하세요."
                )
            }

            # Simple pattern handling: '경기 요약: TeamA vs TeamB' or '선수 통계: Name'
            m = re.search(r"경기 요약[:：]?\s*(.+?)\s+vs\s+(.+)", prompt, re.IGNORECASE)
            if m:
                home, away = m.group(1).strip(), m.group(2).strip()
                tool_out = get_match_summary(home, away)
                # Provide tool output as a tool-role message and ask model to expand
                messages = [system, {"role": "user", "content": prompt}, {"role": "tool", "name": "get_match_summary", "content": tool_out}]
                assistant_reply = call_model(messages, temperature=temp)
            else:
                m2 = re.search(r"선수 통계[:：]?\s*(.+)", prompt, re.IGNORECASE)
                if m2:
                    player = m2.group(1).strip()
                    tool_out = get_player_stats(player)
                    messages = [system, {"role": "user", "content": prompt}, {"role": "tool", "name": "get_player_stats", "content": tool_out}]
                    assistant_reply = call_model(messages, temperature=temp)
                else:
                    # Generic soccer question — just pass system instruction + user prompt
                    messages = [system, {"role": "user", "content": prompt}]
                    assistant_reply = call_model(messages, temperature=temp)
        else:
            # General flow: use existing session messages
            messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.history]
            assistant_reply = call_model(messages, temperature=temp)

        append_history("assistant", assistant_reply)
        st.markdown(f"**Assistant:** {assistant_reply}")

    st.markdown("---")
    st.caption("팁: 축구 전문 응답을 원하면 '선수 통계: 손흥민' 또는 '경기 요약: 맨유 vs 리버풀'처럼 구체적으로 입력하세요.")

# 끝
import streamlit as st
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

# 1. 환경 변수 로드 (.env 파일이 같은 폴더에 있어야 함)
load_dotenv()

st.title("🤖 경기 결과 분석 Bot")

# 2. Azure OpenAI 클라이언트 설정
# (실제 값은 .env 파일이나 여기에 직접 입력하세요)
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OAI_KEY"),
    api_version="2024-05-01-preview",
    azure_endpoint=os.getenv("AZURE_OAI_ENDPOINT")
)

# 3. 대화기록(Session State) 초기화 - 이게 없으면 새로고침 때마다 대화가 날아갑니다!
if "messages" not in st.session_state:
    st.session_state.messages = []

# 4. 화면에 기존 대화 내용 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. 사용자 입력 받기
if prompt := st.chat_input("무엇을 도와드릴까요?"):
    # (1) 사용자 메시지 화면에 표시 & 저장
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # (2) AI 응답 생성 (스트리밍 방식 아님, 단순 호출 예시)
    with st.chat_message("assistant"):
        response = client.chat.completions.create(
            model="gpt-4o-mini", # 사용하시는 배포명(Deployment Name)으로 수정 필요!
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ]
        )
        assistant_reply = response.choices[0].message.content
        st.markdown(assistant_reply)

    # (3) AI 응답 저장
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})

