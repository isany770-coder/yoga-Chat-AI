import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="Check Key", layout="centered")

st.title("🕵️ MÁY SOI API KEY")

# 1. Lấy Key từ secrets
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    st.success("✅ Đã tìm thấy Key trong Secrets")
    
    # Hiện 4 ký tự đầu/cuối để cụ check xem có nhầm key cũ không
    masked_key = f"{api_key[:4]}...{api_key[-4:]}"
    st.code(f"Key đang dùng: {masked_key}")
except:
    st.error("❌ Chưa cấu hình GOOGLE_API_KEY trong secrets.toml")
    st.stop()

# 2. Thử kết nối Google
st.write("---")
st.write("📡 Đang kết nối tới máy chủ Google...")

try:
    genai.configure(api_key=api_key)
    
    # Lấy danh sách toàn bộ Model mà Key này được phép dùng
    all_models = list(genai.list_models())
    
    # Lọc ra các model Embedding
    embed_models = [m.name for m in all_models if 'embed' in m.name]
    
    if embed_models:
        st.success(f"🎉 KẾT NỐI THÀNH CÔNG! Key của cụ rất XỊN.")
        st.write(f"Tìm thấy {len(embed_models)} model Embedding có thể dùng:")
        
        # In danh sách ra để cụ copy
        for m in embed_models:
            st.code(m, language="text")
            
        st.info("👉 Hãy copy chính xác dòng chữ trong khung đen ở trên (ví dụ: models/text-embedding-004) để điền vào code.")
    else:
        st.error("⚠️ KẾT NỐI ĐƯỢC NHƯNG KHÔNG CÓ QUYỀN!")
        st.warning("Key này hợp lệ nhưng Google KHÔNG CẤP QUYỀN dùng model Embedding.")
        st.write("Danh sách model hiện có (chỉ có chat, không có embed):")
        st.json([m.name for m in all_models])
        st.markdown("""
        **Nguyên nhân có thể:**
        1. Key này thuộc dự án chưa bật "Generative Language API".
        2. Key trả phí Vertex AI (cần dùng thư viện khác).
        """)

except Exception as e:
    st.error("❌ KẾT NỐI THẤT BẠI (Key sai hoặc Lỗi mạng)")
    st.error(f"Chi tiết lỗi: {e}")
