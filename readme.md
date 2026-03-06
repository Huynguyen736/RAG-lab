# Corporate Policy AI Auditor (Self-Correction RAG)
Dự án này giải quyết bài toán tra cứu quy định nội bộ doanh nghiệp bằng AI, đảm bảo câu trả lời luôn đi kèm minh chứng (số trang) và định dạng dữ liệu chuẩn (JSON) để tích hợp vào các hệ thống quản trị khác.

## Vấn đề giải quyết (Problem Statement)
- Trong các doanh nghiệp, việc tra cứu chính sách thường gặp 3 trở ngại lớn:
- Dữ liệu phân mảnh: Quy định nằm rải rác trong hàng trăm trang PDF.
- AI "ảo tưởng" (Hallucination): LLM có thể trả lời sai hoặc không căn cứ vào tài liệu thực tế.
- Định dạng không nhất quán: Khó trích xuất dữ liệu từ AI để đưa vào các dashboard hoặc quy trình tự động hóa vì format câu trả lời thay đổi liên tục.

## Giải pháp
Xây dựng một chu trình Self-Correction (Tự sửa lỗi). Nếu AI tạo ra câu trả lời không đúng định dạng JSON hoặc thiếu các trường thông tin quan trọng (answer, source_page, confidence_score), hệ thống sẽ tự động phát hiện và yêu cầu AI làm lại tối đa 3 lần trước khi trả kết quả cuối cùng.

# Kiến trúc & Công nghệ
## Tech Stack
- LLM & Embedding: Google Gemini (Gemini 3 Flash & gemini-embedding-001).
- Orchestration: LangChain & LangGraph
- Vector DB: ChromaDB
- API Framework: FastAPI & Mangum
- Environment: Python 3.10+

## Workflow Logic
1. Retriever: Tìm kiếm các đoạn văn bản (chunks) có điểm số tương đồng cao nhất.
2. Generator: Tổng hợp câu trả lời dựa trên ngữ cảnh và yêu cầu output JSON.
3. Auditor: Kiểm tra tính toàn vẹn của JSON. Nếu lỗi (thiếu key, sai cú pháp), trả về node Generator kèm thông báo lỗi để sửa.
4. Router: Quyết định dừng lại khi kết quả đạt chuẩn hoặc đạt giới hạn số lần thử lại.

# Cách sử dụng
1. Cài đặt thư viện (cmd -> pip install -r requirements.txt)
2. Tạo file .env chứa API Key (GEMINI_API_KEY=your_gemini_api_key_here)
3. Sử dụng Uvicorn để chạy API local (uvicorn main:api --host 127.0.0.1 --port 8000)
4. Gọi API qua cURL hoặc Postman
    - Endpoint: POST /chat?user_id=123&message=Quy định về thai sản là gì?
    - Kết quả trả về luôn ở dạng:
{
  "user_id": "123",
  "response": {
    "answer": "Theo chính sách, nhân viên được nghỉ thai sản 6 tháng...",
    "source_page": 12,
    "confidence_score": 0.89
  }
}
5. Triển khai Cloud
Dự án đã được cấu hình sẵn để chạy trên AWS Lambda thông qua Mangum. Cơ chế sao chép DB từ /var/task sang /tmp giúp vượt qua rào cản "Read-only file system" thường gặp trên môi trường Serverless.