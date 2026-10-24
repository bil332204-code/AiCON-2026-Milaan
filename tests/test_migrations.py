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
