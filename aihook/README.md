# AIHOOK — PDF nhiều hóa đơn, Analytics & AI

## Những gì đã hoàn thành
- PDF: chọn một hóa đơn/tệp (mặc định) hoặc mỗi trang là một hóa đơn độc lập.
- Các hóa đơn theo trang được OCR và tự ghi nhận riêng; trang lỗi không làm mất trang khác.
- Giữ nguyên ocr_service.py bản sửa nhãn mới nhất, điều kiện tự ghi nhận và cấm sửa/xác nhận thủ công.
- PDF cũ: nút Tách PDF theo trang thay bản ghi cũ bằng các bản ghi mới, không cộng trùng.
- Preview từng hóa đơn mở đúng trang; lưu source_file/source_page để truy nguyên. Tệp PDF nguồn được giữ lại.
- Tổng quan và Phân tích dùng đúng file trong src/pages/. Hai file tương thích tại src/ chỉ chuyển tiếp để các bản chép nhầm trước đây không gây lỗi build.
- Menu Phân tích & AI thay mục Cảnh báo. Đường dẫn /alerts chuyển tới /analytics.
- Hỏi đáp nội bộ: số liệu trực tiếp từ DB, không cần khóa; AI hỏi tự do: cần cấu hình dịch vụ Chat Completions trên backend.

## 1. Cập nhật project đang có dữ liệu
1. Tắt backend/frontend, sao lưu backend/aihook.db và backend/uploads/.
2. Giải nén gói này, chép nội dung thư mục aihook/ vào thư mục project đang dùng, giữ đúng backend/ và frontend/.
3. Gói không chứa database, uploads, node_modules hoặc môi trường Python. Không xóa dữ liệu hiện có.
4. Tại backend, dùng môi trường Python hiện tại:
   ```powershell
   python -m pip install -r requirements-dev.txt
   python -m pytest -q
   python -m uvicorn app.main:app --reload
   ```
5. Backend tự thêm hai cột nguồn vào bảng invoices nếu thiếu; không xóa/reset database. Cấu trúc cũ khác schema chuẩn cần được kiểm tra riêng.
6. Tại frontend:
   ```powershell
   npm ci
   npm run build
   npm run dev
   ```
7. Mở http://localhost:5173. API health: http://127.0.0.1:8000/api/health.

## 2. Chuyển bộ mẫu 10 PDF hiện có thành 50 hóa đơn
Không upload lại nếu 10 PDF đã nằm trong hệ thống.
- Vào Hóa đơn.
- Tại từng PDF cũ chọn **Tách PDF theo trang**, xác nhận rằng mỗi trang là một hóa đơn độc lập.
- Chờ xử lý hoàn tất rồi tiếp tục tệp kế tiếp (10 tệp).
- Bản ghi cũ của mỗi PDF được thay bằng 5 hóa đơn theo trang. Bản gốc vẫn lưu trong uploads; không sửa PDF gốc.
- Mở Tổng quan, chọn Toàn bộ thời gian / Làm mới.
- Nếu chỉ có đúng bộ mẫu này: **50 hóa đơn, 100.009.360 đ, 12 đơn vị bán**. Nếu có dữ liệu khác, tổng sẽ cao hơn tương ứng.
- Không tiếp tục upload lại cùng bộ mẫu: bản này chưa có cơ chế chống trùng tất cả các lần upload.

Với dữ liệu mới: chọn **Mỗi trang là một hóa đơn độc lập**, sau đó chọn 10 PDF. Không chọn chế độ này cho một hóa đơn dài nhiều trang. Bản này chưa tự nhận diện ranh giới hóa đơn trong PDF phức tạp và chưa hỗ trợ nhiều hóa đơn trên một trang.

## 3. Phân tích & AI
- Bộ lọc ngày là ngày lập hóa đơn, bao gồm cả ngày đầu/cuối; chỉ tính confirmed.
- Hỏi đáp dùng cùng bộ lọc đang áp dụng. Mỗi câu hỏi độc lập, không kế thừa hội thoại trước. Đổi ngày sẽ mở cuộc hỏi đáp mới.
- Không có khóa: các câu gợi ý tóm tắt, nhà cung cấp lớn nhất, tháng lớn nhất, hóa đơn lớn nhất chạy bằng truy vấn nội bộ. Giao diện ghi rõ đây không phải mô hình AI.
- Có khóa: bật **Dùng AI để hỏi tự do**. Backend gửi câu hỏi, số liệu tổng hợp, tối đa 30 nhà cung cấp, 120 tháng gần nhất và 20 hóa đơn lớn nhất. Không gửi PDF hoặc raw OCR.
- Trả lời có danh sách hóa đơn nguồn để mở đối chiếu. Danh sách là các hóa đơn giá trị cao trong phạm vi, không đại diện toàn bộ tập hóa đơn.
- AI chỉ diễn giải dữ liệu; không được chạy SQL hoặc sửa hóa đơn. Phản hồi mô hình có thể sai, cần đối chiếu số liệu/nguồn.

### Cấu hình AI (tùy chọn)
Sao chép backend/.env.example thành backend/.env, nhập khóa và model mà tài khoản của bạn có quyền sử dụng:
```
AIHOOK_AI_BASE_URL=https://api.openai.com/v1
AIHOOK_AI_MODEL=<ten-model-ho-tro-chat-completions>
AIHOOK_AI_KEY=<khoa-api-cua-ban>
```
Chạy từ backend:
```powershell
python -m uvicorn app.main:app --reload --env-file .env
```
Không đặt khóa trong frontend hay commit .env. Có thể dùng dịch vụ tương thích Chat Completions bằng BASE_URL tương ứng. Chưa cấu hình thì hỏi đáp nội bộ vẫn hoạt động. Không có model hoặc khóa được tích hợp sẵn.
Tham chiếu API: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create

## 4. Kiểm thử đã thực hiện
- **24 tests backend PASS**: OCR cũ, tự ghi nhận, cấm sửa, Analytics, PDF từng trang, chuyển PDF cũ, preview, lỗi từng trang, migration lặp an toàn, hỏi đáp nội bộ/bộ lọc, dịch vụ AI giả lập và lỗi kết nối.
- Trực tiếp đọc bộ mẫu 10 PDF thật qua FastAPI TestClient trên database tạm: nhập mới từng trang và chuyển 10 bản ghi cũ đều cho **50 / 100009360.00**.
- TypeScript + Vite build PASS (cảnh báo bundle lớn do Recharts).
- Chưa kiểm thử AI bằng dịch vụ thật do chưa có khóa/model.
- Chromium không chạy được trong môi trường kiểm thử vì bị chặn socket; chưa xác nhận tương tác và bố cục trên trình duyệt thật.

## 5. Phạm vi và giới hạn
- Demo một doanh nghiệp, VND; chưa có authentication, phân quyền đa người dùng hoặc phân loại doanh thu/chi phí.
- Luồng tách xử lý đồng bộ: PDF scan lớn có thể cần nhiều thời gian; bản PDF mẫu có text layer được xử lý nhanh.
- Không thay engine Tesseract hoặc logic Regex. PDF ảnh vẫn cần Tesseract và dữ liệu ngôn ngữ vie+eng trên máy.
- Ghi nhận tự động nghĩa là vượt các kiểm tra dữ liệu hiện có, không chứng minh tính hợp pháp của hóa đơn.
- Xóa một hóa đơn theo trang không xóa các trang khác; bản nguồn giữ lại để truy nguyên, chưa có công cụ dọn tệp nguồn.
- Tổng hợp Analytics dành cho tập dữ liệu demo/MVP; chưa phân trang bảng nhà cung cấp.
