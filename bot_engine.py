import time
import json
import os
import random
import sys
import asyncio
from urllib.parse import quote
from playwright.sync_api import sync_playwright
import database
from comment_generator import generate_comment

# Windows에서 Playwright(asyncio) 호환성을 위한 패치
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

STATE_FILE = "bot_state.json"

def perform_login():
    """Opens a visible browser for the user to log into Naver and saves the session."""
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Must be headed for login
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://nid.naver.com/nidlogin.login")
        print("Please log in to Naver in the opened browser window.")
        
        # Wait for log in to be completed by checking the URL or a specific element
        page.wait_for_url("https://www.naver.com/**", timeout=300000) # Wait up to 5 minutes
        print("Login successful. Saving session state...")
        
        context.storage_state(path=STATE_FILE)
        browser.close()

def get_joined_cafes():
    """Scrapes the list of joined cafes from Naver."""
    if not os.path.exists(STATE_FILE):
        return []

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    cafes = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=STATE_FILE)
        page = context.new_page()
        page.goto("https://section.cafe.naver.com/ca-fe/home/manage-my-cafe/join")
        
        try:
            current_page = 1
            while True:
                page.wait_for_selector('a.cafe_name', timeout=10000)
                cafe_elements = page.locator('a.cafe_name').all()
                
                for el in cafe_elements:
                    url = el.get_attribute('href')
                    name = el.inner_text().strip()
                    if name and url and 'cafe.naver.com' in url:
                        if not any(c['url'] == url for c in cafes):
                            cafes.append({"name": name, "url": url})
                            
                current_page += 1
                # 네이버는 "다음" 화살표를 초반에 숨기고 페이지 번호만 노출하므로, 정확한 번호를 클릭하도록 설정
                next_page_link = page.locator(f'a.page_item:text-is("{current_page}")')
                
                if next_page_link.is_visible():
                    next_page_link.click()
                    page.wait_for_timeout(1500) # wait for next page to load
                else:
                    # 혹시나 10페이지를 넘어 "다음" 화살표(>)를 눌러야 할 때를 대비
                    next_arrow = page.locator('a.page_item.next')
                    if next_arrow.is_visible() and "display: none" not in next_arrow.get_attribute("style", default=""):
                        next_arrow.click()
                        page.wait_for_timeout(1500)
                    else:
                        break
                        
        except Exception as e:
            print(f"Could not load cafes: {e}")
        
        browser.close()
    return cafes

def run_comment_task(cafe_url: str, keyword: str, prompt: str, max_comments=5, model_name="gemma:2b", prevent_duplicate_author=True, progress_callback=None):



    """
    Searches for the keyword in the cafe and writes comments on new posts.
    """
    if not os.path.exists(STATE_FILE):
        raise Exception("로그인 정보가 없습니다. 먼저 로그인을 진행해주세요.")

    # Process cafe_url to get cafe ID/name if needed, or we just trust the url format
    cafe_id = cafe_url.split('/')[-1] if '/' in cafe_url else cafe_url
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Headless=False helps avoid bot detection sometimes, but True is ok
        context = browser.new_context(storage_state=STATE_FILE)
        page = context.new_page()
        
        if progress_callback: progress_callback(f"해당 카페({cafe_id})의 고유 ID를 분석 중입니다...")
        
        # Navigate to cafe home to get Club ID
        cafe_home_url = f"https://cafe.naver.com/{cafe_id}"
        page.goto(cafe_home_url)
        time.sleep(2)
        
        # Get Club ID from the page source
        import re
        content = page.content()
        match = re.search(r'g_sClubId\s*=\s*\"(\d+)\"', content)
        if not match:
            # Try mobile if desktop failed
            page.goto(f"https://m.cafe.naver.com/{cafe_id}")
            time.sleep(2)
            match = re.search(r'\"clubId\":\s*\"(\d+)\"', page.content())
            
        if not match:
            raise Exception("카페 고유 ID(ClubID) 분석에 실패했습니다. 로그인이 만료되었거나 비공개 카페일 수 있습니다.")
            
        club_id = match.group(1)
        if progress_callback: progress_callback(f"분석 완료 (ID: {club_id}). '{keyword}' 검색 결과를 직접 불러옵니다...")
        
        # Go to NEW direct search URL (Latest verified working format)
        search_query_encoded = quote(keyword)
        # We use the 'f-e/cafes' URL which is confirmed to work on both desktop and mobile views
        direct_search_url = f"https://cafe.naver.com/f-e/cafes/{club_id}/menus/0?viewType=L&ta=ARTICLE_COMMENT&page=1&q={search_query_encoded}"
        page.goto(direct_search_url)
        
        # Extract post URLs with a robust wait loop
        post_links = []
        try:
            start_time = time.time()
            found = False
            while time.time() - start_time < 30: # 30 seconds timeout
                # Check for results
                elements = page.locator("a.article").all()
                if elements:
                    for el in elements:
                        href = el.get_attribute('href')
                        if href:
                            if href.startswith('/'):
                                href = f"https://cafe.naver.com{href}"
                            clean_href = href.split('?')[0]
                            if clean_href not in post_links:
                                post_links.append(clean_href)
                    if post_links:
                        found = True
                        break
                
                # Check for "No results" message
                if "등록된 게시글이 없습니다" in page.content():
                    if progress_callback: progress_callback(f"'{keyword}'에 대한 검색 결과가 이 카페에 없습니다. 작업을 종료합니다.")
                    browser.close()
                    return
                
                if progress_callback: 
                    elapsed = int(time.time() - start_time)
                    progress_callback(f"검색 결과 로딩 대기 중... ({elapsed}초)")
                
                time.sleep(2)
            
            if not found:
                raise Exception("30초 대기 시간 초과: 검색 결과가 나타나지 않습니다. (인터넷 속도나 카페 로딩 지연)")
                            
        except Exception as e:
            raise Exception(f"게시물 목록을 찾는 중 오류 발생: {e}")

            
        if progress_callback: progress_callback(f"총 {len(post_links)}개의 타겟 게시물을 발견했습니다. 중복 검사 및 작업을 시작합니다.")
        
        commented_count = 0
        for link in post_links:
            # Extract article ID
            # Usually format is https://cafe.naver.com/cafeid/articleid
            article_id = link.split('/')[-1].split('?')[0] 
            
            if database.has_commented(article_id):
                continue
            
            # Found a new post
            if progress_callback: progress_callback(f"새 게시글 접속 중: {link}")
            page.goto(link)
            
            # Mimic human reading: wait and scroll
            time.sleep(random.uniform(5, 10))
            if progress_callback: progress_callback("게시글을 읽는 중... (스크롤 시뮬레이션)")
            try:
                # Random scrolling
                for _ in range(random.randint(2, 4)):
                    scroll_amount = random.randint(300, 700)
                    page.mouse.wheel(0, scroll_amount)
                    time.sleep(random.uniform(1, 3))
            except: pass

            
            # Need to switch to the iframe where the cafe content actually is
            try:
                frame = page.frame(name="cafe_main")
                if not frame:
                    continue
                
                # Wait for post content
                frame.wait_for_selector('div.se-main-container', timeout=5000)
                post_title = frame.locator('h3.title_text').inner_text()
                post_content = frame.locator('div.se-main-container').inner_text()
                
                # --- [Duplicate Author Prevention] ---
                # Extract author ID (memberId or similar unique hash)
                author_id = ""
                try:
                    # Method 1: Get from nickname element ID or link
                    nickname_el = frame.locator('a.nickname')
                    if not nickname_el.is_visible():
                        nickname_el = frame.locator('button.nickname')
                        
                    # Usually ID is in href or data-member-id etc.
                    # In modern cafe, it's often accessible via profile link
                    profile_link = nickname_el.get_attribute('href') or ""
                    if 'memberId=' in profile_link:
                        author_id = profile_link.split('memberId=')[-1].split('&')[0]
                    else:
                        # Fallback: use nickname if ID not found (less robust but better than nothing)
                        author_id = nickname_el.inner_text().strip()
                except:
                    pass

                # Check if we should skip this author
                if prevent_duplicate_author and author_id and database.has_commented_to_author(author_id):
                    if progress_callback: progress_callback(f"⏭️ 중복 작성자 건너뜀: '{author_id}'님에게는 이미 다른 글에서 댓글을 남겼습니다.")
                    continue

                # Generate AI comment
                if progress_callback: progress_callback(f"AI 댓글 생성 중... (모델: {model_name})")
                comment = generate_comment(post_title, post_content, prompt, model_name=model_name)


                
                if not comment or comment.isspace() or comment.startswith("Error:"):
                    if progress_callback: progress_callback(f"⚠️ AI 댓글 생성 실패 또는 내용 없음: {comment}")
                    continue


                
                # 0. Scroll to comment section (bottom area)
                if progress_callback: progress_callback("글 하단으로 이동하여 댓글창을 찾는 중...")
                frame.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(random.uniform(1.5, 3))
                
                # --- [Verification Step 1] Get initial comment count ---
                # Use page (top level) or frame to find count
                try:
                    initial_count_el = frame.locator('em#comment_count') # Classic view
                    if not initial_count_el.is_visible():
                        initial_count_el = page.locator('a.button_comment strong') # Modern view
                    
                    inner_count_text = initial_count_el.inner_text().replace(',', '')
                    initial_count = int(inner_count_text) if inner_count_text.isdigit() else 0
                except:
                    initial_count = 0

                # Find the comment textarea
                try:
                    frame.wait_for_selector('textarea.comment_inbox_text', timeout=5000)
                except:
                    if progress_callback: progress_callback(f"❌ 작성 불가: '{post_title[:20]}' 글에 댓글창이 없거나 권한이 없습니다.")
                    continue
                    
                frame.fill('textarea.comment_inbox_text', comment)
                time.sleep(random.uniform(1.5, 3))
                
                # Click Submit
                frame.click('a.btn_register')
                
                # --- [Verification Step 2] Verify count has increased ---
                if progress_callback: progress_callback("댓글 등록 결과 대조 중 (카운트 확인)...")
                verified = False
                for _ in range(10): # wait up to 10 seconds for AJAX
                    time.sleep(1)
                    try:
                        current_count_el = frame.locator('em#comment_count')
                        if not current_count_el.is_visible():
                            current_count_el = page.locator('a.button_comment strong')
                        
                        curr_text = current_count_el.inner_text().replace(',', '')
                        current_count = int(curr_text) if curr_text.isdigit() else 0
                        
                        if current_count > initial_count:
                            verified = True
                            break
                        
                        # Alternative check: is textarea cleared? (for fallback)
                        if not frame.locator('textarea.comment_inbox_text').input_value() and _ > 2:
                            verified = True
                            break
                    except:
                        pass
                
                if not verified:
                    if progress_callback: progress_callback(f"❌ 등록 실패: '{post_title[:20]}' 글에 댓글이 실제로 등록되지 않았습니다.")
                    continue

                # Save to DB (Always save author_id for permanent memory)
                database.mark_commented(cafe_url, article_id, author_id, keyword, comment)
                if progress_callback: progress_callback(f"✔️ 완료 | 게시글: '{post_title[:20]}...'\n└ 작성내용: {comment}")
                commented_count += 1


                
                if commented_count >= max_comments:
                    if progress_callback: progress_callback(f"🎯 설정된 대댓글 작업 수({max_comments}개)를 모두 달성했습니다. 작업을 마무리합니다.")
                    break

                
                # Prevent spamming quickly (20-60 seconds)
                wait_time = random.randint(20, 60)
                if progress_callback: progress_callback(f"안전한 작업을 위해 {wait_time}초 대기 후 다음 글로 이동합니다...")
                time.sleep(wait_time)


            except Exception as e:
                print(f"Failed to process {link}: {e}")
                continue

        if progress_callback: progress_callback(f"작업 완료! 새롭게 작성된 댓글 개수: {commented_count}개")
        browser.close()

if __name__ == "__main__":
    # Test script
    database.init_db()
    # perform_login()
    # print(get_joined_cafes())
