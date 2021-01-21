# Django Rclone Storage

A simple Rclone wrapper as a Django storage.

## Usage

First, add these settings to your Django settings:

```python
# The remote name in your rclone.conf
RCLONE_REMOTE = 'onedrive'
# Remote path where all the files will be uploaded. Default: /
RCLONE_REMOTE_ROOT = '/'
# Local path where your rclone.conf locates. If it's not set, rclone should use the default .conf file.
RCLONE_CONFIG_PATH = '/path/to/config'
```

And, set the default storage:

```python
DEFAULT_FILE_STORAGE = 'rclonestorage.rclone_remote.RcloneRemoteStorage'
```

Or, you can just pass the settings to a RcloneRemoteStorage object and use it in the FileField:

```python
file = models.FileField(
    storage=RcloneRemoteStorage(remote='remote',
                                root_path='/',
                                config_path='/path/to/config')
)
```

## Reference
[django-storages](https://github.com/jschneier/django-storages)

[python-rclone](https://github.com/ddragosd/python-rclone)

