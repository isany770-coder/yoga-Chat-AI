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
        "trigger": ["đau", "chấn thương", "mỏi", "bệnh", "trị liệu", "tư vấn riêng", "khó quá", "không tập được", "thoát vị", "đau gối"]
    },
    "APP_THIEN_THO": {
        "name": "🧘 App Thiền & Hít Thở (Giảm Stress)",
        "url": "https://yogaismylife.vn/thien-hoi-tho-chua-lanh/",
        "trigger": ["stress", "căng thẳng", "mất ngủ", "lo âu", "thở", "thiền", "thư giãn", "mệt mỏi", "áp lực", "ngủ ngon", "yên tĩnh"]
    }
}

# =====================================================
# 3. CSS GIAO DIỆN (ĐÃ SỬA MODAL ĐỂ KHÔNG BỊ KẸT)
# =====================================================
st.markdown("""
<style>
    [data-testid="stAppViewContainer"], .stApp, html, body { background-color: white !important; color: #31333F !important; }
    [data-testid="stToolbar"], header, footer, .stAppDeployButton {display: none !important;}
    
    /* INPUT NỔI */
    div[data-testid="stChatInput"] { 
        position: fixed !important; bottom: 20px !important; left: 10px !important; right: 10px !important; 
        z-index: 999999; background-color: white !important; border-radius: 25px !important; 
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1); padding: 5px !important; border: 1px solid #e0e0e0; 
    }
    textarea[data-testid="stChatInputTextArea"] { font-size: 16px !important; background-color: #f0f2f6 !important; border-radius: 20px !important; }

    /* THẺ GIẢI PHÁP */
    .solution-card {
        background: linear-gradient(135deg, #e0f2f1 0%, #b2dfdb 100%);
        border: 1px solid #009688; border-radius: 10px; padding: 12px; margin-top: 10px;
        display: flex; align-items: center; justify-content: space-between;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1); animation: fadeIn 0.5s;
    }
    .solution-text { font-size: 14px; color: #004d40; font-weight: bold; }
    .solution-btn {
        background-color: #00796b; color: white !important; padding: 6px 15px;
        border-radius: 20px; text-decoration: none; font-size: 12px; font-weight: bold;
        transition: 0.3s; white-space: nowrap;
    }
    .solution-btn:hover { background-color: #004d40; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

    /* NGUỒN */
    .source-box { background-color: #f8f9fa; border-left: 4px solid #0f988b; padding: 12px; margin-top: 15px; border-radius: 0 8px 8px 0; font-size: 0.9em; }
    .tag-science { background-color: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: bold; margin-right: 6px; border: 1px solid #c7d2fe; }
    .tag-blog { background-color: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: bold; margin-right: 6px; border: 1px solid #bbf7d0; }
    .tag-qa { background-color: #fef9c3; color: #854d0e; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: bold; margin-right: 6px; border: 1px solid #fde047; }

    /* --- SỬA LẠI MODAL HẾT LƯỢT (KHÔNG DÙNG FIXED ĐỂ TRÁNH CHE FORM) --- */
    .limit-container {
        margin-top: 50px;
        padding: 40px;
        border-radius: 25px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        text-align: center;
        border: 2px solid #0f988b;
        background: white;
        margin-left: auto; margin-right: auto;
        max-width: 500px;
    }
    .limit-btn { background: linear-gradient(135deg, #0f988b, #14b8a6); color: white !important; padding: 12px 35px; border-radius: 50px; text-decoration: none; font-weight: bold; display: inline-block; margin-top: 15px; }
    
    .zalo-btn { display: flex !important; align-items: center; justify-content: center; width: 100%; background-color: white; color: #0f988b !important; border: 1px solid #dcdfe3; border-radius: 8px; font-weight: 500; font-size: 14px; height: 45px !important; text-decoration: none !important; margin: 0 !important; }
    div[data-testid="stForm"] button { height: 45px !important; border-radius: 8px !important; font-weight: 500 !important; color: #31333F !important; }
    
    .usage-bar-container { position: fixed; top: 0; left: 0; width: 100%; height: 5px; background-color: #f0f0f0; z-index: 1000000; }
    .usage-bar-fill { height: 100%; background: linear-gradient(90deg, #0f988b 0%, #14b8a6 100%); }
    .usage-text { position: fixed; top: 10px; right: 15px; background: rgba(255,255,255,0.9); padding: 4px 12px; border-radius: 20px; font-size: 11px; color: #0f988b !important; font-weight: bold; border: 1px solid #0f988b; z-index: 1000001; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 4. KẾT NỐI DỮ LIỆU
# =====================================================
# 👉 THAY ID FILE CỦA BÁC VÀO ĐÂY
FILE_ID_DRIVE = "https://drive.google.com/file/d/1RYvhzg0ZRLYV-zsMksUcIWHG2XO_l4Mi/view?usp=sharing" 
URL_DRIVE = f'https://drive.google.com/uc?id={FILE_ID_DRIVE}'
OUTPUT_ZIP = "/tmp/bo_nao_vector.zip"
EXTRACT_PATH = "/tmp/bo_nao_vector"

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
            gdown.download(URL_DRIVE, OUTPUT_ZIP, quiet=True)
            with zipfile.ZipFile(OUTPUT_ZIP, 'r') as zip_ref:
                zip_ref.extractall("/tmp/")
            if os.path.exists(OUTPUT_ZIP): os.remove(OUTPUT_ZIP)
        except Exception as e:
            return None, None
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(EXTRACT_PATH, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest')
        return db, model
    except Exception as e:
        return None, None

db, model = load_brain()

if db is None or model is None:
    st.warning("🧘‍♂️ Hệ thống đang khởi động, bác vui lòng vuốt xuống để tải lại (F5) nhé!")
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
# 5. QUẢN LÝ USER & DATA
# =====================================================
USAGE_DB_FILE = "/tmp/usage_history_db.json"
DAILY_LIMIT = 25
TRIAL_LIMIT = 10

def get_data():
    if not os.path.exists(USAGE_DB_FILE): return {}
    try:
        with open(USAGE_DB_FILE, "r") as f: return json.load(f)
    except: return {}

def save_data(data):
    with open(USAGE_DB_FILE, "w") as f: json.dump(data, f)

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""

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
# 6. HÀM LOGIN (Tách ra để dùng ở nhiều chỗ)
# =====================================================
def render_login_form():
    with st.form("login_form"):
        st.write("🔐 **Đăng nhập dành cho Member:**")
        u = st.text_input("Tên đăng nhập", placeholder="Username")
        p = st.text_input("Mật khẩu", type="password", placeholder="Password")
        
        c1, c2 = st.columns(2)
        with c1: submit = st.form_submit_button("Đăng nhập", use_container_width=True)
        with c2: st.markdown(f"""<a href="https://zalo.me/84963759566" target="_blank" style="text-decoration:none;"><div class="zalo-btn">💬 Lấy TK Zalo</div></a>""", unsafe_allow_html=True)

        if submit:
            if u == "admin" and p == "yoga888":
                st.session_state.authenticated = True
                st.session_state.username = u
                st.rerun()
            else:
                try:
                    if st.secrets["passwords"].get(u) == p:
                        st.session_state.authenticated = True
                        st.session_state.username = u
                        st.rerun()
                    else:
                        st.error("Sai mật khẩu rồi!")
                except:
                    st.error("Chưa cấu hình user!")

# =====================================================
# 7. LOGIC GỢI Ý
# =====================================================
def get_recommended_solutions(user_query):
    query_lower = user_query.lower()
    recommendations = []
    for key, data in YOGA_SOLUTIONS.items():
        if any(trigger in query_lower for trigger in data["trigger"]):
            recommendations.append(data)
    return recommendations[:2]

# =====================================================
# 8. XỬ LÝ GIAO DIỆN CHÍNH
# =====================================================

# A. QUẢNG CÁO
if not st.session_state.authenticated:
    st.markdown(f"""<div style="position: fixed; bottom: 80px; left: 15px; right: 15px; background: #fff5f0; border: 1px solid #ffccbc; border-radius: 15px; padding: 10px 15px; z-index: 99999; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 15px rgba(255, 87, 34, 0.1);"><div style="display: flex; align-items: center; gap: 10px;"><div style="background: #ff7043; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center;"><span style="font-size: 16px;">🎁</span></div><div><div style="color: #bf360c !important; font-size: 13px; font-weight: bold;">Combo Thảm & Freeship!!</div><div style="color: #ff7043 !important; font-size: 11px;">Giảm ngay 30% hôm nay!</div></div></div><a href="https://yogaismylife.vn/cua-hang/" target="_blank" style="background: #ff7043; color: white !important; padding: 8px 15px; border-radius: 10px; text-decoration: none; font-weight: bold; font-size: 12px; box-shadow: 0 2px 5px rgba(255, 112, 67, 0.3);">Xem ngay</a></div>""", unsafe_allow_html=True)

# B. HIỂN THỊ LỊCH SỬ CHAT
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"], unsafe_allow_html=True)

# C. XỬ LÝ KHI HẾT LƯỢT (FIXED: HIỆN FORM LOGIN NGAY TẠI ĐÂY)
if not can_chat:
    # Ẩn thanh chat input bằng CSS
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
    
    # Hiển thị thông báo & Form login
    st.markdown(f"""
    <div class="limit-container">
        <div style="font-size:50px;margin-bottom:10px">🧘‍♀️</div>
        <div style="font-size:22px;font-weight:bold;color:#0f988b;margin-bottom:10px">Đã đạt giới hạn tra cứu miễn phí!</div>
        <p style="color:#555;margin-bottom:20px">
            Hệ thống nhận thấy bạn đã dùng hết {TRIAL_LIMIT} lượt hỏi thử.<br>
            Vui lòng đăng nhập để tiếp tục.
        </p>
    </div>
    <br>
    """, unsafe_allow_html=True)
    
    # Gọi Form Login ra đây để bác đăng nhập
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        render_login_form()
        
    st.stop() # Dừng code tại đây, không chạy phần dưới

# D. XỬ LÝ CHAT (NẾU CÒN LƯỢT)
if prompt := st.chat_input("Hỏi tôi về Yoga..."):
    db_data[user_key]["count"] += 1
    db_data[user_key]["history"].append({"role": "user", "content": prompt})
    save_data(db_data)
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        if db:
            docs = db.similarity_search(prompt, k=10)
            
            # Logic lọc Science
            science_docs = [d for d in docs if d.metadata.get('type') == 'science']
            qa_docs = [d for d in docs if d.metadata.get('type') == 'qa']
            blog_docs = [d for d in docs if d.metadata.get('type') == 'blog']
            
            final_docs = science_docs + qa_docs + blog_docs
            final_docs = final_docs[:6] 

            context_parts = []
            source_map = {}
            has_science = False
            
            for i, d in enumerate(final_docs):
                dtype = d.metadata.get('type', 'general')
                title = d.metadata.get('title', 'Tài liệu')
                url = d.metadata.get('url', '#')
                label = ""
                if dtype == 'science': 
                    label = "🔥🔥 NGHIÊN CỨU KHOA HỌC (ƯU TIÊN)"
                    has_science = True
                elif dtype == 'qa': label = "CHUYÊN GIA TƯ VẤN"
                else: label = "KIẾN THỨC BỔ TRỢ"
                context_parts.append(f"--- NGUỒN {i+1} [{label}] ---\nTiêu đề: {title}\nNội dung: {d.page_content}")
                if url != "#" and url is not None:
                    source_map[url] = {"title": title, "type": dtype}
            
            full_context = "\n\n".join(context_parts)
            
            solutions = get_recommended_solutions(prompt)
            sol_context = ""
            if solutions:
                names = ", ".join([s["name"] for s in solutions])
                sol_context = f"\nQUAN TRỌNG: Cuối câu trả lời, hãy khuyên dùng công cụ: {names}."

            sci_instruct = "BẮT BUỘC: Bạn đã tìm thấy NGHIÊN CỨU KHOA HỌC. Hãy trích dẫn cụ thể: 'Theo nghiên cứu năm [Năm] của [Tác giả], kết quả cho thấy [Số liệu]...'" if has_science else "Trả lời dựa trên nguyên lý Yoga chung."

            sys_prompt = f"""
            Bạn là Chuyên gia Yoga Khoa học & Trị liệu.
            DỮ LIỆU: {full_context}
            {sol_context}
            YÊU CẦU:
            1. Ngắn gọn, súc tích.
            2. {sci_instruct}
            3. Cấu trúc: Kết luận -> Khoa học/Cơ chế -> Lời khuyên.
            4. An toàn là trên hết.
            CÂU HỎI: "{prompt}"
            """
            
            try:
                with st.spinner("🧘 Đang phân tích..."):
                    response = model.generate_content(sys_prompt)
                    res_text = response.text
                
                st.markdown(res_text, unsafe_allow_html=True)
                
                if solutions:
                    for sol in solutions:
                        st.markdown(f"""<div class="solution-card"><div class="solution-text">{sol['name']}</div><a href="{sol['url']}" target="_blank" class="solution-btn">Sử dụng ngay 🚀</a></div>""", unsafe_allow_html=True)

                if source_map:
                    links_html = "<div class='source-box'><strong>📚 Nguồn tham khảo uy tín:</strong><div style='margin-top:8px'>"
                    count = 0
                    for url, info in source_map.items():
                        if count >= 3: break
                        tag_html = ""
                        if info['type'] == 'science': tag_html = "<span class='tag-science'>KHOA HỌC</span>"
                        elif info['type'] == 'qa': tag_html = "<span class='tag-qa'>CHUYÊN GIA</span>"
                        else: tag_html = "<span class='tag-blog'>BÀI VIẾT</span>"
                        links_html += f"<div style='margin-bottom:6px'>{tag_html} <a href='{url}' target='_blank' style='text-decoration:none; color:#0f988b; font-weight:500'>{info['title']}</a></div>"
                        count += 1
                    links_html += "</div></div>"
                    st.markdown(links_html, unsafe_allow_html=True)
                    
                db_data[user_key]["history"].append({"role": "assistant", "content": res_text})
                save_data(db_data)
                
            except Exception as e:
                st.error(f"Lỗi: {e}")

# E. FORM LOGIN DỰ PHÒNG (DƯỚI CÙNG CHO AI MUỐN LOG SỚM)
if not st.session_state.authenticated and can_chat:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🔐 Đăng nhập Member (Để có thêm lượt)", expanded=False):
        render_login_form()
    st.markdown("<div style='height: 250px;'></div>", unsafe_allow_html=True)
