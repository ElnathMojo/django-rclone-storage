import io
from unittest import mock
from unittest.mock import mock_open

from django.core.exceptions import (
    ImproperlyConfigured, SuspiciousFileOperation,
)
from django.core.files.base import File
from django.test import TestCase

from rclonestorage import rclone, rclone_remote

FILES_EMPTY_MOCK = []

RCLONE_ERROR = mock.MagicMock('', 'Failed to copy: directory not found')

SUCCESS = 0
FAIL = -1
RCLONE_LSJSON_SUCCESS = (
    '[{"Path":"foo.txt","Name":"foo.txt","Size":3,"MimeType":"text/plain",'
    '"ModTime":"2021-01-21T05:52:50Z","IsDir":false,"ID":"d3e0c0ghrt7d0abbb#D3E0C0FRT%W0ABBB!545862"}]',
    '')
RCLONE_LSJSON_ROOT_SUCCESS = (
    '[{"Path":"foo.txt","Name":"foo.txt","Size":3,"MimeType":"text/plain",'
    '"ModTime":"2021-01-21T05:52:50Z","IsDir":false,"ID":"d3e0c0ghrt7d0abbb#D3E0C0FRT%W0ABBB!545862"},'
    '{"Path":"bar","Name":"bar","Size":-1,"MimeType":"inode/directory","ModTime":"2021-01-21T21:57:32Z",'
    '"IsDir":true,"ID":"d3e0c0ghf6e0abbb#3E0C00AEF6E0ABBB!311"}]',
    '')

FILE_DATE = '2021-01-21T05:52:50Z'
FILE_SIZE = 3

RCLONE_EMPTY = ('[]', '')


class RcloneRemoteTest(TestCase):
    def setUp(self, *args):
        self.storage = rclone_remote.RcloneRemoteStorage('remote')

    def test_no_remote(self, *args):
        with self.assertRaises(ImproperlyConfigured):
            rclone_remote.RcloneRemoteStorage(None)

    @mock.patch('subprocess.Popen')
    def test_delete(self, *args):
        args[0].return_value.__enter__.return_value.communicate.return_value = RCLONE_EMPTY
        args[0].return_value.__enter__.return_value.returncode = SUCCESS
        self.storage.delete('foo')

    @mock.patch('subprocess.Popen')
    def test_exists(self, *args):
        args[0].return_value.__enter__.return_value.communicate.return_value = RCLONE_LSJSON_SUCCESS
        args[0].return_value.__enter__.return_value.returncode = SUCCESS
        exists = self.storage.exists('foo.txt')
        self.assertTrue(exists)

    @mock.patch('subprocess.Popen')
    def test_not_exists(self, *args):
        args[0].return_value.__enter__.return_value.communicate.return_value = RCLONE_EMPTY
        args[0].return_value.__enter__.return_value.returncode = SUCCESS
        exists = self.storage.exists('bar')
        self.assertFalse(exists)

    @mock.patch('subprocess.Popen')
    def test_listdir(self, *args):
        args[0].return_value.__enter__.return_value.communicate.return_value = RCLONE_LSJSON_ROOT_SUCCESS
        args[0].return_value.__enter__.return_value.returncode = SUCCESS
        dirs, files = self.storage.listdir('/')
        dirs2, files2 = self.storage.listdir('')
        self.assertEqual(dirs, dirs2)
        self.assertEqual(files2, files2)

        self.assertGreater(len(dirs), 0)
        self.assertGreater(len(files), 0)
        self.assertEqual(dirs[0], 'bar')
        self.assertEqual(files[0], 'foo.txt')

    @mock.patch('subprocess.Popen')
    def test_size(self, *args):
        args[0].return_value.__enter__.return_value.communicate.return_value = RCLONE_LSJSON_SUCCESS
        args[0].return_value.__enter__.return_value.returncode = SUCCESS
        size = self.storage.size('foo.txt')
        self.assertEqual(size, FILE_SIZE)

    @mock.patch('subprocess.Popen')
    def test_modified_time(self, *args):
        args[0].return_value.__enter__.return_value.communicate.return_value = RCLONE_LSJSON_SUCCESS
        args[0].return_value.__enter__.return_value.returncode = SUCCESS
        mtime = self.storage.get_modified_time('foo.txt')
        self.assertEqual(mtime.strftime('%Y-%m-%dT%H:%M:%SZ'), FILE_DATE)

    @mock.patch('subprocess.Popen')
    def test_accessed_time(self, *args):
        args[0].return_value.__enter__.return_value.communicate.return_value = RCLONE_LSJSON_SUCCESS
        args[0].return_value.__enter__.return_value.returncode = 0
        mtime = self.storage.get_accessed_time('foo.txt')
        self.assertEqual(mtime.strftime('%Y-%m-%dT%H:%M:%SZ'), FILE_DATE)

    @mock.patch('subprocess.Popen')
    def get_created_time(self, *args):
        args[0].return_value.__enter__.return_value.communicate.return_value = RCLONE_LSJSON_SUCCESS
        args[0].return_value.__enter__.return_value.returncode = SUCCESS
        mtime = self.storage.get_created_time('foo.txt')
        self.assertEqual(mtime.strftime('%Y-%m-%dT%H:%M:%SZ'), FILE_DATE)

    def test_open(self, *args):
        obj = self.storage._open('foo')
        self.assertIsInstance(obj, File)

    @mock.patch('subprocess.Popen')
    def test_save(self, *args):
        args[0].return_value.__enter__.return_value.communicate.return_value = RCLONE_EMPTY
        args[0].return_value.__enter__.return_value.returncode = SUCCESS
        self.storage._save('foo.txt', File(io.BytesIO(b'bar'), 'foo.txt'))
        self.assertTrue(args[0].called)

    def test_formats(self, *args):
        self.storage = rclone_remote.RcloneRemoteStorage('foo')
        files = self.storage.path('')
        self.assertEqual(files, self.storage.path('/'))
        self.assertEqual(files, self.storage.path('.'))
        self.assertEqual(files, self.storage.path('..'))
        self.assertEqual(files, self.storage.path('../..'))


class DropBoxFileTest(TestCase):
    def setUp(self, *args):
        self.storage = rclone_remote.RcloneRemoteStorage('foo')
        self.file = rclone_remote.RcloneRemoteFile('/foo.txt', self.storage)

    @mock.patch('subprocess.Popen')
    @mock.patch("builtins.open", mock_open(read_data=b'bar'))
    def test_read(self, *args):
        args[0].return_value.__enter__.return_value.communicate.return_value = RCLONE_LSJSON_SUCCESS
        args[0].return_value.__enter__.return_value.returncode = SUCCESS
        file = self.storage._open('foo.txt')
        self.assertEqual(file.read(), b'bar')

    @mock.patch('subprocess.Popen')
    def test_server_bad_response(self, *args):
        args[0].return_value.__enter__.return_value.communicate.return_value = RCLONE_ERROR
        args[0].return_value.__enter__.return_value.returncode = FAIL
        with self.assertRaises(rclone.RcloneException):
            file = self.storage._open('foo.txt')
            file.read()


@mock.patch('rclonestorage.rclone.RcloneRemote.ls',
            return_value=FILES_EMPTY_MOCK)
class RcloneRemoteRootPathTest(TestCase):
    def test_jailed(self, *args):
        self.storage = rclone_remote.RcloneRemoteStorage('remote', '/bar')
        dirs, files = self.storage.listdir('/')
        self.assertFalse(dirs)
        self.assertFalse(files)

    def test_suspicious(self, *args):
        self.storage = rclone_remote.RcloneRemoteStorage('remote', '/bar')
        with self.assertRaises((SuspiciousFileOperation, ValueError)):
            self.storage.path('..')

    def test_formats(self, *args):
        self.storage = rclone_remote.RcloneRemoteStorage('foo', '/bar')
        files = self.storage.path('')
        self.assertEqual(files, self.storage.path('/'))
        self.assertEqual(files, self.storage.path('.'))
