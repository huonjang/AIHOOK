import fitz
from app import main


def pdf_pages():
    with fitz.open() as doc:
        for number in range(3):
            page=doc.new_page()
            page.insert_text((72,72),f'Invoice Number: TEST{number}\nNgay: 10/11/2026\nSeller: Test Company\nGrand total: 100')
        return doc.tobytes()


def test_per_page_upload_and_single_mode(client):
    api,_,_,_=client
    data=pdf_pages()
    response=api.post('/api/invoices/upload',data={'import_mode':'per_page'},files={'file':('batch.pdf',data,'application/pdf')})
    assert response.status_code==200,response.text
    rows=response.json()['invoices']
    assert len(rows)==3
    assert all(row['status']=='confirmed' for row in rows)
    assert [row['source_page'] for row in rows]==[1,2,3]
    assert api.get('/api/analytics/dashboard').json()['overview']['total_amount']=='300.00'
    # Each preview contains exactly one source page, deleting one preserves siblings.
    preview=api.get(f"/api/invoices/{rows[1]['id']}/file")
    with fitz.open(stream=preview.content,filetype='pdf') as doc:
        assert len(doc)==1
        assert 'TEST1' in doc[0].get_text()
    api.delete(f"/api/invoices/{rows[0]['id']}")
    assert api.get(f"/api/invoices/{rows[1]['id']}/file").status_code==200
    assert api.post(f"/api/invoices/{rows[1]['id']}/split-pages").status_code==409


def test_legacy_split_replaces_not_duplicates(client):
    api,_,_,_=client
    row=api.post('/api/invoices/upload',files={'file':('batch.pdf',pdf_pages(),'application/pdf')}).json()
    assert api.get('/api/analytics/dashboard').json()['overview']['invoice_count']==1
    response=api.post(f"/api/invoices/{row['id']}/split-pages")
    assert response.status_code==200,response.text
    assert api.get('/api/analytics/dashboard').json()['overview']['invoice_count']==3
    assert api.get('/api/analytics/dashboard').json()['overview']['total_amount']=='300.00'
    assert api.post(f"/api/invoices/{row['id']}/split-pages").status_code==404


def test_per_page_failure_isolated(client):
    api,_,_,monkeypatch=client
    original=main.extract_text
    def extract(path):
        text=original(path)
        if 'TEST1' in text: raise RuntimeError('OCR failed')
        return text
    monkeypatch.setattr(main,'extract_text',extract)
    rows=api.post('/api/invoices/upload',data={'import_mode':'per_page'},files={'file':('batch.pdf',pdf_pages(),'application/pdf')}).json()['invoices']
    assert len(rows)==3
    assert rows[1]['processing_error']
    assert api.get('/api/analytics/dashboard').json()['overview']['invoice_count']==2


def test_additive_migration_keeps_old_rows(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text, inspect
    from sqlalchemy.orm import sessionmaker
    engine=create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE invoices (id INTEGER PRIMARY KEY, business_id INTEGER, file_name TEXT, file_path TEXT, verification_status TEXT)'))
        connection.execute(text("INSERT INTO invoices VALUES (1,1,'old.pdf','old.pdf','confirmed')"))
    monkeypatch.setattr(main,'engine',engine)
    monkeypatch.setattr(main,'SessionLocal',sessionmaker(bind=engine))
    main.init_database()
    main.init_database()
    columns={column['name'] for column in inspect(engine).get_columns('invoices')}
    assert {'source_file','source_page'} <= columns
    with engine.connect() as connection:
        assert connection.execute(text('SELECT file_name, verification_status FROM invoices')).one()==('old.pdf','confirmed')
    engine.dispose()
