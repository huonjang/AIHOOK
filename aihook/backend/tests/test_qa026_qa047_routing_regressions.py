"""Regressions: preserve old intent routing while QA-026/QA-047 remain handled."""
import pytest

from app.routers import chat


@pytest.mark.parametrize('question', [
    'So sánh hoạt động giao dịch giữa tháng 9/2026 và tháng 10/2026. Phân tích riêng số lượng hóa đơn, tổng giá trị mua vào, tổng giá trị bán ra và giá trị trung bình mỗi hóa đơn.',
    'Giá trị trung bình mỗi hóa đơn mua vào và bán ra là bao nhiêu? Nhóm giao dịch nào có giá trị trung bình cao hơn? Giải thích ý nghĩa đối với việc quản lý giao dịch.',
    'Tìm 5 hóa đơn có tổng giá trị lớn nhất. Cho biết ngày lập, đối tác, mã hóa đơn và hướng giao dịch. Có hóa đơn nào cần ưu tiên kiểm tra không?',
    'Hóa đơn nào có giá trị lớn nhất tháng 9/2026?',
    'Có bao nhiêu hóa đơn mua vào và bao nhiêu hóa đơn bán ra trong tháng 9/2026?',
])
def test_simple_router_does_not_swallow_advanced_intents(question):
    assert chat._answer_direction_counts_or_largest_invoice(
        question, None, 1, None, None,
    ) is None
