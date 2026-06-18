import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivatePendingMediaStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(
            location=os.path.join(settings.BASE_DIR, "private_media", "midias_pendentes"),
            base_url=None,
        )


@deconstructible
class PrivateSubmissionStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(
            location=os.path.join(settings.BASE_DIR, "private_media", "submissoes"),
            base_url=None,
        )
