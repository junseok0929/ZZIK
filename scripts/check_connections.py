#!/usr/bin/env python3
"""Read-only connection diagnostics. JSON only; never print credentials or raw errors."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import quote

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
REQUIRED_TABLES = {'users', 'sessions', 'albums', 'album_members', 'people', 'photos', 'photo_people',
                   'analysis_jobs', 'analysis_runs', 'versions', 'approval_targets', 'approvals',
                   'comments', 'notifications', 'face_groups', 'group_faces', 'file_cleanup', 'alembic_version'}


def outcome(status, code, message, **details):
    return {'status': status, 'code': code, 'message': message, **details}


@contextmanager
def local_metadata_disabled():
    previous = os.environ.get('AWS_EC2_METADATA_DISABLED')
    os.environ['AWS_EC2_METADATA_DISABLED'] = 'true'
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop('AWS_EC2_METADATA_DISABLED', None)
        else:
            os.environ['AWS_EC2_METADATA_DISABLED'] = previous


def local_credentials():
    """Inspect SDK configuration, never resolve or refresh credential providers.

    get_credentials() can execute credential_process or contact container metadata.
    Deliberately do not call it during the default local probe.
    """
    flags = {
        'environment_pair_present': bool(os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY')),
        'profile_pair_present': False,
        'profile_selected': bool(os.getenv('AWS_PROFILE') or os.getenv('AWS_DEFAULT_PROFILE')),
        'runtime_provider_configured': False,
        'metadata_probed': False,
    }
    if os.getenv('AWS_ACCESS_KEY_ID') and not os.getenv('AWS_SECRET_ACCESS_KEY'):
        return outcome('blocked', 'AWS_PARTIAL_CREDENTIALS', '환경변수 AWS 자격 증명 쌍이 완전하지 않아요.', **flags)
    try:
        import botocore.session
        with local_metadata_disabled():
            session = botocore.session.get_session()
            # This SDK property parses config/credentials files only; no provider is run.
            profile_name = session.get_config_variable('profile') or 'default'
            profiles = session.full_config.get('profiles', {})
            profile = profiles.get(profile_name, {})
            flags['profile_pair_present'] = bool(profile.get('aws_access_key_id') and profile.get('aws_secret_access_key'))
            flags['runtime_provider_configured'] = bool(
                any(profile.get(key) for key in ('role_arn', 'credential_process', 'sso_session', 'sso_start_url', 'web_identity_token_file'))
                or os.getenv('AWS_WEB_IDENTITY_TOKEN_FILE') or os.getenv('AWS_CONTAINER_CREDENTIALS_RELATIVE_URI')
                or os.getenv('AWS_CONTAINER_CREDENTIALS_FULL_URI'))
            if flags['profile_selected'] and profile_name not in profiles:
                return outcome('blocked', 'AWS_PROFILE_NOT_FOUND', '선택한 AWS 프로필을 찾지 못했어요.', **flags)
    except Exception:
        return outcome('blocked', 'AWS_CONFIG_UNREADABLE', 'AWS SDK 설정을 읽지 못했어요. 파일과 프로필 설정을 확인해 주세요.', **flags)
    if flags['environment_pair_present'] or flags['profile_pair_present']:
        return outcome('present', 'AWS_LOCAL_CREDENTIALS_PRESENT', '로컬 자격 증명 쌍이 있어요. 유효성과 권한은 확인하지 않았어요.', **flags)
    if flags['runtime_provider_configured']:
        return outcome('unverified', 'AWS_RUNTIME_PROVIDER_CONFIGURED', '런타임 자격 증명 제공자가 설정되어 있어요. 갱신이나 외부 조회는 하지 않았어요.', **flags)
    return outcome('unverified', 'AWS_LOCAL_CREDENTIALS_NOT_DETECTED', '로컬 자격 증명을 찾지 못했어요. EC2 역할은 기본 점검에서 조회하지 않아요.', **flags)


def check_database(database_url):
    engine = None
    dialect = 'unknown'
    try:
        from alembic.script import ScriptDirectory
        from sqlalchemy import create_engine, inspect, text
        from sqlalchemy.engine import make_url
        from sqlalchemy.pool import NullPool
        url = make_url(database_url)
        dialect = url.get_backend_name()
        if dialect == 'postgresql':
            engine = create_engine(url, poolclass=NullPool, hide_parameters=True, connect_args={
                'connect_timeout': 3,
                'options': '-c default_transaction_read_only=on -c statement_timeout=3000',
            })
        elif dialect == 'sqlite':
            if not url.database or url.database == ':memory:' or not Path(url.database).is_file():
                return outcome('blocked', 'DB_FILE_MISSING', '기존 SQLite DB 파일이 없어요. 점검 명령은 DB를 생성하지 않아요.', dialect='sqlite')
            filename = Path(url.database).resolve()
            engine = create_engine('sqlite://', poolclass=NullPool,
                                   creator=lambda: sqlite3.connect('file:' + quote(str(filename)) + '?mode=ro', uri=True, timeout=3))
        else:
            return outcome('blocked', 'DB_DIALECT_UNSUPPORTED', 'PostgreSQL 또는 기존 SQLite DB만 점검할 수 있어요.', dialect='unsupported')
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            tables_ready = REQUIRED_TABLES.issubset(tables)
            cleanup_ready = 'file_cleanup' in tables and 'not_before' in {column['name'] for column in inspector.get_columns('file_cleanup')}
            heads = set(ScriptDirectory(str(ROOT / 'backend/alembic')).get_heads())
            versions = set(connection.execute(text('SELECT version_num FROM alembic_version')).scalars()) if 'alembic_version' in tables else set()
            migration_current = bool(heads) and heads == versions
            ready = tables_ready and cleanup_ready and migration_current
            return outcome('ready' if ready else 'blocked', 'DB_READY' if ready else 'DB_SCHEMA_OUTDATED',
                           'DB 연결과 현재 스키마가 준비됐어요.' if ready else 'DB에는 연결했지만 현재 migration과 필요한 테이블을 확인해 주세요.',
                           dialect=dialect, connected=True, schema_ready=ready, migration_current=migration_current)
    except Exception:
        return outcome('blocked', 'DB_CONNECTION_FAILED', 'DB 연결 또는 읽기 점검에 실패했어요. 실행 상태·인증·TLS 설정을 확인해 주세요.',
                       dialect=dialect if dialect in {'postgresql', 'sqlite'} else 'unknown', connected=False, schema_ready=False)
    finally:
        if engine is not None:
            engine.dispose()


def check_storage(path):
    try:
        directory = Path(path)
        exists = directory.is_dir()
        readable = exists and os.access(directory, os.R_OK | os.X_OK)
        writable = exists and os.access(directory, os.W_OK | os.X_OK)
        return outcome('ready' if readable and writable else 'blocked',
                       'LOCAL_STORAGE_READY' if readable and writable else 'LOCAL_STORAGE_UNAVAILABLE',
                       '저장 폴더 접근 권한을 확인했어요. 파일 쓰기는 수행하지 않았어요.' if readable and writable else '저장 폴더의 존재와 읽기·쓰기 권한을 확인해 주세요.',
                       exists=exists, readable=readable, writable=writable, write_test_performed=False)
    except Exception:
        return outcome('blocked', 'LOCAL_STORAGE_UNAVAILABLE', '저장 폴더 설정을 확인해 주세요.',
                       exists=False, readable=False, writable=False, write_test_performed=False)


def check_fixture(path):
    try:
        manifest_path = Path(path)
        if not manifest_path.is_file():
            return outcome('blocked', 'FIXTURE_MISSING', 'fixture manifest 파일이 없어요.', exists=False, entries=0)
        if manifest_path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError('manifest too large')
        manifest = json.loads(manifest_path.read_text())
        fixtures = manifest.get('fixtures')
        if not isinstance(fixtures, dict) or not fixtures or not all(
                re.fullmatch(r'[0-9a-f]{64}', key) and isinstance(value, dict) and isinstance(value.get('faces'), list)
                for key, value in fixtures.items()):
            raise ValueError('invalid fixture manifest')
        return outcome('ready', 'FIXTURE_READY', '해시 기반 샘플 manifest를 읽을 수 있어요.', exists=True, entries=len(fixtures))
    except Exception:
        return outcome('blocked', 'FIXTURE_INVALID', 'fixture manifest 형식이나 읽기 권한을 확인해 주세요.', exists=Path(path).is_file() if isinstance(path, (str, Path)) else False, entries=0)


def aws_failure(exc):
    """Only whitelisted categories leave this function; SDK messages can contain secrets."""
    from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
    if isinstance(exc, (NoCredentialsError, PartialCredentialsError)):
        return outcome('blocked', 'AWS_CREDENTIALS_UNAVAILABLE', 'AWS 자격 증명을 가져오지 못했어요.')
    if isinstance(exc, ClientError):
        code = exc.response.get('Error', {}).get('Code')
        if code in {'AccessDenied', 'AccessDeniedException', 'UnauthorizedOperation', '403'}:
            return outcome('blocked', 'AWS_ACCESS_DENIED', '이 읽기 점검에 필요한 AWS 권한을 확인해 주세요.')
        if code in {'InvalidClientTokenId', 'UnrecognizedClientException', 'SignatureDoesNotMatch', 'ExpiredToken', 'ExpiredTokenException'}:
            return outcome('blocked', 'AWS_CREDENTIALS_REJECTED', 'AWS에서 자격 증명을 거부했어요. 만료 또는 설정을 확인해 주세요.')
        if code in {'404', 'NoSuchBucket', 'NotFound'}:
            return outcome('blocked', 'AWS_RESOURCE_NOT_FOUND', '설정한 리소스를 확인하지 못했어요.')
    return outcome('blocked', 'AWS_READ_CHECK_FAILED', 'AWS 읽기 점검에 실패했어요. 네트워크·리전·권한 설정을 확인해 주세요.')


def aws_read_checks(region, bucket):
    """Only called by the explicitly requested --aws-check path."""
    from botocore.config import Config
    import boto3
    config = Config(connect_timeout=3, read_timeout=3, retries={'mode': 'standard', 'total_max_attempts': 1})
    checks = {}
    try:
        session = boto3.Session(region_name=region)
    except Exception as exc:
        error = aws_failure(exc)
        return {name: dict(error) for name in ('identity', 's3_bucket', 'rekognition')}
    operations = [('identity', 'sts', 'get_caller_identity', {}),
                  ('s3_bucket', 's3', 'head_bucket', {'Bucket': bucket}),
                  ('rekognition', 'rekognition', 'list_collections', {'MaxResults': 1})]
    for name, service, method, kwargs in operations:
        if name == 's3_bucket' and not bucket:
            checks[name] = outcome('skipped', 'S3_BUCKET_NOT_CONFIGURED', 'S3 버킷이 설정되지 않아 조회를 생략했어요.')
            continue
        client = None
        try:
            client = session.client(service, region_name=region, config=config)
            getattr(client, method)(**kwargs)
            # Deliberately discard identity ARN/account, collection names, and headers.
            checks[name] = outcome('ready', 'AWS_READ_CHECK_PASSED', '요청한 읽기 점검을 통과했어요.')
        except Exception as exc:
            checks[name] = aws_failure(exc)
        finally:
            if client is not None:
                client.close()
    return checks


def build_report(settings, *, aws_check=False):
    face = settings.face_analysis_provider if settings.face_analysis_provider in {'fixture', 'rekognition'} else 'invalid'
    storage = settings.storage_backend if settings.storage_backend in {'local', 's3'} else 'invalid'
    region = settings.aws_region if re.fullmatch(r'[a-z]{2,6}(?:-[a-z0-9]+){1,4}-[0-9]+', settings.aws_region or '') else None
    credentials = local_credentials()
    checks = {'database': check_database(settings.database_url), 'local_storage': check_storage(settings.storage_root),
              'fixture': check_fixture(settings.fixture_manifest), 'aws_credentials': credentials}
    if aws_check and region:
        checks['aws'] = aws_read_checks(region, settings.s3_bucket)
    else:
        code = 'AWS_REGION_INVALID' if aws_check else 'AWS_CHECK_NOT_REQUESTED'
        message = 'AWS 리전 설정을 확인해 주세요.' if aws_check else '--aws-check를 지정하지 않아 AWS 서비스 호출을 하지 않았어요.'
        checks['aws'] = {name: outcome('blocked' if aws_check else 'not_requested', code, message)
                         for name in ('identity', 's3_bucket', 'rekognition')}
    blockers = []
    def block(scope, code, message, active):
        blockers.append({'scope': scope, 'code': code, 'message': message, 'affects_selected_mode': active})
    if face == 'invalid' or storage == 'invalid':
        block('configuration', 'MODE_INVALID', '분석·저장 모드 설정을 확인해 주세요.', True)
    for check, active in [('database', True), ('local_storage', storage == 'local'), ('fixture', face == 'fixture')]:
        item = checks[check]
        if item['status'] == 'blocked':
            block(check, item['code'], item['message'], active)
    aws_active = face == 'rekognition' or storage == 's3'
    if not region:
        block('aws', 'AWS_REGION_INVALID', 'AWS 리전 설정이 필요해요.', aws_active or aws_check)
    if not settings.s3_bucket:
        block('s3', 'S3_BUCKET_NOT_CONFIGURED', 'S3 연결에는 버킷 설정이 필요해요.', storage == 's3')
    if not aws_check:
        if credentials['status'] != 'present':
            block('aws', credentials['code'], credentials['message'], aws_active and credentials['status'] == 'blocked')
    else:
        for name, item in checks['aws'].items():
            if item['status'] == 'blocked':
                block('aws_' + name, item['code'], item['message'], True)
    blocking = any(item['affects_selected_mode'] for item in blockers)
    pending_aws = aws_active and not aws_check
    return {
        'schema_version': SCHEMA_VERSION,
        'mode': {'face_analysis_provider': face, 'storage_backend': storage, 'aws_region': region,
                 's3_bucket_configured': bool(settings.s3_bucket)},
        'safety': {'read_only': True, 'aws_check_requested': aws_check, 'photo_analysis_performed': False,
                   'settings_changed': False, 'secrets_included': False},
        'checks': checks,
        'blockers': blockers,
        'summary': {'selected_checks_passed': not blocking,
                    'configured_mode_ready': False if blocking else None if pending_aws else True,
                    'aws_reads_verified': all(item['status'] in {'ready', 'skipped'} for item in checks['aws'].values()) if aws_check else False,
                    'photo_analysis_verified': False},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='찍 연결 점검: 기본은 로컬 읽기, --aws-check만 AWS 읽기 호출. 결과는 JSON입니다.')
    parser.add_argument('--aws-check', action='store_true', help='STS identity, 설정된 S3 HeadBucket, Rekognition ListCollections(MaxResults=1) 실행')
    parser.add_argument('--compact', action='store_true', help='JSON을 한 줄로 출력')
    args = parser.parse_args(argv)
    # SDK debug logging must not place request headers or credentials on stdout/stderr.
    previous_logging = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        sys.path.insert(0, str(ROOT))
        from backend.app.config import settings
        report = build_report(settings, aws_check=args.aws_check)
    except Exception:
        report = {'schema_version': SCHEMA_VERSION, 'error': {'code': 'PREFLIGHT_FAILED',
                  'message': '연결 점검을 완료하지 못했어요. Python 의존성과 환경변수 형식을 확인해 주세요.'}}
    finally:
        logging.disable(previous_logging)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=None if args.compact else 2))
    return 0 if report.get('summary', {}).get('selected_checks_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
