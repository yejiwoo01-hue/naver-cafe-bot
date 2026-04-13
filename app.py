import streamlit as st
import os
import requests
import subprocess
import bot_engine
import database
import time
import updater
from dotenv import set_key, load_dotenv



# Database Init
database.init_db()

st.set_page_config(page_title="Naver Cafe Bot", page_icon="🤖", layout="wide")

# Custom CSS for "Wow" factor
st.markdown("""
<style>
    .reportview-container {
        background: #111111;
    }
    .main {
        background: linear-gradient(135deg, #1f1c2c 0%, #928DAB 100%);
        color: white;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 10px 24px;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #45a049;
        transform: scale(1.05);
    }
    h1, h2, h3 {
        color: #ffffff;
        font-family: 'Inter', sans-serif;
    }
    .status-container {
        padding: 15px;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

st.title("✨ AI 네이버 카페 스마트 요정")
st.markdown("관심 있는 카페글을 자동으로 찾고 AI가 자연스럽게 댓글을 남겨드립니다.")

if 'cafes' not in st.session_state:
    st.session_state.cafes = []

# --- Ollama Utilities ---
def get_free_memory_gb():
    try:
        # 윈도우 여유 메모리(GB)를 반환합니다.
        output = subprocess.check_output(['powershell', 'Get-CimInstance Win32_OperatingSystem | Select-Object -ExpandProperty FreePhysicalMemory'], text=True)
        return int(output.strip()) / (1024 * 1024)
    except:
        return 4.0 # 기본값 4GB

def get_local_models():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get('models', [])
            free_ram = get_free_memory_gb()
            
            model_list = []
            for m in models:
                name = m['name']
                size_gb = m.get('size', 0) / (1024 * 1024 * 1024)
                
                # 메모리 여유분보다 작고 안정적인 모델 추천 (여유분의 80% 이내 권장)
                if size_gb < (free_ram * 0.8) or name == "gemma:2b":
                    label = f"{name} [추천]"
                else:
                    label = name
                model_list.append({"name": name, "label": label})
            return model_list
    except:
        pass
    return []

def pull_model(model_name):
    # UTF-8 인코딩을 명시하여 윈도우 환경의 cp949 충돌을 방지합니다.
    try:
        process = subprocess.Popen(
            ["ollama", "pull", model_name], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            encoding='utf-8', 
            errors='replace'
        )
        return process
    except Exception as e:
        st.error(f"모델 설치 중 오류 발생: {e}")
        return None

# --- Custom Sidebar: Model Management ---
st.sidebar.header("🏬 AI 모델 스토어")

# 1. 현재 설치된 모델 목록 조회
installed_names = []
try:
    resp = requests.get("http://localhost:11434/api/tags", timeout=2)
    if resp.status_code == 200:
        installed_names = [m['name'] for m in resp.json().get('models', [])]
except:
    pass

# 2. 설치 가능 모델 리스트 정의 (전체 스토어 목록)
ALL_STORE_MODELS = [
    {"name": "phi3:mini", "label": "phi3:mini - 가장 똑똑함 (2.3GB) ⭐"},
    {"name": "gemma:2b", "label": "gemma:2b - 매우 가벼움 (1.6GB)"},
    {"name": "gemma4:e2b", "label": "gemma4:e2b - 고성능 분석형 (7.2GB)"},
    {"name": "gemma4:latest", "label": "gemma4:latest - 최신 분석형 (9.6GB)"},
    {"name": "llama3:8b", "label": "llama3:8b - 고성능 모델 (4.7GB)"}
]

# 설치 상태에 따라 라벨 업데이트
store_options = []
for m in ALL_STORE_MODELS:
    is_installed = any(m['name'] in name for name in installed_names)
    status_label = f"{m['label']} [설치됨 ✅]" if is_installed else f"{m['label']} [설치하기 📥]"
    store_options.append({"name": m['name'], "label": status_label, "installed": is_installed})

st.sidebar.markdown("설치할 모델을 선택하고 버튼을 누르세요.")
selected_store_item = st.sidebar.selectbox(
    "AI 모델 스토어 목록", 
    options=store_options, 
    format_func=lambda x: x['label']
)

if st.sidebar.button("🚀 선택한 모델 설치/업데이트"):
    model_name = selected_store_item['name']
    if selected_store_item['installed']:
        st.sidebar.info(f"'{model_name}' 모델은 이미 설치되어 있습니다.")
    else:
        with st.sidebar.status(f"{model_name} 설치 중...", expanded=True) as status:
            proc = pull_model(model_name)
            if proc:
                for line in iter(proc.stdout.readline, ""):
                    st.text(line.strip())
                proc.wait()
                status.update(label=f"{model_name} 설치 완료!", state="complete")
                st.rerun()

st.sidebar.divider()

# --- Custom Sidebar: Software Update ---
st.sidebar.header("🔄 소프트웨어 업데이트")

if st.sidebar.button("✨ 최신 코드로 동기화 (GitHub)"):
    with st.sidebar.status("서버에서 최신 코드 가져오는 중...", expanded=True) as status:
        success, msg = updater.sync_from_github()
        if success:
            status.update(label="업데이트 완료!", state="complete")
            st.sidebar.success("성공적으로 모든 파일을 업데이트했습니다. 프로그램을 다시 시작해 주세요.")
            time.sleep(2)
            st.rerun()
        else:
            status.update(label="업데이트 실패", state="error")
            st.sidebar.error(msg)

# --- Admin Section for Backup (Password Protected) ---
with st.sidebar.expander("🛠️ 개발자 관리 전용"):
    admin_pw = st.text_input("관리자 비번 입력", type="password")
    if admin_pw == "yeji01":  # 사용자님만 아는 비밀번호
        st.info("관리자 인증 완료. 지금 이 컴퓨터의 코드를 서버에 저장할 수 있습니다.")
        
        # 이전 실행 결과가 세션에 있다면 표시
        if "backup_msg" in st.session_state:
            if st.session_state.get("backup_success"):
                st.success(st.session_state.backup_msg)
            else:
                st.error(st.session_state.backup_msg)
            if st.button("결과 확인 완료 (메시지 지우기)"):
                del st.session_state.backup_msg
                st.rerun()

        if st.button("📤 현재 코드 GitHub에 백업", help="이 버튼을 클릭하면 온라인 저장소로 코드가 전송됩니다."):
            with st.spinner("GitHub로 전송 중... 잠시만 기다려주세요."):
                try:
                    # 쉘 명령어로 업로드 스크립트 실행
                    proc = subprocess.run(["python", "upload_to_github.py"], capture_output=True, text=True)
                    if proc.returncode == 0:
                        st.session_state.backup_success = True
                        st.session_state.backup_msg = "🎉 GitHub 업로드 성공! 모든 코드가 백업되었습니다."
                        st.toast("백업 완료!", icon="✅")
                    else:
                        st.session_state.backup_success = False
                        st.session_state.backup_msg = f"❌ 업로드 실패: {proc.stderr}"
                except Exception as e:
                    st.session_state.backup_success = False
                    st.session_state.backup_msg = f"⚠️ 오류 발생: {e}"
                st.rerun() # 현재 상태를 반영하기 위해 재실행
    elif admin_pw:
        st.error("비밀번호가 틀렸습니다.")

st.sidebar.divider()









    
# --- Dashboard Layout ---
col1, col2 = st.columns([1, 2])

with col1:
    st.header("1. 계정 연동")
    st.markdown("<div class='status-container'>", unsafe_allow_html=True)
    if os.path.exists("bot_state.json"):
        st.success("네이버 로그인 정보가 저장되어 있습니다.")
        if st.button("내 가입 카페 불러오기"):
            with st.spinner("가입한 모든 카페 목록을 수집 중입니다. (페이지가 많을 경우 수 초가 소요될 수 있습니다)..."):
                cafes = bot_engine.get_joined_cafes()
                st.session_state.cafes = cafes
            st.success(f"{len(cafes)}개의 카페를 성공적으로 불러왔습니다.")
    else:
        st.warning("로그인이 필요합니다.")
    
    if st.button("브라우저 열어서 로그인하기"):
        st.info("브라우저가 열리면 수동으로 로그인해주세요. 로그인이 완료되면 이 창이 업데이트 됩니다.")
        bot_engine.perform_login()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.header("2. 작업 설정")
    with st.form("task_form"):
        cafe_options = {c['name']: c['url'] for c in st.session_state.cafes} if st.session_state.cafes else {"직접 URL 입력": ""}
        
        selected_cafe_name = st.selectbox("대상 카페 선택", list(cafe_options.keys()))
        
        if selected_cafe_name == "직접 URL 입력":
            cafe_url = st.text_input("카페 고유 ID (예: joonggonara)")
        else:
            cafe_url = st.text_input("카페 URL (자동입력됨)", value=cafe_options[selected_cafe_name], disabled=True)
            
        keyword = st.text_input("검색 키워드", placeholder="예: 아이폰16 후기")
        
        prompt = st.text_area("AI 댓글 지시사항", placeholder="예: 축하한다는 말 예쁘게 써줘. 이모티콘도 1개 써주고.")
        
        # Dynamic Model Selection
        raw_models = get_local_models()
        model_labels = [m['label'] for m in raw_models]
        
        # 추천 모델을 기본값으로 찾기
        default_idx = 0
        for i, m in enumerate(raw_models):
            if "[추천]" in m['label']:
                default_idx = i
                break
                
        selected_label = st.selectbox("사용할 AI 모델 선택 (Ollama)", model_labels, index=default_idx if model_labels else 0)
        selected_model = next((m['name'] for m in raw_models if m['label'] == selected_label), "")
        
        max_comments = st.slider("최대 작업 댓글 수", min_value=1, max_value=50, value=5)
        
        prevent_duplicate_author = st.checkbox("작성자 중복 금지 (아이디 확인)", value=True, help="이미 댓글을 남긴 적이 있는 작성자의 글은 건너뜁니다.")
        
        submitted = st.form_submit_button("작업 시작하기")

        
st.divider()
st.header("작업 로그")
log_container = st.empty()

if submitted:
    if not keyword or not prompt:
        st.error("키워드와 AI 댓글 지시사항을 모두 입력해주세요.")

    else:
        st.toast("작업이 시작되었습니다. 마우스나 다른 버튼을 누르지 말고 잠시만 기다려주세요!")
        st.session_state.full_logs = []
        
        # 봇 엔진 실행 시 실시간 로그를 업데이트하는 콜백 함수
        def live_log_cb(msg):
            # 기존 로그 리스트에 새 메시지 추가
            if 'full_logs' not in st.session_state:
                st.session_state.full_logs = []
            
            timestamp = time.strftime("[%H:%M:%S] ")
            full_msg = timestamp + msg
            st.session_state.full_logs.append(full_msg)
            
            # 텍스트 영역에 누적된 로그 전체 표시 (최신 로그가 아래로)
            log_container.text_area(
                "Live Logs (실시간 진행 상황)", 
                value="\n".join(st.session_state.full_logs), 
                height=400,
                key=f"log_{len(st.session_state.full_logs)}" # 강제 갱신을 위해 키 변경
            )
            
        try:
            bot_engine.run_comment_task(cafe_url, keyword, prompt, max_comments=max_comments, model_name=selected_model, prevent_duplicate_author=prevent_duplicate_author, progress_callback=live_log_cb)
            st.success("🎉 모든 작업이 성공적으로 완료되었습니다!")



        except Exception as e:
            st.error(f"❌ 작업 중 오류 발생: {e}")
            live_log_cb(f"실행 중단됨: {e}")
