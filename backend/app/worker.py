"""Durable database worker with bounded retry, heartbeat leases, and fenced writes.

Run: python -m backend.app.worker [--once]
"""
from __future__ import annotations

import argparse
import logging
import signal
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import OperationalError
from .analysis import AnalysisError, analyze
from .config import settings
from .db import SessionLocal
from .image_service import ImageError, quality_metrics
from .models import AnalysisJob, AnalysisRun, Photo, PhotoPerson, Person, now
from .services import invalidate_photo_reviews, drain_cleanup, lock_album
from .storage import get_storage

logger = logging.getLogger(__name__)


def claim_job() -> tuple[str, str] | None:
    """A compare-and-swap is portable to SQLite; PostgreSQL workers never share a lease."""
    current = now()
    cutoff = current - timedelta(seconds=settings.worker_lease_seconds)
    eligible = or_(and_(AnalysisJob.status == 'pending', AnalysisJob.available_at <= current),
                   and_(AnalysisJob.status == 'processing', AnalysisJob.locked_at < cutoff))
    with SessionLocal() as db:
        candidates = db.execute(select(AnalysisJob.id, AnalysisJob.attempts, AnalysisJob.photo_id)
                                .where(eligible).order_by(AnalysisJob.available_at).limit(30)).all()
        for job_id, attempts, photo_id in candidates:
            if attempts >= settings.worker_max_attempts:
                changed = db.execute(update(AnalysisJob).where(AnalysisJob.id == job_id, eligible)
                                     .values(status='failed', error='WORKER_LEASE_EXHAUSTED: 작업 실행 횟수를 초과했어요.',
                                             locked_by=None, locked_at=None, finished_at=current)).rowcount
                db.commit()
                if changed:
                    with SessionLocal() as photo_db:
                        album_id = photo_db.scalar(select(Photo.album_id).where(Photo.id == photo_id))
                        if album_id and lock_album(photo_db, album_id, exclusive=True):
                            photo = photo_db.scalar(select(Photo).where(Photo.id == photo_id).with_for_update())
                            job = photo_db.scalar(select(AnalysisJob).where(AnalysisJob.id == job_id).with_for_update()
                                                  .execution_options(populate_existing=True))
                            if job and job.status == 'failed' and photo:
                                photo.analysis_status, photo.analysis_error = 'failed', job.error
                                photo_db.commit()
                continue
            token = str(uuid.uuid4())
            changed = db.execute(update(AnalysisJob).where(AnalysisJob.id == job_id, eligible, AnalysisJob.attempts == attempts)
                                 .values(status='processing', attempts=attempts + 1, locked_at=current,
                                         locked_by=token, error=None, finished_at=None)).rowcount
            db.commit()
            if changed:
                return job_id, token
    return None


def heartbeat(job_id, token, stop):
    interval = max(.25, min(20, settings.worker_lease_seconds / 3))
    while not stop.wait(interval):
        try:
            with SessionLocal() as db:
                changed = db.execute(update(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.locked_by == token,
                                                               AnalysisJob.status == 'processing').values(locked_at=now())).rowcount
                db.commit()
                if not changed:
                    return
        except Exception:
            logger.exception('Lease heartbeat failed; fenced completion will check ownership')


def _owns(job, token):
    return job is not None and job.status == 'processing' and job.locked_by == token


def _load_input(job_id, token):
    with SessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        if not _owns(job, token):
            return None
        photo = db.get(Photo, job.photo_id)
        if not photo:
            return None
        data = get_storage().get(photo.original_key)
        references = [{'id': person.id, 'name': person.name, 'data': get_storage().get(person.reference_key)}
                      for person in db.scalars(select(Person).where(Person.album_id == photo.album_id,
                                                                   Person.reference_key.is_not(None)))]
        inputs = (photo.id, photo.album_id, photo.original_hash, data, references, photo.latitude, photo.longitude)
        db.rollback()
        if not lock_album(db, inputs[1], exclusive=True):
            return None
        photo = db.scalar(select(Photo).where(Photo.id == inputs[0]).with_for_update())
        job = db.scalar(select(AnalysisJob).where(AnalysisJob.id == job_id).with_for_update().execution_options(populate_existing=True))
        if not photo or not _owns(job, token):
            return None
        photo.analysis_status, photo.analysis_error = "processing", None
        photo.analysis_provider = settings.face_analysis_provider
        photo.analysis_mode = "sample" if settings.face_analysis_provider == "fixture" else "live"
        db.commit()
        return inputs


def reverse_geocode(latitude, longitude):
    raise NotImplementedError("ZZIK_STARTER:location:reverse_geocode")


def _apply_result(db, photo, result):
    raise NotImplementedError("ZZIK_STARTER:worker-publish:_apply_result")


def process_claim(job_id: str, token: str) -> bool:
    raise NotImplementedError("ZZIK_STARTER:worker-publish:process_claim")


def process_one() -> bool:
    claim = claim_job()
    if claim is None:
        return False
    process_claim(*claim)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='Drain all currently available jobs and exit')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    shutdown = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: shutdown.set())
    cleanup_lock = threading.Lock()
    last_cleanup = [0.0]
    def loop():
        while not shutdown.is_set():
            if time.monotonic() - last_cleanup[0] >= 30 and cleanup_lock.acquire(blocking=False):
                try:
                    last_cleanup[0] = time.monotonic()
                    drain_cleanup()
                finally:
                    cleanup_lock.release()
            if not process_one():
                if args.once:
                    return
                shutdown.wait(settings.worker_poll_seconds)
    with ThreadPoolExecutor(max_workers=max(1, settings.worker_concurrency)) as pool:
        futures = [pool.submit(loop) for _ in range(max(1, settings.worker_concurrency))]
        for future in futures:
            future.result()
    drain_cleanup()


if __name__ == '__main__':
    main()
