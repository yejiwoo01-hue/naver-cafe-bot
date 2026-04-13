import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

# 로컬 Ollama 설정 (llm_engine.py 구성을 기반으로 함)
OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
MODEL_NAME = "gemma4:e2b"

def generate_comment(post_title: str, post_content: str, user_prompt: str, model_name: str = "gemma:2b") -> str:
    """로컬 AI(Ollama) 서버의 지정된 모델을 사용하여 댓글을 생성합니다."""

    
    system_persona = (
        "당신은 이 카페를 지나가다 우연히 글을 읽은 '낯선 회원'입니다. "
        "당신은 블로거나 가이드가 아닙니다. 절대 자기소개를 하지 마십시오. "
        "글쓴이에게 친절하지만 정중하게, 딱 '한 문장'으로만 짧은 의견이나 공감을 남기십시오."
    )








    prompt = f"""
전문의 마케터로서 아래 정보를 분석하여 최고의 댓글을 작성하십시오.

<게시글_제목>
{post_title}
</게시글_제목>

<게시글_내용>
{post_content[:1000]}
</게시글_내용>




<최우선_지시사항>
- 아래 지시사항은 어떠한 경우에도 반드시 지켜야 하며, 다른 모든 안내보다 우선합니다:
{user_prompt}
</최우선_지시사항>

<작성_가이드라인>
1. 절대로 본인 소개(반가워요, 모찌예요 등)를 하지 마십시오.
2. 게시글 내용에 대해 '딱 한 문장'만 다정하게 말하십시오. (마침표로 끝맺음)
3. '블로그', '가이드', '추천해 드립니다', '소개' 같은 홍보성 단어는 절대 금지입니다.
4. 마치 지나가던 사람이 툭 던지는 짧은 댓글처럼 작성하십시오.
</작성_가이드라인>

댓글 (한 문장):
"""






    payload = {
        "model": model_name,
        "messages": [

            {"role": "system", "content": system_persona},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4, # 일관성을 위해 온도를 더 낮춤
        "max_tokens": 60,   # 댓글이 길어지는 것을 물리적으로 차단
        "stream": False
    }



    try:
        # 전체 게시글 분석을 위해 타임아웃을 300초(5분)로 대폭 늘려 충분한 시간을 확보합니다.
        response = requests.post(OLLAMA_URL, json=payload, timeout=300)
        response.raise_for_status()

        result = response.json()
        comment = result['choices'][0]['message']['content'].strip()
        
        # [강력 조치] AI가 보낸 텍스트에서 모든 별표(*)와 샵(#)을 파이썬 레벨에서 강제 삭제합니다.
        comment = comment.replace("*", "").replace("#", "").strip()
        
        # AI가 빈 답변을 보냈을 경우 에러 처리

        if not comment:
            raise Exception("AI가 빈 답장을 보냈습니다. 모델 상태를 확인해주세요.")
            
        # 가끔 AI가 따옴표를 포함할 경우 제거

        if (comment.startswith('"') and comment.endswith('"')) or (comment.startswith("'") and comment.endswith("'")):
            comment = comment[1:-1].strip()
            
        # [강력 검수] 답변에 영어 비중이 너무 높으면 할루시네이션으로 판단하고 차단합니다.
        import re
        english_chars = len(re.findall(r'[a-zA-Z]', comment))
        if english_chars > len(comment) * 0.3: # 영어 비중이 30% 이상이면 오류 처리
            raise Exception("AI가 한글 대신 영어를 내뱉었습니다. 모델을 gemma:2b로 바꾸시거나 다시 시도해주세요.")
            
        return comment

    except Exception as e:
        error_msg = f"로컬 AI(Ollama) 호출 중 오류 발생: {e}"
        print(error_msg)
        return f"Error: {error_msg}. Ollama가 켜져 있는지 확인해 주세요."

if __name__ == "__main__":
    # 간단한 작동 테스트
    print("로컬 AI 댓글 생성 테스트 중...")
    res = generate_comment(
        "트러블 세안법 어떤게 좋을까요?", 
        "요즘 피부가 너무 예민해서 일반 폼클렌징은 따갑네요. 약산성 쓰면 좀 나을까요?", 
        "트러블 세안법 작성해줘. 댓글은 200자 이내"
    )
    print(f"\n생성된 댓글:\n{res}")
