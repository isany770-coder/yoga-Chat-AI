import streamlit as st
import gdown
import zipfile
import os
import sqlite3
import datetime
import re
import time
import uuid
import gc
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH TRANG & GIAO DIỆN
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    header[data-testid="stHeader"], footer, .stDeployButton {display: none !important;}
    
    /* ---------------------------------------------------- */
    /* SỬA LỖI 1: Bắt buộc bẻ gãy các link dài trên Mobile */
    /* ---------------------------------------------------- */
    a, .stMarkdown a {
        word-wrap: break-word !important;
        word-break: break-all !important;
        overflow-wrap: break-word !important;
    }
    
    /* ---------------------------------------------------- */
    /* SỬA LỖI 2: Nâng ô chat lên cao hơn (bottom: 35px)    */
    /* ---------------------------------------------------- */
    div[data-testid="stChatInput"] {
        bottom: 35px !important; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    
    /* Dòng cảnh báo Disclaimer ở đáy màn hình */
    .disclaimer-text {
        position: fixed; bottom: 5px; left: 0; right: 0;
        font-size: 11px; color: #888; z-index: 999; width: 100%; text-align: center;
        font-family: sans-serif; 
        pointer-events: none; /* Thêm cái này để lỡ bấm nhầm vào chữ nó xuyên qua luôn, ko bị kẹt */
    }
    
    /* Banner Welcome xịn sò */
    .welcome-banner {
        background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%);
        padding: 12px 15px; margin-bottom: 20px; border-radius: 12px;
        text-align: center; color: #2c3e50; font-size: 15px; font-weight: 600;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;
    }
    
    .upsell-box {
        background: linear-gradient(135deg, #f1f8e9 0%, #dcedc8 100%);
        padding: 12px; border-radius: 12px; margin-top: 15px;
        border: 1px solid #aed581; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .upsell-btn {
        background-color: #33691e; color: white !important; padding: 6px 15px;
        border-radius: 20px; text-decoration: none; font-size: 13px; font-weight: bold;
        float: right; margin-top: -2px;
    }
    .bottom-spacer { height: 130px; } /* Tăng khoảng đệm để cuộn xuống không bị che text */
</style>

<div class="disclaimer-text">
    AI can make mistakes. Verify medical information with a healthcare professional.
</div>
""", unsafe_allow_html=True)

# =====================================================
# 2. CẤU HÌNH ADMIN & UPSELL
# =====================================================
ADMIN_PROFILE = {
    "name": "YIML Assistant",
    "role": "Medical Yoga Expert",
    "certs": "Certified by Dr. Pham Van Quan",
    "contact": "Zalo (+84) 963.759.566",
    "mission": "Empowering the community with evidence-based yoga and medical science.",
}

BLOCKED_KEYWORDS = ["xổ số", "lô đề", "đánh bạc", "sex", "khiêu dâm", "chính trị", "phản động", "code python", "lập trình", "viết code"]

YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "🗺️ Lộ trình Trị Liệu 8 Bước (8-Step Therapy)", "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/", "key": ["đau","bệnh","trị liệu","phục hồi","lưng","gối","cột sống","thoát vị","tim mạch","huyết áp","mất ngủ","cổ vai gáy","pain","therapy","recovery","back","knee","spine","herniated"]},
    "AI_COACH": {"name": "🤖 AI Coach Chỉnh Tư Thế (Posture Correction)", "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/", "key": ["tập đúng","sai kỹ thuật","kỹ thuật","định tuyến","chỉnh dáng","hướng dẫn","căn chỉnh","bắt đầu","correct","form","alignment","technique"]},
    "KHOA_HOC": {"name": "🎓 Khóa Đào Tạo HLV (Teacher Training)", "url": "https://yogaismylife.vn/dao-tao-hlv/", "key": ["huấn luyện viên","dạy yoga","bằng cấp","chứng chỉ","nghề yoga","teacher","training","certification"]}
}

# =====================================================
# 3. KẾT NỐI DATA & DATABASE
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Missing configuration in secrets.toml"); st.stop()

ZIP_PATH = "/tmp/brain_data_v6.zip" 
EXTRACT_PATH = "/tmp/brain_data_extracted_v6"
DB_PATH = "user_usage.db"

# --- A. DATABASE & BLACKLIST ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS usage (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))')
    c.execute('CREATE TABLE IF NOT EXISTS blacklist (user_id TEXT PRIMARY KEY, reason TEXT, timestamp TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chat_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, timestamp TEXT, prompt TEXT)')
    conn.commit(); conn.close()
init_db()

def check_ban_status(user_id):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT reason FROM blacklist WHERE user_id=?", (user_id,))
    row = c.fetchone(); conn.close()
    return row[0] if row else None

def ban_user_forever(user_id, reason="Policy Violation"):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        now = str(datetime.datetime.now())
        c.execute("INSERT OR REPLACE INTO blacklist (user_id, reason, timestamp) VALUES (?, ?, ?)", (user_id, reason, now))
        conn.commit(); conn.close()
    except Exception as e: pass

def check_usage(user_id):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT count FROM usage WHERE user_id=? AND date=?", (user_id, today))
    r = c.fetchone(); conn.close()
    return r[0] if r else 0

def increment_usage(user_id):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO usage (user_id, date, count) VALUES (?, ?, 0)", (user_id, today))
    c.execute("UPDATE usage SET count = count + 1 WHERE user_id=? AND date=?", (user_id, today))
    conn.commit(); conn.close()

def log_user_prompt(user_id, prompt):
    """Âm thầm lưu câu hỏi của khách vào DB"""
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO chat_logs (user_id, timestamp, prompt) VALUES (?, ?, ?)", (user_id, now, prompt))
        conn.commit(); conn.close()
    except Exception as e: pass

# --- B. LOAD AI ENGINE ---
@st.cache_resource
def load_brain_engine_safe():
    if not os.path.exists(EXTRACT_PATH):
        try:
            if not os.path.exists("/tmp"): os.makedirs("/tmp")
            if os.path.exists(ZIP_PATH): os.remove(ZIP_PATH)
            
            with st.spinner("Downloading database..."):
                url = f'https://drive.google.com/uc?id={file_id}'
                gdown.download(url, ZIP_PATH, quiet=True, fuzzy=True)
            
            if not zipfile.is_zipfile(ZIP_PATH): return None, "ZIP file error"

            with st.spinner("Extracting data..."):
                with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
            os.remove(ZIP_PATH); gc.collect()
        except Exception as e: return None, str(e)
    
    def find_db_path(folder):
        for root, dirs, files in os.walk(EXTRACT_PATH):
            if folder in dirs and "index.faiss" in os.listdir(os.path.join(root, folder)):
                return os.path.join(root, folder)
        return None

    text_db_path = find_db_path("vector_db")
    if not text_db_path: return None, "Database not found"

    try:
        with st.spinner("Initializing AI Engine..."):
            embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=api_key)
            db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
            gc.collect()
        return db_text, "OK"
    except Exception as e: return None, str(e)

db_text, status = load_brain_engine_safe()
if status != "OK": st.error(f"Data Error: {status}"); st.stop()

# =====================================================
# 4. HÀM AI THÔNG MINH (BẢN FINAL 7.0: SẠCH BÓNG, TỰ TẠO LINK)
# =====================================================
def get_ai_response_custom(prompt, context_text, history_context):
    try:
        for kw in BLOCKED_KEYWORDS:
            if kw in prompt.lower(): return "VIOLATION_DETECTED"

        valid_model = 'models/gemini-1.5-flash'
        try:
            for m in genai.list_models():
                if 'flash' in m.name.lower(): valid_model = m.name; break
        except: pass
        model = genai.GenerativeModel(valid_model)
        
        sys_prompt = f"""
        🛑 **SECURITY PROTOCOL:**
        - Input: "{prompt}"
        - Check: If user asks about Lottery, Gambling, Sex, Politics -> REPLY EXACTLY: "VIOLATION_DETECTED".

        ROLE: You are **{ADMIN_PROFILE['name']}**, the official Medical Yoga Expert for YogaIsMyLife.vn.

        🌍 **LANGUAGE RULE:**
        - User asks in VN -> Reply 100% in VN.
        - User asks in EN -> Reply 100% in EN. Translate ALL data into English.

        🎯 **EVIDENCE RULES (CRITICAL):**
        1. Read the [DATA] provided below. It is strictly divided into "NGHIÊN CỨU KHOA HỌC" and "BÀI VIẾT TỪ CHUYÊN GIA".
        2. For the "Scientific Evidence / Bằng chứng Y khoa" section, you MUST ONLY list items from the "NGHIÊN CỨU KHOA HỌC" group. 
        3. SOURCE URL RULE: Print the exact "Link:" provided in the data. DO NOT alter it.
        4. ABSOLUTELY DO NOT use citation tags like [Ref: 1] or [1].
        5. NO META-COMMENTARY. DO NOT apologize or explain.

        🛠️ **MANDATORY RESPONSE FORMAT (DO NOT PRINT ANY INSTRUCTIONS OUT LOUD):**

        **[IF USER ASKS IN ENGLISH]**
        [Warm greeting and direct answer].

        🧠 **The Science Behind It**
        [Explain mechanisms using bullet points based on the data. No Ref tags].

        📚 **Scientific Evidence**
        * 📘 **Study:** [Study Title]
            * *Result:* [Result/Key Point]
            * *Source:* [Raw URL from data]

        💡 **Expert Advice**
        [Actionable advice].

        **[IF USER ASKS IN VIETNAMESE]**
        [Lời chào ấm áp và câu trả lời trực diện].

        🧠 **Góc nhìn Khoa học & Cơ chế**
        [Giải thích cơ chế bằng các gạch đầu dòng tự nhiên].

        📚 **Bằng chứng Y khoa**
        * 📘 **Nghiên cứu:** [Tên nghiên cứu]
            * *Kết quả:* [Kết luận/Điểm chính]
            * *Nguồn:* [Raw URL từ data]

        💡 **Lời khuyên từ Chuyên gia**
        [Đưa ra lời khuyên thực tế].

        --------------------------------------------------
        [DATA (CONTEXT)]:
        {context_text}

        [HISTORY]:
        {history_context}

        USER QUESTION: "{prompt}"
        """
        response = model.generate_content(sys_prompt)
        return response.text.strip()
    except Exception as e: return f"ERR_SYS: {str(e)}"

# =====================================================
# 5. QUẢN LÝ SESSION
# =====================================================
try:
    qp = st.query_params
    url_uid = qp.get("uid", None)
except:
    url_uid = None

if "user_id" not in st.session_state:
    if url_uid: st.session_state.user_id = url_uid
    else:
        new_uid = str(uuid.uuid4())[:8]
        st.session_state.user_id = new_uid
        try: st.query_params["uid"] = new_uid
        except: pass

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "bad_attempts" not in st.session_state: st.session_state.bad_attempts = 0
if "is_blocked" not in st.session_state: st.session_state.is_blocked = False
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": f"Hello! I am **{ADMIN_PROFILE['name']}**. How can I assist you with your health and yoga practice today?"}]

current_user = st.session_state.username if st.session_state.authenticated else st.session_state.user_id

ban_reason = check_ban_status(current_user)
if ban_reason:
    st.error(f"🚫 **ACCOUNT BLOCKED**\n\nReason: {ban_reason}\n\nContact Admin: {ADMIN_PROFILE['contact']}")
    st.stop()

used = check_usage(current_user)
LIMIT = 50 if st.session_state.authenticated else 30
is_limit_reached = used >= LIMIT

# =====================================================
# 6. GIAO DIỆN SIDEBAR
# =====================================================
with st.sidebar:
    st.title("🔐 VIP Access")
    
    if st.session_state.authenticated:
        st.success(f"Hi {st.session_state.username}")
        if st.session_state.username == "admin_yiml": 
            import pandas as pd
            if st.button("👁️ Xem lịch sử khách hỏi"):
                st.markdown("### 🕵️ Hồ sơ Chat")
                try:
                    conn = sqlite3.connect(DB_PATH)
                    df = pd.read_sql_query("SELECT timestamp, prompt, user_id FROM chat_logs ORDER BY id DESC LIMIT 50", conn)
                    st.dataframe(df, use_container_width=True)
                    conn.close()
                except Exception as e: st.error("Chưa có data!")
        if st.button("Logout"): st.session_state.authenticated = False; st.rerun()
    else:
        with st.form("login_sidebar"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("Login"):
                if st.secrets["passwords"].get(u) == p:
                    st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
                else: st.error("Wrong password")
    
    st.markdown("---")
    with st.expander("👨‍⚕️ About the Expert", expanded=True):
        st.markdown(f"**{ADMIN_PROFILE['name']}** *({ADMIN_PROFILE['role']})*\n\n🎖️ {ADMIN_PROFILE['certs']}\n\n💬 **{ADMIN_PROFILE['contact']}**\n\n> *\"{ADMIN_PROFILE['mission']}\"*")

percent = min(100, int((used / LIMIT) * 100))
st.markdown(f"""
<div style="position: fixed; top: 10px; right: 10px; z-index: 100000;">
    <div style="background: rgba(255,255,255,0.95); padding: 5px 12px; border-radius: 20px; border: 1px solid #009688; box-shadow: 0 2px 5px rgba(0,0,0,0.1); font-size: 12px; font-weight: bold; color: #00796b; display: flex; align-items: center; gap: 8px;">
        <span>⚡ {used}/{LIMIT}</span>
        <div style="width: 40px; height: 4px; background: #e0e0e0; border-radius: 2px;">
            <div style="width: {percent}%; height: 100%; background: linear-gradient(90deg, #009688, #80cbc4); border-radius: 2px;"></div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

if is_limit_reached:
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
    st.warning("Bạn đã hết lượt hỏi hôm nay. Vui lòng quay lại vào ngày mai.")
    st.stop()

# =====================================================
# 8. XỬ LÝ CHAT CHÍNH
# =====================================================
import urllib.parse # Import bùa hộ mệnh tạo Link

if not st.session_state.authenticated:
    st.markdown("""<div class="welcome-banner">✨ Welcome to YIML Pro • Evidence-Based Medical Yoga Assistant</div>""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"], unsafe_allow_html=True)
st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

if prompt := st.chat_input(f"Ask {ADMIN_PROFILE['name']} about yoga & health..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(current_user)
    log_user_prompt(current_user, prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing medical databases..."):
            
            chat_history = ""
            for msg in st.session_state.messages[-4:]:
                clean_content = re.sub(r'<[^>]*>', '', msg['content'])
                chat_history += f"{msg['role']}: {clean_content}\n"

            # --- THUẬT TOÁN LỌC NGHIÊN CỨU ƯU TIÊN (BẢN TÀN NHẪN NHẤT) ---
            research_texts = ""
            blog_texts = ""
            r_count = 0
            b_count = 0

            try:
                docs = db_text.similarity_search(prompt, k=15)
                if docs:
                    for d in docs:
                        meta = d.metadata
                        
                        # Vét sạch mọi loại Key viết hoa viết thường
                        url_val = meta.get('url') or meta.get('URL') or meta.get('link') or meta.get('Link')
                        doi_val = meta.get('doi') or meta.get('DOI')
                        source_val = meta.get('source') or meta.get('Source')
                        
                        raw_link = str(url_val or doi_val or source_val or '#').strip()
                        title = str(meta.get('title') or meta.get('Title') or 'Nghiên cứu Y khoa')
                        
                        # QUÂN LUẬT 1: Cứ có yogaismylife là tống sang mục Blog (THAM KHẢO)
                        if 'yogaismylife.vn' in raw_link.lower():
                            if b_count < 3:
                                b_count += 1
                                blog_texts += f"\n--- BÀI VIẾT TỪ CHUYÊN GIA {b_count} ---\nTên: {title}\nLink: {raw_link}\nNội dung:\n{d.page_content}\n"
                        else:
                            # QUÂN LUẬT 2: Còn lại chắc chắn là Nghiên cứu Y Khoa
                            if r_count < 3:
                                r_count += 1
                                
                                # BÙA HỘ MỆNH: Không có link ư? Tự tạo link tra cứu Google Scholar luôn!
                                if raw_link == '#' or raw_link.lower() == 'none' or raw_link == '' or raw_link == 'Không có sẵn':
                                    safe_title = urllib.parse.quote(title)
                                    final_link = f"https://scholar.google.com/scholar?q={safe_title}"
                                else:
                                    final_link = raw_link
                                    # Phủ đầu lỗi chỉ có mã DOI trần
                                    if not final_link.startswith('http'):
                                        final_link = f"https://doi.org/{final_link.replace('DOI:', '').strip()}"
                                        
                                research_texts += f"\n--- NGHIÊN CỨU KHOA HỌC {r_count} ---\nTên: {title}\nLink: {final_link}\nNội dung:\n{d.page_content}\n"
            except: pass

            context_text = research_texts + "\n" + blog_texts

            ai_raw = get_ai_response_custom(prompt, context_text, chat_history)
            final_content = ""
            
            if ai_raw == "VIOLATION_DETECTED":
                st.session_state.bad_attempts += 1
                if st.session_state.bad_attempts >= 3:
                    ban_user_forever(current_user, "Spam/Policy Violation")
                    st.session_state.is_blocked = True
                    msg = "🚫 **ACCOUNT BLOCKED**"
                else:
                    msg = f"⚠️ **WARNING ({st.session_state.bad_attempts}/3)**"
                st.markdown(msg); final_content = msg
                if st.session_state.is_blocked: time.sleep(3); st.rerun()

            elif ai_raw.startswith("ERR_SYS:"):
                st.error(f"System Error: {ai_raw}"); final_content = "Sorry, system error."

            else:
                clean_text = ai_raw.strip()
                
                vn_chars = "áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ"
                is_vietnamese = any(char in prompt.lower() for char in vn_chars)

                upsell_html = ""
                recs = [v for k,v in YOGA_SOLUTIONS.items() if any(key in prompt.lower() for key in v['key'])]
                if recs and is_vietnamese:
                    upsell_html += "<div class='upsell-box'><b>💡 Giải pháp gợi ý từ Chuyên gia:</b><br>"
                    for r in recs[:2]:
                        upsell_html += f"""<div style="margin-top:8px; display:flex; justify-content:space-between; align-items:center;"><span style="color:#33691e; font-weight:500">👉 {r['name']}</span><a href="{r['url']}" target="_blank" class="upsell-btn">Xem</a></div>"""
                    upsell_html += "</div>"
                
                st.markdown(clean_text, unsafe_allow_html=True)
                if upsell_html: st.markdown(upsell_html, unsafe_allow_html=True)
                
                final_content = clean_text + "\n" + upsell_html

            if final_content:
                st.session_state.messages.append({"role": "assistant", "content": final_content})
