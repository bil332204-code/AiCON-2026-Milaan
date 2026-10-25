from io import BytesIO
from pathlib import Path
import hashlib, warnings
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 25_000_000

def clean_image(raw):
    if len(raw) > 10 * 1024 * 1024: raise ValueError("Image exceeds 10 MB")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(BytesIO(raw)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}: raise ValueError("Only JPG, PNG and WEBP are accepted")
                if image.width * image.height > 25_000_000: raise ValueError("Image exceeds 25 megapixels")
                image.load()
                clean = ImageOps.exif_transpose(image).convert("RGB")
                clean.thumbnail((2400, 2400))
                out = BytesIO()
                clean.save(out, "JPEG", quality=92)
                return out.getvalue(), hashlib.sha256(raw).hexdigest()
        except (Image.DecompressionBombError, Image.DecompressionBombWarning, OSError) as exc:
            raise ValueError("Invalid or oversized image") from exc

def image_path(settings, filename):
    if Path(filename).name != filename: raise ValueError("Invalid storage path")
    return settings.storage_dir / filename


class StorageUnavailable(Exception):
    """Sanitized storage error: never include provider URLs, keys or response bodies."""


class StorageMissing(Exception):
    pass


def valid_key(key):
    import re
    if not isinstance(key, str) or not re.fullmatch(r"(?:[a-f0-9]{32}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})\.jpg", key):
        raise ValueError("Invalid receipt key")
    return key


class LocalReceiptStorage:
    def __init__(self, settings):
        self.directory = settings.storage_dir
        self.directory.mkdir(parents=True, exist_ok=True)
        self.identity = hashlib.sha256(('local:' + str(self.directory.resolve())).encode()).hexdigest()

    def put(self, key, data):
        import os
        path = self.directory / valid_key(key)
        # Exclusive creation: receipt keys are immutable and never reused.
        with path.open('xb') as output:
            os.chmod(path, 0o600)
            output.write(data)

    def get(self, key):
        try:
            return (self.directory / valid_key(key)).read_bytes()
        except FileNotFoundError:
            raise StorageMissing() from None

    def delete(self, key):
        (self.directory / valid_key(key)).unlink(missing_ok=True)

    def objects(self):
        from datetime import datetime, timezone
        for path in self.directory.glob('*.jpg'):
            try:
                valid_key(path.name)
                yield path.name, datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(tzinfo=None)
            except (ValueError, FileNotFoundError):
                continue


class S3ReceiptStorage:
    def __init__(self, settings):
        import boto3
        from botocore.config import Config
        self.bucket, self.prefix = settings.s3_bucket, settings.s3_prefix
        self.identity = hashlib.sha256(('s3:' + settings.s3_endpoint_url.rstrip('/') + '/' + self.bucket + '/' + self.prefix).encode()).hexdigest()
        from botocore.session import Session
        session = Session(session_vars={'profile': (None, None, None, None)})
        self.client = boto3.session.Session(botocore_session=session).client('s3', endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region, aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            aws_session_token=settings.s3_session_token or None,
            config=Config(signature_version='s3v4', s3={'addressing_style': settings.s3_addressing_style},
                connect_timeout=5, read_timeout=15, retries={'mode': 'standard', 'total_max_attempts': 3},
                request_checksum_calculation='when_required', response_checksum_validation='when_required'))

    def _key(self, key):
        return self.prefix + valid_key(key)

    def put(self, key, data):
        from botocore.exceptions import BotoCoreError, ClientError
        try:
            # No public ACL, browser URL, multipart temp file or disk cache.
            self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=data,
                                   ContentType='image/jpeg', CacheControl='no-store')
        except (BotoCoreError, ClientError):
            raise StorageUnavailable() from None

    def get(self, key):
        from botocore.exceptions import BotoCoreError, ClientError
        body = None
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
            body = response['Body']
            if response['ContentLength'] > 10 * 1024 * 1024:
                raise StorageUnavailable()
            data = body.read(10 * 1024 * 1024 + 1)
            if len(data) > 10 * 1024 * 1024:
                raise StorageUnavailable()
            return data
        except ClientError as exc:
            if exc.response.get('Error', {}).get('Code') in {'NoSuchKey', '404', 'NotFound'}:
                raise StorageMissing() from None
            raise StorageUnavailable() from None
        except BotoCoreError:
            raise StorageUnavailable() from None
        finally:
            if body is not None: body.close()

    def delete(self, key):
        from botocore.exceptions import BotoCoreError, ClientError
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self._key(key))
        except (BotoCoreError, ClientError):
            raise StorageUnavailable() from None

    def objects(self):
        from botocore.exceptions import BotoCoreError, ClientError
        from datetime import timezone
        try:
            pages = self.client.get_paginator('list_objects_v2').paginate(Bucket=self.bucket, Prefix=self.prefix)
            for page in pages:
                for item in page.get('Contents', []):
                    key = item['Key'][len(self.prefix):]
                    try: valid_key(key)
                    except ValueError: continue
                    yield key, item['LastModified'].astimezone(timezone.utc).replace(tzinfo=None)
        except (BotoCoreError, ClientError):
            raise StorageUnavailable() from None


def receipt_storage(settings):
    return S3ReceiptStorage(settings) if settings.storage_backend == 's3' else LocalReceiptStorage(settings)


def enqueue_deletion(db, storage, key):
    from .models import ReceiptDeletion
    valid_key(key)
    # Sweep/retry races must not create duplicate, unbounded erasure work.
    if db.get_bind().dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    db.execute(insert(ReceiptDeletion).values(object_key=key, storage_identity=storage.identity)
        .on_conflict_do_nothing(index_elements=['storage_identity', 'object_key']))


def drain_deletions(database, storage, *, limit=100):
    """At-least-once deletion. Keep failures durable; no receipt details in logs."""
    from datetime import timedelta
    from sqlalchemy import select
    from .models import ReceiptDeletion, now
    for _ in range(limit):
        with database.transaction() as db:
            row = db.scalar(select(ReceiptDeletion).where(
                ReceiptDeletion.storage_identity == storage.identity,
                ReceiptDeletion.next_attempt_at <= now()).order_by(ReceiptDeletion.next_attempt_at)
                .limit(1).with_for_update(skip_locked=True))
            if row is None: break
            try: storage.delete(row.object_key)
            except (StorageUnavailable, OSError):
                row.attempts += 1
                row.next_attempt_at = now() + timedelta(seconds=min(3600, 2 ** min(row.attempts, 12)))
                return  # Stop an outage multiplying remote timeouts across a batch.
            else: db.delete(row)
