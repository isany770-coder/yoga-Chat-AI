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
# 2. CSS GIAO DIỆN (ĐÃ FIX LỖI MẤT CHỮ QUẢNG CÁO)
# =====================================================
st.markdown("""
<style>
    /* Reset nền trắng & chữ đen */
    [data-testid="stAppViewContainer"], .stApp, html, body {
        background-color: white !important;
        color: #31333F !important;
    }
    /* Ép màu chung (nhưng chừa thằng quảng cáo ra) */
    p, h1, h2, h3, h4, h5, h6, label, li {
        color: #31333F !important;
    }
    
    /* Ẩn header mặc định */
    [data-testid="stToolbar"], header, footer, .stAppDeployButton {
        display: none !important;
    }

    /* THANH CHAT INPUT (NỔI) */
    div[data-testid="stChatInput"] {
        position: fixed !important;
        bottom: 20px !important;
        left: 10px !important;
        right: 10px !important;
        width: auto !important;
        z-index: 999999;
        background-color: white !important;
        border-radius: 25px !important;
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
        padding: 5px !important;
        border: 1px solid #e0e0e0;
        transition: bottom 0.3s ease;
    }
    
    textarea[data-testid="stChatInputTextArea"] {
        font-size: 16px !important;
        color: #333333 !important;
        background-color: #f0f2f6 !important;
        border-radius: 20px !important;
    }

    /* FIX LỖI BÀN PHÍM CHE INPUT */
    @media (max-height: 500px) {
        div[data-testid="stChatInput"] {
            bottom: 0px !important;
            border-radius: 0 !important;
            border-bottom: none !important;
        }
        .ad-banner { display: none !important; } /* Ẩn quảng cáo khi gõ phím */
        .usage-bar-container, .usage-text { display: none !important; }
    }

    /* --- CSS QUẢNG CÁO (FIX MẠNH MẼ) --- */
    .ad-banner {
        position: fixed;
        bottom: 85px;
        left: 15px;
        right: 15px;
        background: linear-gradient(90deg, #fff3e0 0%, #ffe0b2 100%);
        border: 1px solid #ffcc80;
        border-radius: 12px;
        padding: 10px 15px;
        z-index: 999990;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        animation: slideUp 0.5s ease-out;
    }
    
    /* Ép màu chữ cam đậm cho nội dung quảng cáo */
    .ad-content, .ad-content span {
        font-size: 14px !important;
        font-weight: 700 !important;
        color: #e65100 !important; /* Màu cam đậm */
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .ad-btn {
        background: #e65100;
        color: white !important;
        padding: 6px 15px;
        border-radius: 20px;
        font-size: 12px;
        text-decoration: none;
        font-weight: bold;
        white-space: nowrap;
        box-shadow: 0 2px 5px rgba(230, 81, 0, 0.3);
    }

    /* Animation */
    @keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

    /* CÁC THÀNH PHẦN KHÁC */
    .main .block-container { padding-top: 3rem !important; padding-bottom: 250px !important; }
    div[data-testid="stChatMessage"] { background-color: #f8f9fa !important; border: 1px solid #eee; }
    div[data-testid="stChatMessage"][data-test-role="user"] { background-color: #e3f2fd !important; }
    
    .usage-bar-container { position: fixed; top: 0; left: 0; width: 100%; height: 5px; background-color: #f0f0f0; z-index: 1000000; }
    .usage-bar-fill { height: 100%; background: linear-gradient(90deg, #0f988b 0%, #14b8a6 100%); }
    .usage-text { position: fixed; top: 10px; right: 15px; background: rgba(255,255,255,0.9); padding: 4px 12px; border-radius: 20px; font-size: 11px; color: #0f988b !important; font-weight: bold; border: 1px solid #0f988b; z-index: 1000001; }

    .zalo-btn { display: flex !important; align-items: center; justify-content: center; width: 100%; background-color: white; color: #0f988b !important; border: 1px solid #dcdfe3; border-radius: 8px; font-weight: 500; font-size: 14px; height: 45px !important; text-decoration: none !important; margin: 0 !important; }
    div[data-testid="stForm"] button { height: 45px !important; border-radius: 8px !important; font-weight: 500 !important; color: #31333F !important; }

    /* MODAL HẾT LƯỢT */
    .limit-modal { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); z-index: 2147483647 !important; display: flex; align-items: center; justify-content: center; flex-direction: column; }
    .limit-box { background: white; padding: 40px; border-radius: 25px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); text-align: center; max-width: 90%; width: 400px; border: 2px solid #0f988b; }
    .limit-btn { background: linear-gradient(135deg, #0f988b, #14b8a6); color: white !important; padding: 12px 35px; border-radius: 50px; text-decoration: none; font-weight: bold; display: inline-block; margin-top: 15px; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# 3. KẾT NỐI API & GOOGLE DRIVE
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
    # 1. Kiểm tra folder não bộ đã có chưa để tránh tải lại vô ích trên Mobile
    if not os.path.exists(EXTRACT_PATH):
        try:
            gdown.download(URL_DRIVE, OUTPUT_ZIP, quiet=True)
            with zipfile.ZipFile(OUTPUT_ZIP, 'r') as zip_ref:
                zip_ref.extractall("/tmp/")
            # Xóa file zip ngay để nhẹ máy Mobile
            if os.path.exists(OUTPUT_ZIP):
                os.remove(OUTPUT_ZIP)
        except Exception as e:
            # Nếu lỗi, hiện thông báo thay vì để trắng trang
            st.error(f"⚠️ Lỗi tải dữ liệu: {e}")
            return None, None
    
    # 2. Khởi tạo AI với đúng bản của bác
    try:
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004", 
            google_api_key=api_key
        )
        db = FAISS.load_local(
            EXTRACT_PATH, 
            embeddings, 
            allow_dangerous_deserialization=True
        )
        # GIỮ NGUYÊN BẢN AI CỦA BÁC
        model = genai.GenerativeModel('gemini-flash-latest')
        
        return db, model
    except Exception as e:
        st.error(f"⚠️ Lỗi AI: {e}")
        return None, None

# Gọi hàm
db, model = load_brain()

# 3. CHỐNG TRẮNG TRANG: Nếu db hoặc model lỗi, dừng app và báo khách F5
if db is None or model is None:
    st.warning("🧘‍♂️ Hệ thống đang khởi động, bác vui lòng vuốt xuống để tải lại (F5) nhé!")
    st.stop()
    
def get_remote_ip():
    """Lấy địa chỉ IP thật của người dùng trên Streamlit Cloud"""
    try:
        from streamlit.web.server.websocket_headers import _get_headers
        headers = _get_headers()
        # Streamlit Cloud dùng proxy nên IP thật nằm ở 'X-Forwarded-For'
        ip = headers.get("X-Forwarded-For")
        if ip:
            return ip.split(",")[0].strip()
    except:
        pass
    return "guest_unknown"

# =====================================================
# 4. QUẢN LÝ DATABASE
# =====================================================
USAGE_DB_FILE = "/tmp/usage_history_db.json"
DAILY_LIMIT = 25
TRIAL_LIMIT = 10

def get_data():
    if not os.path.exists(USAGE_DB_FILE): return {}
    try:
        with open(USAGE_DB_FILE, "r") as f: return json.load(f)
    except: return {}

def save_data(data):
    with open(USAGE_DB_FILE, "w") as f: json.dump(data, f)

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""

# Nếu chưa đăng nhập, dùng IP làm định danh để chặn lách luật bằng tab ẩn danh
user_key = st.session_state.username if st.session_state.authenticated else get_remote_ip()
today = str(datetime.date.today())
db_data = get_data()

if user_key not in db_data or db_data[user_key].get("date") != today:
    db_data[user_key] = {
        "date": today,
        "count": 0,
        "history": [{"role":"assistant","content":"Namaste! 🙏 Thật vui được gặp bạn. Hôm nay chúng ta sẽ bắt đầu từ đâu?"}]
    }
    save_data(db_data)

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
# 5. HIỂN THỊ CHAT, QUẢNG CÁO & ADMIN
# =====================================================
can_chat = used < limit

# --- QUẢNG CÁO (BẢN MÔNG MÁ - ĐẸP & CHUYÊN NGHIỆP) ---
if not st.session_state.authenticated:
    st.markdown(f"""
    <div style="position: fixed; bottom: 80px; left: 15px; right: 15px; 
                background: #fff5f0; 
                border: 1px solid #ffccbc; border-radius: 15px; 
                padding: 10px 15px; z-index: 99999; 
                display: flex; align-items: center; justify-content: space-between;
                box-shadow: 0 4px 15px rgba(255, 87, 34, 0.1);">
        <div style="display: flex; align-items: center; gap: 10px;">
            <div style="background: #ff7043; width: 32px; height: 32px; border-radius: 50%; 
                        display: flex; align-items: center; justify-content: center;">
                <span style="font-size: 16px;">🎁</span>
            </div>
            <div>
                <div style="color: #bf360c !important; font-size: 13px; font-weight: bold; font-family: sans-serif;">
                    Combo Thảm & Freeship!!
                </div>
                <div style="color: #ff7043 !important; font-size: 11px; font-family: sans-serif;">
                    Giảm ngay 30% hôm nay!
                </div>
            </div>
        </div>
        <a href="https://yogaismylife.vn/cua-hang/" target="_blank" 
           style="background: #ff7043; color: white !important; 
                  padding: 8px 15px; border-radius: 10px; 
                  text-decoration: none; font-weight: bold; font-size: 12px;
                  transition: all 0.3s; box-shadow: 0 2px 5px rgba(255, 112, 67, 0.3);">
            Xem ngay
        </a>
    </div>
    """, unsafe_allow_html=True)

# --- ADMIN VIEW ---
if st.session_state.authenticated and st.session_state.username == "admin":
    st.info("🕵️ **CHẾ ĐỘ ADMIN: SOI LOG CHAT**")
    if st.button("🔄 Cập nhật Log"):
        st.rerun()
    if "anonymous_guest" in db_data:
        anon_hist = db_data["anonymous_guest"]["history"]
        with st.expander(f"👥 Khách vãng lai ({len(anon_hist)} tin nhắn)", expanded=True):
            for msg in reversed(anon_hist):
                if msg['role'] == 'user':
                    st.write(f"👤 **Khách:** {msg['content']}")
                else:
                    st.caption(f"🤖 AI: {msg['content'][:50]}...")
                st.divider()

# --- CHAT HISTORY ---
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"], unsafe_allow_html=True)

# --- MODAL HẾT LƯỢT (BẢN NÂNG CẤP BÁN HÀNG) ---
if not can_chat:
    st.markdown(f"""
    <div class="limit-modal">
        <div class="limit-box">
            <div style="font-size:50px;margin-bottom:10px">🧘‍♀️</div>
            <div style="font-size:20px;font-weight:bold;color:#0f988b">Đã đạt giới hạn tra cứu miễn phí!</div>
            <p style="color:#555;margin:15px 0">
                Hệ thống nhận thấy bạn đã sử dụng hết lượt dùng thử cho kết nối này.<br><br>
                Để tiếp tục tra cứu <b>Kho dữ liệu 15 triệu từ</b> được bác sĩ kiểm duyệt và nhận ưu đãi <b>Mua Thảm tặng Tài khoản Member</b>, mời bạn liên hệ Admin:
            </p>
            <a href="https://zalo.me/84963759566" target="_blank" class="limit-btn">💬 Nhận mã kích hoạt qua Zalo</a>
            <p style="font-size:11px; color:#999; margin-top:10px;">(Hoặc đăng nhập nếu bạn đã là Member ở phía dưới)</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# --- INPUT & XỬ LÝ ---
if prompt := st.chat_input("Hỏi chuyên gia Yoga..."):
    db_data[user_key]["count"] += 1
    db_data[user_key]["history"].append({"role": "user", "content": prompt})
    save_data(db_data)
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if db:
            # Tăng k=7 để quét rộng hơn, dễ tìm thấy các bài RCT/Meta nằm sâu
            docs = db.similarity_search(prompt, k=7)
            source_map = {}
            context_parts = []
            
            for i, d in enumerate(docs):
                u = d.metadata.get('url', '#')
                t = d.metadata.get('title', 'Tài liệu')
                # Dán nhãn để AI biết bài nào là nghiên cứu
                context_parts.append(f"--- NGUỒN {i+1} ---\nTIÊU ĐỀ: {t}\nLINK: {u}\nNỘI DUNG: {d.page_content}")
                source_map[u] = t
            
            context_string = "\n\n".join(context_parts)
            
            sys_prompt = (
                f"Bạn là chuyên gia Yoga Y khoa. Hãy trả lời dựa trên DỮ LIỆU NGUỒN.\n"
                f"1. ƯU TIÊN CAO NHẤT: Nếu trong nguồn có các nghiên cứu RCT, Meta-analysis hoặc bằng chứng lâm sàng, hãy trình bày chúng lên đầu.\n"
                f"2. Trình bày bằng GẠCH ĐẦU DÒNG, rõ ràng, dễ đọc.\n"
                f"3. Cuối bài, trích xuất đúng Link URL của bài viết bạn đã dùng theo cú pháp: 'LINK_CHỌN: [Dán URL]'.\n\n"
                f"DỮ LIỆU NGUỒN:\n{context_string}\n\n"
                f"CÂU HỎI: {prompt}"
            )
            
            try:
                with st.spinner("🧘 Chuyên gia đang phân tích dữ liệu nghiên cứu..."):
                    response = model.generate_content(sys_prompt)
                    res_text = response.text
                
                import re
                found_links = re.findall(r'LINK_CHỌN:\s*(https?://[^\s\n]+)', res_text)
                clean_res = re.sub(r'LINK_CHỌN:.*', '', res_text).strip()

                links_html = ""
                # Lấy link AI chọn, nếu không thấy thì lấy 2 link đầu từ kết quả tìm kiếm cho chắc
                final_links = list(set([l for l in found_links if l in source_map]))
                if not final_links and source_map:
                    final_links = list(source_map.keys())[:2]

                if final_links:
                    links_html += "<br><hr><b>📚 Bằng chứng khoa học liên quan:</b><ul style='list-style:none;padding:0'>"
                    for url in final_links:
                        title = source_map.get(url, "Xem chi tiết nghiên cứu")
                        links_html += f"<li style='margin-bottom:5px'>🔗 <a href='{url}' target='_blank' style='color:#0f988b;text-decoration:none;font-weight:600'>{title}</a></li>"
                    links_html += "</ul>"
                
                # FIX LỖI: Tạo biến final_res ở đây
                final_res_to_display = clean_res + links_html
                st.markdown(final_res_to_display, unsafe_allow_html=True)
                
                # Lưu vào lịch sử
                db_data[user_key]["history"].append({"role": "assistant", "content": final_res_to_display})
                save_data(db_data)
                
            except Exception as e:
                st.error(f"Lỗi hệ thống: {e}")

# =====================================================
# 6. LOGIN FORM
# =====================================================
if not st.session_state.authenticated:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🔐 Đăng nhập / Lấy thêm lượt (Dành cho Member)", expanded=not can_chat):
        with st.form("login_form"):
            u = st.text_input("Tên đăng nhập", placeholder="Username")
            p = st.text_input("Mật khẩu", type="password", placeholder="Password")
            
            st.write("")
            c1, c2 = st.columns(2)
            with c1:
                submit = st.form_submit_button("Đăng nhập", use_container_width=True)
            with c2:
                st.markdown(f"""<div style="margin-top:0px;"><a href="https://zalo.me/84963759566" target="_blank" style="text-decoration:none;"><div class="zalo-btn">💬 Lấy TK Zalo</div></a></div>""", unsafe_allow_html=True)

            if submit:
                if u == "admin" and p == "yoga888":
                    st.session_state.authenticated = True
                    st.session_state.username = u
                    st.rerun()
                else:
                    try:
                        if st.secrets["passwords"].get(u) == p:
                            st.session_state.authenticated = True
                            st.session_state.username = u
                            st.rerun()
                        else:
                            st.error("Sai mật khẩu rồi bác ơi!")
                    except:
                        st.error("Chưa cấu hình mật khẩu user!")

    st.markdown("<div style='height: 250px; display: block;'></div>", unsafe_allow_html=True)
