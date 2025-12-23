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
# 1. CẤU HÌNH & CSS (ĐÃ CHỈNH Z-INDEX CHO BANNER)
# =====================================================
st.set_page_config(page_title="Yoga Assistant Pro", page_icon="🧘", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    [data-testid="stAppViewContainer"], .stApp, html, body { background-color: white !important; color: #31333F !important; }
    [data-testid="stToolbar"], header, footer {display: none !important;}
    
    /* INPUT CHAT FIX CỨNG DƯỚI ĐÁY */
    div[data-testid="stChatInput"] { 
        position: fixed !important; bottom: 20px !important; left: 10px !important; right: 10px !important; 
        z-index: 999999; background-color: white !important; border-radius: 25px !important; 
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1); padding: 5px !important; border: 1px solid #e0e0e0; 
    }
    
    /* LIMIT BOX - THÔNG BÁO HẾT HẠN */
    .limit-container {
        margin-top: 50px; padding: 30px 20px; border-radius: 15px; text-align: center;
        border: 2px solid #e0f2f1; background: white; max-width: 500px; margin-left: auto; margin-right: auto;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    .zalo-btn { 
        display: flex; align-items: center; justify-content: center; width: 100%; 
        background-color: #0f988b; color: white !important; border-radius: 8px; 
        font-weight: bold; height: 45px; text-decoration: none; margin-top: 15px; 
    }

    /* SOURCE BOX - TRÍCH DẪN */
    .source-box { background-color: #f8f9fa; border: 1px solid #e9ecef; padding: 12px; margin-top: 10px; border-radius: 8px; }
    .source-item { margin-bottom: 8px; display: flex; align-items: flex-start; line-height: 1.4; border-bottom: 1px dashed #eee; padding-bottom: 5px; }
    .source-item:last-child { border-bottom: none; }
    
    .tag-badge { font-size: 0.65em; font-weight: bold; padding: 2px 6px; border-radius: 4px; margin-right: 8px; white-space: nowrap; margin-top: 2px; }
    .tag-science { background-color: #e0e7ff; color: #3730a3; border: 1px solid #c7d2fe; }
    .tag-blog { background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
    
    /* ADS BANNER - LUÔN NỔI LÊN TRÊN */
    .ads-banner {
        position: fixed; bottom: 90px; left: 15px; right: 15px; background: #fff5f0; 
        border: 1px solid #ffccbc; border-radius: 12px; padding: 8px 15px; z-index: 90000; 
        display: flex; align-items: center; justify-content: space-between; 
        box-shadow: 0 4px 15px rgba(255, 87, 34, 0.1);
    }
    
    div[data-testid="stForm"] { border: none !important; padding: 10px !important; background: #f8f9fa; border-radius: 10px; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. XỬ LÝ SERVER & NÃO BỘ
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
    # 1. Download & Unzip (Nếu chưa có)
    if not os.path.exists(EXTRACT_PATH):
        try:
            if os.path.exists(OUTPUT_ZIP): os.remove(OUTPUT_ZIP)
            gdown.download(URL_DRIVE, OUTPUT_ZIP, quiet=False, fuzzy=True)
            with zipfile.ZipFile(OUTPUT_ZIP, 'r') as zip_ref:
                zip_ref.extractall(EXTRACT_PATH)
            os.remove(OUTPUT_ZIP) # Xóa file zip ngay để nhẹ máy
        except:
            return None, None
    
    # 2. Tìm file vector
    vector_db_path = None
    for root, dirs, files in os.walk(EXTRACT_PATH):
        for file in files:
            if file.endswith(".faiss"):
                vector_db_path = root; break
        if vector_db_path: break
    
    if not vector_db_path: return None, None

    # 3. Load Model
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(vector_db_path, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest')
        gc.collect() # Dọn RAM ngay lập tức
        return db, model
    except:
        return None, None

db, model = load_brain()

# =====================================================
# 3. LOGIC USER & SESSION
# =====================================================
USAGE_DB = "/tmp/usage_db_final.json"
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
    data[user_id] = {"date": today_str, "count": 0, "history": [{"role":"assistant","content":"Chào bác! 🙏 Bác cần hỗ trợ vấn đề sức khỏe nào hôm nay?"}]}
    save_data(data)

st.session_state.messages = data[user_id]["history"]
used = data[user_id]["count"]
limit = DAILY_LIMIT if st.session_state.authenticated else TRIAL_LIMIT
can_chat = used < limit

# Thanh usage bar
pct = min(100, int((used/limit)*100))
st.markdown(f"""
<div style="position:fixed;top:0;left:0;width:100%;height:3px;background:#eee;z-index:999999">
    <div style="height:100%;width:{pct}%;background:#0f988b;"></div>
</div>
""", unsafe_allow_html=True)

# =====================================================
# 4. HIỂN THỊ BANNER QUẢNG CÁO (ĐƯA LÊN ĐẦU)
# =====================================================
# Logic: Chỉ hiện khi chưa đăng nhập VÀ còn lượt chat
if not st.session_state.authenticated and can_chat:
    st.markdown("""
    <div class="ads-banner">
        <div style="display:flex;align-items:center;gap:10px">
            <span style="font-size:20px">🎁</span>
            <div><div style="color:#bf360c;font-size:13px;font-weight:bold">Combo Thảm & Freeship</div>
            <div style="color:#ff7043;font-size:10px">Ưu đãi 30% hôm nay</div></div>
        </div>
        <a href="https://yogaismylife.vn/cua-hang/" target="_blank" style="background:#ff7043;color:white;padding:5px 12px;border-radius:8px;text-decoration:none;font-size:11px;font-weight:bold">Xem</a>
    </div>
    """, unsafe_allow_html=True)

# =====================================================
# 5. RENDER LỊCH SỬ CHAT
# =====================================================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

# =====================================================
# 6. KIỂM TRA LIMIT & LOGIN
# =====================================================
if not can_chat:
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="limit-container">
        <div style="font-size: 30px;">🛑</div>
        <div style="font-size: 18px; font-weight: bold; color: #00796b; margin-top:5px">Đã hết lượt miễn phí</div>
        <div style="color: #666; font-size: 13px; margin: 10px 0;">Vui lòng đăng ký Member để tra cứu không giới hạn.</div>
        <a href="https://zalo.me/84963759566" target="_blank" class="zalo-btn">Nhận mã kích hoạt Zalo</a>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if not st.session_state.show_login:
            if st.button("🔐 Đăng nhập Member", use_container_width=True):
                st.session_state.show_login = True
                st.rerun()
        else:
            with st.form("login"):
                u = st.text_input("User")
                p = st.text_input("Pass", type="password")
                if st.form_submit_button("Đăng nhập ngay"):
                    if (u=="admin" and p=="yoga888") or (st.secrets["passwords"].get(u)==p):
                        st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
                    else: st.error("Sai mật khẩu")
    st.stop() # Dừng code tại đây nếu hết hạn

# =====================================================
# 7. XỬ LÝ CHAT (LOGIC TÁCH HTML KHỎI MARKDOWN)
# =====================================================
if prompt := st.chat_input("Gõ câu hỏi ngắn gọn..."):
    # Cập nhật số lượt
    data[user_id]["count"] += 1
    save_data(data)
    
    # Hiện câu hỏi user
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        if not db or not model:
            st.warning("Server đang khởi động, vui lòng đợi 5s và thử lại.")
        else:
            with st.spinner("Đang tìm tài liệu chuẩn..."):
                # 1. TÌM KIẾM (K=20 cho nhẹ)
                docs = db.similarity_search(prompt, k=20)
                
                # 2. LỌC TITLE GUARD (Bắt buộc tiêu đề phải chứa từ khóa)
                stop_words = ["tôi", "bị", "có", "không", "làm", "sao", "ở", "là", "gì", "muốn", "hỏi", "đau"]
                # Lấy từ khóa > 2 ký tự và không nằm trong stop_words
                keywords = [w.lower() for w in prompt.split() if w.lower() not in stop_words and len(w) > 2]
                
                valid_docs = []
                seen_urls = set()
                
                for d in docs:
                    url = d.metadata.get('url', '')
                    title = d.metadata.get('title', '').lower()
                    
                    if len(url) > 5:
                        if url in seen_urls: continue
                        seen_urls.add(url)
                    
                    # Logic chấm điểm
                    score = 0
                    # Cộng 100 điểm cho mỗi từ khóa khớp trong Title
                    matches = sum(1 for kw in keywords if kw in title)
                    if matches > 0:
                        score += (matches * 100)
                        valid_docs.append((score, d))
                
                # Lấy top 3 bài điểm cao nhất
                valid_docs.sort(key=lambda x: x[0], reverse=True)
                top_docs = [x[1] for x in valid_docs[:3]]
                
                # 3. CHUẨN BỊ NỘI DUNG
                context_text = ""
                sources_html = "" # Biến chứa HTML riêng biệt
                
                if top_docs:
                    sources_html = "<div class='source-box'><div><b>📚 Tài liệu tham khảo:</b></div>"
                    for d in top_docs:
                        dtype = d.metadata.get('type', 'general')
                        title = d.metadata.get('title', 'Tài liệu')
                        url = d.metadata.get('url', '#')
                        
                        context_text += f"Tiêu đề: {title}\nNội dung: {d.page_content}\n---\n"
                        
                        # Tạo HTML badge
                        b_cls = "tag-science" if dtype == 'science' else "tag-blog"
                        b_text = "NGHIÊN CỨU" if dtype == 'science' else "BÀI VIẾT"
                        d_title = (title[:45] + '..') if len(title) > 45 else title
                        
                        sources_html += f"""
                        <div class="source-item">
                            <span class="tag-badge {b_cls}">{b_text}</span>
                            <a href="{url}" target="_blank" style="color:#333;text-decoration:none;font-weight:600">{d_title}</a>
                        </div>"""
                    sources_html += "</div>"
                
                # 4. GỌI AI TRẢ LỜI
                sys_prompt = f"""Bạn là Chuyên gia Yoga. Dựa vào tài liệu sau:
                {context_text}
                Câu hỏi: {prompt}
                Yêu cầu: 
                - Trả lời ngắn gọn, tập trung vào vấn đề.
                - Nếu không có tài liệu khớp, hãy trả lời dựa trên kiến thức Yoga chung chung và khuyên đi khám bác sĩ.
                - Dùng icon sinh động."""
                
                try:
                    gc.collect() # Dọn rác
                    response = model.generate_content(sys_prompt)
                    ai_text = response.text
                    
                    # QUAN TRỌNG: Hiển thị 2 phần riêng biệt để không vỡ layout
                    st.markdown(ai_text)
                    if top_docs:
                        st.markdown(sources_html, unsafe_allow_html=True)
                    
                    # Lưu vào lịch sử (Gộp lại thành string để lần sau load lại vẫn thấy)
                    full_log = ai_text + "\n" + sources_html if top_docs else ai_text
                    st.session_state.messages.append({"role": "assistant", "content": full_log})
                    
                except:
                    st.error("Server quá tải, vui lòng hỏi lại câu ngắn hơn.")
