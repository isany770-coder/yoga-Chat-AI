import streamlit as st
import gdown
import zipfile
import os
import json
import datetime
import gc  # <--- QUAN TRỌNG: Thư viện dọn rác bộ nhớ
import shutil
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH & CSS (ĐÃ FIX LỖI HIỂN THỊ)
# =====================================================
st.set_page_config(page_title="Yoga Assistant Pro", page_icon="🧘", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    [data-testid="stAppViewContainer"], .stApp, html, body { background-color: white !important; color: #31333F !important; }
    [data-testid="stToolbar"], header, footer {display: none !important;}
    
    div[data-testid="stChatInput"] { 
        position: fixed !important; bottom: 20px !important; left: 10px !important; right: 10px !important; 
        z-index: 999999; background-color: white !important; border-radius: 25px !important; 
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1); padding: 5px !important; border: 1px solid #e0e0e0; 
    }
    
    /* LIMIT BOX */
    .limit-container {
        margin-top: 30px; padding: 30px 20px; border-radius: 15px; text-align: center;
        border: 2px solid #e0f2f1; background: white; max-width: 500px; margin-left: auto; margin-right: auto;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    .zalo-btn { 
        display: flex; align-items: center; justify-content: center; width: 100%; 
        background-color: #0f988b; color: white !important; border-radius: 8px; 
        font-weight: bold; height: 45px; text-decoration: none; margin-top: 15px; 
    }

    /* SOURCE BOX FIX */
    .source-box { background-color: #fafafa; border: 1px solid #eee; padding: 15px; margin-top: 15px; border-radius: 10px; font-size: 0.9em; }
    .source-item { margin-bottom: 8px; display: flex; align-items: flex-start; line-height: 1.4; }
    .tag-badge { font-size: 0.7em; font-weight: bold; padding: 2px 6px; border-radius: 4px; margin-right: 8px; white-space: nowrap; margin-top: 3px; }
    .tag-science { background-color: #e0e7ff; color: #3730a3; border: 1px solid #c7d2fe; }
    .tag-blog { background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
    
    /* ADS BANNER */
    .ads-banner {
        position: fixed; bottom: 85px; left: 15px; right: 15px; background: #fff5f0; 
        border: 1px solid #ffccbc; border-radius: 15px; padding: 10px 15px; z-index: 99990; 
        display: flex; align-items: center; justify-content: space-between; 
        box-shadow: 0 4px 15px rgba(255, 87, 34, 0.1);
    }
    
    /* LOGIN FORM */
    div[data-testid="stForm"] { border: none !important; padding: 10px !important; background: #f8f9fa; border-radius: 10px; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. XỬ LÝ DỮ LIỆU & BỘ NHỚ (FIX TRÀN RAM)
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
    # 1. Tải và giải nén (Chỉ làm nếu chưa có folder)
    if not os.path.exists(EXTRACT_PATH):
        try:
            if os.path.exists(OUTPUT_ZIP): os.remove(OUTPUT_ZIP) # Xóa file zip cũ nếu lỗi
            gdown.download(URL_DRIVE, OUTPUT_ZIP, quiet=False, fuzzy=True)
            with zipfile.ZipFile(OUTPUT_ZIP, 'r') as zip_ref:
                zip_ref.extractall(EXTRACT_PATH)
            # DỌN RÁC 1: Xóa ngay file zip để nhẹ ổ cứng
            os.remove(OUTPUT_ZIP)
        except:
            return None, None
    
    # 2. Tìm file .faiss
    vector_db_path = None
    for root, dirs, files in os.walk(EXTRACT_PATH):
        for file in files:
            if file.endswith(".faiss"):
                vector_db_path = root
                break
        if vector_db_path: break
    
    if not vector_db_path: return None, None

    # 3. Load Model & FAISS
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(vector_db_path, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest')
        
        # DỌN RÁC 2: Ép Python xả RAM thừa ngay lập tức
        gc.collect() 
        return db, model
    except:
        return None, None

db, model = load_brain()
if not db or not model:
    st.warning("🔄 Đang khởi động não bộ (lần đầu mất khoảng 30s)... Vui lòng F5 lại trang.")
    st.stop()

# =====================================================
# 3. QUẢN LÝ USER (LOGIC MỚI)
# =====================================================
USAGE_DB = "/tmp/usage_db.json"
DAILY_LIMIT = 25
TRIAL_LIMIT = 10

def get_remote_ip():
    try:
        return st.context.headers.get("X-Forwarded-For", "guest").split(",")[0]
    except:
        return "guest"

def load_data():
    if os.path.exists(USAGE_DB):
        with open(USAGE_DB, "r") as f: return json.load(f)
    return {}

def save_data(data):
    with open(USAGE_DB, "w") as f: json.dump(data, f)

# Setup Session
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "show_login" not in st.session_state: st.session_state.show_login = False

user_id = st.session_state.username if st.session_state.authenticated else get_remote_ip()
today_str = str(datetime.date.today())
data = load_data()

if user_id not in data or data[user_id]["date"] != today_str:
    data[user_id] = {"date": today_str, "count": 0, "history": [{"role":"assistant","content":"Namaste! 🙏 Tôi là Yoga AI Coach. Bạn cần hỗ trợ gì?"}]}
    save_data(data)

st.session_state.messages = data[user_id]["history"]
used = data[user_id]["count"]
limit = DAILY_LIMIT if st.session_state.authenticated else TRIAL_LIMIT
can_chat = used < limit

# Thanh tiến trình
pct = min(100, int((used/limit)*100))
st.markdown(f"""
<div style="position:fixed;top:0;left:0;width:100%;height:4px;background:#eee;z-index:999999">
    <div style="height:100%;width:{pct}%;background:#0f988b;"></div>
</div>
<div style="position:fixed;top:10px;right:15px;background:rgba(255,255,255,0.9);padding:2px 10px;border-radius:15px;font-size:11px;color:#0f988b;border:1px solid #0f988b;z-index:999999;font-weight:bold">
    ⚡ {used}/{limit}
</div>
""", unsafe_allow_html=True)

# =====================================================
# 4. GIAO DIỆN CHÍNH & LOGIC CHAT
# =====================================================

# Hiển thị lịch sử chat (QUAN TRỌNG: unsafe_allow_html=True để render đẹp)
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

# MÀN HÌNH LIMIT (Khi hết hạn)
if not can_chat:
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="limit-container">
        <div style="font-size: 40px; margin-bottom: 10px">🧘‍♀️</div>
        <div style="font-size: 20px; font-weight: bold; color: #00796b">Hết lượt miễn phí hôm nay</div>
        <div style="color: #666; font-size: 14px; margin: 10px 0;">Vui lòng kết nối Zalo để nhận mã kích hoạt full tính năng.</div>
        <a href="https://zalo.me/84963759566" target="_blank" class="zalo-btn">💬 Nhận mã kích hoạt Zalo</a>
    </div>
    """, unsafe_allow_html=True)
    
    # Nút Toggle Login
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if not st.session_state.show_login:
            if st.button("🔐 Đăng nhập Member", use_container_width=True):
                st.session_state.show_login = True
                st.rerun()
        else:
            with st.form("login_frm"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Đăng nhập"):
                    if (u=="admin" and p=="yoga888") or (st.secrets["passwords"].get(u)==p):
                        st.session_state.authenticated = True
                        st.session_state.username = u
                        st.session_state.show_login = False
                        st.rerun()
                    else:
                        st.error("Sai mật khẩu")
            if st.button("Hủy"):
                st.session_state.show_login = False
                st.rerun()
    st.stop()

# QUẢNG CÁO (Chỉ hiện khi CÒN CHAT ĐƯỢC)
if not st.session_state.authenticated:
    st.markdown("""
    <div class="ads-banner">
        <div style="display:flex;align-items:center;gap:10px">
            <span style="font-size:20px">🎁</span>
            <div><div style="color:#bf360c;font-size:13px;font-weight:bold">Combo Thảm & Freeship</div>
            <div style="color:#ff7043;font-size:11px">Ưu đãi hôm nay</div></div>
        </div>
        <a href="https://yogaismylife.vn/cua-hang/" target="_blank" style="background:#ff7043;color:white;padding:5px 12px;border-radius:8px;text-decoration:none;font-size:12px;font-weight:bold">Xem</a>
    </div>
    """, unsafe_allow_html=True)

# XỬ LÝ CHAT
if prompt := st.chat_input("Hỏi tôi về Yoga..."):
    # Cập nhật DB
    data[user_id]["count"] += 1
    save_data(data)
    
    # Hiển thị user
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    # Xử lý AI
    with st.chat_message("assistant"):
        with st.spinner("Đang nghiên cứu..."):
            # 1. TÌM KIẾM (GIẢM K XUỐNG 40 ĐỂ TRÁNH TRÀN RAM)
            docs = db.similarity_search(prompt, k=40)
            
            # 2. THUẬT TOÁN RANKING (SCIENCE > BLOG)
            scored_docs = []
            seen_urls = set()
            
            for d in docs:
                url = d.metadata.get('url', '')
                dtype = d.metadata.get('type', 'general')
                title = d.metadata.get('title', 'Tài liệu')
                
                # Logic lọc trùng
                if len(url) > 5:
                    if url in seen_urls: continue
                    seen_urls.add(url)
                
                # Chấm điểm
                score = 0
                if dtype == 'science': score = 100  # Ưu tiên Science cực cao
                elif dtype == 'qa': score = 50
                
                # Cộng điểm từ khóa
                prompt_lower = prompt.lower()
                if any(w in title.lower() for w in prompt_lower.split() if len(w)>3):
                    score += 20
                
                scored_docs.append((score, d))
            
            # Sắp xếp theo điểm cao xuống thấp -> Lấy top 6
            scored_docs.sort(key=lambda x: x[0], reverse=True)
            top_docs = [x[1] for x in scored_docs[:6]]
            
            # 3. TẠO CONTEXT
            context_text = ""
            sources_html = ""
            if top_docs:
                sources_html = "<div class='source-box'><div><b>📚 Nguồn tham khảo chọn lọc:</b></div>"
                for d in top_docs:
                    dtype = d.metadata.get('type', 'general')
                    title = d.metadata.get('title', 'Tài liệu')
                    url = d.metadata.get('url', '#')
                    content = d.page_content
                    
                    # Context gửi AI
                    context_text += f"Nguồn ({dtype}): {title}\nNội dung: {content}\n---\n"
                    
                    # HTML hiển thị
                    badge = "KHOA HỌC" if dtype == 'science' else "BÀI VIẾT"
                    b_cls = "tag-science" if dtype == 'science' else "tag-blog"
                    display_title = (title[:55] + '...') if len(title) > 55 else title
                    
                    sources_html += f"""
                    <div class="source-item">
                        <span class="tag-badge {b_cls}">{badge}</span>
                        <a href="{url}" target="_blank" style="color:#333;text-decoration:none;font-weight:500">{display_title}</a>
                    </div>"""
                sources_html += "</div>"

            # 4. GỌI GEMINI
            final_prompt = f"""Bạn là Chuyên gia Yoga. Dựa vào thông tin sau:\n{context_text}\n
            Câu hỏi: {prompt}
            Yêu cầu: Trả lời ngắn gọn, tình cảm, có icon. KHÔNG tự bịa thông tin. Cuối lời khuyên hãy nhắc người dùng lắng nghe cơ thể."""
            
            try:
                response = model.generate_content(final_prompt)
                ai_text = response.text
                
                # Ghép AI Text + Source HTML
                full_content = ai_text + "\n\n" + sources_html
                
                st.markdown(full_content, unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": full_content})
                
            except Exception as e:
                st.error("Server quá tải, vui lòng thử lại sau 30s.")
