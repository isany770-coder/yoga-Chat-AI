import streamlit as st
import gdown
import zipfile
import os
import json
import datetime
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH TRANG
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =====================================================
# 2. HỆ SINH THÁI GIẢI PHÁP
# =====================================================
YOGA_SOLUTIONS = {
    "QUY_TRINH_8_BUOC": {
        "name": "🗺️ Quy trình 8 Bước Toàn Diện",
        "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/",
        "trigger": ["bắt đầu", "lộ trình", "người mới", "từ đầu", "cơ bản", "hướng dẫn", "bao lâu", "học yoga", "nhập môn"]
    },
    "AI_COACH": {
        "name": "🤖 Gặp AI Coach 1:1",
        "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/",
        "trigger": ["đau", "chấn thương", "mỏi", "bệnh", "trị liệu", "tư vấn riêng", "khó quá", "không tập được", "thoát vị", "đau gối", "lưng", "cổ", "vai", "xương khớp"]
    },
    "APP_THIEN_THO": {
        "name": "🧘 App Thiền & Hít Thở",
        "url": "https://yogaismylife.vn/thien-hoi-tho-chua-lanh/",
        "trigger": ["stress", "căng thẳng", "mất ngủ", "lo âu", "thở", "thiền", "thư giãn", "mệt mỏi", "áp lực", "ngủ ngon", "yên tĩnh"]
    }
}

# =====================================================
# 3. CSS GIAO DIỆN (ĐÃ TỐI ƯU)
# =====================================================
st.markdown("""
<style>
    [data-testid="stAppViewContainer"], .stApp, html, body { background-color: white !important; color: #31333F !important; }
    [data-testid="stToolbar"], header, footer, .stAppDeployButton {display: none !important;}
    
    div[data-testid="stChatInput"] { 
        position: fixed !important; bottom: 20px !important; left: 10px !important; right: 10px !important; 
        z-index: 999999; background-color: white !important; border-radius: 25px !important; 
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1); padding: 5px !important; border: 1px solid #e0e0e0; 
    }
    textarea[data-testid="stChatInputTextArea"] { font-size: 16px !important; background-color: #f0f2f6 !important; border-radius: 20px !important; }

    /* CONTAINER HẾT HẠN - UPDATE GIAO DIỆN */
    .limit-container {
        margin-top: 20px;
        padding: 30px 20px;
        border-radius: 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        text-align: center;
        border: 2px solid #e0f2f1;
        background: white;
        margin-left: auto; margin-right: auto;
        max-width: 450px;
    }
    .limit-icon { font-size: 40px; display: block; margin-bottom: 10px; }
    .limit-title { font-size: 20px; font-weight: 800; color: #00796b; margin-bottom: 8px; }
    .limit-desc { font-size: 14px; color: #555; margin-bottom: 20px; line-height: 1.5; }

    /* STYLE CHO NGUỒN THAM KHẢO (ĐÃ CHUẨN HÓA) */
    .source-box { 
        background-color: #fafafa; 
        border: 1px solid #eee;
        padding: 15px; 
        margin-top: 15px; 
        border-radius: 10px; 
        font-size: 0.9em; 
    }
    .source-title {
        font-weight: bold; color: #333; margin-bottom: 10px; display: flex; align-items: center; gap: 5px;
    }
    .source-item {
        display: flex; align-items: flex-start; margin-bottom: 8px; line-height: 1.4;
    }
    .tag-badge {
        font-size: 0.7em; font-weight: bold; padding: 2px 6px; border-radius: 4px; margin-right: 8px; white-space: nowrap; margin-top: 2px;
    }
    .tag-science { background-color: #e0e7ff; color: #3730a3; border: 1px solid #c7d2fe; }
    .tag-blog { background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
    
    /* BUTTONS STYLE */
    .zalo-btn { display: flex !important; align-items: center; justify-content: center; width: 100%; background-color: #0f988b; color: white !important; border: none; border-radius: 8px; font-weight: bold; font-size: 14px; height: 45px !important; text-decoration: none !important; margin-top: 10px !important; box-shadow: 0 4px 10px rgba(15, 152, 139, 0.2); }
    
    /* Custom style cho nút toggle login */
    .login-toggle-btn {
        background: transparent; border: 1px solid #ccc; color: #666; width: 100%; padding: 10px;
        border-radius: 8px; font-weight: 600; cursor: pointer; margin-top: 10px;
    }

    div[data-testid="stForm"] { border: none !important; padding: 15px !important; background: #f9f9f9; border-radius: 10px; margin-top: 10px;}
    div[data-testid="stForm"] button { height: 40px !important; border-radius: 6px !important; font-weight: 600 !important; color: white !important; width: 100%; background-color: #333 !important; }
    
    .usage-bar-container { position: fixed; top: 0; left: 0; width: 100%; height: 5px; background-color: #f0f0f0; z-index: 1000000; }
    .usage-bar-fill { height: 100%; background: linear-gradient(90deg, #0f988b 0%, #14b8a6 100%); }
    .usage-text { position: fixed; top: 10px; right: 15px; background: rgba(255,255,255,0.9); padding: 4px 12px; border-radius: 20px; font-size: 11px; color: #0f988b !important; font-weight: bold; border: 1px solid #0f988b; z-index: 1000001; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 4. KẾT NỐI API & DRIVE
# =====================================================
FILE_ID_DRIVE = "13z82kBBd8QwpCvUqGysD9DXI8Xurvtq9" 
URL_DRIVE = f'https://drive.google.com/uc?id={FILE_ID_DRIVE}'
OUTPUT_ZIP = "/tmp/brain_v9_stable.zip"
EXTRACT_PATH = "/tmp/brain_v9_stable"

try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Thiếu API KEY")
    st.stop()

@st.cache_resource
def load_brain():
    if not os.path.exists(EXTRACT_PATH):
        try:
            print("Dang tai file...")
            gdown.download(URL_DRIVE, OUTPUT_ZIP, quiet=False, fuzzy=True)
            print("Dang giai nen...")
            with zipfile.ZipFile(OUTPUT_ZIP, 'r') as zip_ref:
                zip_ref.extractall(EXTRACT_PATH)
            if os.path.exists(OUTPUT_ZIP):
                os.remove(OUTPUT_ZIP)
        except Exception as e:
            if os.path.exists(EXTRACT_PATH):
                import shutil
                shutil.rmtree(EXTRACT_PATH)
            return None, None
    
    vector_db_path = None
    for root, dirs, files in os.walk(EXTRACT_PATH):
        for file in files:
            if file.endswith(".faiss"):
                vector_db_path = root
                break
        if vector_db_path:
            break
    
    if vector_db_path is None:
        return None, None

    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(vector_db_path, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest')
        return db, model
    except:
        return None, None

db, model = load_brain()
if db is None or model is None:
    st.warning("🧘‍♂️ Đang khởi động não bộ... Vui lòng chờ 30s rồi tải lại (F5).")
    st.stop()

def get_remote_ip():
    try:
        from streamlit.web.server.websocket_headers import _get_headers
        headers = _get_headers()
        ip = headers.get("X-Forwarded-For")
        if ip: return ip.split(",")[0].strip()
    except:
        pass
    return "guest_unknown"

# =====================================================
# 5. QUẢN LÝ USER & DATA
# =====================================================
USAGE_DB_FILE = "/tmp/usage_history_db.json"
DAILY_LIMIT = 25
TRIAL_LIMIT = 10

def get_data():
    if not os.path.exists(USAGE_DB_FILE):
        return {}
    try:
        with open(USAGE_DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    try:
        with open(USAGE_DB_FILE, "w") as f:
            json.dump(data, f)
    except:
        pass

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
# Biến trạng thái để bật/tắt form đăng nhập
if "show_login_form" not in st.session_state:
    st.session_state.show_login_form = False

user_key = st.session_state.username if st.session_state.authenticated else get_remote_ip()
today = str(datetime.date.today())
db_data = get_data()

if user_key not in db_data or db_data[user_key].get("date") != today:
    db_data[user_key] = {
        "date": today,
        "count": 0,
        "history": [{"role":"assistant","content":"Namaste! 🙏 Tôi là Trợ lý Yoga AI chuyên sâu. Bác cần tư vấn gì hôm nay?"}]
    }
    save_data(db_data)

st.session_state.messages = db_data[user_key]["history"]
used = db_data[user_key]["count"]
limit = DAILY_LIMIT if st.session_state.authenticated else TRIAL_LIMIT
percent = min(100, int((used / limit) * 100))
st.markdown(f"""<div class="usage-bar-container"><div class="usage-bar-fill" style="width: {percent}%;"></div></div><div class="usage-text">⚡ Lượt dùng: {used}/{limit}</div>""", unsafe_allow_html=True)
can_chat = used < limit

# =====================================================
# 6. MÀN HÌNH HẾT HẠN & ĐĂNG NHẬP (TỐI ƯU UX/UI)
# =====================================================
def render_limit_screen():
    # Ẩn thanh chat
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
    
    # 1. Hiển thị Container thông báo
    st.markdown("""
    <div class="limit-container">
        <span class="limit-icon">🧘‍♀️</span>
        <div class="limit-title">Hết lượt dùng thử!</div>
        <div class="limit-desc">
            Bạn đã dùng hết lượt hỏi miễn phí hôm nay.<br>
            Kết nối Zalo để nhận mã kích hoạt <b>Full Tính Năng</b> hoặc đăng nhập bên dưới.
        </div>
    """, unsafe_allow_html=True)

    # 2. Nút Zalo (Call To Action chính)
    st.markdown(f"""<a href="https://zalo.me/84963759566" target="_blank" style="text-decoration:none;"><button class="zalo-btn">💬 Nhận mã kích hoạt qua Zalo</button></a>""", unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True) # Đóng div container để nút login nằm riêng hoặc trong đó tùy chỉnh
    
    # 3. Nút Toggle Đăng nhập (Nằm dưới box thông báo một chút cho thoáng)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Nếu chưa mở form thì hiện nút "Đăng nhập Member"
        if not st.session_state.show_login_form:
            if st.button("🔐 Đăng nhập Member", use_container_width=True):
                st.session_state.show_login_form = True
                st.rerun()
        
        # Nếu đã ấn nút thì hiện Form
        if st.session_state.show_login_form:
             with st.form("login_form_limit"):
                st.markdown("##### 🔐 Đăng nhập hệ thống")
                u = st.text_input("Tên đăng nhập", placeholder="Username")
                p = st.text_input("Mật khẩu", type="password", placeholder="Password")
                submit = st.form_submit_button("XÁC THỰC")
                
                # Nút hủy/đóng form
                if submit:
                    if (u=="admin" and p=="yoga888") or (st.secrets["passwords"].get(u)==p):
                        st.session_state.authenticated = True
                        st.session_state.username = u
                        st.session_state.show_login_form = False # Reset lại
                        st.rerun()
                    else:
                        st.error("Sai mật khẩu!")

             if st.button("Quay lại / Đóng", use_container_width=True):
                 st.session_state.show_login_form = False
                 st.rerun()

def get_recommended_solutions(user_query):
    query_lower = user_query.lower()
    recommendations = []
    for key, data in YOGA_SOLUTIONS.items():
        if any(trigger in query_lower for trigger in data["trigger"]):
            recommendations.append(data)
    return recommendations[:2]

# =====================================================
# 7. GIAO DIỆN CHÍNH
# =====================================================

# --- LOGIC QUAN TRỌNG: CHỈ HIỆN QUẢNG CÁO KHI CÒN CHAT ĐƯỢC ---
# Nếu hết hạn (can_chat = False), ẩn quảng cáo đi để người dùng focus vào màn hình Limit
if not st.session_state.authenticated and can_chat:
    st.markdown(f"""<div style="position: fixed; bottom: 80px; left: 15px; right: 15px; background: #fff5f0; border: 1px solid #ffccbc; border-radius: 15px; padding: 10px 15px; z-index: 99999; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 15px rgba(255, 87, 34, 0.1);"><div style="display: flex; align-items: center; gap: 10px;"><div style="background: #ff7043; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center;"><span style="font-size: 16px;">🎁</span></div><div><div style="color: #bf360c !important; font-size: 13px; font-weight: bold;">Combo Thảm & Freeship!!</div><div style="color: #ff7043 !important; font-size: 11px;">Giảm ngay 30% hôm nay!</div></div></div><a href="https://yogaismylife.vn/cua-hang/" target="_blank" style="background: #ff7043; color: white !important; padding: 8px 15px; border-radius: 10px; text-decoration: none; font-weight: bold; font-size: 12px; box-shadow: 0 2px 5px rgba(255, 112, 67, 0.3);">Xem ngay</a></div>""", unsafe_allow_html=True)

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"], unsafe_allow_html=True)

# --- KIỂM TRA GIỚI HẠN ---
if not can_chat:
    render_limit_screen()
    st.stop()

# XỬ LÝ CHAT
if prompt := st.chat_input("Hỏi tôi về Yoga..."):
    db_data[user_key]["count"] += 1
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if db:
            docs = db.similarity_search(prompt, k=80)
            user_keywords = [w for w in prompt.lower().split() if len(w) > 2]
            
            science_pool = []
            qa_pool = []
            blog_pool = []
            seen_urls = set()

            for d in docs:
                url = d.metadata.get('url', '#')
                if url != '#' and len(str(url)) > 10:
                    if url in seen_urls: continue
                    seen_urls.add(url)
                
                dtype = d.metadata.get('type', 'general')
                title = d.metadata.get('title', '').lower()
                
                score = 0
                for kw in user_keywords:
                    if kw in title:
                        score += 10
                
                item = (score, d)
                if dtype == 'science': science_pool.append(item)
                elif dtype == 'qa': qa_pool.append(item)
                else: blog_pool.append(item)
            
            science_pool.sort(key=lambda x: x[0], reverse=True)
            qa_pool.sort(key=lambda x: x[0], reverse=True)
            blog_pool.sort(key=lambda x: x[0], reverse=True)

            final_docs = [x[1] for x in science_pool[:2]] + [x[1] for x in qa_pool[:2]] + [x[1] for x in blog_pool[:2]]

            context_parts = []
            source_map = {}
            for i, d in enumerate(final_docs):
                dtype = d.metadata.get('type', 'general')
                title = d.metadata.get('title', 'Tài liệu')
                url = d.metadata.get('url', '#')
                
                label = "NGHIÊN CỨU" if dtype == 'science' else "BÀI VIẾT"
                context_parts.append(f"--- NGUỒN {i+1} [{label}] ---\nTiêu đề: {title}\nNội dung: {d.page_content}")
                
                if url and len(str(url)) > 10:
                    source_map[url] = {"title": title, "type": dtype}
            
            full_context = "\n\n".join(context_parts)
            solutions = get_recommended_solutions(prompt)
            sol_context = ""
            if solutions:
                names = ", ".join([s["name"] for s in solutions])
                sol_context = f"\nLưu ý: Cuối bài, khuyên dùng: {names}."

            sys_prompt = f"""
            Bạn là Chuyên gia Yoga. DỮ LIỆU:
            {full_context}
            {sol_context}
            YÊU CẦU:
            1. Trả lời ngắn gọn, chân thành.
            2. Sử dụng icon hợp lý.
            CÂU HỎI: "{prompt}"
            """
            
            try:
                with st.spinner("🧘 Đang tra cứu..."):
                    response = model.generate_content(sys_prompt)
                    res_text = response.text
                
                full_html_content = res_text
                
                if solutions:
                    full_html_content += "<hr style='margin: 15px 0; border: 0; border-top: 1px solid #eee;'>"
                    for sol in solutions:
                        full_html_content += f"""<div class="solution-card"><div class="solution-text">{sol['name']}</div><a href="{sol['url']}" target="_blank" class="solution-btn">Sử dụng ngay 🚀</a></div>"""
                
                # --- PHẦN XỬ LÝ TRÍCH DẪN LINK MỚI (CHUẨN HƠN) ---
                if source_map:
                    links_html = """
                    <div class='source-box'>
                        <div class='source-title'>📚 Tài liệu tham khảo</div>
                        <div>
                    """
                    sorted_urls = sorted(source_map.items(), key=lambda x: 0 if x[1]['type']=='science' else 1)
                    
                    for url, info in sorted_urls:
                        # Rút gọn title nếu quá dài để hiển thị đẹp trên mobile
                        display_title = info['title']
                        if len(display_title) > 60: display_title = display_title[:57] + "..."
                        
                        badge_class = "tag-science" if info['type']=='science' else "tag-blog"
                        badge_text = "KHOA HỌC" if info['type']=='science' else "BÀI VIẾT"
                        
                        links_html += f"""
                        <div class='source-item'>
                            <span class='tag-badge {badge_class}'>{badge_text}</span>
                            <a href='{url}' target='_blank' style='text-decoration:none; color:#333; font-weight:500; font-size: 0.95em;'>{display_title}</a>
                        </div>
                        """
                    links_html += "</div></div>"
                    full_html_content += links_html
                # ------------------------------------------------
                
                st.markdown(full_html_content, unsafe_allow_html=True)
                
                db_data[user_key]["history"].append({"role": "user", "content": prompt})
                db_data[user_key]["history"].append({"role": "assistant", "content": full_html_content})
                save_data(db_data)
                
            except Exception as e:
                st.error(f"Lỗi: {e}")
