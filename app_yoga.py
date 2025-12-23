import streamlit as st
import gdown
import zipfile
import os
import sqlite3
import datetime
import gc
import re
import time
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH TRANG & CSS (CHUẨN UI/UX MOBILE)
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* 1. Tối ưu khung nền */
    .stApp { background-color: #ffffff; }
    header[data-testid="stHeader"], footer {display: none;}
    .stDeployButton {display:none;}

    /* 2. Khung Chat Input (Hiện đại, bo tròn) */
    div[data-testid="stChatInput"] {
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    
    /* 3. Thanh Quảng Cáo (Banner) */
    .promo-banner {
        background: linear-gradient(90deg, #e0f2f1 0%, #b2dfdb 100%);
        padding: 10px 15px; margin-bottom: 20px; border-radius: 10px;
        display: flex; align-items: center; justify-content: space-between;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #80cbc4;
    }
    .promo-text { color: #00695c; font-weight: bold; font-size: 14px; }
    .promo-btn {
        background-color: #00796b; color: white !important; padding: 6px 12px;
        border-radius: 15px; text-decoration: none; font-weight: bold; font-size: 12px;
        white-space: nowrap;
    }

    /* 4. Màn hình Hết Hạn (Limit Screen - Chuẩn mẫu ảnh) */
    .limit-overlay {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(255, 255, 255, 0.95); z-index: 9999;
        display: flex; align-items: center; justify-content: center;
        flex-direction: column;
    }
    .limit-card {
        background: white; width: 90%; max-width: 400px;
        padding: 30px 20px; border-radius: 20px;
        text-align: center;
        border: 2px solid #26a69a; /* Viền xanh như ảnh */
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    .limit-icon { font-size: 50px; margin-bottom: 15px; display: block; }
    .limit-title { 
        font-size: 18px; font-weight: bold; color: #00897b; 
        margin-bottom: 10px; text-transform: uppercase;
    }
    .limit-desc { font-size: 14px; color: #555; line-height: 1.5; margin-bottom: 25px; }
    .zalo-btn-limit {
        display: block; width: 100%; padding: 12px;
        background-color: #009688; color: white !important;
        text-decoration: none; font-weight: bold; border-radius: 25px;
        margin-bottom: 15px; box-shadow: 0 4px 10px rgba(0, 150, 136, 0.3);
    }
    .login-link { color: #00796b; font-size: 13px; cursor: pointer; text-decoration: underline;}

    /* 5. Hiển thị nguồn (Citation) */
    .source-box { background-color: #f1f8e9; border: 1px solid #c5e1a5; border-radius: 10px; padding: 12px; margin-top: 10px; }
    .source-link { 
        display: block; color: #33691e; text-decoration: none; font-size: 14px; 
        margin-bottom: 6px; padding: 5px; border-radius: 5px; transition: 0.2s;
    }
    .source-link:hover { background-color: #dcedc8; }
    .tag { font-size: 10px; padding: 2px 6px; border-radius: 4px; margin-right: 8px; font-weight: bold; text-transform: uppercase; border: 1px solid; }
    
    .bottom-spacer { height: 100px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. LOGIC BACKEND (CẤU HÌNH & DATA)
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Chưa cấu hình secrets.toml")
    st.stop()

ZIP_PATH = "/tmp/brain_data.zip"
EXTRACT_PATH = "/tmp/brain_data_extracted"
DB_PATH = "user_usage.db"

@st.cache_resource
def load_brain_engine():
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
            if os.path.exists(ZIP_PATH): os.remove(ZIP_PATH)
        except: return None, None, "Lỗi tải dữ liệu"
    
    vector_path = None
    for root, _, files in os.walk(EXTRACT_PATH):
        for f in files:
            if f.endswith(".faiss"): vector_path = root; break
        if vector_path: break
    
    if not vector_path: return None, None, "Không tìm thấy vector"

    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(vector_path, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest')
        return db, model, "OK"
    except Exception as e: return None, None, str(e)

db, model, status = load_brain_engine()
if status != "OK": st.stop()

# =====================================================
# 3. QUẢN LÝ USER & GIỚI HẠN
# =====================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS usage (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))')
    conn.commit(); conn.close()
init_db()

def check_usage(user_id):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT count FROM usage WHERE user_id=? AND date=?", (user_id, today))
    res = c.fetchone(); conn.close()
    return res[0] if res else 0

def increment_usage(user_id):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO usage (user_id, date, count) VALUES (?, ?, 0)", (user_id, today))
    c.execute("UPDATE usage SET count = count + 1 WHERE user_id=? AND date=?", (user_id, today))
    conn.commit(); conn.close()

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Tôi là Trợ lý Yoga.\nBạn cần tìm bài tập hay tư vấn bệnh lý gì hôm nay?"}]

def get_user_id():
    if st.session_state.authenticated: return st.session_state.username
    try:
        from streamlit.web.server.websocket_headers import _get_headers
        return _get_headers().get("X-Forwarded-For", "guest").split(",")[0]
    except: return "guest"

user_id = get_user_id()
used = check_usage(user_id)
LIMIT = 30 if st.session_state.authenticated else 5
is_limit_reached = used >= LIMIT

# --- CHÈN THÊM ĐOẠN NÀY ĐỂ HIỆN THANH ĐẾM LƯỢT ---
percent = min(100, int((used / LIMIT) * 100))
st.markdown(f"""
<div style="position: fixed; top: 10px; right: 10px; z-index: 100000;">
    <div style="background: rgba(255,255,255,0.95); padding: 5px 12px; border-radius: 20px; 
                border: 1px solid #009688; box-shadow: 0 2px 5px rgba(0,0,0,0.1); 
                font-size: 12px; font-weight: bold; color: #00796b; display: flex; align-items: center; gap: 8px;">
        <span>⚡ {used}/{LIMIT}</span>
        <div style="width: 40px; height: 4px; background: #e0e0e0; border-radius: 2px;">
            <div style="width: {percent}%; height: 100%; background: linear-gradient(90deg, #009688, #80cbc4); border-radius: 2px;"></div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
# ------------------------------------------------

# =====================================================
# 4. GIAO DIỆN HẾT HẠN (V15 - SIÊU BỀN, KHÔNG VỠ)
# =====================================================
if is_limit_reached:
    # 1. Logic nút Đóng (X)
    if "hide_limit_modal" not in st.session_state:
        st.session_state.hide_limit_modal = False
    
    # CSS để ẩn thanh chat input
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)

    # Nếu chưa bấm đóng, hiện màn hình thông báo
    if not st.session_state.hide_limit_modal:
        
        # --- LAYOUT CĂN GIỮA (Chìa khóa để không bị vỡ) ---
        # Chia màn hình làm 3 cột: [Lề trái] - [Nội dung chính] - [Lề phải]
        # Trên mobile cột giữa sẽ tự to ra, trên PC nó sẽ gọn lại.
        col_left, col_center, col_right = st.columns([1, 4, 1]) 
        
        with col_center:
            # Tạo một cái hộp có viền bo tròn (Native Streamlit)
            with st.container(border=True):
                
                # Nút X đóng (Dùng cột nhỏ bên trong để đẩy sang phải)
                c1, c2 = st.columns([9, 1])
                with c2:
                    if st.button("✕", help="Đóng để xem lại lịch sử"):
                        st.session_state.hide_limit_modal = True
                        st.rerun()
                
                # --- PHẦN HÌNH ẢNH & TEXT (HTML) ---
                st.markdown("""
                    <div style="text-align: center;">
                        <div style="font-size: 60px; margin-bottom: 10px;">🧘‍♀️</div>
                        <h3 style="color: #00897b; margin: 0; font-weight: 800;">ĐÃ ĐẠT GIỚI HẠN!</h3>
                        <p style="color: #555; font-size: 15px; margin-top: 10px; line-height: 1.5;">
                            Hệ thống nhận thấy bạn đã dùng hết lượt thử.<br>
                            Để tra cứu <b>Kho dữ liệu 15 triệu từ</b> và nhận ưu đãi 
                            <b>Mua Thảm tặng Tài khoản Member</b>, mời bạn liên hệ Admin:
                        </p>
                        <a href="https://zalo.me/84963759566" target="_blank" 
                           style="display: inline-block; width: 100%; background-color: #009688; 
                                  color: white; padding: 12px 0; border-radius: 30px; 
                                  text-decoration: none; font-weight: bold; font-size: 16px;
                                  margin: 15px 0 25px 0; box-shadow: 0 4px 10px rgba(0,150,136,0.3);">
                           💬 Nhận mã kích hoạt qua Zalo
                        </a>
                        <div style="border-top: 1px dashed #ccc; margin: 10px 0;"></div>
                        <p style="font-size: 13px; color: #666; margin-top: 10px;">Hoặc đăng nhập thành viên:</p>
                    </div>
                """, unsafe_allow_html=True)

                # --- PHẦN FORM ĐĂNG NHẬP (Native Widget - Bấm bao nhạy) ---
                with st.form("login_form_limit"):
                    user_input = st.text_input("Tên đăng nhập")
                    pass_input = st.text_input("Mật khẩu", type="password")
                    
                    # Nút đăng nhập full width
                    btn_login = st.form_submit_button("Đăng Nhập Ngay", use_container_width=True)
                    
                    if btn_login:
                        if st.secrets["passwords"].get(user_input) == pass_input:
                            st.session_state.authenticated = True
                            st.session_state.username = user_input
                            st.session_state.hide_limit_modal = True
                            st.success("✅ Đăng nhập thành công!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Sai tên đăng nhập hoặc mật khẩu")

        # Dừng app để người dùng tập trung vào thông báo
        st.stop()
    
    else:
        # TRẠNG THÁI ĐÃ BẤM ĐÓNG (CHỈ ĐỌC)
        st.markdown("""
        <div style="background:#ffebee; color:#c62828; padding:12px; text-align:center; border-radius:12px; margin-bottom:15px; border:1px solid #ffcdd2; font-weight: 500;">
            🚫 Bạn đang xem ở chế độ chỉ đọc. <a href="https://zalo.me/84963759566" target="_blank" style="text-decoration: underline; color: #b71c1c;">Nâng cấp ngay</a> để tiếp tục hỏi.
        </div>
        """, unsafe_allow_html=True)
# =====================================================
# 5. GIAO DIỆN CHAT CHÍNH
# =====================================================

# Banner quảng cáo (Chỉ hiện khi chưa login)
if not st.session_state.authenticated:
    st.markdown("""
    <div class="promo-banner">
        <div class="promo-text">🎁 Combo Thảm tập + Freeship giảm 30% hôm nay!</div>
        <a href="https://yogaismylife.vn/cua-hang/" target="_blank" class="promo-btn">Xem Ngay 🚀</a>
    </div>
    """, unsafe_allow_html=True)

# Hiển thị tin nhắn
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"], unsafe_allow_html=True)

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

# Gợi ý giải pháp (Upsell)
YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "🗺️ Lộ trình 8 Bước", "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/", "key": ["đau","bệnh","trị liệu","phục hồi","lưng","đau lưng","gối","đau gối","cột sống","thoát vị","thoát vị đĩa đệm","tim mạch","tim","huyết áp","cao huyết áp","hạ huyết áp","tuần hoàn","mạch máu","đau ngực","suy nhược"]},
    "AI_COACH": {"name": "🤖 Gặp AI Coach Trị Liệu", "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/", "key": ["tập đúng","tập sai","lỗi sai","sai kỹ thuật","kỹ thuật","đúng kỹ thuật","chỉnh tư thế","canh chỉnh","căn chỉnh","hướng dẫn","định tuyến","quy trình","trình tự","bước thực hiện","chuẩn hóa","tối ưu","hiệu chỉnh","điều chỉnh","sửa lỗi","khắc phục"]},
    "THIEN": {"name": "🧘 App Thiền Chữa Lành", "url": "https://yogaismylife.vn/thien-hoi-tho-chua-lanh/", "key": ["stress","căng thẳng","áp lực","lo âu","bất an","mệt mỏi tinh thần","ngủ","giấc ngủ","mất ngủ","ngủ sâu","ngủ không ngon","nghỉ ngơi","thiền","thiền định","chánh niệm","tĩnh tâm","an trú","thở","hít thở","điều hòa hơi thở"]}
}

# =====================================================
# 6. XỬ LÝ CHAT (ĐÃ BỎ BỘ LỌC CHẶT)
# =====================================================
# --- HÀM MỚI: LỌC LỊCH SỬ CHAT (BỎ HTML ĐỂ AI KHÔNG BỊ LOẠN) ---
def get_clean_history():
    """Lấy 4 câu hội thoại gần nhất, lọc bỏ code HTML"""
    history_text = ""
    # Lấy 4 tin nhắn cuối cùng (bỏ qua tin nhắn chào hỏi đầu tiên nếu muốn)
    recent_msgs = st.session_state.messages[-4:] 
    for msg in recent_msgs:
        role = "User" if msg["role"] == "user" else "AI"
        # Xóa các thẻ HTML như <div>, <a>, <br>... chỉ giữ lại chữ
        clean_content = re.sub(r'<[^>]+>', '', msg["content"]) 
        history_text += f"{role}: {clean_content}\n"
    return history_text
# -------------------------------------------------------------
# =====================================================
# 6. XỬ LÝ CHAT (ĐÃ CĂN CHỈNH LỀ CHUẨN & FIX NÃO AI)
# =====================================================
if prompt := st.chat_input("Hỏi về thoát vị, đau lưng, bài tập..."):
    # 1. Hiện câu hỏi user
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(user_id)

    # 2. Xử lý AI
    with st.chat_message("assistant"):
        with st.spinner("Đang tra cứu kho dữ liệu..."):
            try:
                # --- A. TÌM KIẾM DỮ LIỆU ---
                docs = db.similarity_search(prompt, k=6) # Giảm k xuống 6 để bớt nhiễu
                
                context_text = ""
                source_map = {}
                for i, d in enumerate(docs):
                    doc_id = i + 1
                    url = d.metadata.get('url', '#')
                    title = d.metadata.get('title', 'Tài liệu Yoga')
                    type_ = d.metadata.get('type', 'blog')
                    source_map[doc_id] = {"url": url, "title": title, "type": type_}
                    context_text += f"\n[Nguồn {doc_id}]: {title}\nNội dung: {d.page_content}\n"

                # --- B. LẤY LỊCH SỬ (Chỉ lấy 2 câu gần nhất để tránh loạn) ---
                history_text = ""
                if len(st.session_state.messages) >= 3:
                    recent = st.session_state.messages[-3:-1] # Bỏ qua câu hỏi hiện tại, lấy 2 cái trước
                    for msg in recent:
                        clean_content = re.sub(r'<[^>]+>', '', msg["content"])
                        history_text += f"{msg['role']}: {clean_content}\n"

                # --- C. PROMPT (YÊU CẦU AI TẬP TRUNG VÀO CÂU HỎI MỚI) ---
                sys_prompt = f"""
                Bạn là chuyên gia Yoga Y Khoa (Medical Yoga).
                
                1. DỮ LIỆU TRA CỨU TỪ KHO (QUAN TRỌNG NHẤT):
                {context_text}
                
                2. CÂU HỎI CỦA NGƯỜI DÙNG: "{prompt}"
                
                3. LỊCH SỬ CHAT (Chỉ tham khảo nếu cần):
                {history_text}

                YÊU CẦU TRẢ LỜI:
                - ƯU TIÊN SỐ 1: Trả lời đúng trọng tâm "CÂU HỎI CỦA NGƯỜI DÙNG".
                - Kiểm tra "DỮ LIỆU TRA CỨU": Nếu dữ liệu khớp với câu hỏi, hãy dùng nó và ghi chú [Ref: X].
                - Nếu "DỮ LIỆU TRA CỨU" không liên quan (ví dụ: hỏi bệnh mà dữ liệu ra triết lý), HÃY BỎ QUA DỮ LIỆU ĐÓ và trả lời bằng kiến thức Yoga Y Khoa chuẩn xác của bạn.
                - Tuyệt đối không trả lời lung tung. Nếu là bệnh lý (huyết áp, thoát vị...), ưu tiên bài tập nhẹ nhàng, an toàn.
                - Tối đa 150 từ.
                - Nếu câu hỏi không có trong dữ liệu ví dụ hỏi về bóng đá, người mẫu... từ chối khéo, nếu cố tình 2 lần chặn, không được phép trả lời hiện thông báo nhẹ nhàng rằng tôi sẽ ko trả lời trong 5 phút
                """
                
                response = model.generate_content(sys_prompt)
                ai_resp = response.text
                
                # --- D. XỬ LÝ HIỂN THỊ ---
                # 1. Thay thế [Ref: X] thành icon
                clean_text = re.sub(r'\[Ref:?\s*(\d+)\]', ' 🔖', ai_resp)
                st.markdown(clean_text)
                
                # 2. Lọc và hiện Link (Chỉ hiện link nếu AI thực sự dùng)
                used_ids = [int(m) for m in re.findall(r'\[Ref:?\s*(\d+)\]', ai_resp) if int(m) in source_map]
                unique_used_ids = sorted(list(set(used_ids)))
                
                html_sources = ""
                if unique_used_ids:
                    html_sources += "<div class='source-box'><b>📚 Nguồn tham khảo:</b>"
                    seen_urls = set()
                    for uid in unique_used_ids:
                        info = source_map[uid]
                        if info['url'] != '#' and info['url'] not in seen_urls:
                            seen_urls.add(info['url'])
                            color = "#e3f2fd" if info['type']=='science' else "#e8f5e9"
                            lbl = "NGHIÊN CỨU" if info['type']=='science' else "BÀI VIẾT"
                            html_sources += f"""<a href="{info['url']}" target="_blank" class="source-link"><span class="tag" style="background:{color}">{lbl}</span>{info['title']}</a>"""
                    html_sources += "</div>"
                    st.markdown(html_sources, unsafe_allow_html=True)

                # 3. Upsell (Gợi ý giải pháp)
                upsell_html = ""
                recs = [v for k,v in YOGA_SOLUTIONS.items() if any(key in prompt.lower() for key in v['key'])]
                if recs:
                    upsell_html += "<div style='margin-top:15px'>"
                    for r in recs[:2]:
                         upsell_html += f"""<div style="background:#e0f2f1; padding:10px; border-radius:10px; margin-bottom:8px; border:1px solid #009688; display:flex; justify-content:space-between; align-items:center;"><span style="font-weight:bold; color:#004d40; font-size:14px">{r['name']}</span><a href="{r['url']}" target="_blank" style="background:#00796b; color:white; padding:5px 10px; border-radius:15px; text-decoration:none; font-size:12px; font-weight:bold;">Xem ngay</a></div>"""
                    upsell_html += "</div>"
                    st.markdown(upsell_html, unsafe_allow_html=True)
                
                # Lưu lịch sử
                full_save = clean_text
                if html_sources: full_save += "\n\n" + html_sources
                if upsell_html: full_save += "\n\n" + upsell_html
                st.session_state.messages.append({"role": "assistant", "content": full_save})

            except Exception as e:
                # Bắt lỗi êm ái, không văng code ra màn hình
                st.error("Hệ thống đang bận. Vui lòng thử lại câu hỏi khác.")
                print(f"Lỗi: {e}")
                st.error("Hệ thống đang bận. Vui lòng thử lại.")
