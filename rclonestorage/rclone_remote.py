import os
import tempfile
from datetime import datetime
from shutil import copyfileobj
from tempfile import SpooledTemporaryFile

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import File
from django.core.files.storage import Storage
from django.db.models.fields.files import FieldFile
from django.utils._os import safe_join
from django.utils.deconstruct import deconstructible

from rclonestorage.rclone import RcloneRemote


def _setting(name, default=None):
    return getattr(settings, name, default)


class RcloneRemoteFile(File):
    def __init__(self, name, storage, mode='rb'):
        self.name = name
        self._storage = storage
        self._file = None
        self._mode = mode

    def _get_file(self):
        if self._file is None:
            self._file = SpooledTemporaryFile()
            with tempfile.TemporaryDirectory() as tmpdirname:
                filename = os.path.basename(self.name)
                filepath = os.path.join(tmpdirname, filename)
                self._storage.rclone.get_file(self.name, filepath)
                with open(filepath, self._mode) as f:
                    copyfileobj(f, self._file)
            self._file.seek(0)
        return self._file

    def _set_file(self, value):
        self._file = value

    file = property(_get_file, _set_file)


@deconstructible
class RcloneRemoteStorage(Storage):
    """RClone Storage class for Django pluggable storage system."""

    remote = _setting('RCLONE_REMOTE')
    location = _setting('RCLONE_REMOTE_ROOT', '/')
    config = _setting('RCLONE_CONFIG_PATH')

    def __init__(self, remote=remote, root_path=location, config_path=config):
        if remote is None:
            raise ImproperlyConfigured("You must configure an remote at 'settings.RCLONE_REMOTE'.")

        self.root_path = root_path
        self.rclone = RcloneRemote(remote, config_path=config_path)

    def path(self, name):
        if name == '/':
            name = ''
        return safe_join(self.root_path, name).replace('\\', '/')

    def delete(self, name):
        self.rclone.delete(self.path(name))

    def exists(self, name):
        return self.rclone.exists(self.path(name))

    def listdir(self, path):
        directories, files = [], []
        full_path = self.path(path)

        if full_path == '/':
            full_path = ''

        metadata = self.rclone.ls(full_path)
        for entry in metadata:
            if entry["IsDir"]:
                directories.append(entry["Name"])
            else:
                files.append(entry["Name"])
        return directories, files

    def size(self, name):
        return self.rclone.size(self.path(name))

    @staticmethod
    def _datetime_from_timestring(ts):
        try:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f%z")

    def get_accessed_time(self, name):
        return self._datetime_from_timestring(self.rclone.meta(self.path(name))["ModTime"])

    def get_created_time(self, name):
        return self._datetime_from_timestring(self.rclone.meta(self.path(name))["ModTime"])

    def get_modified_time(self, name):
        return self._datetime_from_timestring(self.rclone.meta(self.path(name))["ModTime"])

    def _open(self, name, mode='rb'):
        remote_file = RcloneRemoteFile(self.path(name), self, mode=mode)
        return remote_file

    def _save(self, name, content):
        if isinstance(content, FieldFile):
            try:
                self.rclone.send_file(content.path, self.path(name))
                return name
            except ValueError:
                pass
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = os.path.join(tmpdir, os.path.basename(name))
            content.open()
            with open(local_path, 'wb') as tmpfile:
                copyfileobj(content, tmpfile)
            content.close()
            self.rclone.send_file(local_path, self.path(name))
        return name

    def force_save(self, name, content):
        if name is None:
            name = content.name

        if not hasattr(content, 'chunks'):
            content = File(content, name)
        return self._save(name, content)
