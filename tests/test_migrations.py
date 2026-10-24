"""Check retained synthetic data through the unique-index migration."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import pytest


def test_unique_index_upgrade_preserves_records(tmp_path):
    database = tmp_path / 'migration.db'
    env = {**os.environ, 'DATABASE_URL': f'sqlite:///{database}'}
    backend = Path(__file__).resolve().parents[1] / 'milaan/backend'
    def migrate(*args):
        subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=backend, env=env, check=True, capture_output=True)
    migrate('upgrade', '20261010_marketplace')
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO products (id,name,description,sku,category,purchase_price_paisa,selling_price_paisa,stock_quantity,low_stock_threshold,is_active,created_at,updated_at) VALUES ('synthetic','Mug','','DEMO-SKU','General',100,200,1,1,1,'2026-10-24','2026-10-24')")
    for target in ['head', '20261010_marketplace', 'head']:
        migrate('downgrade' if target != 'head' else 'upgrade', target)
        with sqlite3.connect(database) as db:
            assert db.execute('SELECT sku FROM products').fetchall() == [('DEMO-SKU',)]
            for table, column in [('products', 'sku'), ('marketplace_orders', 'order_number')]:
                indexes = db.execute(f'PRAGMA index_list({table})').fetchall()
                assert any(row[2] and db.execute(f'PRAGMA index_info({row[1]})').fetchall()[0][2] == column for row in indexes)
            with pytest.raises(sqlite3.IntegrityError):
                db.execute("INSERT INTO products SELECT 'duplicate', name, description, sku, category, purchase_price_paisa, selling_price_paisa, stock_quantity, low_stock_threshold, is_active, image_url, created_at, updated_at FROM products")
    migrate('check')


def test_payment_shares_migration_preserves_whole_allocations_and_blocks_lossy_downgrade(tmp_path):
    database=tmp_path/'allocations.db'
    env={**os.environ,'DATABASE_URL':f'sqlite:///{database}'}
    backend=Path(__file__).resolve().parents[1]/'milaan/backend'
    def migrate(*args,check=True):
        return subprocess.run([sys.executable,'-m','alembic',*args],cwd=backend,env=env,check=check,capture_output=True,text=True)
    migrate('upgrade','head')
    seed='''
from datetime import timedelta
from app.database import Database
from app.models import User,Batch,Order,Statement,StatementLine,Claim,Run,Match,Allocation,now
import os
with Database(os.environ['DATABASE_URL']).transaction() as db:
    db.add(User(id='u',email='synthetic@example.com',password_hash='unused-synthetic-hash',display_name='Synthetic'));db.flush()
    db.add(Batch(id='b',owner_id='u',name='Synthetic',expires_at=now()+timedelta(days=1)));db.flush()
    db.add(Order(id='o',batch_id='b',order_ref='SYNTHETIC',customer_name='Synthetic',amount_due_paisa=10000,account_id='wallet'))
    db.add(Statement(id='s',batch_id='b',account_id='wallet',coverage_start=now(),coverage_end=now()+timedelta(days=1),filename='synthetic.csv'));db.flush()
    db.add(StatementLine(id='l',batch_id='b',statement_id='s',account_id='wallet',posted_at=now(),amount_paisa=10000,direction='CREDIT',transaction_id='SYNTHETIC-REF',credit_key='synthetic-key'))
    db.add(Claim(id='c',batch_id='b',order_id='o',account_id='wallet',filename='synthetic.jpg',sha256='synthetic-digest'))
    db.add(Run(id='r',batch_id='b',input_revision=1));db.flush()
    db.add(Match(id='m',run_id='r',batch_id='b',order_id='o',claim_id='c',machine_verdict='ship',final_status='ship',reason_code='EXACT_MATCH',reason='Synthetic fixture'));db.flush()
    db.add(Allocation(id='a',owner_id='u',batch_id='b',match_id='m',order_id='o',claim_id='c',credit_key='synthetic-key',statement_line_id='l',amount_paisa=10000))
'''
    subprocess.run([sys.executable,'-c',seed],cwd=backend,env=env,check=True,capture_output=True)
    migrate('downgrade','20261024_unique_indexes')
    with sqlite3.connect(database) as db: assert db.execute('SELECT id FROM allocations').fetchall()==[('a',)]
    migrate('upgrade','head');migrate('check')
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT id,amount_paisa FROM allocations').fetchall()==[('a',10000)]
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
        with pytest.raises(sqlite3.IntegrityError): db.execute('UPDATE allocations SET amount_paisa=0')
        db.execute('UPDATE allocations SET amount_paisa=6000')
    failed=migrate('downgrade','20261024_unique_indexes',check=False)
    assert failed.returncode!=0 and 'Cannot downgrade partial allocations' in failed.stderr
    with sqlite3.connect(database) as db: assert db.execute('SELECT amount_paisa FROM allocations').fetchone()==(6000,)
