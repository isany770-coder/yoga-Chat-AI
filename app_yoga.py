import streamlit as st
import gdown
import zipfile
import os
import json
import datetime
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

# =====================================================
# 1. CẤU HÌNH TRANG
# =====================================================
st.set_page_config(
    page_title="Yoga Assistant Pro",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =====================================================
# 2. CẤU HÌNH "HỆ SINH THÁI GIẢI PHÁP" CỦA BÁC
# =====================================================
YOGA_SOLUTIONS = { 
    "QUY_TRINH_8_BUOC": {
        "name": "🗺️ Quy trình 8 Bước Toàn Diện",
        "url": "https://yogaismylife.vn/kiem-tra-suc-khoe-toan-dien/",
        "trigger": ["bắt đầu", "lộ trình", "người mới", "từ đầu", "cơ bản", "hướng dẫn", "bao lâu", "học yoga"]
    },
    "AI_COACH": {
        "name": "🤖 Gặp AI Coach 1:1 - Live",
        "url": "https://yogaismylife.vn/kiem-tra-tu-the-yoga/",
        "trigger": ["đau", "chấn thương", "mỏi", "bệnh", "trị liệu", "tư vấn riêng", "khó quá", "không tập được"]
    },
    "APP_THIEN_THO": {
        "name": "🧘 App Thiền & Hít Thở (Giảm Stress)",
        "url": "https://yogaismylife.vn/thien-hoi-tho-chua-lanh/",  # <--- Thay link thật của bác vào
        "trigger": ["stress", "căng thẳng", "mất ngủ", "lo âu", "thở", "thiền", "thư giãn", "mệt mỏi", "áp lực", "ngủ ngon"]
    }
}

# =====================================================
# 3. CSS GIAO DIỆN (NÂNG CẤP HIỂN THỊ GIẢI PHÁP)
# =====================================================
st.markdown("""
<style>
    /* ... (Giữ nguyên CSS cũ) ... */
    [data-testid="stAppViewContainer"], .stApp, html, body {
        background-color: white !important;
        color: #31333F !important;
    }
    
    /* STYLE CHO THẺ GIẢI PHÁP (SOLUTION CARD) */
    .solution-card {
        background: linear-gradient(135deg, #e0f2f1 0%, #b2dfdb 100%);
        border: 1px solid #009688;
        border-radius: 10px;
        padding: 12px;
        margin-top: 10px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .solution-text {
        font-size: 14px;
        color: #004d40;
        font-weight: bold;
    }
    .solution-btn {
        background-color: #00796b;
        color: white !important;
        padding: 6px 15px;
        border-radius: 20px;
        text-decoration: none;
        font-size: 12px;
        font-weight: bold;
        transition: 0.3s;
    }
    .solution-btn:hover {
        background-color: #004d40;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }

    /* Các thành phần cũ */
    .source-box { background-color: #f8f9fa; border-left: 4px solid #0f988b; padding: 12px; margin-top: 15px; border-radius: 0 8px 8px 0; font-size: 0.9em; }
    .tag-science { background-color: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: bold; margin-right: 6px; border: 1px solid #c7d2fe; }
    .tag-blog { background-color: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: bold; margin-right: 6px; border: 1px solid #bbf7d0; }
    .tag-qa { background-color: #fef9c3; color: #854d0e; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; font-weight: bold; margin-right: 6px; border: 1px solid #fde047; }
    
    /* Ẩn Header */
    [data-testid="stToolbar"], header, footer {display: none !important;}
    
    /* Input nổi */
    div[data-testid="stChatInput"] { position: fixed !important; bottom: 20px !important; left: 10px !important; right: 10px !important; z-index: 999999; background-color: white !important; border-radius: 25px !important; box-shadow: 0 -2px 10px rgba(0,0,0,0.1); padding: 5px !important; border: 1px solid #e0e0e0; }
    .main .block-container { padding-top: 2rem !important; padding-bottom: 200px !important; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 4. KẾT NỐI API & DRIVE
# =====================================================
# 👉 BÁC THAY ID FILE VECTOR MỚI VÀO ĐÂY
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
            with zipfile.ZipFile(OUTPUT_ZIP, 'r') as zip_ref:
                zip_ref.extractall("/tmp/")
            if os.path.exists(OUTPUT_ZIP): os.remove(OUTPUT_ZIP)
        except Exception as e:
            st.error(f"⚠️ Lỗi tải dữ liệu: {e}")
            return None, None
    
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        db = FAISS.load_local(EXTRACT_PATH, embeddings, allow_dangerous_deserialization=True)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return db, model
    except Exception as e:
        st.error(f"⚠️ Lỗi AI: {e}")
        return None, None

db, model = load_brain()

if db is None or model is None:
    st.warning("🧘‍♂️ Hệ thống đang khởi động, bác vui lòng vuốt xuống để tải lại (F5) nhé!")
    st.stop()

# =====================================================
# 5. LOGIC XÁC ĐỊNH GIẢI PHÁP (RECOMMENDER ENGINE)
# =====================================================
def get_recommended_solutions(user_query):
    """Hàm này soi câu hỏi của khách để gợi ý đồ chơi của bác"""
    query_lower = user_query.lower()
    recommendations = []
    
    for key, data in YOGA_SOLUTIONS.items():
        # Nếu từ khóa của giải pháp xuất hiện trong câu hỏi
        if any(trigger in query_lower for trigger in data["trigger"]):
            recommendations.append(data)
    
    # Giới hạn tối đa 2 giải pháp để không bị loãng
    return recommendations[:2]

# =====================================================
# 6. GIAO DIỆN CHAT & XỬ LÝ (NÂNG CẤP)
# =====================================================
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 Tôi là Trợ lý Yoga AI. Bác muốn kiểm tra tư thế, hỏi về lộ trình hay tìm hiểu kiến thức khoa học?"}]

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"], unsafe_allow_html=True)

if prompt := st.chat_input("Hỏi tôi về Yoga, tư thế, đau mỏi..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if db:
            # 1. Tìm kiếm dữ liệu
            docs = db.similarity_search(prompt, k=5)
            
            context_parts = []
            source_map = {}
            
            for i, d in enumerate(docs):
                dtype = d.metadata.get('type', 'general')
                title = d.metadata.get('title', 'Tài liệu')
                url = d.metadata.get('url', '#')
                
                label = "NGHIÊN CỨU" if dtype == 'science' else "CHUYÊN GIA" if dtype == 'qa' else "BÀI VIẾT"
                context_parts.append(f"--- NGUỒN {i+1}: [{label}] ---\nTiêu đề: {title}\nNội dung: {d.page_content}")
                
                if url != "#" and url is not None:
                    source_map[url] = {"title": title, "type": dtype}
            
            full_context = "\n\n".join(context_parts)

            # 2. Tìm Giải pháp đề xuất (Sản phẩm của bác)
            solutions = get_recommended_solutions(prompt)
            solution_context = ""
            if solutions:
                solution_names = ", ".join([s["name"] for s in solutions])
                solution_context = f"\nQUAN TRỌNG: Hãy khuyên người dùng sử dụng công cụ sau của chúng tôi: {solution_names}. Lồng ghép khéo léo vào câu trả lời."

            # 3. Prompt thông minh
            sys_prompt = f"""
            Bạn là Chuyên gia Yoga và Trị liệu cấp cao. Trả lời câu hỏi dựa trên DỮ LIỆU.
            
            DỮ LIỆU THAM KHẢO:
            {full_context}
            {solution_context}

            HƯỚNG DẪN TRẢ LỜI:
            1. **Phân tích:** Dùng [NGHIÊN CỨU] để giải thích cơ chế (nếu có).
            2. **Thực hành:** Dùng [CHUYÊN GIA] để chỉ lỗi sai và cách sửa.
            3. **Đề xuất:** Nếu câu hỏi liên quan đến kỹ thuật/lộ trình/đau, hãy GỢI Ý NGƯỜI DÙNG dùng công cụ của chúng tôi (như đã cung cấp ở trên) để được hỗ trợ tốt hơn.
            4. **Phong cách:** Ngắn gọn, súc tích, dùng icon.
            5. **An toàn:** Luôn nhắc lắng nghe cơ thể (Ahimsa).

            CÂU HỎI: "{prompt}"
            """
            
            try:
                with st.spinner("🧘 Đang phân tích kỹ thuật và tìm tài liệu..."):
                    response = model.generate_content(sys_prompt)
                    res_text = response.text
                
                # --- RENDER KẾT QUẢ ---
                
                # 1. Hiển thị Lời giải của AI
                st.markdown(res_text, unsafe_allow_html=True)
                
                # 2. Hiển thị "THẺ GIẢI PHÁP" (Đồ chơi của bác) - Nổi bật
                if solutions:
                    for sol in solutions:
                        st.markdown(f"""
                        <div class="solution-card">
                            <div class="solution-text">{sol['name']}</div>
                            <a href="{sol['url']}" target="_blank" class="solution-btn">Sử dụng ngay 🚀</a>
                        </div>
                        """, unsafe_allow_html=True)

                # 3. Hiển thị Nguồn tham khảo (Uy tín)
                if source_map:
                    links_html = "<div class='source-box'><strong>📚 Nguồn tham khảo uy tín:</strong><div style='margin-top:8px'>"
                    count = 0
                    for url, info in source_map.items():
                        if count >= 3: break
                        tag_html = ""
                        if info['type'] == 'science': tag_html = "<span class='tag-science'>KHOA HỌC</span>"
                        elif info['type'] == 'qa': tag_html = "<span class='tag-qa'>CHUYÊN GIA</span>"
                        else: tag_html = "<span class='tag-blog'>BÀI VIẾT</span>"
                        links_html += f"<div style='margin-bottom:6px'>{tag_html} <a href='{url}' target='_blank' style='text-decoration:none; color:#0f988b; font-weight:500'>{info['title']}</a></div>"
                        count += 1
                    links_html += "</div></div>"
                    st.markdown(links_html, unsafe_allow_html=True)
                    
                    # Lưu vào lịch sử (cả text + html thẻ)
                    full_content_to_save = res_text
                    # (Lưu ý: Không lưu HTML phức tạp vào history để tránh lỗi render lần sau, chỉ lưu text AI)
                    st.session_state.messages.append({"role": "assistant", "content": res_text})
                
            except Exception as error:
                st.error(f"Hệ thống đang quá tải: {error}")
