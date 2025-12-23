import streamlit as st
import gdown
import zipfile
import os
import sqlite3
import datetime
import gc
import time
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH TRANG & CSS (GIAO DIỆN)
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS Tùy chỉnh: Làm đẹp khung chat, ẩn header mặc định, thiết kế thẻ quảng cáo
st.markdown("""
<style>
    /* Ẩn Header mặc định của Streamlit */
    header[data-testid="stHeader"] {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    
    /* Nền trắng sạch sẽ */
    .stApp { background-color: #ffffff; }

    /* Khung Chat Input cố định dưới cùng */
    div[data-testid="stChatInput"] {
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        width: 90%;
        max-width: 800px;
        z-index: 1000;
        background-color: white;
        border-radius: 30px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        padding: 5px;
        border: 1px solid #e0e0e0;
    }
    
    /* Thanh Quảng Cáo (Banner) */
    .promo-banner {
        background: linear-gradient(90deg, #fff3e0 0%, #ffe0b2 100%);
        border-left: 5px solid #ff9800;
        padding: 12px 20px;
        margin-bottom: 25px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .promo-text { color: #e65100; font-weight: bold; font-size: 15px; }
    .promo-sub { color: #ef6c00; font-size: 13px; }
    .promo-btn {
        background-color: #ff9800; color: white !important;
        padding: 8px 16px; border-radius: 20px;
        text-decoration: none; font-weight: bold; font-size: 13px;
        box-shadow: 0 2px 5px rgba(230, 81, 0, 0.3);
        transition: all 0.3s;
    }
    .promo-btn:hover { background-color: #e65100; transform: translateY(-1px); }

    /* Giao diện tin nhắn */
    .stChatMessage { padding: 10px; border-radius: 10px; }
    div[data-testid="stMarkdownContainer"] p { font-size: 16px; line-height: 1.6; }
    
    /* Hộp nguồn tham khảo */
    .source-box {
        background-color: #f1f8e9;
        border: 1px solid #c5e1a5;
        border-radius: 10px;
        padding: 15px;
        margin-top: 15px;
        font-size: 0.9em;
    }
    .source-title { font-weight: bold; color: #33691e; margin-bottom: 8px; display: flex; align-items: center; gap: 5px; }
    .source-link { 
        display: block; margin-bottom: 6px; 
        text-decoration: none; color: #2e7d32; 
        font-weight: 500; transition: 0.2s;
    }
    .source-link:hover { color: #1b5e20; text-decoration: underline; }
    .tag-type { 
        font-size: 0.7em; padding: 2px 6px; border-radius: 4px; 
        margin-right: 8px; font-weight: bold; text-transform: uppercase;
    }
    .tag-science { background: #e3f2fd; color: #1565c0; border: 1px solid #bbdefb; }
    .tag-blog { background: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9; }

    /* Thanh giới hạn lượt dùng */
    .usage-bar-wrapper {
        position: fixed; top: 0; left: 0; width: 100%; height: 4px;
        background: #f0f0f0; z-index: 9999;
    }
    .usage-fill { height: 100%; background: linear-gradient(90deg, #4db6ac, #009688); transition: width 0.5s; }
    .usage-badge {
        position: fixed; top: 10px; right: 10px;
        background: rgba(255,255,255,0.95);
        padding: 4px 12px; border-radius: 15px;
        font-size: 12px; color: #00796b; font-weight: bold;
        border: 1px solid #b2dfdb; z-index: 10000;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 2. KHỞI TẠO NÃO BỘ (BACKEND)
# =====================================================
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    file_id = st.secrets["DRIVE_FILE_ID"]
    genai.configure(api_key=api_key)
except:
    st.error("❌ Lỗi: Chưa cấu hình secrets.toml (Thiếu API Key hoặc File ID)")
    st.stop()

# Đường dẫn file
ZIP_PATH = "/tmp/brain_data.zip"
EXTRACT_PATH = "/tmp/brain_data_extracted"
DB_PATH = "user_usage.db" # Database SQLite an toàn

@st.cache_resource
def load_brain_engine():
    """Tải và khởi động não bộ AI một lần duy nhất"""
    # 1. Tải file nếu chưa có
    if not os.path.exists(EXTRACT_PATH):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, ZIP_PATH, quiet=True)
            
            with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
                zip_ref.extractall(EXTRACT_PATH)
            
            # Dọn dẹp RAM ngay lập tức
            if os.path.exists(ZIP_PATH): os.remove(ZIP_PATH)
            gc.collect()
        except Exception as e:
            return None, None, f"Lỗi tải dữ liệu: {str(e)}"

    # 2. Tìm file FAISS
    vector_path = None
    for root, dirs, files in os.walk(EXTRACT_PATH):
        for file in files:
            if file.endswith(".faiss"):
                vector_path = root
                break
        if vector_path: break
    
    if not vector_path:
        return None, None, "Không tìm thấy file vector (.faiss)"

    # 3. Load Model
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        vector_db = FAISS.load_local(vector_path, embeddings, allow_dangerous_deserialization=True)
        chat_model = genai.GenerativeModel('gemini-flash-latest')
        return vector_db, chat_model, "OK"
    except Exception as e:
        return None, None, f"Lỗi khởi động AI: {str(e)}"

db, model, status = load_brain_engine()

if status != "OK":
    st.warning(f"⚠️ Đang bảo trì hệ thống não bộ: {status}. Vui lòng thử lại sau 1 phút.")
    st.stop()

# =====================================================
# 3. QUẢN LÝ USER & DATABASE (CHỐNG SẬP)
# =====================================================
def init_db():
    """Tạo database SQLite nếu chưa có"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tạo bảng: user_id | ngày | số lần dùng
    c.execute('''CREATE TABLE IF NOT EXISTS usage 
                 (user_id TEXT, date TEXT, count INTEGER, PRIMARY KEY (user_id, date))''')
    conn.commit()
    conn.close()

def check_usage(user_id):
    """Kiểm tra số lượt đã dùng hôm nay"""
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT count FROM usage WHERE user_id=? AND date=?", (user_id, today))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def increment_usage(user_id):
    """Tăng số lượt dùng lên 1"""
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Thử insert, nếu trùng (đã có hôm nay) thì update
    c.execute("INSERT OR IGNORE INTO usage (user_id, date, count) VALUES (?, ?, 0)", (user_id, today))
    c.execute("UPDATE usage SET count = count + 1 WHERE user_id=? AND date=?", (user_id, today))
    conn.commit()
    conn.close()

# Khởi tạo DB khi chạy app
init_db()

# Lấy ID người dùng (Nếu chưa đăng nhập thì dùng IP giả lập)
def get_user_key():
    if st.session_state.get("authenticated"):
        return st.session_state.username
    # Lấy IP để giới hạn khách vãng lai
    try:
        from streamlit.web.server.websocket_headers import _get_headers
        headers = _get_headers()
        return headers.get("X-Forwarded-For", "guest_unknown").split(",")[0]
    except:
        return "guest_unknown"

# =====================================================
# 4. LOGIC CHÍNH (SESSION & AUTH)
# =====================================================
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "messages" not in st.session_state: 
    st.session_state.messages = [{"role":"assistant", "content":"Namaste! 🙏 Tôi là AI Yoga. Bạn đang gặp vấn đề gì (đau lưng, mất ngủ, hay cần lộ trình tập)?"}]

user_id = get_user_key()
used_count = check_usage(user_id)

# Cấu hình giới hạn
LIMIT = 30 if st.session_state.authenticated else 5
can_chat = used_count < LIMIT

# Hiển thị thanh tiến trình sử dụng
percent = min(100, int((used_count / LIMIT) * 100))
st.markdown(f"""
    <div class="usage-bar-wrapper"><div class="usage-fill" style="width: {percent}%;"></div></div>
    <div class="usage-badge">⚡ {used_count}/{LIMIT} lượt</div>
""", unsafe_allow_html=True)

# =====================================================
# D. XỬ LÝ CHAT LOGIC (Strict Citation Mode V2)
# =====================================================
if prompt := st.chat_input("Hỏi về nghiên cứu, bệnh lý, bài tập..."):
    # 1. Hiển thị tin nhắn user
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    increment_usage(user_id)

    with st.chat_message("assistant"):
        with st.spinner("🔍 Đang đối chiếu các nghiên cứu RCT & Meta-Analysis..."):
            try:
                # BƯỚC 1: Tìm kiếm có chấm điểm (Score)
                # k=10 là đủ, lấy nhiều quá sẽ bị loãng
                docs_and_scores = db.similarity_search_with_score(prompt, k=10)
                
                # BƯỚC 2: Lọc nhiễu (Quan trọng!)
                # Score càng thấp càng giống. Thường < 1.0 là ổn, < 0.8 là rất tốt.
                # Ta chỉ lấy những tài liệu có liên quan thực sự.
                qualified_docs = []
                for doc, score in docs_and_scores:
                    if score < 1.2: # Ngưỡng lọc (tùy chỉnh nếu cần chặt hơn thì giảm xuống 1.0)
                        qualified_docs.append(doc)
                
                if not qualified_docs:
                    st.warning("⚠️ Không tìm thấy nghiên cứu nào trong dữ liệu khớp với câu hỏi này.")
                    st.stop()

                # BƯỚC 3: Xây dựng Context có đánh số ID
                context_text = ""
                source_map = {} # Map từ ID -> Thông tin Link
                
                for i, d in enumerate(qualified_docs):
                    doc_id = i + 1
                    url = d.metadata.get('url', '#')
                    title = d.metadata.get('title', 'Tài liệu không tên')
                    type_ = d.metadata.get('type', 'blog')
                    
                    # Lưu mapping
                    source_map[doc_id] = {
                        "url": url,
                        "title": title,
                        "type": type_
                    }
                    
                    # Nhồi vào context cho AI đọc
                    context_text += f"""
                    --- TÀI LIỆU SỐ [{doc_id}] ---
                    Tiêu đề: {title}
                    Nội dung: {d.page_content}
                    ---------------------------
                    """

                # BƯỚC 4: Prompt "Khóa mõm" (Strict Prompt)
                sys_prompt = f"""
                Bạn là Trợ lý Nghiên cứu Khoa học Yoga (Evidence-Based Yoga).
                Nhiệm vụ: Trả lời câu hỏi dựa trên các "TÀI LIỆU SỐ" được cung cấp bên dưới.
                
                QUY TẮC BẮT BUỘC:
                1. Mọi thông tin đưa ra phải lấy từ tài liệu. KHÔNG ĐƯỢC BỊA.
                2. Cuối mỗi ý hoặc đoạn văn, PHẢI ghi chú nguồn gốc bằng cách viết: [Nguồn: X] (với X là số thứ tự tài liệu).
                   Ví dụ: "Yoga giúp giảm huyết áp tâm thu [Nguồn: 1], và cải thiện giấc ngủ [Nguồn: 2]."
                3. Nếu câu hỏi không có trong tài liệu, hãy trả lời: "Dữ liệu hiện tại chưa có nghiên cứu về vấn đề này."
                4. Phong cách: Khoa học, khách quan, trích dẫn cụ thể.
                5. Độ dài tối đa không quá 200 từ.

                DỮ LIỆU ĐẦU VÀO:
                {context_text}
                
                CÂU HỎI CỦA NGƯỜI DÙNG: "{prompt}"
                """
                
                # Gọi Gemini
                response = model.generate_content(sys_prompt)
                ai_raw_text = response.text

                # BƯỚC 5: Hậu xử lý - Chỉ hiện Link mà AI thực sự dùng
                # Logic: Quét xem AI đã viết "[Nguồn: 1]", "[Nguồn: 2]" nào thì hiện link đó.
                used_sources = set()
                
                # Thay thế [Nguồn: X] thành icon nhỏ đẹp hơn trong văn bản
                final_text = ai_raw_text
                import re
                
                # Tìm tất cả các số X trong chuỗi "[Nguồn: X]"
                matches = re.findall(r'\[Nguồn: (\d+)\]', ai_raw_text)
                for m in matches:
                    doc_id = int(m)
                    if doc_id in source_map:
                        used_sources.add(doc_id)
                        # Tạo hiệu ứng highlight nhỏ trong văn bản (tùy chọn)
                        # final_text = final_text.replace(f"[Nguồn: {doc_id}]", f" **(Ref.{doc_id})**")

                # Hiển thị câu trả lời
                st.markdown(final_text)
                
                # Hiển thị Link (Chỉ những link có trong used_sources)
                if used_sources:
                    st.markdown("---")
                    st.markdown("#### 📚 Tài liệu tham khảo & Kiểm chứng:")
                    
                    # Sắp xếp để hiện theo thứ tự 1, 2, 3...
                    sorted_ids = sorted(list(used_sources))
                    
                    for doc_id in sorted_ids:
                        info = source_map[doc_id]
                        if len(str(info['url'])) > 5: # Chỉ hiện nếu có link thật
                            tag_label = "NGHIÊN CỨU RCT" if info['type'] == 'science' else "BÀI VIẾT CHUYÊN GIA"
                            tag_color = "#e3f2fd" if info['type'] == 'science' else "#e8f5e9"
                            text_color = "#1565c0" if info['type'] == 'science' else "#2e7d32"
                            
                            st.markdown(f"""
                            <div style="margin-bottom:8px; background: {tag_color}; padding: 8px; border-radius: 8px; border-left: 4px solid {text_color};">
                                <span style="font-weight:bold; font-size:0.8em; color:{text_color}; margin-right:5px;">[{doc_id}] {tag_label}</span>
                                <a href="{info['url']}" target="_blank" style="text-decoration:none; color:#333; font-weight:500;">
                                    {info['title']}
                                </a>
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    # Trường hợp AI trả lời nhưng quên trích dẫn (Hiếm gặp với prompt này)
                    # Ta có thể hiện fallback 3 link đầu tiên có độ khớp cao nhất
                    if len(qualified_docs) > 0:
                        st.markdown("---")
                        st.caption("Các nguồn có liên quan nhất (AI tổng hợp):")
                        for i in range(min(3, len(qualified_docs))):
                            info = source_map[i+1]
                            st.markdown(f"- [{info['title']}]({info['url']})")

                # Lưu lịch sử
                st.session_state.messages.append({"role": "assistant", "content": final_text})

            except Exception as e:
                st.error(f"Lỗi xử lý: {str(e)}")
