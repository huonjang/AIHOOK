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
