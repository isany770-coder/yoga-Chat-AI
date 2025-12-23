import streamlit as st
import gdown
import zipfile
import os
import json
import datetime
import gc # <--- QUAN TRỌNG: Thư viện dọn rác bộ nhớ
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
        "trigger": ["bắt đầu", "lộ trình", "người mới", "từ đầu", "cơ bản", "hướng dẫn", "bao lâu", "học yoga", "nhập môn", "luân xa", "sức khỏe", "thực đơn"]
    },
    "AI_COACH": {
        "name": "🤖 Gặp AI Coach 1:1",
        "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/",
        "trigger": ["đau", "chấn thương", "mỏi", "bệnh", "trị liệu", "tư vấn riêng", "khó quá", "không tập được", "thoát vị", "đau gối", "lưng", "cổ", "vai", "tư thế", "lỗi sai", "tập đúng", "tập chuẩn", "xương khớp"]
    },
    "APP_THIEN_THO": {
        "name": "🧘 App Thiền & Hít Thở",
        "url": "https://yogaismylife.vn/thien-hoi-tho-chua-lanh/",
        "trigger": ["stress", "căng thẳng", "mất ngủ", "lo âu", "thở", "thiền", "thư giãn", "mệt mỏi", "áp lực", "ngủ ngon", "yên tĩnh"]
    }
}

# =====================================================
# 3. CSS GIAO DIỆN (PREMIUM UI)
# =====================================================
st.markdown("""
<style>
    [data-testid="stAppViewContainer"], .stApp, html, body { background-color: white !important; color: #31333F !important; }
    [data-testid="stToolbar"], header, footer, .stAppDeployButton {display: none !important;}
    
    /* INPUT CHAT */
    div[data-testid="stChatInput"] { 
        position: fixed !important; bottom: 20px !important; left: 10px !important; right: 10px !important; 
        z-index: 999999; background-color: white !important; border-radius: 25px !important; 
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1); padding: 5px !important; border: 1px solid #e0e0e0; 
    }
    textarea[data-testid="stChatInputTextArea"] { font-size: 16px !important; background-color: #f0f2f6 !important; border-radius: 20px !important; }

    /* CARD GIỚI HẠN (PREMIUM) */
    .limit-overlay {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(255, 255, 255, 0.9);
        z-index: 9999990;
        backdrop-filter: blur(5px);
    }
    .limit-card {
        position: relative;
        background: white;
        padding: 40px;
        border-radius: 25px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.15);
        border: 1px solid #e0f2f1;
        text-align: center;
        max-width: 500px;
        margin: 10vh auto; /* Cách top 10% màn hình */
        z-index: 9999999;
        animation: slideDown 0.5s ease-out;
    }
    @keyframes slideDown { from { transform: translateY(-20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    
    .limit-icon { font-size: 60px; margin-bottom: 15px; display: block; }
    .limit-title { font-size: 24px; font-weight: 800; color: #00796b; margin-bottom: 10px; }
    .limit-desc { font-size: 15px; color: #555; margin-bottom: 30px; line-height: 1.6; }
    
    /* Form Login trong Card */
    .login-box { text-align: left; background: #f8f9fa; padding: 20px; border-radius: 15px; margin-bottom: 20px; }
    div[data-testid="stForm"] { border: none !important; padding: 0 !important; }
    div[data-testid="stForm"] button { 
        width: 100%; border-radius: 50px !important; height: 50px !important; 
        background: linear-gradient(135deg, #009688 0%, #00796b 100%) !important;
        color: white !important; font-weight: bold !important; font-size: 16px !important; border: none !important;
        box-shadow: 0 4px 15px rgba(0, 150, 136, 0.3); transition: 0.3s;
    }
    div[data-testid="stForm"] button:hover { transform: scale(1.02); box-shadow: 0 6px 20px rgba(0, 150, 136, 0.4); }

    /* Nút Zalo */
    .zalo-link { text-decoration: none; display: block; margin-top: 15px; }
    .zalo-btn { 
        background: white; color: #0068ff; border: 2px solid #0068ff; 
        padding: 10px 20px; border-radius: 50px; font-weight: bold; font-size: 14px; 
        display: inline-flex; align-items: center; gap: 8px; transition: 0.3s;
    }
    .zalo-btn:hover { background: #0068ff; color: white; }

    /* THANH TRẠNG THÁI TRÊN CÙNG */
    .usage-bar-container { position: fixed; top: 0; left: 0; width: 100%; height: 5px; background-color: #f0f0f0; z-index: 1000000; }
    .usage-bar-fill { height: 100%; background: linear-gradient(90deg, #0f988b 0%, #14b8a6 100%); }
    .usage-text { position: fixed; top: 10px; right: 15px; background: rgba(255,255,255,0.9); padding: 4px 12px; border-radius: 20px; font-size: 11px; color: #0f988b !important; font-weight: bold; border: 1px solid #0f988b; z-index: 1000001; }

    /* HIỂN THỊ TIN NHẮN */
    .source-box { background-color: #f8f9fa; border-left: 4px solid #0f988b; padding: 12px; margin-top: 15px; border-radius: 0 8px 8px 0; font-size: 0.9em; }
    .solution-card { background: linear-gradient(135deg, #e0f2f1 0%, #b2dfdb 100%); border: 1px solid #009688; border-radius: 10px; padding: 12px; margin-top: 10px; display: flex; align-items: center; justify-content: space-between; }
    .solution-text { font-size: 14px; color: #004d40; font-weight: bold; }
    .solution-btn { background-color: #00796b; color: white !important; padding: 6px 15px; border-radius: 20px; text-decoration: none; font-size: 12px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 4. KẾT NỐI API & DRIVE (TỐI ƯU RAM)
# =====================================================
FILE_ID_DRIVE = "13z82kBBd8QwpCvUqGysD9DXI8Xurvtq9" 
URL_DRIVE = f'https://drive.google.com/uc?id={FILE_ID_DRIVE}'
OUTPUT_ZIP = "/tmp/brain_final.zip"
EXTRACT_PATH = "/tmp/brain_final"

try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Thiếu API KEY")
    st.stop()

@st.cache_resource
def load_brain():
    # 1. Tải file (Chỉ tải nếu chưa có folder giải nén)
    if not os.path.exists(EXTRACT_PATH):
        try:
            print("Dang tai file...")
            gdown.download(URL_DRIVE, OUTPUT_ZIP, quiet=False, fuzzy=True)
            print("Dang giai nen...")
            with zipfile.ZipFile(OUTPUT_ZIP, 'r') as zip_ref:
                zip_ref.extractall(EXTRACT_PATH)
            
            # XÓA ZIP NGAY ĐỂ GIẢM RAM
            if os.path.exists(OUTPUT_ZIP):
                os.remove(OUTPUT_ZIP)
            gc.collect() # Dọn rác bộ nhớ
            
        except Exception as e:
            if os.path.exists(EXTRACT_PATH):
                import shutil
                shutil.rmtree(EXTRACT_PATH)
            return None, None
    
    # 2. Tìm file não
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

    # 3. Load Model
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(vector_db_path, embeddings, allow_dangerous_deserialization=True)
        # Dùng model Flash để nhanh và nhẹ
        model = genai.GenerativeModel('gemini-flash-latest') 
        return db, model
    except:
        return None, None

db, model = load_brain()

# Nếu lỗi tải não
if db is None or model is None:
    st.warning("🧘‍♂️ Đang khởi động hệ thống... Vui lòng chờ 30s rồi tải lại trang (F5).")
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
# 5. QUẢN LÝ USER
# =====================================================
USAGE_DB_FILE = "/tmp/usage_history_db.json"
DAILY_LIMIT = 25
TRIAL_LIMIT = 5 # Giới hạn 5 câu hỏi cho khách

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

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""

user_key = st.session_state.username if st.session_state.authenticated else get_remote_ip()
today = str(datetime.date.today())
db_data = get_data()

if user_key not in db_data or db_data[user_key].get("date") != today:
    db_data[user_key] = {"date": today, "count": 0, "history": [{"role":"assistant","content":"Namaste! 🙏 Tôi là Trợ lý Yoga AI. Bác cần tư vấn gì hôm nay?"}]}
    save_data(db_data)

st.session_state.messages = db_data[user_key]["history"]
used = db_data[user_key]["count"]
limit = DAILY_LIMIT if st.session_state.authenticated else TRIAL_LIMIT
percent = min(100, int((used / limit) * 100))
st.markdown(f"""<div class="usage-bar-container"><div class="usage-bar-fill" style="width: {percent}%;"></div></div><div class="usage-text">⚡ Lượt dùng: {used}/{limit}</div>""", unsafe_allow_html=True)
can_chat = used < limit

# =====================================================
# 6. GIAO DIỆN CHÍNH
# =====================================================
if not st.session_state.authenticated:
    # Banner quảng cáo dưới cùng
    st.markdown(f"""<div style="position: fixed; bottom: 80px; left: 15px; right: 15px; background: #fff5f0; border: 1px solid #ffccbc; border-radius: 15px; padding: 10px 15px; z-index: 99999; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 15px rgba(255, 87, 34, 0.1);"><div style="display: flex; align-items: center; gap: 10px;"><div style="background: #ff7043; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center;"><span style="font-size: 16px;">🎁</span></div><div><div style="color: #bf360c !important; font-size: 13px; font-weight: bold;">Combo Thảm & Freeship!!</div><div style="color: #ff7043 !important; font-size: 11px;">Giảm ngay 30% hôm nay!</div></div></div><a href="https://yogaismylife.vn/cua-hang/" target="_blank" style="background: #ff7043; color: white !important; padding: 8px 15px; border-radius: 10px; text-decoration: none; font-weight: bold; font-size: 12px; box-shadow: 0 2px 5px rgba(255, 112, 67, 0.3);">Xem ngay</a></div>""", unsafe_allow_html=True)

# Hiển thị lịch sử chat
for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"], unsafe_allow_html=True)

# =====================================================
# 7. XỬ LÝ HẾT LƯỢT (GIAO DIỆN PREMIUM CARD)
# =====================================================
if not can_chat:
    # Ẩn thanh chat
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
    
    # Hiển thị Card + Form Đăng Nhập
    st.markdown("""<div class="limit-overlay"></div>""", unsafe_allow_html=True)
    
    # Mở container cột giữa
    _, col, _ = st.columns([1, 10, 1])
    with col:
        st.markdown("""
        <div class="limit-card">
            <span class="limit-icon">🧘‍♀️</span>
            <div class="limit-title">Đã đạt giới hạn hôm nay!</div>
            <div class="limit-desc">
                Bạn đã dùng hết lượt hỏi miễn phí.<br>
                Đăng nhập Member để mở khóa kho tri thức không giới hạn.
            </div>
            <div class="login-box">
                <div style="font-size:14px; font-weight:bold; color:#333; margin-bottom:10px;">🔐 Đăng nhập ngay:</div>
        """, unsafe_allow_html=True)
        
        # Form nằm TRONG Card
        with st.form("login_form_limit"):
            u = st.text_input("Tên đăng nhập", placeholder="Nhập username...", label_visibility="collapsed")
            p = st.text_input("Mật khẩu", type="password", placeholder="Nhập password...", label_visibility="collapsed")
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            submit = st.form_submit_button("ĐĂNG NHẬP")
            
            if submit:
                if (u=="admin" and p=="yoga888") or (st.secrets["passwords"].get(u)==p):
                    st.session_state.authenticated = True
                    st.session_state.username = u
                    st.rerun()
                else:
                    st.error("❌ Sai mật khẩu hoặc tên đăng nhập!")
        
        st.markdown("""
            </div>
            <a href="https://zalo.me/84963759566" target="_blank" class="zalo-link">
                <div class="zalo-btn">💬 Liên hệ Admin lấy tài khoản</div>
            </a>
        </div>
        """, unsafe_allow_html=True)
    
    st.stop()

# =====================================================
# 8. XỬ LÝ CHAT (LOGIC V9 - CHUẨN)
# =====================================================
def get_recommended_solutions(user_query):
    query_lower = user_query.lower()
    recommendations = []
    for key, data in YOGA_SOLUTIONS.items():
        if any(trigger in query_lower for trigger in data["trigger"]): recommendations.append(data)
    return recommendations[:2]

if prompt := st.chat_input("Hỏi tôi về Yoga..."):
    db_data[user_key]["count"] += 1
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        if db:
            # 1. Tìm kiếm rộng (k=80)
            docs = db.similarity_search(prompt, k=80)
            
            # 2. Chấm điểm từ khóa
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
                    if kw in title: score += 10
                
                item = (score, d)
                if dtype == 'science': science_pool.append(item)
                elif dtype == 'qa': qa_pool.append(item)
                else: blog_pool.append(item)
            
            # 3. Sắp xếp & Chọn lọc
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
                if url and len(str(url)) > 10: source_map[url] = {"title": title, "type": dtype}
            
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
            1. Tuyệt đối KHÔNG dùng Markdown Header lớn (#, ##). Dùng in đậm (**ABC**) nếu cần tiêu đề.
            2. KHÔNG viết hoa toàn bộ câu.
            3. Ngắn gọn, súc tích.
            CÂU HỎI: "{prompt}"
            """
            
            try:
                with st.spinner("🧘 Đang tra cứu..."):
                    response = model.generate_content(sys_prompt)
                    res_text = response.text
                
                full_html_content = res_text
                
                if solutions:
                    full_html_content += "<hr>"
                    for sol in solutions:
                        full_html_content += f"""<div class="solution-card"><div class="solution-text">{sol['name']}</div><a href="{sol['url']}" target="_blank" class="solution-btn">Sử dụng ngay 🚀</a></div>"""
                
                if source_map:
                    links_html = "<div class='source-box'><strong>📚 Nguồn tham khảo:</strong><div style='margin-top:8px'>"
                    sorted_urls = sorted(source_map.items(), key=lambda x: 0 if x[1]['type']=='science' else 1)
                    for url, info in sorted_urls:
                        tag_html = "<span class='tag-science'>KHOA HỌC</span>" if info['type']=='science' else "<span class='tag-blog'>BÀI VIẾT</span>"
                        links_html += f"<div style='margin-bottom:6px'>{tag_html} <a href='{url}' target='_blank' style='text-decoration:none; color:#0f988b; font-weight:500'>{info['title']}</a></div>"
                    links_html += "</div></div>"
                    full_html_content += links_html
                
                st.markdown(full_html_content, unsafe_allow_html=True)
                
                db_data[user_key]["history"].append({"role": "user", "content": prompt})
                db_data[user_key]["history"].append({"role": "assistant", "content": full_html_content})
                save_data(db_data)
                
            except Exception as e:
                st.error(f"Lỗi: {e}")

# (Nút đăng nhập dự phòng dưới cùng đã bỏ vì đã tích hợp vào Card)
