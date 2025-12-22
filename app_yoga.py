import streamlit as st
import gdown, zipfile, os, re, json, datetime
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. PAGE CONFIG
# =====================================================
st.set_page_config(page_title="Yoga Assistant Pro", page_icon="🧘", layout="wide", initial_sidebar_state="collapsed")

# =====================================================
# 2. CSS - (GIỮ NGUYÊN CŨ + THÊM QUẢNG CÁO & FIX PHÍM)
# =====================================================
st.markdown("""
<style>
    /* --- CSS CŨ CỦA BÁC (GIỮ NGUYÊN) --- */
    [data-testid="stAppViewContainer"], .stApp, html, body { background-color: white !important; color: #31333F !important; }
    p, h1, h2, h3, h4, h5, h6, span, div, label, li { color: #31333F !important; }
    [data-testid="stToolbar"], header, footer, .stAppDeployButton { display: none !important; }

    /* CHAT INPUT */
    div[data-testid="stChatInput"] {
        position: fixed !important; bottom: 20px !important; left: 10px !important; right: 10px !important;
        width: auto !important; z-index: 999999; background-color: white !important;
        border-radius: 25px !important; box-shadow: 0 -2px 10px rgba(0,0,0,0.1); padding: 5px !important; border: 1px solid #e0e0e0;
        transition: bottom 0.3s ease;
    }
    /* FIX: Khi bàn phím điện thoại bật lên (màn hình thấp đi), ép input dính đáy */
    @media (max-height: 500px) {
        div[data-testid="stChatInput"] { bottom: 0px !important; border-radius: 0 !important; border-bottom: none !important; }
        .ad-banner { display: none !important; } /* Ẩn quảng cáo khi gõ phím */
        .usage-bar-container, .usage-text { display: none !important; } /* Ẩn thanh top */
    }

    textarea[data-testid="stChatInputTextArea"] {
        font-size: 16px !important; color: #333333 !important; -webkit-text-fill-color: #333333 !important;
        background-color: #f0f2f6 !important; border-radius: 20px !important; caret-color: #0f988b !important;
    }
    textarea[data-testid="stChatInputTextArea"]::placeholder { color: #888 !important; opacity: 1 !important; }
    button[data-testid="stChatInputSubmit"] { background-color: #0f988b !important; color: white !important; border-radius: 50% !important; right: 10px !important; bottom: 8px !important; }
    button[data-testid="stChatInputSubmit"] svg { fill: white !important; }

    div[data-testid="stChatMessage"] { background-color: #f8f9fa !important; border: 1px solid #eee; }
    div[data-testid="stChatMessage"][data-test-role="user"] { background-color: #e3f2fd !important; }

    .usage-bar-container { position: fixed; top: 0; left: 0; width: 100%; height: 5px; background-color: #f0f0f0; z-index: 1000000; }
    .usage-bar-fill { height: 100%; background: linear-gradient(90deg, #0f988b 0%, #14b8a6 100%); }
    .usage-text { position: fixed; top: 10px; right: 15px; background: rgba(255,255,255,0.9); padding: 4px 12px; border-radius: 20px; font-size: 11px; color: #0f988b !important; font-weight: bold; border: 1px solid #0f988b; z-index: 1000001; }
    
    .main .block-container { padding-top: 3rem !important; padding-bottom: 220px !important; }

    .zalo-btn { display: flex !important; align-items: center; justify-content: center; width: 100%; background-color: white; color: #0f988b !important; border: 1px solid #dcdfe3; border-radius: 8px; font-weight: 500; font-size: 14px; height: 45px !important; text-decoration: none !important; margin: 0 !important; }
    div[data-testid="stForm"] button { height: 45px !important; border-radius: 8px !important; font-weight: 500 !important; color: #31333F !important; }

    /* Modal Hết Lượt */
    .limit-modal { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); z-index: 2147483647 !important; display: flex; align-items: center; justify-content: center; flex-direction: column; }
    .limit-box { background: white; padding: 40px; border-radius: 25px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); text-align: center; max-width: 90%; width: 400px; border: 2px solid #0f988b; animation: popup 0.5s cubic-bezier(0.68, -0.55, 0.27, 1.55); }
    @keyframes popup { 0% { transform: scale(0.5); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }
    .limit-btn { background: linear-gradient(135deg, #0f988b, #14b8a6); color: white !important; padding: 12px 35px; border-radius: 50px; text-decoration: none; font-weight: bold; display: inline-block; box-shadow: 0 5px 15px rgba(15, 152, 139, 0.4); margin-top: 15px; }

    /* --- 🆕 CSS CHO QUẢNG CÁO (BANNER NỔI) --- */
    .ad-banner {
        position: fixed; bottom: 85px; left: 15px; right: 15px;
        background: linear-gradient(90deg, #fff3e0 0%, #ffe0b2 100%);
        border: 1px solid #ffcc80; border-radius: 12px; padding: 10px;
        z-index: 999990; display: flex; align-items: center; justify-content: space-between;
        box-shadow: 0 5px 15px rgba(0,0,0,0.05); animation: slideUp 0.5s ease-out;
    }
    @keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    .ad-content { font-size: 13px; font-weight: 600; color: #e65100 !important; display: flex; align-items: center; gap: 8px; }
    .ad-btn { background: #e65100; color: white !important; padding: 5px 12px; border-radius: 20px; font-size: 11px; text-decoration: none; font-weight: bold; white-space: nowrap; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 3. LOAD NÃO & API (GIỮ NGUYÊN)
# =====================================================
FILE_ID_DRIVE = "1vOvvanNvDaLwP8Xs4nn1UhkciRvTxzyA" 
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
            with zipfile.ZipFile(OUTPUT_ZIP, 'r') as zip_ref: zip_ref.extractall("/tmp/")
        except: return None, None
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(EXTRACT_PATH, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-flash-latest')
        return db, model
    except: return None, None
db, model = load_brain()

# =====================================================
# 4. QUẢN LÝ DATA: LƯỢT DÙNG + LỊCH SỬ CHAT (ĐÃ NÂNG CẤP)
# =====================================================
USAGE_DB_FILE = "/tmp/usage_history_db.json" # File mới chứa cả lịch sử
DAILY_LIMIT = 25
TRIAL_LIMIT = 10

def get_data():
    if not os.path.exists(USAGE_DB_FILE): return {}
    try: with open(USAGE_DB_FILE, "r") as f: return json.load(f)
    except: return {}

def save_data(data):
    with open(USAGE_DB_FILE, "w") as f: json.dump(data, f)

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""

# Xác định User
user_key = st.session_state.username if st.session_state.authenticated else "anonymous_guest"
today = str(datetime.date.today())
db_data = get_data()

# Reset hoặc tạo mới user
if user_key not in db_data or db_data[user_key].get("date") != today:
    # Reset count về 0, tạo mới history
    db_data[user_key] = {
        "date": today, 
        "count": 0, 
        "history": [{"role":"assistant","content":"Namaste! 🙏 Thật vui được gặp bạn. Hôm nay chúng ta sẽ bắt đầu từ đâu?"}]
    }
    save_data(db_data)

# ĐỒNG BỘ SESSION TỪ FILE (CỐT LÕI ĐỂ KHÔNG MẤT CHAT)
st.session_state.messages = db_data[user_key]["history"]
used = db_data[user_key]["count"]
limit = DAILY_LIMIT if st.session_state.authenticated else TRIAL_LIMIT
percent = min(100, int((used / limit) * 100))

# Thanh tiến trình
st.markdown(f"""
    <div class="usage-bar-container"><div class="usage-bar-fill" style="width: {percent}%;"></div></div>
    <div class="usage-text">⚡ Lượt dùng: {used}/{limit}</div>
""", unsafe_allow_html=True)

# =====================================================
# 5. HIỂN THỊ CHAT & CÁC TÍNH NĂNG MỚI
# =====================================================
can_chat = used < limit

# --- 🆕 QUẢNG CÁO "VỢT KHÁCH" (Chỉ hiện khi chưa đăng nhập) ---
if not st.session_state.authenticated:
    st.markdown("""
    <div class="ad-banner" id="promo-banner">
        <div class="ad-content">
            <span>🎁</span>
            <span>Combo Thảm + Gạch Yoga giảm 30%!</span>
        </div>
        <a href="https://yogaismylife.vn/khuyen-mai" target="_blank" class="ad-btn">Xem ngay 👉</a>
    </div>
    """, unsafe_allow_html=True)

# --- 🆕 ADMIN VIEW (SOI LOG CHAT) ---
if st.session_state.authenticated and st.session_state.username == "admin":
    st.info("🕵️ **CHẾ ĐỘ ADMIN: SOI LOG CHAT**")
    if st.button("🔄 Tải lại Log"): st.rerun()
    if "anonymous_guest" in db_data:
        anon_hist = db_data["anonymous_guest"]["history"]
        with st.expander(f"👥 Khách vãng lai ({len(anon_hist)} tin nhắn)", expanded=True):
            for msg in reversed(anon_hist): 
                if msg['role'] == 'user': st.write(f"👤 **Khách:** {msg['content']}")
                else: st.caption(f"🤖 AI: {msg['content'][:50]}...")
                st.divider()

# --- HIỂN THỊ LỊCH SỬ CHAT ---
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"], unsafe_allow_html=True)

# --- MODAL HẾT LƯỢT ---
if not can_chat:
    st.markdown(f"""
    <div class="limit-modal"><div class="limit-box"><div style="font-size:50px;margin-bottom:10px">🧘‍♀️</div>
    <div style="font-size:20px;font-weight:bold;color:#ff6b6b">Đã hết năng lượng!</div>
    <p style="color:#555;margin:15px 0">Bạn đã dùng hết {limit} câu hỏi miễn phí hôm nay.</p>
    <a href="https://zalo.me/84963759566" target="_blank" class="limit-btn">💬 Liên hệ Admin ngay</a></div></div>
    """, unsafe_allow_html=True)
    st.stop()

# --- XỬ LÝ CHAT MỚI (CÓ LƯU VÀO FILE DB) ---
if prompt := st.chat_input("Hỏi chuyên gia Yoga..."):
    # 1. Lưu User Message vào DB
    db_data[user_key]["count"] += 1
    db_data[user_key]["history"].append({"role": "user", "content": prompt})
    save_data(db_data)
    
    # 2. Hiển thị User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    # 3. AI Trả lời
    with st.chat_message("assistant"):
        if db:
            docs = db.similarity_search(prompt, k=4)
            source_map = {}; context_parts = []
            for i, d in enumerate(docs):
                u = d.metadata.get('url', '#'); t = d.metadata.get('title', 'Tài liệu')
                context_parts.append(f"--- NGUỒN {i+1} ---\nTIÊU ĐỀ: {t}\nURL: {u}\nNỘI DUNG: {d.page_content}")
                source_map[u] = t 

            sys_prompt = f"Bạn là chuyên gia Yoga. Dựa vào nguồn: {context_parts}. Trả lời câu hỏi: {prompt}. Ngắn gọn dưới 100 từ. Không bịa link."
            
            try:
                res_text = model.generate_content(sys_prompt).text
                
                # Tạo Link HTML (Mở tab mới)
                links_html = ""
                if source_map:
                    links_html += "<br><hr><b>📚 Tài liệu tham khảo:</b><ul style='list-style:none;padding:0'>"
                    seen = set(); c = 0
                    for url, title in source_map.items():
                        if url != "#" and url not in seen and c < 3:
                            links_html += f"<li style='margin-bottom:5px'>🔗 <a href='{url}' target='_blank' style='color:#0f988b;text-decoration:none;font-weight:500'>{title}</a></li>"
                            seen.add(url); c += 1
                    links_html += "</ul>"
                
                final_res = res_text + links_html
                st.markdown(final_res, unsafe_allow_html=True)
                
                # 4. Lưu AI Message vào DB
                db_data[user_key]["history"].append({"role": "assistant", "content": final_res})
                save_data(db_data)
                
                st.rerun()
            except: st.error("AI đang thở gấp...")

# =====================================================
# 6. LOGIN FORM & SPACER (ĐỆM CAO HƠN CHO QUẢNG CÁO)
# =====================================================
if not st.session_state.authenticated:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🔐 Đăng nhập / Lấy thêm lượt (Dành cho Member)", expanded=not can_chat):
        with st.form("login_form"):
            u = st.text_input("Tên đăng nhập", placeholder="Username")
            p = st.text_input("Mật khẩu", type="password", placeholder="Password")
            st.write("")
            c1, c2 = st.columns(2)
            with c1: submit = st.form_submit_button("Đăng nhập", use_container_width=True)
            with c2: st.markdown(f"""<div style="margin-top:0px;"><a href="https://zalo.me/84963759566" target="_blank" style="text-decoration:none;"><div class="zalo-btn">💬 Lấy TK Zalo</div></a></div>""", unsafe_allow_html=True)

            if submit:
                # CHECK ADMIN & USER
                if u == "admin" and p == "yoga888": # Admin Login
                    st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
                elif st.secrets["passwords"].get(u) == p: # User thường
                    st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
                else: st.error("Sai rồi bác ơi!")

    # Spacer siêu dày để nội dung không bị Input + Quảng cáo che
    st.markdown("<div style='height: 250px; display: block;'></div>", unsafe_allow_html=True)
