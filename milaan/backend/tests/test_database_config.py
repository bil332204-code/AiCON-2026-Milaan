import pytest
from app.config import Settings
from app.database import database_url, Database


def production(**overrides):
    fields = dict(app_env='production', public_origin='https://milaan.example.com', cookie_secure=True,
        database_url='postgresql://synthetic:unused@db.example.com/synthetic?sslmode=verify-full',
        migration_database_url='', storage_backend='s3', s3_endpoint_url='https://storage.example.com', s3_bucket='synthetic',
        s3_region='ap-southeast-1', s3_access_key_id='synthetic', s3_secret_access_key='synthetic-secret',
        require_email_verification=True, demo_seller_email='', demo_seller_password='')
    return Settings(**(fields | overrides))


def test_driver_selection_and_pool_are_bounded_without_connecting():
    for scheme in ['postgres', 'postgresql', 'postgresql+psycopg']:
        assert database_url(scheme+'://user:unused@localhost/test').drivername == 'postgresql+psycopg'
    db = Database('postgres://user:unused@localhost/test', pool_size=3, max_overflow=0)
    assert db.engine.pool.size() == 3
    assert db.engine.hide_parameters
    db.engine.dispose()
    with pytest.raises(ValueError): database_url('mysql://localhost/test')


@pytest.mark.parametrize('overrides', [
    {'database_url':'sqlite:///./data/test.db'}, {'storage_backend':'local'},
    {'database_url':'postgresql://synthetic:unused@db.example.com/test?sslmode=disable'},
    {'s3_endpoint_url':'http://storage.example.com'}, {'s3_secret_access_key':''},
    {'s3_prefix':'../'}, {'s3_prefix':''}, {'s3_endpoint_url':'https://key:secret@storage.example.com'},
    {'database_pool_size':0}, {'database_max_overflow':100},
    {'migration_database_url':'postgresql://unused@db-pooler.example.com/test?sslmode=verify-full'},
    {'migration_database_url':'sqlite:///./data/test.db'},
])
def test_production_fails_closed_for_unsafe_bindings(overrides):
    with pytest.raises(ValueError): production(**overrides)


def test_secrets_are_not_in_settings_repr():
    assert 'synthetic-secret' not in repr(production())
    assert 'postgresql://' not in repr(production())
