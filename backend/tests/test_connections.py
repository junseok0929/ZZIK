"""Read-only diagnostics never disclose secrets or activate AWS by default."""
import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import botocore.session
from botocore.exceptions import ClientError, NoCredentialsError
import pytest
from scripts import check_connections as check


@pytest.fixture
def settings(tmp_path):
    folder = tmp_path / 'storage'
    folder.mkdir()
    manifest = tmp_path / 'fixture.json'
    manifest.write_text(json.dumps({'fixtures': {'a' * 64: {'faces': []}}}))
    return SimpleNamespace(face_analysis_provider='fixture', storage_backend='local',
                           aws_region='ap-northeast-2', s3_bucket='', storage_root=str(folder),
                           fixture_manifest=str(manifest), database_url='postgresql+psycopg://u:SECRET_DB_PASSWORD@db/app')


@pytest.fixture
def no_credentials(monkeypatch):
    for name in list(os.environ):
        if name.startswith('AWS_'):
            monkeypatch.delenv(name)
    class NoCredentialsSession:
        full_config = {'profiles': {}}
        def get_config_variable(self, key):
            assert key == 'profile'
            assert os.environ['AWS_EC2_METADATA_DISABLED'] == 'true'
            return None
        def get_credentials(self):
            pytest.fail('Default diagnostics must never resolve credentials')
        def create_client(self, *args, **kwargs):
            pytest.fail('Default diagnostics must never create an AWS client')
    monkeypatch.setattr(botocore.session, 'get_session', NoCredentialsSession)


def test_default_local_probe_has_no_aws_calls_and_reports_missing_credentials(settings, no_credentials, monkeypatch):
    monkeypatch.setattr(check, 'check_database', lambda _: check.outcome('ready', 'DB_READY', 'ready'))
    monkeypatch.setattr(check, 'aws_read_checks', lambda *args: pytest.fail('AWS called without --aws-check'))
    before = set(Path(settings.storage_root).iterdir())
    report = check.build_report(settings)
    assert report['summary']['configured_mode_ready'] is True
    assert report['checks']['aws_credentials']['code'] == 'AWS_LOCAL_CREDENTIALS_NOT_DETECTED'
    assert report['checks']['aws']['identity']['status'] == 'not_requested'
    assert report['summary']['photo_analysis_verified'] is False
    assert report['safety']['settings_changed'] is False
    assert set(Path(settings.storage_root).iterdir()) == before
    assert 'AWS_EC2_METADATA_DISABLED' not in os.environ
    assert 'SECRET_DB_PASSWORD' not in json.dumps(report)


def test_runtime_provider_is_detected_without_executing_command(no_credentials, monkeypatch):
    class RuntimeSession:
        full_config = {'profiles': {'default': {'credential_process': 'do-not-run SECRET_PROCESS',
                                               'sso_start_url': 'https://secret-account.local'}}}
        def get_config_variable(self, key):
            return None
    monkeypatch.setattr(botocore.session, 'get_session', RuntimeSession)
    monkeypatch.setenv('AWS_EC2_METADATA_DISABLED', 'false')
    result = check.local_credentials()
    assert result['runtime_provider_configured'] and result['status'] == 'unverified'
    assert os.environ['AWS_EC2_METADATA_DISABLED'] == 'false'
    assert 'SECRET_PROCESS' not in json.dumps(result)
    assert 'secret-account' not in json.dumps(result)


def test_env_credentials_are_presence_only_and_never_echoed(no_credentials, monkeypatch):
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'SECRET_ACCESS_KEY')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'SECRET_PRIVATE_VALUE')
    monkeypatch.setenv('AWS_SESSION_TOKEN', 'SECRET_SESSION_TOKEN')
    result = check.local_credentials()
    assert result['status'] == 'present' and result['environment_pair_present']
    assert 'SECRET_' not in json.dumps(result)
    monkeypatch.delenv('AWS_SECRET_ACCESS_KEY')
    assert check.local_credentials()['code'] == 'AWS_PARTIAL_CREDENTIALS'


def test_explicit_aws_check_only_uses_read_operations_and_discards_response_secrets(monkeypatch):
    import boto3
    calls = []
    class Client:
        def __init__(self, service):
            self.service = service
        def get_caller_identity(self):
            calls.append(('sts', 'get_caller_identity', {}))
            return {'Account': 'SECRET_ACCOUNT', 'Arn': 'SECRET_ARN', 'UserId': 'SECRET_USER'}
        def head_bucket(self, **kwargs):
            calls.append(('s3', 'head_bucket', kwargs))
            return {'ResponseMetadata': {'HTTPHeaders': {'x-private': 'SECRET_HEADER'}}}
        def list_collections(self, **kwargs):
            calls.append(('rekognition', 'list_collections', kwargs))
            return {'CollectionIds': ['SECRET_COLLECTION']}
        def close(self):
            pass
    class Session:
        def __init__(self, **kwargs):
            assert kwargs == {'region_name': 'ap-northeast-2'}
        def client(self, service, region_name, config):
            assert config.connect_timeout == 3 and config.read_timeout == 3
            assert config.retries['total_max_attempts'] == 1
            return Client(service)
    monkeypatch.setattr(boto3, 'Session', Session)
    result = check.aws_read_checks('ap-northeast-2', 'SECRET_BUCKET')
    assert calls == [('sts', 'get_caller_identity', {}), ('s3', 'head_bucket', {'Bucket': 'SECRET_BUCKET'}),
                     ('rekognition', 'list_collections', {'MaxResults': 1})]
    assert all(item['status'] == 'ready' for item in result.values())
    assert 'SECRET_' not in json.dumps(result)


def test_aws_errors_and_missing_credentials_never_echo_provider_messages(monkeypatch):
    import boto3
    class Session:
        def __init__(self, **kwargs):
            pass
        def client(self, service, **kwargs):
            if service == 'sts':
                raise NoCredentialsError()
            raise ClientError({'Error': {'Code': 'AccessDenied', 'Message': 'SECRET_TOKEN /private/path'},
                               'ResponseMetadata': {'secret': 'SECRET_HEADER'}}, 'HeadBucket')
    monkeypatch.setattr(boto3, 'Session', Session)
    result = check.aws_read_checks('ap-northeast-2', 'SECRET_BUCKET')
    assert result['identity']['code'] == 'AWS_CREDENTIALS_UNAVAILABLE'
    assert result['s3_bucket']['code'] == 'AWS_ACCESS_DENIED'
    assert 'SECRET_' not in json.dumps(result)
    assert '/private/path' not in json.dumps(result)


def test_missing_storage_and_sqlite_are_not_created(tmp_path):
    folder, database = tmp_path / 'missing-storage', tmp_path / 'missing.db'
    assert check.check_storage(folder)['status'] == 'blocked'
    assert check.check_database('sqlite:///' + str(database))['code'] == 'DB_FILE_MISSING'
    assert not folder.exists() and not database.exists()


def test_existing_sqlite_is_read_only_and_schema_failure_is_clear(tmp_path):
    database = tmp_path / 'existing.db'
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE preserve_me (value TEXT)')
        connection.execute("INSERT INTO preserve_me VALUES ('unchanged')")
    before = database.read_bytes()
    result = check.check_database('sqlite:///' + str(database))
    assert result['connected'] and result['code'] == 'DB_SCHEMA_OUTDATED'
    assert database.read_bytes() == before


def test_cli_failure_is_machine_readable_without_raw_exception(settings, monkeypatch, capsys):
    monkeypatch.setattr(check, 'build_report', lambda *a, **kw: (_ for _ in ()).throw(ValueError('SECRET_PASSWORD')))
    assert check.main(['--compact']) == 1
    output = capsys.readouterr()
    result = json.loads(output.out)
    assert result['schema_version'] == 1 and result['error']['code'] == 'PREFLIGHT_FAILED'
    assert 'SECRET_PASSWORD' not in output.out + output.err


def test_live_mode_is_not_reported_ready_without_explicit_aws_verification(settings, no_credentials, monkeypatch):
    monkeypatch.setattr(check, 'check_database', lambda _: check.outcome('ready', 'DB_READY', 'ready'))
    settings.face_analysis_provider = 'rekognition'
    report = check.build_report(settings)
    assert report['summary']['configured_mode_ready'] is None
    assert report['summary']['aws_reads_verified'] is False
    settings.storage_backend = 's3'
    report = check.build_report(settings)
    assert report['summary']['configured_mode_ready'] is False
    assert any(item['code'] == 'S3_BUCKET_NOT_CONFIGURED' and item['affects_selected_mode'] for item in report['blockers'])
