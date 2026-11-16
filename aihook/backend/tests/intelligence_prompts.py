"""Verbatim user-supplied evaluation questions, including the three-turn sequence.

The supplied transcript contains 26 turns; do not rename/reword them to fit routing.
"""
CASES = [
    ('Phân tích tổng quan các hóa đơn đã xác nhận. Nêu xu hướng, điểm đáng chú ý và giới hạn dữ liệu.', 'overview'),
    ('Đưa ra 5 khuyến nghị giúp tôi quản lý dữ liệu hóa đơn tốt hơn, dựa trên dữ liệu đã ghi nhận.', 'recommendation'),
    ('Nhà cung cấp nào có tổng giá trị hóa đơn mua vào lớn nhất? Cho tôi biết tên nhà cung cấp, tổng giá trị giao dịch, số lượng hóa đơn và tỷ trọng trên tổng giá trị mua vào.', 'supplier'),
    ('So sánh Top 5 nhà cung cấp theo tổng giá trị mua vào và Top 5 nhà cung cấp theo số lượng hóa đơn. Có nhà cung cấp nào xuất hiện trong cả hai nhóm không? Đâu là đối tác cần ưu tiên theo dõi?', 'supplier'),
    ('Những khách hàng nào mang lại giá trị hóa đơn bán ra lớn nhất? Xếp hạng Top 5 theo tổng giá trị và số lượng hóa đơn.', 'customer'),
    ('Doanh nghiệp có đang phụ thuộc quá nhiều vào một nhà cung cấp hoặc khách hàng hay không? Phân tích mức độ tập trung giao dịch dựa trên tỷ trọng của các đối tác lớn nhất. Không tự kết luận rủi ro nếu dữ liệu chưa đủ.', 'partners'),
    ('Đối tác nào xuất hiện nhiều nhất trong dữ liệu giao dịch? Phân biệt rõ nhà cung cấp và khách hàng, đồng thời giải thích sự khác biệt giữa tần suất giao dịch và tổng giá trị.', 'partners'),
    ('Hóa đơn sớm nhất và gần nhất trong hệ thống là những hóa đơn nào? So sánh ngày lập, mã hóa đơn, đối tác và tổng giá trị. Tính khoảng cách thời gian giữa hai hóa đơn', 'date'),
    ('Phân tích biến động tổng giá trị hóa đơn mua vào và bán ra theo từng tháng. Tháng nào có giá trị cao nhất, thấp nhất? Có xu hướng đáng chú ý nào không?', 'monthly'),
    ('So sánh hoạt động giao dịch giữa tháng 9/2026 và tháng 10/2026. Phân tích riêng số lượng hóa đơn, tổng giá trị mua vào, tổng giá trị bán ra và giá trị trung bình mỗi hóa đơn.', 'comparison'),
    ('Hoạt động giao dịch trong tháng 11/2026 hiện tại như thế nào so với các tháng trước? Lưu ý tháng hiện tại có thể chưa kết thúc, không được kết luận rằng hoạt động kinh doanh đang suy giảm chỉ dựa trên tổng giá trị thấp hơn.', 'monthly'),
    ('Giá trị trung bình mỗi hóa đơn mua vào và bán ra là bao nhiêu? Nhóm giao dịch nào có giá trị trung bình cao hơn? Giải thích ý nghĩa đối với việc quản lý giao dịch.', 'averages'),
    ('Tìm 5 hóa đơn có tổng giá trị lớn nhất. Cho biết ngày lập, đối tác, mã hóa đơn và hướng giao dịch. Có hóa đơn nào cần ưu tiên kiểm tra không?', 'top_invoices'),
    ('Đánh giá chất lượng dữ liệu hóa đơn hiện tại. Kiểm tra các trường bị thiếu như ngày lập, mã hóa đơn, mã số thuế, tên người bán, tên người mua và tổng giá trị. Đề xuất cách cải thiện.', 'quality'),
    ('Kiểm tra xem hệ thống có hóa đơn trùng mã hóa đơn, trùng đối tác hoặc trùng giá trị trong cùng khoảng thời gian không. Phân biệt bản ghi nghi trùng với trường hợp thực sự trùng lặp.', 'duplicates'),
    ('Có hóa đơn nào có giá trị khác biệt đáng kể so với những giao dịch thông thường của cùng đối tác không? Hãy xác định các trường hợp cần rà soát, nêu rõ cơ sở so sánh và không tự kết luận gian lận.', 'anomalies'),
    ('Đề xuất quy trình kiểm tra và xác nhận dữ liệu OCR để giảm sai sót khi ghi nhận hóa đơn. Ưu tiên những trường dữ liệu có ảnh hưởng lớn đến báo cáo tài chính và quản lý giao dịch.', 'ocr'),
    ('Dựa trên dữ liệu hóa đơn đã ghi nhận, đưa ra đúng 5 khuyến nghị giúp chủ doanh nghiệp quản lý hoạt động mua vào, bán ra và kiểm soát chứng từ tốt hơn. Mỗi khuyến nghị phải có lý do và hành động cụ thể.', 'recommendation'),
    ('Hãy tạo một báo cáo điều hành dành cho chủ doanh nghiệp, sử dụng dữ liệu hóa đơn đã xác nhận. Bao gồm: Tổng quan hoạt động mua vào và bán ra. Các nhà cung cấp và khách hàng quan trọng. Xu hướng giao dịch theo thời gian. Những vấn đề về chất lượng dữ liệu. Các rủi ro cần kiểm tra thêm. Năm hành động ưu tiên trong thời gian tới.', 'report'),
    ('Tại sao nhà cung cấp có tổng giá trị lớn nhất chưa chắc là đối tác quan trọng nhất của doanh nghiệp?', 'advice'),
    ('Dựa trên dữ liệu hiện tại, hãy cho tôi biết doanh nghiệp có lợi nhuận bao nhiêu và nhà cung cấp nào có giá bán tốt nhất.', 'limits'),
    ('Nhà cung cấp nào có tổng giá trị lớn nhất?', 'supplier'),
    ('Còn nếu xét số lượng hóa đơn thì sao?', 'supplier'),
    ('Vậy đối tác nào đáng quan tâm hơn?', 'advice'),
    ('Đối tác nào tốt nhất?', 'clarification'),
    ('Tổng giá trị hóa đơn bán ra cao hơn mua vào, vậy doanh nghiệp đang kinh doanh có lãi đúng không?', 'limits'),
]
