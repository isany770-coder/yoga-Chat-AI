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
# 2. CẤU HÌNH "HỆ SINH THÁI GIẢI PHÁP" CỦA BÁC
# =====================================================
YOGA_SOLUTIONS = { 
    "QUY_TRINH_8_BUOC": {
        "name": "🗺️ Quy trình 8 Bước Toàn Diện",
        "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/",
        "trigger": ["bắt đầu", "lộ trình", "người mới", "từ đầu", "cơ bản", "hướng dẫn", "bao lâu", "học yoga"]
    },
    "AI_COACH": {
        "name": "🤖 Gặp AI Coach 1:1 - Live",
        "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/",
        "trigger": ["đau", "chấn thương", "mỏi", "bệnh", "trị liệu", "tư vấn riêng", "khó quá", "không tập được"]
    },
    "APP_THIEN_THO": {
        "name": "🧘 App Thiền & Hít Thở (Giảm Stress)",
        "url": "https://yogaismylife.vn/thien-hoi-tho-chua-lanh/",  # <--- Thay link thật của bác vào
        "trigger": ["stress", "căng thẳng", "mất ngủ", "lo âu", "thở", "thiền", "thư giãn", "mệt mỏi", "áp lực", "ngủ ngon"]
    }
}

# =====================================================
# 3. CSS GIAO DIỆN (FULL ĐẸP)
# =====================================================
st.markdown("""
<style>
    /* Reset nền */
    [data-testid="stAppViewContainer"], .stApp, html, body {
        background-color: white !important;
        color: #31333F !important;
    }
    
    /* Ẩn Header/Footer thừa */
    [data-testid="stToolbar"], header, footer, .stAppDeployButton {display: none !important;}
    
    /* THANH CHAT INPUT NỔI */
    div[data-testid="stChatInput"] { 
        position: fixed !important; bottom: 20px !important; left: 10px !important; right: 10px !important; 
        z-index: 999999; background-color: white !important; border-radius: 25px !important; 
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1); padding: 5px !important; border: 1px solid #e0e0e0; 
    }
    textarea[data-testid="stChatInputTextArea"] {
        font-size: 16px !important; background-color: #f0f2f6 !important; border-radius: 20px !important;
    }

    /* FIX LỖI BÀN PHÍM MOBILE */
    @media (max-height: 500px) {
        div[data-testid="stChatInput"] { bottom: 0px !important; border-radius: 0 !important; }
        .ad-banner, .usage-bar-container, .usage-text { display: none !important; }
    }

    /* --- STYLE THẺ GIẢI PHÁP (SOLUTION CARD) --- */
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

    /* --- STYLE NGUỒN THAM KHẢO (PHÂN LOẠI) --- */
    .source-box { background-color: #f8f9fa; border-left: 4px solid #0f988b; padding: 12px; margin-top: 15px; border-radius: 0 8px 8px 0; font-size: 0.9em; }
    .tag-science { background-color: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: bold; margin-right: 6px; border: 1px solid #c7d2fe; }
    .tag-blog { background-color: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: bold; margin-right: 6px; border: 1px solid #bbf7d0; }
    .tag-qa { background-color: #fef9c3; color: #854d0e; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: bold; margin-right: 6px; border: 1px solid #fde047; }

    /* THANH TIẾN TRÌNH & USER */
    .main .block-container { padding-top: 3rem !important; padding-bottom: 250px !important; }
    div[data-testid="stChatMessage"] { background-color: #f8f9fa !important; border: 1px solid #eee; }
    div[data-testid="stChatMessage"][data-test-role="user"] { background-color: #e3f2fd !important; }
    .usage-bar-container { position: fixed; top: 0; left: 0; width: 100%; height: 5px; background-color: #f0f0f0; z-index: 1000000; }
    .usage-bar-fill { height: 100%; background: linear-gradient(90deg, #0f988b 0%, #14b8a6 100%); }
    .usage-text { position: fixed; top: 10px; right: 15px; background: rgba(255,255,255,0.9); padding: 4px 12px; border-radius: 20px; font-size: 11px; color: #0f988b !important; font-weight: bold; border: 1px solid #0f988b; z-index: 1000001; }
    
    /* LIMIT MODAL */
    .limit-modal { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); z-index: 2147483647 !important; display: flex; align-items: center; justify-content: center; flex-direction: column; }
    .limit-box { background: white; padding: 40px; border-radius: 25px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); text-align: center; max-width: 90%; width: 400px; border: 2px solid #0f988b; }
    .limit-btn { background: linear-gradient(135deg, #0f988b, #14b8a6); color: white !important; padding: 12px 35px; border-radius: 50px; text-decoration: none; font-weight: bold; display: inline-block; margin-top: 15px; }
    
    .zalo-btn { display: flex !important; align-items: center; justify-content: center; width: 100%; background-color: white; color: #0f988b !important; border: 1px solid #dcdfe3; border-radius: 8px; font-weight: 500; font-size: 14px; height: 45px !important; text-decoration: none !important; margin: 0 !important; }
    div[data-testid="stForm"] button { height: 45px !important; border-radius: 8px !important; font-weight: 500 !important; color: #31333F !important; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 4. KẾT NỐI API & DRIVE (QUAN TRỌNG)
# =====================================================
# 👉 THAY ID FILE VECTOR MỚI CỦA BÁC VÀO ĐÂY
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
            st.error(f"⚠️ Lỗi tải não: {e}")
            return None, None
    
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(EXTRACT_PATH, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest')
        return db, model
    except Exception as e:
        st.error(f"⚠️ Lỗi AI: {e}")
        return None, None

db, model = load_brain()

# Chống trắng trang
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
# 5. QUẢN LÝ DATABASE & USER
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
        "history": [{"role":"assistant","content":"Namaste! 🙏 Tôi là Trợ lý Yoga AI chuyên sâu. Bác cần tìm hiểu về kỹ thuật, bệnh lý hay lộ trình tập luyện?"}]
    }
    save_data(db_data)

st.session_state.messages = db_data[user_key]["history"]
used = db_data[user_key]["count"]
limit = DAILY_LIMIT if st.session_state.authenticated else TRIAL_LIMIT
percent = min(100, int((used / limit) * 100))

# Thanh tiến trình
st.markdown(f"""<div class="usage-bar-container"><div class="usage-bar-fill" style="width: {percent}%;"></div></div><div class="usage-text">⚡ Lượt dùng: {used}/{limit}</div>""", unsafe_allow_html=True)

can_chat = used < limit

# =====================================================
# 6. LOGIC GỢI Ý GIẢI PHÁP (RECOMMENDER ENGINE)
# =====================================================
def get_recommended_solutions(user_query):
    """Quét câu hỏi để tìm giải pháp phù hợp trong YOGA_SOLUTIONS"""
    query_lower = user_query.lower()
    recommendations = []
    
    for key, data in YOGA_SOLUTIONS.items():
        if any(trigger in query_lower for trigger in data["trigger"]):
            recommendations.append(data)
    
    return recommendations[:2] # Lấy tối đa 2 cái

# =====================================================
# 7. QUẢNG CÁO & ADMIN & MODAL
# =====================================================
# Quảng cáo
if not st.session_state.authenticated:
    st.markdown(f"""
    <div style="position: fixed; bottom: 80px; left: 15px; right: 15px; background: #fff5f0; border: 1px solid #ffccbc; border-radius: 15px; padding: 10px 15px; z-index: 99999; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 15px rgba(255, 87, 34, 0.1);">
        <div style="display: flex; align-items: center; gap: 10px;">
            <div style="background: #ff7043; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center;"><span style="font-size: 16px;">🎁</span></div>
            <div><div style="color: #bf360c !important; font-size: 13px; font-weight: bold;">Combo Thảm & Freeship!!</div><div style="color: #ff7043 !important; font-size: 11px;">Giảm ngay 30% hôm nay!</div></div>
        </div>
        <a href="https://yogaismylife.vn/cua-hang/" target="_blank" style="background: #ff7043; color: white !important; padding: 8px 15px; border-radius: 10px; text-decoration: none; font-weight: bold; font-size: 12px; box-shadow: 0 2px 5px rgba(255, 112, 67, 0.3);">Xem ngay</a>
    </div>
    """, unsafe_allow_html=True)

# Admin
if st.session_state.authenticated and st.session_state.username == "admin":
    st.info("🕵️ **CHẾ ĐỘ ADMIN: SOI LOG CHAT**")
    if st.button("🔄 Cập nhật Log"): st.rerun()
    # (Code hiển thị log giữ nguyên hoặc thêm vào nếu bác cần)

# Modal Hết lượt
if not can_chat:
    st.markdown(f"""<div class="limit-modal"><div class="limit-box"><div style="font-size:50px;margin-bottom:10px">🧘‍♀️</div><div style="font-size:20px;font-weight:bold;color:#0f988b">Đã đạt giới hạn tra cứu miễn phí!</div><p style="color:#555;margin:15px 0">Hệ thống nhận thấy bạn đã sử dụng hết lượt dùng thử.<br>Để tiếp tục tra cứu <b>Kho dữ liệu chuyên sâu</b> và nhận ưu đãi, mời bạn liên hệ Admin:</p><a href="https://zalo.me/84963759566" target="_blank" class="limit-btn">💬 Nhận mã kích hoạt qua Zalo</a></div></div>""", unsafe_allow_html=True)
    st.stop()

# =====================================================
# 8. XỬ LÝ CHAT (CỐT LÕI THÔNG MINH)
# =====================================================
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"], unsafe_allow_html=True)

if prompt := st.chat_input("Hỏi tôi về Yoga, tư thế, đau mỏi..."):
    # Lưu user chat
    db_data[user_key]["count"] += 1
    db_data[user_key]["history"].append({"role": "user", "content": prompt})
    save_data(db_data)
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if db:
            # 1. TÌM KIẾM SÂU HƠN (Lấy 8 kết quả để vớt được Science)
            docs = db.similarity_search(prompt, k=8)
            
            context_parts = []
            source_map = {}
            has_science = False
            
            for i, d in enumerate(docs):
                dtype = d.metadata.get('type', 'general')
                title = d.metadata.get('title', 'Tài liệu')
                url = d.metadata.get('url', '#')
                
                # Ưu tiên hiển thị Science lên đầu prompt
                label = ""
                if dtype == 'science': 
                    label = "🔥🔥 NGHIÊN CỨU KHOA HỌC (ƯU TIÊN DÙNG)"
                    has_science = True
                elif dtype == 'qa': label = "CHUYÊN GIA TƯ VẤN"
                else: label = "KIẾN THỨC BỔ TRỢ"
                
                context_parts.append(f"--- NGUỒN {i+1} [{label}] ---\nTiêu đề: {title}\nNội dung: {d.page_content}")
                
                if url != "#" and url is not None:
                    source_map[url] = {"title": title, "type": dtype}
            
            full_context = "\n\n".join(context_parts)
            
            # Gợi ý giải pháp (Giữ nguyên logic cũ)
            solutions = get_recommended_solutions(prompt)
            solution_context = ""
            if solutions:
                names = ", ".join([s["name"] for s in solutions])
                solution_context = f"\nLƯU Ý: Cuối câu trả lời, hãy khuyên dùng: {names}."

            # 2. PROMPT "ÉP" AI DÙNG SỐ LIỆU
            science_instruction = ""
            if has_science:
                science_instruction = "BẮT BUỘC: Bạn đã tìm thấy NGHIÊN CỨU KHOA HỌC. Hãy trích dẫn cụ thể: 'Theo nghiên cứu năm [Năm] của [Tác giả], kết quả cho thấy [Số liệu/Kết quả]...'. Đừng nói chung chung."

            sys_prompt = f"""
            Bạn là Chuyên gia Yoga Khoa học & Trị liệu.
            
            DỮ LIỆU THAM KHẢO:
            {full_context}
            {solution_context}

            YÊU CẦU TRẢ LỜI:
            1. **Ngắn gọn:** Trả lời súc tích, đi thẳng vào vấn đề. Tối đa 200 từ.
            2. **Bằng chứng:** {science_instruction}
            3. **Cấu trúc:** - **Kết luận:** (Ngắn gọn 1 câu).
               - **Khoa học nói gì:** (Dùng dữ liệu Nghiên cứu nếu có).
               - **Lời khuyên:** (Dựa trên dữ liệu Chuyên gia).
            4. **An toàn:** Nhắc lắng nghe cơ thể.

            CÂU HỎI: "{prompt}"
            """
            
            try:
                with st.spinner("🧘 Đang phân tích kỹ thuật và tìm tài liệu..."):
                    response = model.generate_content(sys_prompt)
                    res_text = response.text
                
                # --- RENDER KẾT QUẢ ---
                
                # 1. Hiển thị Lời giải của AI
                st.markdown(res_text, unsafe_allow_html=True)
                
                # 2. Hiển thị "THẺ GIẢI PHÁP" (Đồ chơi của bác) - Nổi bật
                if solutions:
                    for sol in solutions:
                        st.markdown(f"""
                        <div class="solution-card">
                            <div class="solution-text">{sol['name']}</div>
                            <a href="{sol['url']}" target="_blank" class="solution-btn">Sử dụng ngay 🚀</a>
                        </div>
                        """, unsafe_allow_html=True)

                # 3. Hiển thị Nguồn tham khảo (Uy tín)
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
                    
                    # Lưu vào lịch sử (Chỉ lưu text AI để tránh lỗi render HTML phức tạp khi load lại)
                    db_data[user_key]["history"].append({"role": "assistant", "content": res_text})
                    save_data(db_data)
                
            except Exception as error:
                st.error(f"Hệ thống đang quá tải: {error}")

# =====================================================
# 9. LOGIN FORM
# =====================================================
if not st.session_state.authenticated:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🔐 Đăng nhập / Lấy thêm lượt (Dành cho Member)", expanded=not can_chat):
        with st.form("login_form"):
            u = st.text_input("Tên đăng nhập", placeholder="Username")
            p = st.text_input("Mật khẩu", type="password", placeholder="Password")
            
            st.write("")
            c1, c2 = st.columns(2)
            with c1:
                submit = st.form_submit_button("Đăng nhập", use_container_width=True)
            with c2:
                st.markdown(f"""<div style="margin-top:0px;"><a href="https://zalo.me/84963759566" target="_blank" style="text-decoration:none;"><div class="zalo-btn">💬 Lấy TK Zalo</div></a></div>""", unsafe_allow_html=True)

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
                            st.error("Sai mật khẩu rồi bác ơi!")
                    except:
                        st.error("Chưa cấu hình mật khẩu user!")

    st.markdown("<div style='height: 250px; display: block;'></div>", unsafe_allow_html=True)
