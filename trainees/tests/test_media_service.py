from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from trainees.services.media_service import (
    media_program_folder,
    safe_media_part,
    save_uploaded_media,
    trainee_media_base_name,
    trainee_media_folder,
)


class FakeUploadedFile:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def chunks(self):
        yield self._data


class MediaServiceTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='media-service-')
        self.obj = SimpleNamespace(اللقب='بن/علي', الاسم='أحمد', التخصص='شبكات/معلوماتية')

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_safe_media_part_strips_invalid_chars(self):
        self.assertEqual(safe_media_part('  اسم:/\\?*    '), 'اسم ')
        self.assertEqual(safe_media_part(''), 'بدون_اسم')

    def test_media_program_folder_uses_program_mapping(self):
        self.assertEqual(media_program_folder('initial'), 'الحضوري أولي')
        self.assertEqual(media_program_folder('unknown'), 'عام')

    def test_trainee_media_folder_builds_expected_path(self):
        with patch('trainees.services.media_service.settings.MEDIA_ROOT', self.tmpdir):
            folder = trainee_media_folder(self.obj, 'initial', 'صور')
        self.assertEqual(
            folder,
            Path(self.tmpdir) / 'trainees' / 'الحضوري أولي' / 'شبكات معلوماتية' / 'صور',
        )

    def test_save_uploaded_media_replaces_old_variant(self):
        with patch('trainees.services.media_service.settings.MEDIA_ROOT', self.tmpdir):
            folder = trainee_media_folder(self.obj, 'initial', 'صور')
            folder.mkdir(parents=True, exist_ok=True)
            old_base_name = trainee_media_base_name(self.obj)
            old_path = folder / f'{old_base_name}.jpg'
            old_path.write_bytes(b'old')

            saved_path = save_uploaded_media(
                self.obj,
                'initial',
                FakeUploadedFile('profile.png', b'new-image'),
                'صور',
            )

        self.assertFalse(old_path.exists())
        self.assertIsNotNone(saved_path)
        self.assertTrue(saved_path.exists())
        self.assertEqual(saved_path.suffix, '.png')
        self.assertEqual(saved_path.read_bytes(), b'new-image')
