# 🤖 AI Assistant 3-in-1: Chitchat + RAG (pgvector) + Tools Execution

Dự án Trợ lý AI Đa Năng tích hợp 3 mục đích trong 1 hệ thống:
1. **💬 Chitchat / Trợ lý thông minh**: Trò chuyện tự nhiên, giải đáp thắc mắc, viết lách, code.
2. **📚 RAG (Retrieval-Augmented Generation) với pgvector**: Nạp tài liệu (PDF, TXT, MD), băm chunk thông minh, lưu vector nhúng vào PostgreSQL và tra cứu theo độ tương đồng Cosine.
3. **⚡ Thực thi Tác vụ tự động (Function Calling / Tools)**:
   - `tra_cuu_tai_lieu`: Tự động kích hoạt khi câu hỏi liên quan đến kiến thức đã nạp.
   - `tra_cuu_thoi_gian`: Xem giờ và ngày tháng thực tế (Việt Nam UTC+7).
   - `tao_phieu_ho_tro`: Tạo Ticket hỗ trợ hệ thống.
   - `may_tinh`: Thực hiện các phép tính số học chính xác tuyệt đối.

---

## 🧩 Cơ chế Băm Chunk (Chunking) & Các mẹo đã áp dụng

Hệ thống tích hợp sẵn engine băm chunk tại `app/chunker.py` với các chuẩn mực tối ưu nhất:
- **Recursive Splitting**: Tách ưu tiên theo Đoạn (`\n\n`) ➔ Dòng (`\n`) ➔ Câu (`. `) ➔ Từ (` `).
- **Chunk Overlap (20%)**: Mặc định kích thước chunk 600 ký tự với 120 ký tự gối đầu, ngăn chặn việc câu văn hay số liệu bị cắt đứt gãy giữa 2 chunk.
- **Contextual Prefixing (Anthropic Style)**: Trước khi sinh vector embedding, hệ thống tự động gắn tiêu đề ngữ cảnh vào đầu mỗi chunk:
  ```text
  [Tài liệu: quy_che_cong_ty.txt | Đoạn 1/4]
  Nội dung: Chương I: QUY ĐỊNH LÀM VIỆC TỪ XA...
  ```
  Giúp mô hình embedding hiểu chính xác ngữ cảnh mà không bị mơ hồ.
- **Xem trước trực quan (Chunk Visualizer)**: Cho phép xem kết quả băm chunk, số ký tự, và phần header ngay trên giao diện web trước khi lưu vào DB.

---

## 🚀 Hướng dẫn Cài đặt & Chạy Dự Án

### 1. Chuẩn bị Cơ sở dữ liệu (PostgreSQL + pgvector)

Nếu bạn có Docker Desktop, chỉ cần chạy 1 lệnh để bật PostgreSQL có sẵn `pgvector`:
```bash
docker compose up -d
```
*(Lưu ý: Nếu bạn chưa bật PostgreSQL, hệ thống sẽ **tự động chuyển sang In-Memory Vector Store** để bạn có thể test ngay lập tức mà không bị gián đoạn).*

### 2. Cấu hình API Key

Mở file [.env](file:///d:/Project/phu/chatbot/.env) và điền API Key bạn đang có:
```env
LLM_PROVIDER=gemini       # Hoặc 'openai'
GEMINI_API_KEY=AIzaSy...  # Điền key Gemini của bạn
OPENAI_API_KEY=sk-...     # Hoặc key OpenAI nếu dùng OpenAI
```
*(Bạn cũng có thể nhập API Key trực tiếp từ nút **Cài đặt ⚙️** trên giao diện Web).*

### 3. Khởi động Chatbot

Chạy lệnh sau:
```bash
python run.py
```
Hệ thống sẽ tự động khởi động máy chủ tại `http://localhost:8000` và mở trình duyệt cho bạn!

---

## 📁 Cấu trúc Thư mục

```
chatbot/
├── docker-compose.yml       # Khởi chạy PostgreSQL 16 + pgvector
├── .env.example             # File mẫu biến môi trường
├── .env                     # File cấu hình thực tế
├── requirements.txt         # Danh sách thư viện Python
├── run.py                   # Script khởi chạy ứng dụng 1 chạm
├── sample_data/
│   └── quy_che_cong_ty.txt  # File mẫu kiểm thử RAG
├── app/
│   ├── config.py            # Quản lý cấu hình & dimensions vector
│   ├── chunker.py           # Engine băm chunk, overlap, contextual header
│   ├── database.py          # Kết nối pgvector với fallback thông minh
│   ├── embeddings.py        # Dịch vụ sinh vector (Gemini, OpenAI, Local)
│   ├── tools.py             # 4 công cụ Agent (RAG, Thời gian, Ticket, Máy tính)
│   ├── agent.py             # Bộ não AI điều phối 3-in-1 (SSE Streaming + Tools)
│   └── main.py              # FastAPI server (Chat, Upload, Preview API)
└── static/
    ├── index.html           # Giao diện Chatbot & Visualizer hiện đại
    ├── style.css            # Dark mode, Glassmorphism, animations
    └── app.js               # Logic Chat streaming & xem trước chunk
```
