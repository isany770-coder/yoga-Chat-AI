import streamlit as st
import gdown
import zipfile
import os
import sqlite3
import datetime
import gc
import time
import re
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH TRANG & CSS
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS GIAO DIỆN (Đã tối ưu) ---
st.markdown("""
<style>
    /* Ẩn Header & Footer mặc định */
    header[data-testid="stHeader"] {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    .stApp { background-color: #ffffff; }

    /* Khung Chat Input */
    div[data-testid="stChatInput"] {
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        width: 90%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 30px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1); padding: 5px; border: 1px solid #e0e0e0;
    }
    
    /* Thanh Quảng Cáo (Top Banner) */
    .promo-banner {
        background: linear-gradient(90deg, #fff3e0 0%, #ffe0b2 100%);
        border-left: 5px solid #ff9800; padding: 12px 20px; margin-bottom: 25px;
        border-radius: 8px; display: flex; align-items: center; justify-content: space-between;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .promo-text { color: #e65100; font-weight: bold; font-size: 15px; }
    .promo-btn {
        background-color: #ff9800; color: white !important; padding: 8px 16px;
        border-radius: 20px; text-decoration: none; font-weight: bold; font-size: 13px;
        box-shadow: 0 2px 5px rgba(230, 81, 0, 0.3);
    }

    /* Thẻ Giải Pháp (Upsell Card) - Đã thêm lại */
    .solution-card {
        background: linear-gradient(135deg, #e0f2f1 0%, #b2dfdb 100%);
        border: 1px solid #009688; border-radius: 12px; padding: 15px; margin-top: 15px;
        display: flex; align-items: center; justify-content: space-between;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .sol-name { font-weight: bold; color: #00695c; font-size: 15px; }
    .sol-btn {
        background-color: #00796b; color: white !important; padding: 6px 15px;
        border-radius: 15px; text-decoration: none; font-size: 12px; font-weight: bold;
    }

    /* Hộp nguồn tham khảo */
    .source-box { background-color: #f9fbe7; border: 1px solid #dce775; border-radius: 12px; padding: 15px; margin-top: 15px; }
    .source-item {
        display: flex; align-items: center; background: white; padding: 8px 12px;
        border-radius: 8px; margin-bottom: 8px; border: 1px solid #f0f4c3; transition: transform 0.2s;
    }
    .source-item:hover { transform: translateX(5px); border-color: #c0ca33; }
    .tag-pill { font-size: 0.7em; padding: 3px 8px; border-radius: 12px; margin-right: 10px; font-weight: bold; white-space: nowrap; }
    
    .bottom-spacer { height: 120px; width: 100%; }
    .usage-badge {
        position: fixed; top: 10px; right: 10px; background: rgba(255,255,255,0.95);
        padding: 4px 12px; border-radius: 15px; font-size: 12px; color: #00796b; font-weight: bold;
        border: 1px solid #b2dfdb; z-index: 10000; box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. HỆ SINH THÁI GIẢI PHÁP (ĐÃ KHÔI PHỤC)
# =====================================================
YOGA_SOLUTIONS = {
    "QUY_TRINH_8_BUOC": {
        "name": "🗺️ Lộ trình 8 Bước Toàn Diện cho người mới",
        "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/",
        "trigger": ["bắt đầu", "lộ trình", "người mới", "từ đầu", "cơ bản", "hướng dẫn", "bao lâu", "học yoga", "nhập môn"]
    },
    "AI_COACH": {
        "name": "🤖 Gặp AI Coach 1:1 (Chỉnh sửa tư thế & Trị liệu)",
        "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/",
        "trigger": ["đau", "chấn thương", "mỏi", "bệnh", "trị liệu", "tư vấn riêng", "khó quá", "không tập được", "thoát vị", "gối", "lưng", "cổ", "vai"]
    },
    "APP_THIEN_THO": {
        "name": "🧘 App Thiền & Hít Thở Chữa Lành",
        "url": "https://yogaismylife.vn/thien-hoi-tho-chua-lanh/",
        "trigger": ["stress", "căng thẳng", "mất ngủ", "lo âu", "thở", "thiền", "thư giãn", "mệt", "áp lực", "ngủ ngon"]
    }
}

def get_recommended_solutions(user_query):
    """Tìm giải pháp phù hợp dựa trên từ khóa"""
    query_lower = user_query.lower()
    recommendations = []
    for key, data in YOGA_SOLUTIONS.items():
        if any(trigger in query_lower for trigger in data["trigger"]):
            recommendations.append(data)
    return recommendations[:2] # Tối đa 2 gợi ý

# =====================================================
# 3. BACKEND & DATABASE
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Lỗi: Chưa cấu hình secrets.toml")
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
            with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref: zip_ref.extractall(EXTRACT_PATH)
            if os.path.exists(ZIP_PATH): os.remove(ZIP_PATH)
            gc.collect()
        except: return None, None, "Lỗi tải dữ liệu"

    vector_path = None
    for root, dirs, files in os.walk(EXTRACT_PATH):
        for file in files:
            if file.endswith(".faiss"):
                vector_path = root; break
        if vector_path: break
    
    if not vector_path: return None, None, "Không tìm thấy file vector"

    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        vector_db = FAISS.load_local(vector_path, embeddings, allow_dangerous_deserialization=True)
        chat_model = genai.GenerativeModel('gemini-flash-latest')
        return vector_db, chat_model, "OK"
    except Exception as e: return None, None, f"Lỗi AI: {str(e)}"

db, model, status = load_brain_engine()
if status != "OK": st.stop()

# --- DATABASE USER ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usage (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))''')
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
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Tôi là Trợ lý Yoga Y Khoa.\nTôi có thể giúp gì cho sức khỏe của bạn hôm nay?"}]

def get_user_key():
    if st.session_state.authenticated: return st.session_state.username
    try:
        from streamlit.web.server.websocket_headers import _get_headers
        return _get_headers().get("X-Forwarded-For", "guest").split(",")[0]
    except: return "guest"

user_id = get_user_key()
used_count = check_usage(user_id)
LIMIT = 30 if st.session_state.authenticated else 5
can_chat = used_count < LIMIT

st.markdown(f"""<div class="usage-badge">⚡ {used_count}/{LIMIT} lượt</div>""", unsafe_allow_html=True)

# =====================================================
# 4. GIAO DIỆN CHÍNH
# =====================================================
if not st.session_state.authenticated:
    st.markdown("""
    <div class="promo-banner">
        <div class="promo-text">🎁 Combo Thảm tập + Gạch Yoga giảm 30% hôm nay!</div>
        <a href="https://yogaismylife.vn/cua-hang/" target="_blank" class="promo-btn">Xem Ngay 🚀</a>
    </div>
    """, unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"], unsafe_allow_html=True)

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

if not can_chat:
    st.markdown("""<div style="text-align:center; padding:20px; border:2px dashed #ff9800; background:#fff8e1; border-radius:10px;">🚫 Hết lượt dùng thử. Vui lòng đăng nhập!</div>""", unsafe_allow_html=True)
    with st.form("login"):
        u = st.text_input("Username"); p = st.text_input("Password", type="password")
        if st.form_submit_button("Đăng Nhập"):
            if st.secrets["passwords"].get(u) == p:
                st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
            else: st.error("Sai mật khẩu")
    st.stop()

# =====================================================
# 5. XỬ LÝ CHAT (FULL LOGIC)
# =====================================================
if prompt := st.chat_input("Hỏi về bệnh lý, nghiên cứu, bài tập..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(user_id)

    with st.chat_message("assistant"):
        with st.spinner("🧘 Đang tra cứu tài liệu Y Khoa..."):
            try:
                # 1. Tìm kiếm & Lọc
                docs_and_scores = db.similarity_search_with_score(prompt, k=10)
                qualified_docs = [d for d, s in docs_and_scores if s < 1.0] # Ngưỡng lọc
                
                context_text = ""
                source_map = {}
                
                if not qualified_docs:
                    ai_response = "Xin lỗi, dữ liệu hiện tại chưa có nghiên cứu cụ thể về vấn đề này."
                    used_sources = set()
                else:
                    for i, d in enumerate(qualified_docs):
                        doc_id = i + 1
                        url = d.metadata.get('url', '#')
                        title = d.metadata.get('title', 'Tài liệu')
                        type_ = d.metadata.get('type', 'blog')
                        source_map[doc_id] = {"url": url, "title": title, "type": type_}
                        context_text += f"\n[Tài liệu {doc_id}]: {title}\nNội dung: {d.page_content}\n"

                    sys_prompt = f"""
                    Bạn là Trợ lý Yoga Y Khoa (Evidence-Based). Dựa vào [Tài liệu] dưới đây để trả lời.
                    QUY TẮC:
                    1. Trả lời ngắn gọn, súc tích.
                    2. Mọi ý đưa ra PHẢI có dẫn chứng [Ref: X] (X là số tài liệu).
                    3. Không bịa kiến thức ngoài tài liệu.
                    
                    TÀI LIỆU:
                    {context_text}
                    CÂU HỎI: "{prompt}"
                    """
                    response = model.generate_content(sys_prompt)
                    ai_response = response.text
                    
                    used_sources = set()
                    for m in re.findall(r'\[Ref: (\d+)\]', ai_response):
                        if int(m) in source_map: used_sources.add(int(m))

                # 2. Xử lý hiển thị Text
                clean_text = re.sub(r'\[Ref: \d+\]', ' 🔖', ai_response)
                st.markdown(clean_text)
                full_content_to_save = clean_text

                # 3. Hiển thị Link Nguồn (Citations)
                if used_sources:
                    html_sources = "<div class='source-box'><div style='font-weight:bold; color:#827717; margin-bottom:10px'>📚 Tài liệu kiểm chứng:</div>"
                    seen_urls = set()
                    for doc_id in sorted(list(used_sources)):
                        info = source_map[doc_id]
                        url = info['url']
                        if url != '#' and url in seen_urls: continue
                        if url != '#': seen_urls.add(url)
                            
                        label = "NGHIÊN CỨU" if info['type']=='science' else "BÀI VIẾT"
                        color = "#e1f5fe" if info['type']=='science' else "#e8f5e9"
                        text_col = "#0277bd" if info['type']=='science' else "#2e7d32"
                        
                        if len(str(url)) > 5:
                            html_sources += f"""<a href="{url}" target="_blank" style="text-decoration:none;"><div class="source-item"><span class="tag-pill" style="background:{color}; color:{text_col}">{label}</span><span style="color:#333; font-weight:500;">{info['title']}</span></div></a>"""
                        else:
                            html_sources += f"""<div class="source-item" style="cursor: default;"><span class="tag-pill" style="background:#eeeeee; color:#616161">Nguồn</span><span style="color:#616161;">{info['title']}</span></div>"""
                    html_sources += "</div>"
                    st.markdown(html_sources, unsafe_allow_html=True)
                    full_content_to_save += "\n\n" + html_sources

                # 4. Gợi ý Giải Pháp (Upsell) - MỚI THÊM LẠI
                solutions = get_recommended_solutions(prompt)
                if solutions:
                    st.markdown("---")
                    html_sols = ""
                    for sol in solutions:
                        html_sols += f"""<div class="solution-card"><div class="sol-name">{sol['name']}</div><a href="{sol['url']}" target="_blank" class="sol-btn">Xem ngay ➔</a></div>"""
                    st.markdown(html_sols, unsafe_allow_html=True)
                    full_content_to_save += "\n\n" + html_sols

                # Lưu history
                st.session_state.messages.append({"role": "assistant", "content": full_content_to_save})
                st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

            except Exception as e: st.error("⚠️ Hệ thống đang bận. Vui lòng thử lại.")
