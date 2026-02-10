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
def extract_doi(text):
    if not text:
        return None
    match = re.search(
        r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)',
        text,
        re.IGNORECASE
    )
    return match.group(1) if match else None

# =====================================================
# 1. CẤU HÌNH TRANG & GIAO DIỆN
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    header[data-testid="stHeader"], footer, .stDeployButton {display: none !important;}
    
    div[data-testid="stChatInput"] {
        position: fixed; bottom: 10px; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    
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
    .bottom-spacer { height: 100px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. CẤU HÌNH ADMIN & UPSELL
# =====================================================
ADMIN_PROFILE = {
    "name": "YIML Assistant",
    "role": "Trợ lý Yoga Y Khoa",
    "certs": "Được bảo chứng bởi Bác sĩ Phạm Văn Quân",
    "contact": "Zalo 0963.759.566",
    "mission": "Sứ mệnh giúp cộng đồng có cái nhìn khoa học hơn về Yoga.",
    "bio_full": "Tôi là Trợ lý YIML- Chuyên gia Yoga. Tôi chỉ trả lời các vấn đề về Sức khỏe, Giải phẫu và Yoga."
}

# Từ khóa cấm (Check nhanh bằng Python)
BLOCKED_KEYWORDS = ["xổ số", "lô đề", "đánh bạc", "sex", "khiêu dâm", "chính trị", "phản động", "code python", "lập trình", "viết code"]

YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "🗺️ Lộ trình Trị Liệu 8 Bước", "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/", "key": ["đau","bệnh","trị liệu","phục hồi","lưng","gối","cột sống","thoát vị","tim mạch","huyết áp","mất ngủ","cổ vai gáy","pain","therapy","recovery","back","knee","spine","herniated"]},
    "AI_COACH": {"name": "🤖 AI Coach Chỉnh Tư Thế", "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/", "key": ["tập đúng","sai kỹ thuật","kỹ thuật","định tuyến","chỉnh dáng","hướng dẫn","căn chỉnh","bắt đầu","correct","form","alignment","technique"]},
    "KHOA_HOC": {"name": "🎓 Khóa Đào Tạo HLV", "url": "https://yogaismylife.vn/dao-tao-hlv/", "key": ["huấn luyện viên","dạy yoga","bằng cấp","chứng chỉ","nghề yoga","teacher","training","certification"]}
}

# =====================================================
# 3. KẾT NỐI DATA & DATABASE
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Chưa cấu hình secrets.toml"); st.stop()

ZIP_PATH = "/tmp/brain_data_v3.zip" 
EXTRACT_PATH = "/tmp/brain_data_extracted_v5"
DB_PATH = "user_usage.db"

# --- A. DATABASE & BLACKLIST (CHỐNG F5) ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Bảng đếm lượt
    c.execute('CREATE TABLE IF NOT EXISTS usage (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))')
    # Bảng SỔ ĐEN (Lưu ID bị khóa vĩnh viễn)
    c.execute('CREATE TABLE IF NOT EXISTS blacklist (user_id TEXT PRIMARY KEY, reason TEXT, timestamp TEXT)')
    conn.commit(); conn.close()
init_db()

def check_ban_status(user_id):
    """Kiểm tra xem user có nằm trong sổ đen không"""
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT reason FROM blacklist WHERE user_id=?", (user_id,))
    row = c.fetchone(); conn.close()
    return row[0] if row else None

def ban_user_forever(user_id, reason="Vi phạm chính sách"):
    """Khóa vĩnh viễn user vào DB"""
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        now = str(datetime.datetime.now())
        c.execute("INSERT OR REPLACE INTO blacklist (user_id, reason, timestamp) VALUES (?, ?, ?)", (user_id, reason, now))
        conn.commit(); conn.close()
    except Exception as e: print(f"Ban Err: {e}")

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

# --- B. LOAD AI ENGINE ---
@st.cache_resource
def load_brain_engine_safe():
    if not os.path.exists(EXTRACT_PATH):
        try:
            if not os.path.exists("/tmp"): os.makedirs("/tmp")
            if os.path.exists(ZIP_PATH): os.remove(ZIP_PATH)
            
            with st.spinner(f"Đang tải dữ liệu..."):
                url = f'https://drive.google.com/uc?id={file_id}'
                gdown.download(url, ZIP_PATH, quiet=True, fuzzy=True)
            
            if not zipfile.is_zipfile(ZIP_PATH): return None, "Lỗi file ZIP"

            with st.spinner("Đang giải nén..."):
                with zipfile.ZipFile(ZIP_PATH, 'r') as z: z.extractall(EXTRACT_PATH)
            os.remove(ZIP_PATH); gc.collect()
        except Exception as e: return None, str(e)
    
    def find_db_path(folder):
        for root, dirs, files in os.walk(EXTRACT_PATH):
            if folder in dirs and "index.faiss" in os.listdir(os.path.join(root, folder)):
                return os.path.join(root, folder)
        return None

    text_db_path = find_db_path("vector_db")
    if not text_db_path: return None, "Không tìm thấy vector_db"

    try:
        with st.spinner("Đang nạp não..."):
            embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=api_key)
            db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
            gc.collect()
        return db_text, "OK"
    except Exception as e: return None, str(e)

db_text, status = load_brain_engine_safe()
if status != "OK": st.error(f"Lỗi Data: {status}"); st.stop()

# =====================================================
# 4. HÀM AI THÔNG MINH (BẢN FINAL: CẤU TRÚC CŨ + IDENTITY + SECURITY)
# =====================================================
def get_ai_response_custom(prompt, context_text, history_context):
    try:
        # 1. CHECK TỪ KHÓA CẤM (Lớp vỏ cứng Python - giữ nguyên)
        for kw in BLOCKED_KEYWORDS:
            if kw in prompt.lower(): return "VIOLATION_DETECTED"

        # 2. CẤU HÌNH MODEL
        valid_model = 'models/gemini-1.5-flash'
        try:
            for m in genai.list_models():
                if 'flash' in m.name.lower(): valid_model = m.name; break
        except: pass
        model = genai.GenerativeModel(valid_model)
        import textwrap

# =====================================================
# 3. SYSTEM PROMPT (EVIDENCE-ONLY – FINAL LOCKED VERSION)
# =====================================================
# =====================================================
# 3. SYSTEM PROMPT (EVIDENCE-ONLY – FINAL LOCKED VERSION)
# =====================================================

# Lưu ý: Đảm bảo các biến prompt, ADMIN_PROFILE, context_text, history_context
# đã được định nghĩa trước khi chạy dòng lệnh dưới đây.

sys_prompt = f"""\
🛑 **SECURITY PROTOCOL (PRIORITY 1):**
- Input: "{prompt}"
- Check: If user asks about Lottery, Gambling, Sex, Politics, Coding, or NON-HEALTH topics -> REPLY EXACTLY: "VIOLATION_DETECTED".
- If valid -> Proceed to ROLE & LOGIC below.

--------------------------------------------------

ROLE: You are **{ADMIN_PROFILE['name']}** ({ADMIN_PROFILE['role']}), the official Medical Yoga Expert for **{ADMIN_PROFILE.get('website', 'YogaIsMyLife.vn')}**.
MISSION: {ADMIN_PROFILE['mission']}

🌍 **LANGUAGE:**
- User asks in English -> Reply in English.
- User asks in Vietnamese -> Reply in Vietnamese.

🧠 **CONTEXT AWARENESS:**
- You must read the [HISTORY] below to understand the conversation flow (e.g., if user says "bài tập đó", refer to the previous exercise mentioned).

--------------------------------------------------
🧬 **EVIDENCE-ONLY ANSWER ELIGIBILITY (ABSOLUTE RULE):**
- ANY question related to disease, disorder, symptoms, treatment, prevention, rehabilitation, or health outcomes
  MUST be answered using evidence from at least ONE explicitly identified scientific study (author + year).
- General medical explanations or textbook-style answers WITHOUT anchoring to a specific study are STRICTLY FORBIDDEN.
- If no suitable study exists in the provided [DATA], you MUST respond:
  "No eligible scientific study with DOI is available in the provided data to answer this question."

--------------------------------------------------
🎯 **STRICT CITATION RULES (TUÂN THỦ TUYỆT ĐỐI - CORE LOGIC):**
1. You are provided with context chunks labeled [Ref: 1], [Ref: 2], etc.
2. **ACCURACY IS PARAMOUNT:** When you state a fact, you MUST check which [Ref: ID] it came from.
3. **DO NOT MIX SOURCES:** If information is in [Ref: 1], do NOT cite [Ref: 2].
4. If a fact is NOT in the provided [DATA], do NOT attach a [Ref].
5. **SOURCE HIERARCHY:** If you find a study (e.g., Cramer 2025) mentioned in a General Article (Source A) BUT you also see the Original Study File (Source B) in the list, **YOU MUST CITE SOURCE B** as the primary evidence. Source A is just a secondary reference.
6. **Science First:** For ALL health-related questions, prioritize sources labeled [LOẠI: BẰNG CHỨNG KHOA HỌC].
7. Maximum: 300 words.
8. If a scientific reference shows a DOI in [DATA], you MUST explicitly display the DOI.
9. If the DOI is not shown in [DATA], you MUST state: "The DOI is not available in the provided data."
10. You are strictly forbidden from guessing or recalling DOIs from memory.
11. Any answer that relies on scientific evidence MUST explicitly include at least one DOI in the main answer text.
12. If multiple studies are cited, include the DOI of the highest-level evidence (systematic review or meta-analysis).
13. The DOI must appear inline in the answer, not only in the reference list.
14. When explaining or interpreting research findings, you MUST mention at least one DOI inline in the explanatory text
    (e.g., “as shown in a systematic review, DOI: xxxx”), not only in the reference section.

--------------------------------------------------
🖥️ **OUTPUT DISPLAY RULES (MANDATORY):**
- References must be displayed as single-line markdown anchor text: [Title](URL).
- Never output raw URLs.
- Never separate title and link into different lines.
- Never use labels such as "Link:" or "URL:".

--------------------------------------------------
STRUCTURE:
- **Greeting:** Short & warm (e.g., "Chào bạn, tôi là {ADMIN_PROFILE['name']}...").
- **Direct Answer:** Answer the question clearly.
- **Scientific Explanation:** MUST be anchored to at least one cited study.
- **Specific Evidence:** Explicitly name the study and DOI inline.
- **Conclusion/Advice:** Actionable advice, consistent with cited evidence.

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
# 5. QUẢN LÝ SESSION "DÍNH CHẶT" (CHỐNG F5)
# =====================================================
# Lấy ID từ URL (Nếu F5 thì ID này vẫn còn trên thanh địa chỉ)
try:
    # Streamlit mới dùng query_params, cũ dùng experimental_get_query_params
    qp = st.query_params
    url_uid = qp.get("uid", None)
except:
    url_uid = None

if "user_id" not in st.session_state:
    if url_uid:
        # Nếu trên URL có ID -> Dùng lại ID cũ (Người quen F5)
        st.session_state.user_id = url_uid
    else:
        # Khách mới tinh -> Tạo ID mới & Gắn lên URL ngay lập tức
        new_uid = str(uuid.uuid4())[:8]
        st.session_state.user_id = new_uid
        try:
            st.query_params["uid"] = new_uid # Dán ID lên URL (Sticky)
        except: pass

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "bad_attempts" not in st.session_state: st.session_state.bad_attempts = 0
if "is_blocked" not in st.session_state: st.session_state.is_blocked = False
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": f"Chào bạn! Tôi là **{ADMIN_PROFILE['name']}**. Tôi có thể giúp gì cho sức khỏe của bạn hôm nay?"}]

# Xác định User & Kiểm tra SỔ ĐEN
current_user = st.session_state.username if st.session_state.authenticated else st.session_state.user_id

# --- CHỐT CHẶN: KIỂM TRA SỔ ĐEN NGAY ĐẦU CỔNG ---
ban_reason = check_ban_status(current_user)
if ban_reason:
    st.error(f"🚫 **TÀI KHOẢN ĐÃ BỊ KHÓA VĨNH VIỄN**\n\nLý do: {ban_reason}\n\nLiên hệ Admin: {ADMIN_PROFILE['contact']}")
    st.stop() # Dừng hình, không cho load tiếp

used = check_usage(current_user)
LIMIT = 50 if st.session_state.authenticated else 5
is_limit_reached = used >= LIMIT

# =====================================================
# 6. GIAO DIỆN & SIDEBAR (CÓ ADMIN BIO)
# =====================================================
with st.sidebar:
    st.title("🔐 VIP Access")
    
    # 1. Login
    if st.session_state.authenticated:
        st.success(f"Hi {st.session_state.username}")
        if st.button("Logout"): st.session_state.authenticated = False; st.rerun()
    else:
        with st.form("login_sidebar"):
            u = st.text_input("User"); p = st.text_input("Pass", type="password")
            if st.form_submit_button("Login"):
                if st.secrets["passwords"].get(u) == p:
                    st.session_state.authenticated = True; st.session_state.username = u; st.rerun()
                else: st.error("Sai mật khẩu")
    
    st.markdown("---")
    
    # 2. Admin Info (BIO)
    with st.expander("👨‍⚕️ Về Chuyên Gia", expanded=True):
        st.markdown(f"""
        **{ADMIN_PROFILE['name']}** *{ADMIN_PROFILE['role']}*
        
        🎖️ {ADMIN_PROFILE['certs']}
        
        💬 **{ADMIN_PROFILE['contact']}**
        
        > *"{ADMIN_PROFILE['mission']}"*
        """)

# Thanh đếm lượt
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

# =====================================================
# 4. GIAO DIỆN HẾT HẠN (GIỮ NGUYÊN BẢN GỐC - KHÔNG SỬA)
# =====================================================
if is_limit_reached:
    if "hide_limit_modal" not in st.session_state:
        st.session_state.hide_limit_modal = False
    
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)

    if not st.session_state.hide_limit_modal:
        col_left, col_center, col_right = st.columns([1, 4, 1]) 
        with col_center:
            with st.container(border=True):
                c1, c2 = st.columns([9, 1])
                with c2:
                    if st.button("✕"):
                        st.session_state.hide_limit_modal = True
                        st.rerun()
                
                st.markdown("""
                    <div style="text-align: center;">
                        <div style="font-size: 60px; margin-bottom: 10px;">🧘‍♀️</div>
                        <h3 style="color: #00897b; margin: 0; font-weight: 800;">ĐÃ ĐẠT GIỚI HẠN!</h3>
                        <p style="color: #555; font-size: 15px; margin-top: 10px; line-height: 1.5;">
                            Hệ thống nhận thấy bạn đã dùng hết lượt thử. Hãy quay lại vào ngày mai<br>
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

                with st.form("login_form_limit"):
                    user_input = st.text_input("Tên đăng nhập")
                    pass_input = st.text_input("Mật khẩu", type="password")
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
        st.stop()

# =====================================================
# 7. XỬ LÝ CHAT CHÍNH (LOGIC PHẠT & REF MỚI)
# =====================================================
if not st.session_state.authenticated:
    st.markdown("""<div class="promo-banner"><div class="promo-text">🎁 Ưu đãi: Thảm Yoga + Tài khoản VIP giảm 30%!</div><a href="https://yogaismylife.vn/cua-hang/" class="promo-btn">Xem ngay</a></div>""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"], unsafe_allow_html=True)
st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

if prompt := st.chat_input(f"Hỏi {ADMIN_PROFILE['name']} về đau lưng, trị liệu..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(current_user)

    with st.chat_message("assistant"):
        with st.spinner(f"{ADMIN_PROFILE['name']} đang tra cứu hồ sơ y khoa..."):
            
            # Context History
            chat_history = ""
            for msg in st.session_state.messages[-4:]:
                clean_content = re.sub(r'<[^>]*>', '', msg['content'])
                chat_history += f"{msg['role']}: {clean_content}\n"

            # 1. Vector Search
            context_text = ""
            source_map = {}
            try:
                docs = db_text.similarity_search(prompt, k=6)
                if docs:
                    for i, d in enumerate(docs):
                        idx = i + 1
                        meta = d.metadata
                        type_label = "BẰNG CHỨNG KHOA HỌC" if 'SCIENCE' in meta.get('type','').upper() else "THAM KHẢO"
                        link = meta.get('url') or meta.get('source') or '#'
                        title = meta.get('title') or f"Source {idx}"
                        
                        raw_doi = meta.get("doi")
                        doi = raw_doi if raw_doi and raw_doi.lower() != "not provided" else extract_doi(d.page_content)
                        source_map[idx] = {
                        "id": idx,
                        "url": link,
                        "title": title,
                        "type": meta.get('type',''),
                        "doi": doi
                        }

                        doi_line = f"DOI: {doi}" if doi else "DOI: Not provided"

                        context_text += f"""
                        [Ref: {idx}] [{type_label}] ({title})
                        {doi_line}
                        {d.page_content}
                        """
            except: pass

            # 2. Gọi AI
            ai_raw = get_ai_response_custom(prompt, context_text, chat_history)

            # 3. Xử lý Kết quả (Logic Phạt)
            final_content = ""
            
            # --- A. TRƯỜNG HỢP VI PHẠM ---
            if ai_raw == "VIOLATION_DETECTED":
                st.session_state.bad_attempts += 1
                
                if st.session_state.bad_attempts >= 3:
                    # GHI VÀO SỔ ĐEN DATABASE -> KHÓA VĨNH VIỄN
                    ban_user_forever(current_user, "Spam/Hỏi sai chủ đề 3 lần")
                    st.session_state.is_blocked = True
                    msg = f"🚫 **TÀI KHOẢN ĐÃ BỊ KHÓA!**\n\nBạn đã cố tình hỏi sai chủ đề 3 lần. ID {current_user} đã bị đưa vào danh sách hạn chế vĩnh viễn."
                else:
                    # Cảnh cáo
                    left = 3 - st.session_state.bad_attempts
                    msg = f"⚠️ **CẢNH BÁO ({st.session_state.bad_attempts}/3)**\n\nTôi là **{ADMIN_PROFILE['name']}**. Tôi chỉ hỗ trợ chuyên môn về YOGA & SỨC KHỎE.\n\nVui lòng không hỏi về Xổ số, Code, Chính trị...\n*Bạn còn {left} lần thử trước khi bị khóa tài khoản.*"
                
                st.markdown(msg)
                final_content = msg
                # Nếu bị khóa -> Rerun để dính vào Chốt chặn ở đầu file
                if st.session_state.is_blocked:
                    time.sleep(3)
                    st.rerun()

            # --- B. TRƯỜNG HỢP LỖI ---
            elif ai_raw.startswith("ERR_SYS:"):
                st.error(f"Lỗi hệ thống: {ai_raw}")
                final_content = "Xin lỗi, hệ thống đang bảo trì."

                        # --- C. TRƯỜNG HỢP THÀNH CÔNG ---
            else:
                ref_ids = [int(m) for m in re.findall(r'\[Ref:?\s*(\d+)\]', ai_raw)]
                clean_text = re.sub(r'\[Ref:?\s*(\d+)\]', '', ai_raw).strip()

                for p in ["Nguồn tham khảo", "References", "📚 Tài liệu"]:
                    if p in clean_text:
                        clean_text = clean_text.split(p)[0].strip()
                        break

                unique_sources = {
                    source_map[rid]['url']: source_map[rid]
                    for rid in ref_ids
                    if rid in source_map and source_map[rid]['url'] != '#'
                }

                sources_html = ""
                if unique_sources:
                    sources_html += "\n\n---\n**📚 Nguồn tham khảo & Bằng chứng:**\n\n"
                    list_src = sorted(unique_sources.values(), key=lambda x: x['id'])

                    for info in list_src:
                        icon = "🧪" if 'SCIENCE' in info['type'].upper() else "🔗"
                        sources_html += f"- {icon} **[{info['id']}]** {info['title']}\n"

                        if info.get("doi"):
                            sources_html += f"  - DOI: `{info['doi']}`\n"

                        sources_html += f"  - Link: {info['url']}\n"

                upsell_html = ""
                recs = [
                    v for v in YOGA_SOLUTIONS.values()
                    if any(key in prompt.lower() for key in v['key'])
                ]

                if recs:
                    upsell_html += "<div class='upsell-box'><b>💡 Giải pháp gợi ý từ Chuyên gia:</b><br>"
                    for r in recs[:2]:
                        upsell_html += (
                            "<div style='margin-top:8px; display:flex; justify-content:space-between; align-items:center;'>"
                            f"<span style='color:#33691e; font-weight:500'>👉 {r['name']}</span>"
                            f"<a href='{r['url']}' target='_blank' class='upsell-btn'>Xem</a>"
                            "</div>"
                        )
                    upsell_html += "</div>"

                if any(
                    'SCIENCE' in source_map[rid]['type'].upper()
                    for rid in ref_ids
                    if rid in source_map
                ):
                    if not re.search(r'10\.\d{4,9}/', clean_text):
                        added = False
                        for rid in ref_ids:
                            doi = source_map.get(rid, {}).get("doi")
                            if doi:
                                clean_text += f"\n\n**Evidence DOI:** `{doi}`"
                                added = True
                                break

                        if not added:
                            clean_text += "\n\n⚠️ **No DOI available in provided scientific sources.**"

                final_content = clean_text

                st.markdown(final_content, unsafe_allow_html=True)
                if sources_html:
                    st.markdown(sources_html)
                if upsell_html:
                    st.markdown(upsell_html, unsafe_allow_html=True)

                final_content = final_content + "\n" + sources_html + "\n" + upsell_html


            # Lưu vào session
            if final_content:
                st.session_state.messages.append({"role": "assistant", "content": final_content})
