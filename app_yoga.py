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
# 1. CẤU HÌNH TRANG & GIAO DIỆN (STYLE APP 7 + UPSELL APP 5)
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Ẩn Header/Footer mặc định */
    header[data-testid="stHeader"], footer, .stDeployButton {display: none !important;}

    /* Khung chat (App 7) */
    div[data-testid="stChatInput"] {
        position: fixed; bottom: 10px; left: 50%; transform: translateX(-50%);
        width: 95%; max-width: 800px; z-index: 1000;
        background-color: white; border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08); padding: 5px; border: 1px solid #e0e0e0;
    }
    
    /* Banner (App 7) */
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
    
    /* Link tham khảo (App 7) - Style đẹp */
    .ref-link { 
        color: #00796b; font-weight: bold; text-decoration: none; 
        background: #e0f2f1; padding: 2px 8px; border-radius: 12px; margin: 0 2px;
        font-size: 0.85em; border: 1px solid #b2dfdb; display: inline-flex; align-items: center; gap: 4px;
    }
    .ref-link:hover { background: #b2dfdb; transform: translateY(-1px); }
    
    /* Upsell Box (Tích hợp từ App 5) */
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
# 2. DỮ LIỆU UPSELL (TỪ APP 5 - GIẢI PHÁP)
# =====================================================
YOGA_SOLUTIONS = {
    "QUY_TRINH": {"name": "🗺️ Lộ trình Trị Liệu 8 Bước", "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/", "key": ["đau","bệnh","trị liệu","phục hồi","lưng","gối","cột sống","thoát vị","tim mạch","huyết áp","mất ngủ","cổ vai gáy","pain","therapy","recovery","back","knee","spine","herniated","heart","blood pressure","insomnia"]},
    "AI_COACH": {"name": "🤖 AI Coach Chỉnh Tư Thế", "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/", "key": ["tập đúng","sai kỹ thuật","kỹ thuật","định tuyến","chỉnh dáng","hướng dẫn","căn chỉnh","bắt đầu","correct","form","alignment","technique","guide"]},
    "KHOA_HOC": {"name": "🎓 Khóa Đào Tạo HLV", "url": "https://yogaismylife.vn/dao-tao-hlv/", "key": ["huấn luyện viên","dạy yoga","bằng cấp","chứng chỉ","nghề yoga","teacher","training","certification","career"]}
}

# =====================================================
# 3. KẾT NỐI DATA (CHỈ LOAD NÃO CHỮ, BỎ NÃO ẢNH)
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Chưa cấu hình secrets.toml")
    st.stop()

ZIP_PATH = "/tmp/brain_data_v3.zip" 
EXTRACT_PATH = "/tmp/brain_data_extracted_v5"
DB_PATH = "user_usage.db"

# =====================================================
# HÀM LOAD SIÊU CẤP (FIX LỖI FILE LỚN GOOGLE DRIVE)
# =====================================================
# Thêm import gc ở đầu file cùng các import khác
import gc 

# ... (Các đoạn code khác giữ nguyên)

# Thay thế hàm load_brain_engine_safe cũ bằng hàm này:
@st.cache_resource
def load_brain_engine_safe():
    # 1. Tải và giải nén
    if not os.path.exists(EXTRACT_PATH):
        try:
            if not os.path.exists("/tmp"): os.makedirs("/tmp")
            
            # Xóa file lỗi cũ
            if os.path.exists(ZIP_PATH): os.remove(ZIP_PATH)
            
            with st.spinner(f"Đang tải dữ liệu (Step 1/3)..."):
                url = f'https://drive.google.com/uc?id={file_id}'
                gdown.download(url, ZIP_PATH, quiet=False, fuzzy=True)
            
            # Check zip
            if not zipfile.is_zipfile(ZIP_PATH):
                return None, "Lỗi: File tải về không phải ZIP"

            with st.spinner("Đang giải nén (Step 2/3)..."):
                with zipfile.ZipFile(ZIP_PATH, 'r') as z: 
                    z.extractall(EXTRACT_PATH)
            
            # --- TỐI ƯU RAM: XÓA NGAY FILE ZIP ---
            os.remove(ZIP_PATH) 
            gc.collect() # Dọn sạch bộ nhớ đệm ngay lập tức
            
        except Exception as e: return None, f"Lỗi tải/giải nén: {str(e)}"
    
    # 2. Tìm đường dẫn
    def find_db_path(target_folder_name):
        for root, dirs, files in os.walk(EXTRACT_PATH):
            if target_folder_name in dirs:
                check_path = os.path.join(root, target_folder_name)
                if "index.faiss" in os.listdir(check_path): return check_path
        return None

    text_db_path = find_db_path("vector_db")
    if not text_db_path: return None, "Không tìm thấy vector_db"

    # 3. Load Vector DB
    try:
        with st.spinner("Đang nạp não vào bộ nhớ (Step 3/3)..."):
            embeddings = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001", 
                google_api_key=api_key
            )
            
            # Load DB
            db_text = FAISS.load_local(text_db_path, embeddings, allow_dangerous_deserialization=True)
            
            # --- TỐI ƯU RAM CUỐI CÙNG ---
            # Xóa biến embeddings trung gian nếu không dùng nữa (Langchain lưu nó trong db_text rồi)
            # del embeddings 
            gc.collect()
            
        return db_text, "OK"
    except Exception as e: return None, f"Lỗi nạp não: {str(e)}"

with st.spinner("Đang khởi động hệ thống siêu trí tuệ..."):
    data_result, status = load_brain_engine_safe()

if status != "OK": st.error(f"Lỗi: {status}"); st.stop()
db_text = data_result # Chỉ lấy não chữ

# =====================================================
# 4. HÀM AI THÔNG MINH (ĐA NGÔN NGỮ & SỐ LIỆU)
# =====================================================
def get_ai_response_custom(prompt, context_text, history_context):
    try:
        # --- 1. THÔNG TIN CÁ NHÂN ---
        ADMIN_NAME = "An Nguyễn" 
        WEBSITE = "yogaismylife.vn"
        
        # --- 2. TÌM MODEL ---
        valid_model = 'models/gemini-1.5-flash'
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    if 'flash' in m.name.lower(): valid_model = m.name; break
        except: pass
        model = genai.GenerativeModel(valid_model)
        
        # --- 3. KIỂM TRA DỮ LIỆU ---
        data_instruction = "Dữ liệu tra cứu bên dưới."
        if not context_text.strip():
            data_instruction = "Không tìm thấy tài liệu cụ thể. Hãy trả lời dựa trên kiến thức chuyên gia YOGA chuẩn y khoa."
        
        # --- 4. SYSTEM PROMPT (PHIÊN BẢN SIẾT KỶ LUẬT SOURCE) ---
        sys_prompt = f"""
        ROLE: World-class Medical Yoga Expert & Researcher for **{WEBSITE}**.
        
        🌍 **LANGUAGE:**
        - User asks in English -> Reply in English.
        - User asks in Vietnamese -> Reply in Vietnamese.

        🎯 **STRICT CITATION RULES (TUÂN THỦ TUYỆT ĐỐI):**
        1. You are provided with context chunks labeled [Ref: 1], [Ref: 2], etc.
        2. **ACCURACY IS PARAMOUNT:** When you state a fact, you MUST check which [Ref: ID] it came from.
        3. **DO NOT MIX SOURCES:** If information is in [Ref: 1], do NOT cite [Ref: 2]. 
        4. If a fact is NOT in the provided [DATA], do NOT attach a [Ref].
        5. **Science First:** If the user asks for evidence, prioritize sources labeled [LOẠI: BẰNG CHỨNG KHOA HỌC].

        STRUCTURE:
        - Direct Answer.
        - Scientific Explanation (Biomechanics/Physiology).
        - **Specific Evidence:** "Research shows... [Ref: X]" (Make sure X is the CORRECT ID from the Data below).
        - Conclusion/Advice.

        [DATA (CONTEXT)]:
        {context_text}

        [HISTORY]:
        {history_context}

        USER QUESTION: "{prompt}"
        """
        
        response = model.generate_content(sys_prompt)
        return response.text.strip()
    except Exception as e:
        return f"ERR_SYS: {str(e)}"

# =====================================================
# 5. QUẢN LÝ DATABASE & SESSION
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
    r = c.fetchone(); conn.close()
    return r[0] if r else 0

def increment_usage(user_id):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO usage (user_id, date, count) VALUES (?, ?, 0)", (user_id, today))
    c.execute("UPDATE usage SET count = count + 1 WHERE user_id=? AND date=?", (user_id, today))
    conn.commit(); conn.close()

if "user_id" not in st.session_state: st.session_state.user_id = str(uuid.uuid4())[:8]
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "bad_attempts" not in st.session_state: st.session_state.bad_attempts = 0
if "is_blocked" not in st.session_state: st.session_state.is_blocked = False
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 I am your Medical Yoga Assistant. How can I help you today? (Tôi có thể hỗ trợ gì cho bạn?)"}]

current_user = st.session_state.username if st.session_state.authenticated else st.session_state.user_id
used = check_usage(current_user)
LIMIT = 50 if st.session_state.authenticated else 5
is_limit_reached = used >= LIMIT

# =====================================================
# 6. GIAO DIỆN & SIDEBAR
# =====================================================
with st.sidebar:
    st.title("🔐 VIP Access")
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

# Màn hình hết hạn
if is_limit_reached:
    if "hide_limit_modal" not in st.session_state: st.session_state.hide_limit_modal = False
    st.markdown("""<style>div[data-testid="stChatInput"] {display: none !important;}</style>""", unsafe_allow_html=True)
    if not st.session_state.hide_limit_modal:
        col_left, col_center, col_right = st.columns([1, 4, 1]) 
        with col_center:
            with st.container(border=True):
                c1, c2 = st.columns([9, 1])
                with c2:
                    if st.button("✕"): st.session_state.hide_limit_modal = True; st.rerun()
                st.markdown("""
                    <div style="text-align: center;">
                        <h3 style="color: #00897b;">LIMIT REACHED / HẾT LƯỢT!</h3>
                        <p>Contact Admin for VIP Access / Liên hệ Admin lấy mã:</p>
                        <a href="https://zalo.me/84963759566" target="_blank" style="display:inline-block;background:#009688;color:white;padding:10px 20px;border-radius:20px;text-decoration:none;">💬 Contact Zalo</a>
                    </div>
                """, unsafe_allow_html=True)
                with st.form("login_form_limit"):
                    u = st.text_input("User"); p = st.text_input("Password", type="password")
                    if st.form_submit_button("Login"):
                        if st.secrets["passwords"].get(u) == p:
                            st.session_state.authenticated = True; st.session_state.username = u; st.session_state.hide_limit_modal = True; st.rerun()
                        else: st.error("Wrong info")
        st.stop()

# =====================================================
# 7. XỬ LÝ CHAT CHÍNH (LOGIC MỚI: NO IMAGE, CLEAN REF, UPSELL)
# =====================================================
if not st.session_state.authenticated:
    st.markdown("""<div class="promo-banner"><div class="promo-text">🎁 Special Offer: Yoga Mats + VIP Account 30% OFF!</div><a href="https://yogaismylife.vn/cua-hang/" class="promo-btn">Shop Now</a></div>""", unsafe_allow_html=True)

# Hiển thị lịch sử
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

if st.session_state.is_blocked: st.error("🚫 ACCOUNT BLOCKED / TÀI KHOẢN BỊ KHÓA"); st.stop()

if prompt := st.chat_input("Ask about back pain, yoga poses... (Hỏi về đau lưng, tư thế...)"):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(current_user)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing 85M characters of medical data..."):
            
            # Lịch sử chat
            chat_history = ""
            for msg in st.session_state.messages[-4:]:
                clean_content = re.sub(r'<[^>]*>', '', msg['content'])
                chat_history += f"{msg['role']}: {clean_content}\n"

            # 1. Tìm kiếm (Vector Search) - Chỉ Text
            context_text = ""
            source_map = {}
            
            try:
                # Tìm 6 kết quả tốt nhất
                docs = db_text.similarity_search(prompt, k=6)
                
                if docs:
                    for i, d in enumerate(docs):
                        idx = i + 1
                        meta = d.metadata
                        
                        # Phân loại nguồn
                        doc_type = meta.get('type', 'general').upper()
                        type_label = ""
                        if 'SCIENCE' in doc_type: type_label = "LOẠI: BẰNG CHỨNG KHOA HỌC"
                        elif 'QA' in doc_type: type_label = "LOẠI: CHUYÊN GIA TƯ VẤN"
                        elif 'DEFINITION' in doc_type: type_label = "LOẠI: TỪ ĐIỂN"
                        
                        link = meta.get('url') or meta.get('source') or '#'
                        title = meta.get('title') or f"Source {idx}"
                        source_map[idx] = {"id": idx, "url": link, "title": title, "type": doc_type}

                        context_text += f"\n[Ref: {idx}] [{type_label}] (Source: {title}):\n{d.page_content}\n"
            except Exception as e:
                print(f"Search Error: {e}")

            # 2. Gọi AI
            ai_raw = get_ai_response_custom(prompt, context_text, chat_history)

            # 3. Xử lý kết quả & Hiển thị
            final_content_to_show = "" # Biến an toàn
            
            if "REFUSE_TOPIC" in ai_raw:
                st.session_state.bad_attempts += 1
                if st.session_state.bad_attempts >= 3:
                    st.session_state.is_blocked = True
                    msg = "🚫 BLOCKED: Off-topic questions detected."
                else:
                    msg = f"⚠️ I only answer Yoga & Health questions. (Warning {st.session_state.bad_attempts}/3)"
                
                st.markdown(msg)
                final_content_to_show = msg
                if st.session_state.is_blocked: st.stop()
            
            elif ai_raw.startswith("ERR_SYS:"):
                error_msg = f"System Error: {ai_raw}"
                st.error(error_msg)
                final_content_to_show = error_msg
            else:
                # A. Tách ID nguồn
                ref_ids = [int(m) for m in re.findall(r'\[Ref:?\s*(\d+)\]', ai_raw)]
                
                # B. Làm sạch văn bản (Xóa thẻ Ref, xóa phần nguồn tự viết của AI)
                clean_text = re.sub(r'\[Ref:?\s*(\d+)\]', '', ai_raw).strip()
                
                # Cắt bỏ phần "Nguồn tham khảo" do AI tự viết (nếu có)
                split_patterns = ["Nguồn tham khảo", "Tài liệu tham khảo", "References", "Sources", "📚 Tài liệu", "📚 Nguồn"]
                for p in split_patterns:
                    if p in clean_text:
                        clean_text = clean_text.split(p)[0].strip(); break

                # C. Tạo danh sách nguồn XỊN (Không lặp)
                unique_sources = {}
                for rid in ref_ids:
                    if rid in source_map:
                        src = source_map[rid]
                        if src['url'] != '#': unique_sources[src['url']] = src # Key theo URL để không lặp

                # D. Xây dựng HTML Nguồn
                # ... (Đoạn code cũ) ...
                # D. Xây dựng HTML Nguồn (CÓ HIỂN THỊ SỐ REF ID)
                sources_html = ""
                if unique_sources:
                    sources_html += "\n\n---\n**📚 References & Scientific Evidence:**\n\n"
                    science_links, expert_links, other_links = [], [], []
                    
                    # Sắp xếp theo ID để dễ tra cứu
                    sorted_sources = sorted(unique_sources.items(), key=lambda x: x[1]['id'])
                    
                    for url, info in sorted_sources:
                        rid = info['id'] # Lấy ID gốc (1, 2, 3...)
                        title = info['title']
                        # Thêm số [1], [2] vào trước link để đối chiếu
                        link_md = f"**[{rid}]** [{title}]({url})"
                        
                        if 'SCIENCE' in info['type']: science_links.append(f"- 🧪 {link_md}")
                        elif 'QA' in info['type']: expert_links.append(f"- 🚑 {link_md}")
                        else: other_links.append(f"- 🔗 {link_md}")

                    sources_html += "\n".join(science_links + expert_links + other_links)

                # E. Upsell Logic
                upsell_html = ""
                recs = [v for k,v in YOGA_SOLUTIONS.items() if any(key in prompt.lower() for key in v['key'])]
                if recs:
                    upsell_html += "<div class='upsell-box'><b>💡 Recommended Solutions:</b><br>"
                    for r in recs[:2]:
                        upsell_html += f"""
                        <div style="margin-top:8px; display:flex; justify-content:space-between; align-items:center;">
                            <span style="color:#33691e; font-weight:500">👉 {r['name']}</span>
                            <a href="{r['url']}" target="_blank" class="upsell-btn">View</a>
                        </div>
                        """
                    upsell_html += "</div>"
                
                # F. Hiển thị & Lưu
                final_content_to_show = clean_text
                st.markdown(final_content_to_show, unsafe_allow_html=True) # Bài viết
                if sources_html: st.markdown(sources_html) # Nguồn
                if upsell_html: st.markdown(upsell_html, unsafe_allow_html=True) # Upsell

                # Gộp để lưu history
                final_content_to_show = final_content_to_show + "\n" + sources_html + "\n" + upsell_html

            # Lưu vào session
            if final_content_to_show:
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": final_content_to_show
                })
