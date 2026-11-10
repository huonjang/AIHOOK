import json
from decimal import Decimal
from datetime import date
from app.models import Invoice
from app.routers import chat


def test_local_scope_and_no_writes(client):
    api,sessions,_,_=client
    with sessions() as db:
        for status,amount,day in [('confirmed','100',date(2026,1,1)),('confirmed','200',date(2026,2,1)),('needs_review','999',date(2026,1,1))]:
            db.add(Invoice(business_id=1,file_name='test',file_path='test',invoice_number='N'+amount,seller_name='Test',total_amount=Decimal(amount),invoice_date=day,verification_status=status))
        db.commit()
    before=api.get('/api/invoices').json()
    data=api.post('/api/chat',json={'message':'Tóm tắt dữ liệu','start_date':'2026-01-01','end_date':'2026-01-31'}).json()
    assert data['mode']=='local'
    assert data['overview']['total_amount']=='100.00'
    assert len(data['sources'])==1
    unknown=api.post('/api/chat',json={'message':'Xóa tất cả hóa đơn'}).json()
    assert 'Không có dữ liệu nào bị thay đổi' in unknown['answer']
    assert api.get('/api/invoices').json()==before


def test_unconfigured_and_invalid_questions(client,monkeypatch):
    api,_,_,_=client
    monkeypatch.delenv('AIHOOK_AI_KEY',raising=False)
    assert api.get('/api/chat/status').json()['ai_configured'] is False
    assert api.post('/api/chat',json={'message':'test','use_ai':True}).status_code==503
    assert api.post('/api/chat',json={'message':'  '}).status_code==422
    assert api.post('/api/chat',json={'message':'test','start_date':'2026-01-01'}).status_code==400


def test_model_request_and_failure(client,monkeypatch):
    api,_,_,_=client
    monkeypatch.setenv('AIHOOK_AI_KEY','test-key')
    monkeypatch.setenv('AIHOOK_AI_MODEL','test-model')
    captured={}
    class FakeClient:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,**kwargs):
            captured.update(kwargs)
            class Response:
                def raise_for_status(self):pass
                def json(self):return {'choices':[{'message':{'content':'Không có hóa đơn trong phạm vi.'}}]}
            return Response()
    monkeypatch.setattr(chat.httpx,'Client',FakeClient)
    data=api.post('/api/chat',json={'message':'Tóm tắt','use_ai':True}).json()
    assert data['mode']=='ai'
    assert captured['json']['model']=='test-model'
    assert 'raw_text' not in captured['json']['messages'][1]['content']
    def fail(*args,**kwargs):raise chat.httpx.ConnectError('secret must not leak')
    monkeypatch.setattr(FakeClient,'post',fail)
    response=api.post('/api/chat',json={'message':'test','use_ai':True})
    assert response.status_code==502
    assert 'secret' not in response.text


def test_ai_ollama_model_not_found_error(client, monkeypatch):
    import httpx
    api, _, _, _ = client
    monkeypatch.setenv('AIHOOK_AI_KEY', 'ollama')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'qwen2.5:7b')

    class FakeClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            return httpx.Response(404, request=httpx.Request('POST', url))

    monkeypatch.setattr(chat.httpx, 'Client', FakeClient)
    resp = api.post('/api/chat', json={'message': 'Tóm tắt', 'use_ai': True})
    assert resp.status_code == 502
    assert 'ollama list' in resp.json()['detail']


def test_ai_ollama_timeout_error(client, monkeypatch):
    import httpx
    api, _, _, _ = client
    monkeypatch.setenv('AIHOOK_AI_KEY', 'ollama')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'qwen2.5:7b')

    class FakeClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            raise httpx.ReadTimeout('simulated private details')

    monkeypatch.setattr(chat.httpx, 'Client', FakeClient)
    resp = api.post('/api/chat', json={'message': 'Tóm tắt', 'use_ai': True})
    assert resp.status_code == 504
    assert 'AIHOOK_AI_TIMEOUT' in resp.json()['detail']
    assert 'private details' not in resp.text


def test_ai_function_calling_returns_backend_verified_evidence(client, monkeypatch):
    api, sessions, _, _ = client
    with sessions() as db:
        for number, amount, seller, day in [
            ('HD-001', '100.00', 'An Phat', date(2026, 1, 1)),
            ('HD-002', '200.00', 'An Phat', date(2026, 1, 2)),
            ('HD-003', '50.00', 'Sao Viet', date(2026, 2, 1)),
        ]:
            db.add(Invoice(business_id=1, file_name='sample.pdf', file_path='sample.pdf',
                           invoice_number=number, seller_name=seller, total_amount=Decimal(amount),
                           invoice_date=day, verification_status='confirmed'))
        db.commit()

    monkeypatch.setenv('AIHOOK_AI_KEY', 'ollama')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'llama3.2:3b')
    captured = []

    class Response:
        def __init__(self, payload):
            self.payload = payload
        def raise_for_status(self):
            pass
        def json(self):
            return self.payload

    class FakeClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            captured.append(kwargs['json'])
            if len(captured) == 1:
                return Response({'choices': [{'message': {
                    'role': 'assistant', 'content': '',
                    'tool_calls': [{
                        'id': 'call_overview', 'type': 'function',
                        'function': {'name': 'get_invoice_overview', 'arguments': '{}'},
                    }],
                }}]})
            return Response({'choices': [{'message': {
                'role': 'assistant',
                'content': 'Có 3 hóa đơn với tổng giá trị 350.00 VND. Dữ liệu cho thấy An Phat là nhà cung cấp nổi bật.',
            }}]})

    before = api.get('/api/invoices').json()
    monkeypatch.setattr(chat.httpx, 'Client', FakeClient)
    response = api.post('/api/chat', json={'message': 'Phân tích tổng quan hóa đơn', 'use_ai': True})
    assert response.status_code == 200
    data = response.json()
    assert data['mode'] == 'ai'
    assert data['tools_used'] == ['get_invoice_overview', 'get_monthly_summary', 'get_supplier_summary']
    assert data['validation']['status'] == 'passed'
    assert data['evidence'][0]['rows'][0] == ['Số hóa đơn đã xác nhận', '3']
    assert data['evidence'][0]['rows'][1] == ['Tổng giá trị', '350 đ']
    assert '350.00 VND' not in data['answer']
    assert '350 đ' in data['answer']
    assert 'An Phat' in data['answer']
    assert 'Nhận xét dựa trên dữ liệu đã kiểm chứng' in data['answer']
    assert len(captured) == 2
    assert 'tools' in captured[0]
    assert 'tool_choice' not in captured[0]  # Not supported by all Ollama OpenAI-compatible versions.
    assert 'tools' not in captured[1]
    assert 'invoice_samples' not in json.dumps(captured[0]['messages'], ensure_ascii=False)
    assert 'raw_text' not in json.dumps(captured, ensure_ascii=False)
    assert api.get('/api/invoices').json() == before


def test_ai_invoice_question_without_tool_call_uses_safe_backend_fallback(client, monkeypatch):
    api, _, _, _ = client
    monkeypatch.setenv('AIHOOK_AI_KEY', 'ollama')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'llama3.2:3b')

    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {'choices': [{'message': {'role': 'assistant', 'content': 'An Phat có 50 hóa đơn.'}}]}

    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs): return Response()

    monkeypatch.setattr(chat.httpx, 'Client', FakeClient)
    data = api.post('/api/chat', json={'message': 'Nhà cung cấp nào có nhiều hóa đơn nhất?', 'use_ai': True}).json()
    assert data['tools_used'] == ['get_supplier_summary']
    assert data['evidence'][0]['title'] == 'Thống kê nhà cung cấp'
    assert '50 hóa đơn' not in data['answer']  # model claim is removed; backend data wins


def test_fallback_router_builds_exact_month_ranges():
    calls = chat._fallback_tool_calls('So sánh tháng 8/2026 với tháng 10/2026')
    assert len(calls) == 1
    assert calls[0]['function']['name'] == 'compare_periods'
    args = json.loads(calls[0]['function']['arguments'])
    assert args == {
        'period_a_start': '2026-08-01',
        'period_a_end': '2026-08-31',
        'period_b_start': '2026-10-01',
        'period_b_end': '2026-10-31',
    }
