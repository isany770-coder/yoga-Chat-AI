import streamlit as st
import gdown
import zipfile
import os
import json
import datetime
import gc 
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH GIAO DIỆN (GIỮ NGUYÊN)
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

    /* SOURCE BOX ĐẸP - GỌN */
    .source-box { background-color: #fcfcfc; border: 1px solid #eee; padding: 12px; margin-top: 10px; border-radius: 8px; font-size: 0.85em; }
    .source-item { margin-bottom: 6px; display: flex; align-items: flex-start; line-height: 1.4; border-bottom: 1px dashed #f0f0f0; padding-bottom: 4px;}
    .source-item:last-child { border-bottom: none; }
    
    .tag-badge { font-size: 0.7em; font-weight: bold; padding: 1px 5px; border-radius: 3px; margin-right: 6px; white-space: nowrap; margin-top: 2px; }
    .tag-science { background-color: #e0e7ff; color: #3730a3; border: 1px solid #c7d2fe; }
    .tag-blog { background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
    
    .ads-banner {
        position: fixed; bottom: 85px; left: 15px; right: 15px; background: #fff5f0; 
        border: 1px solid #ffccbc; border-radius: 15px; padding: 10px 15px; z-index: 99990; 
        display: flex; align-items: center; justify-content: space-between; 
        box-shadow: 0 4px 15px rgba(255, 87, 34, 0.1);
    }
    
    div[data-testid="stForm"] { border: none !important; padding: 10px !important; background: #f8f9fa; border-radius: 10px; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. LOAD BRAIN (SIÊU NHẸ)
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
            if os.path.exists(OUTPUT_ZIP): os.remove(OUTPUT_ZIP)
            gdown.download(URL_DRIVE, OUTPUT_ZIP, quiet=False, fuzzy=True)
            with zipfile.ZipFile(OUTPUT_ZIP, 'r') as zip_ref:
                zip_ref.extractall(EXTRACT_PATH)
            os.remove(OUTPUT_ZIP) # Xóa ngay
        except:
            return None, None
    
    vector_db_path = None
    for root, dirs, files in os.walk(EXTRACT_PATH):
        for file in files:
            if file.endswith(".faiss"):
                vector_db_path = root; break
        if vector_db_path: break
    
    if not vector_db_path: return None, None

    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(vector_db_path, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest')
        gc.collect() # Dọn RAM ngay
        return db, model
    except:
        return None, None

db, model = load_brain()
if not db or not model:
    st.warning("🔄 Đang khởi động... Vui lòng F5 lại trang.")
    st.stop()

# =====================================================
# 3. USER & AUTH
# =====================================================
USAGE_DB = "/tmp/usage_db_v2.json"
DAILY_LIMIT = 25
TRIAL_LIMIT = 3

def load_data():
    if os.path.exists(USAGE_DB):
        with open(USAGE_DB, "r") as f: return json.load(f)
    return {}
def save_data(d):
    with open(USAGE_DB, "w") as f: json.dump(d, f)

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "show_login" not in st.session_state: st.session_state.show_login = False

def get_ip():
    try: return st.context.headers.get("X-Forwarded-For", "guest").split(",")[0]
    except: return "guest"

user_id = st.session_state.username if st.session_state.authenticated else get_ip()
today_str = str(datetime.date.today())
data = load_data()

if user_id not in data or data[user_id]["date"] != today_str:
    data[user_id] = {"date": today_str, "count": 0, "history": [{"role":"assistant","content":"Chào bác! 🙏 Bác đang đau mỏi ở đâu không?"}]}
    save_data(data)

st.session_state.messages = data[user_id]["history"]
used = data[user_id]["count"]
limit = DAILY_LIMIT if st.session_state.authenticated else TRIAL_LIMIT
can_chat = used < limit

# Thanh tiến trình
pct = min(100, int((used/limit)*100))
st.markdown(f"""
<div style="position:fixed;top:0;left:0;width:100%;height:3px;background:#eee;z-index:999999">
    <div style="height:100%;width:{pct}%;background:#0f988b;"></div>
</div>
<div style="position:fixed;top:5px;right:10px;background:rgba(255,255,255,0.9);padding:2px 8px;border-radius:12px;font-size:10px;color:#0f988b;border:1px solid #0f988b;z-index:999999;font-weight:bold">
    {used}/{limit}
</div>
""", unsafe_allow_html=True)

# =====================================================
# 4. GIAO DIỆN CHAT & XỬ LÝ
# =====================================================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

if not can_chat:
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="limit-container">
        <div style="font-size: 30px;">🛑</div>
        <div style="font-size: 18px; font-weight: bold; color: #00796b; margin-top:5px">Hết lượt hỏi hôm nay</div>
        <div style="color: #666; font-size: 13px; margin: 10px 0;">Đăng ký Member để tra cứu không giới hạn.</div>
        <a href="https://zalo.me/84963759566" target="_blank" class="zalo-btn">Nhận mã kích hoạt</a>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if not st.session_state.show_login:
            if st.button("🔐 Đăng nhập", use_container_width=True):
                st.session_state.show_login = True
                st.rerun()
        else:
            with st.form("login"):
                u = st.text_input("User")
                p = st.text_input("Pass", type="password")
                if st.form_submit_button("Login"):
                    if (u=="admin" and p=="yoga888") or (st.secrets["passwords"].get(u)==p):
                        st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
                    else: st.error("Sai mật khẩu")
    st.stop()

# ADS
if not st.session_state.authenticated:
    st.markdown("""
    <div class="ads-banner">
        <div style="display:flex;align-items:center;gap:10px">
            <span style="font-size:20px">🎁</span>
            <div><div style="color:#bf360c;font-size:13px;font-weight:bold">Combo Thảm Yoga</div>
            <div style="color:#ff7043;font-size:10px">Freeship hôm nay</div></div>
        </div>
        <a href="https://yogaismylife.vn/cua-hang/" target="_blank" style="background:#ff7043;color:white;padding:4px 10px;border-radius:6px;text-decoration:none;font-size:11px;font-weight:bold">Xem</a>
    </div>
    """, unsafe_allow_html=True)

# XỬ LÝ CHAT THÔNG MINH
if prompt := st.chat_input("Gõ câu hỏi ngắn gọn..."):
    data[user_id]["count"] += 1
    save_data(data)
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Đang lọc tài liệu chuẩn..."):
            # 1. TÌM KIẾM ÍT NHƯNG CHẤT (K=15)
            docs = db.similarity_search(prompt, k=15)
            
            # 2. BỘ LỌC "LÍNH GÁC TIÊU ĐỀ" (TITLE GUARD)
            # Tách từ khóa quan trọng (bỏ các từ nối vô nghĩa)
            stop_words = ["tôi", "bị", "có", "không", "làm", "sao", "như", "thế", "nào", "ở", "của", "là", "gì", "muốn", "hỏi"]
            keywords = [w.lower() for w in prompt.split() if w.lower() not in stop_words and len(w) > 2]
            
            scored_docs = []
            seen_urls = set()
            
            for d in docs:
                url = d.metadata.get('url', '')
                title = d.metadata.get('title', '').lower()
                dtype = d.metadata.get('type', 'general')
                
                # Bỏ trùng
                if len(url) > 5:
                    if url in seen_urls: continue
                    seen_urls.add(url)

                # --- THUẬT TOÁN CHẤM ĐIỂM ---
                score = 0
                
                # A. Điểm Tiêu Đề (QUAN TRỌNG NHẤT): Tiêu đề phải chứa từ khóa user hỏi
                matched_kw = sum(1 for kw in keywords if kw in title)
                if matched_kw > 0:
                    score += 50 * matched_kw # Thưởng cực lớn nếu khớp title
                else:
                    score -= 50 # Phạt nặng nếu tiêu đề không liên quan
                
                # B. Điểm uy tín
                if dtype == 'science': score += 40
                elif dtype == 'qa': score += 20
                
                # Chỉ lấy những bài có điểm dương (Tức là phải khớp Title hoặc là bài Science cực xịn)
                if score > 0:
                    scored_docs.append((score, d))
            
            # 3. LẤY TOP 3 TUYỆT ĐỐI
            scored_docs.sort(key=lambda x: x[0], reverse=True)
            top_docs = [x[1] for x in scored_docs[:3]] # Chỉ lấy 3 cái
            
            # Tạo Context
            context_text = ""
            sources_html = ""
            if top_docs:
                sources_html = "<div class='source-box'><div><b>📚 Tài liệu liên quan nhất:</b></div>"
                for d in top_docs:
                    dtype = d.metadata.get('type', 'general')
                    title = d.metadata.get('title', 'Tài liệu')
                    url = d.metadata.get('url', '#')
                    
                    # Thêm vào context cho AI
                    context_text += f"Bài viết: {title}\nNội dung: {d.page_content}\n---\n"
                    
                    # Hiển thị
                    badge = "NGHIÊN CỨU" if dtype == 'science' else "BÀI VIẾT"
                    b_cls = "tag-science" if dtype == 'science' else "tag-blog"
                    
                    # Cắt ngắn title nếu quá dài
                    display_title = (title[:50] + '..') if len(title) > 50 else title
                    sources_html += f"""
                    <div class="source-item">
                        <span class="tag-badge {b_cls}">{badge}</span>
                        <a href="{url}" target="_blank" style="color:#333;text-decoration:none;font-weight:600;">{display_title}</a>
                    </div>"""
                sources_html += "</div>"
            
            # Gọi AI
            final_sys = f"""Bạn là Trợ lý Yoga.
            DỮ LIỆU THAM KHẢO (Chỉ dùng thông tin này):
            {context_text}
            
            CÂU HỎI: "{prompt}"
            
            YÊU CẦU:
            - Trả lời thẳng vào vấn đề.
            - Nếu dữ liệu không có câu trả lời, hãy nói "Tôi chưa tìm thấy tài liệu chính xác về vấn đề này trong kho dữ liệu".
            - Giọng văn ân cần, ngắn gọn."""
            
            try:
                # Ép dọn rác lần nữa trước khi generate
                gc.collect()
                response = model.generate_content(final_sys)
                
                full_content = response.text
                if top_docs: full_content += f"\n{sources_html}"
                
                st.markdown(full_content, unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": full_content})
            except:
                st.error("Server đang bận. Vui lòng thử lại câu hỏi ngắn hơn.")
