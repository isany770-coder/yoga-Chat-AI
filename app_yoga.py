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
st.set_page_config(page_title="Yoga Assistant Pro", page_icon="🧘", layout="wide", initial_sidebar_state="collapsed")

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
# 3. CSS GIAO DIỆN
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

    .solution-card {
        background: linear-gradient(135deg, #e0f2f1 0%, #b2dfdb 100%);
        border: 1px solid #009688; border-radius: 10px; padding: 12px; margin-top: 10px;
        display: flex; align-items: center; justify-content: space-between;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .solution-text { font-size: 14px; color: #004d40; font-weight: bold; }
    .solution-btn {
        background-color: #00796b; color: white !important; padding: 6px 15px;
        border-radius: 20px; text-decoration: none; font-size: 12px; font-weight: bold; white-space: nowrap;
    }
    .solution-btn:hover { background-color: #004d40; }

    .source-box { background-color: #f8f9fa; border-left: 4px solid #0f988b; padding: 12px; margin-top: 15px; border-radius: 0 8px 8px 0; font-size: 0.9em; }
    .tag-science { background-color: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: bold; margin-right: 6px; border: 1px solid #c7d2fe; }
    .tag-blog { background-color: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: bold; margin-right: 6px; border: 1px solid #bbf7d0; }
    .tag-qa { background-color: #fef9c3; color: #854d0e; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: bold; margin-right: 6px; border: 1px solid #fde047; }
    
    .limit-container { margin-top: 50px; padding: 40px; border-radius: 25px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); text-align: center; border: 2px solid #0f988b; background: white; margin-left: auto; margin-right: auto; max-width: 500px; }
    .zalo-btn { display: flex !important; align-items: center; justify-content: center; width: 100%; background-color: white; color: #0f988b !important; border: 1px solid #dcdfe3; border-radius: 8px; font-weight: 500; font-size: 14px; height: 45px !important; text-decoration: none !important; margin: 0 !important; }
    div[data-testid="stForm"] button { height: 45px !important; border-radius: 8px !important; font-weight: 500 !important; color: #31333F !important; }
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
OUTPUT_ZIP = "/tmp/brain_v9_clean.zip"
EXTRACT_PATH = "/tmp/brain_v9_clean"

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
            # Tải file
            gdown.download(URL_DRIVE, OUTPUT_ZIP, quiet=False, fuzzy=True)
            # Giải nén
            with zipfile.ZipFile(OUTPUT_ZIP, 'r') as zip_ref:
                zip_ref.extractall(EXTRACT_PATH)
            # Xóa zip
            if os.path.exists(OUTPUT_ZIP):
                os.remove(OUTPUT_ZIP)
        except Exception as e:
            if os.path.exists(EXTRACT_PATH):
                import shutil
                shutil.rmtree(EXTRACT_PATH)
            return None, None
    
    # Tự động dò tìm file index.faiss
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
    except: pass
    return "guest_unknown"

# =====================================================
# 5. QUẢN LÝ USER & DATA (ĐÃ SỬA CÚ PHÁP CHUẨN)
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
    with open(USAGE_DB_FILE, "w") as f:
        json.dump(data, f)

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""

user_key = st.session_state.username if st.session_state.authenticated else get_remote_ip()
today = str(datetime.date.today())
db_data = get_data()

if user_key not in db_data or db_data[user_key].get("date") != today:
    db_data[user_key] = {"date": today, "count": 0, "history": [{"role":"assistant","content":"Namaste! 🙏 Tôi là Trợ lý Yoga AI chuyên sâu. Bác cần tư vấn gì hôm nay?"}]}
    save_data(db_data)

st.session_state.messages = db_data[user_key]["history"]
used = db_data[user_key]["count"]
limit = DAILY_LIMIT if st.session_state.authenticated else TRIAL_LIMIT
percent = min(100, int((used / limit) * 100))
st.markdown(f"""<div class="usage-bar-container"><div class="usage-bar-fill" style="width: {percent}%;"></div></div><div class="usage-text">⚡ Lượt dùng: {used}/{limit}</div>""", unsafe_allow_html=True)
can_chat = used < limit

def render_login_form():
    with st.form("login_form"):
        st.write("🔐 **Đăng nhập Member:**")
        u = st.text_input("Tên đăng nhập", placeholder="Username")
        p = st.text_input("Mật khẩu", type="password", placeholder="Password")
        c1, c2 = st.columns(2)
        with c1: submit = st.form_submit_button("Đăng nhập", use_container_width=True)
        with c2: st.markdown(f"""<a href="https://zalo.me/84963759566" target="_blank" style="text-decoration:none;"><div class="zalo-btn">💬 Lấy TK Zalo</div></a>""", unsafe_allow_html=True)
        if submit:
            if (u=="admin" and p=="yoga888") or (st.secrets["passwords"].get(u)==p):
                st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
            else: st.error("Sai mật khẩu!")

def get_recommended_solutions(user_query):
    query_lower = user_query.lower()
    recommendations = []
    for key, data in YOGA_SOLUTIONS.items():
        if any(trigger in query_lower for trigger in data["trigger"]): recommendations.append(data)
    return recommendations[:2]

# =====================================================
# 6. GIAO DIỆN CHÍNH
# =====================================================
if not st.session_state.authenticated:
    st.markdown(f"""<div style="position: fixed; bottom: 80px; left: 15px; right: 15px; background: #fff5f0; border: 1px solid #ffccbc; border-radius: 15px; padding: 10px 15px; z-index: 99999; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 15px rgba(255, 87, 34, 0.1);"><div style="display: flex; align-items: center; gap: 10px;"><div style="background: #ff7043; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center;"><span style="font-size: 16px;">🎁</span></div><div><div style="color: #bf360c !important; font-size: 13px; font-weight: bold;">Combo Thảm & Freeship!!</div><div style="color: #ff7043 !important; font-size: 11px;">Giảm ngay 30% hôm nay!</div></div></div><a href="https://yogaismylife.vn/cua-hang/" target="_blank" style="background: #ff7043; color: white !important; padding: 8px 15px; border-radius: 10px; text-decoration: none; font-weight: bold; font-size: 12px; box-shadow: 0 2px 5px rgba(255, 112, 67, 0.3);">Xem ngay</a></div>""", unsafe_allow_html=True)

for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"], unsafe_allow_html=True)

if not can_chat:
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
    st.markdown(f"""<div class="limit-container"><div style="font-size:50px;margin-bottom:10px">🧘‍♀️</div><div style="font-size:22px;font-weight:bold;color:#0f988b;margin-bottom:10px">Đã đạt giới hạn!</div><p style="color:#555;margin-bottom:20px">Hết {TRIAL_LIMIT} lượt dùng thử.<br>Vui lòng đăng nhập.</p></div><br>""", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2: render_login_form()
    st.stop()

# XỬ LÝ CHAT (LOGIC MỚI: BẮT DÍNH TỪ KHÓA)
if prompt := st.chat_input("Hỏi tôi về Yoga..."):
    db_data[user_key]["count"] += 1
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        if db:
            # 1. VÉT 80 KẾT QUẢ
            docs = db.similarity_search(prompt, k=80)
            
            # 2. XÁC ĐỊNH TỪ KHÓA QUAN TRỌNG TỪ CÂU HỎI
            # Ví dụ: "tập yoga có giảm cân không" -> keywords: ["giảm", "cân", "béo", "mỡ"]
            user_keywords = prompt.lower().split()
            # Lọc từ ngắn quá (<3 ký tự)
            user_keywords = [w for w in user_keywords if len(w) > 2]

            science_pool = []
            qa_pool = []
            blog_pool = []
            seen_urls = set()

            for d in docs:
                url = d.metadata.get('url', '#')
                # Lọc trùng URL (Deduplication)
                if url != '#' and len(str(url)) > 10:
                    if url in seen_urls: continue
                    seen_urls.add(url)

                dtype = d.metadata.get('type', 'general')
                title = d.metadata.get('title', '').lower()
                
                # --- TÍNH ĐIỂM KHỚP TỪ KHÓA ---
                # Nếu tiêu đề bài viết chứa từ khóa trong câu hỏi -> Cộng điểm cực mạnh
                score = 0
                for kw in user_keywords:
                    if kw in title:
                        score += 10 # Điểm thưởng lớn
                
                # Đóng gói (điểm, document)
                item = (score, d)

                if dtype == 'science': science_pool.append(item)
                elif dtype == 'qa': qa_pool.append(item)
                else: blog_pool.append(item)
            
            # 3. SẮP XẾP THEO ĐIỂM CAO NHẤT
            science_pool.sort(key=lambda x: x[0], reverse=True)
            qa_pool.sort(key=lambda x: x[0], reverse=True)
            blog_pool.sort(key=lambda x: x[0], reverse=True)

            # 4. CHIA SLOT (Lấy doc từ tuple)
            # Lấy 2 Science tốt nhất (dù điểm thấp hơn blog cũng phải lấy)
            final_docs = [x[1] for x in science_pool[:2]]
            # Lấy 2 QA tốt nhất
            final_docs += [x[1] for x in qa_pool[:2]]
            # Lấy 2 Blog tốt nhất (khớp từ khóa nhất)
            final_docs += [x[1] for x in blog_pool[:2]]

            context_parts = []
            source_map = {}
            has_science = False
            
            for i, d in enumerate(final_docs):
                dtype = d.metadata.get('type', 'general')
                title = d.metadata.get('title', 'Tài liệu')
                url = d.metadata.get('url', '#')
                
                label = ""
                if dtype == 'science': 
                    label = "NGHIÊN CỨU KHOA HỌC"
                    has_science = True
                elif dtype == 'qa': label = "CHUYÊN GIA"
                else: label = "BÀI VIẾT"
                
                context_parts.append(f"--- NGUỒN {i+1} [{label}] ---\nTiêu đề: {title}\nNội dung: {d.page_content}")
                
                if url and len(str(url)) > 10:
                    source_map[url] = {"title": title, "type": dtype}
            
            full_context = "\n\n".join(context_parts)
            
            solutions = get_recommended_solutions(prompt)
            sol_context = ""
            if solutions:
                names = ", ".join([s["name"] for s in solutions])
                sol_context = f"\nLưu ý: Cuối câu trả lời, khuyên dùng: {names}."

            sci_instruct = "BẮT BUỘC: Nếu có nguồn [NGHIÊN CỨU KHOA HỌC], hãy trích dẫn 'Theo nghiên cứu năm [Năm] của [Tác giả]...'" if has_science else "Trả lời dựa trên kiến thức Yoga chuẩn."

            sys_prompt = f"""
            Bạn là Chuyên gia Yoga Khoa học. DỮ LIỆU THAM KHẢO:
            {full_context}
            {sol_context}

            YÊU CẦU:
            1. KHÔNG VIẾT HOA TOÀN BỘ TIÊU ĐỀ (Ví dụ: Đừng viết "KẾT LUẬN", hãy viết "Kết luận").
            2. Trả lời thẳng vào vấn đề, ngắn gọn (dưới 150 từ).
            3. {sci_instruct}
            4. Luôn nhắc nhở lắng nghe cơ thể.

            CÂU HỎI: "{prompt}"
            """
            
            try:
                with st.spinner("🧘 Đang phân tích dữ liệu chuyên sâu..."):
                    response = model.generate_content(sys_prompt)
                    res_text = response.text
                
                full_html_content = res_text
                
                if solutions:
                    full_html_content += "<hr>"
                    for sol in solutions:
                        full_html_content += f"""<div class="solution-card"><div class="solution-text">{sol['name']}</div><a href="{sol['url']}" target="_blank" class="solution-btn">Sử dụng ngay 🚀</a></div>"""
                
                if source_map:
                    # Sắp xếp hiển thị: Science lên đầu
                    sorted_urls = sorted(source_map.items(), key=lambda x: 0 if x[1]['type']=='science' else 1 if x[1]['type']=='qa' else 2)
                    
                    links_html = "<div class='source-box'><strong>📚 Nguồn tham khảo uy tín:</strong><div style='margin-top:8px'>"
                    for url, info in sorted_urls:
                        tag_html = ""
                        if info['type'] == 'science': tag_html = "<span class='tag-science'>KHOA HỌC</span>"
                        elif info['type'] == 'qa': tag_html = "<span class='tag-qa'>CHUYÊN GIA</span>"
                        else: tag_html = "<span class='tag-blog'>BÀI VIẾT</span>"
                        links_html += f"<div style='margin-bottom:6px'>{tag_html} <a href='{url}' target='_blank' style='text-decoration:none; color:#0f988b; font-weight:500'>{info['title']}</a></div>"
                    links_html += "</div></div>"
                    full_html_content += links_html
                
                st.markdown(full_html_content, unsafe_allow_html=True)
                
                # Lưu lịch sử FULL HTML để không bị mất khi load lại
                db_data[user_key]["history"].append({"role": "user", "content": prompt})
                db_data[user_key]["history"].append({"role": "assistant", "content": full_html_content})
                save_data(db_data)
                
            except Exception as e:
                st.error(f"Lỗi AI: {e}")

if not st.session_state.authenticated and can_chat:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🔐 Đăng nhập (Dành cho Member)", expanded=False): render_login_form()
    st.markdown("<div style='height: 250px;'></div>", unsafe_allow_html=True)
