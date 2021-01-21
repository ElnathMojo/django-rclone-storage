import json
import os
import subprocess
from signal import Signals


class RcloneException(subprocess.SubprocessError):
    def __init__(self, returncode, stderr=None):
        self.returncode = returncode
        self.stderr = stderr

    def __str__(self):
        if self.returncode and self.returncode < 0:
            try:
                return "RClone died with %r. \n%s" % (
                    Signals(value=-self.returncode), self.stderr)
            except ValueError:
                return "RClone died with unknown signal %d.  \n%s" % (
                    -self.returncode, self.stderr)
        else:
            return "RClone returned non-zero exit status %d. \n%s" % (
                self.returncode, self.stderr)


class RcloneRemote(object):

    def __init__(self, remote, config_path=None):
        """
        Args:
        remote (string): The name of the rclone remote
        config_path (string): The path of the rclone config file.
                              If it's None, rclone should use the default config file.
        """
        self.config_path = config_path
        self.remote = remote

    @staticmethod
    def _raise_exception(command_result):
        if command_result["code"] != 0:
            raise RcloneException(command_result["code"], command_result["error"])

    def _remote_prefix(self, path):
        return self.remote + ":" + path

    @staticmethod
    def _execute(command_with_args):
        """
        Execute the given `command_with_args` using Popen
        Args:
            - command_with_args (list) : An array with the command to execute,
                                         and its arguments. Each argument is given
                                         as a new element in the list.
        """
        try:
            with subprocess.Popen(
                    command_with_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE) as proc:
                (out, err) = proc.communicate()

                return {
                    "code": proc.returncode,
                    "out": out,
                    "error": err
                }
        except FileNotFoundError as not_found_e:
            return {
                "code": -20,
                "error": not_found_e
            }
        except Exception as generic_e:
            return {
                "code": -30,
                "error": generic_e
            }

    def run_cmd(self, command, extra_args=None):
        """
        Execute rclone command
        Args:
            - command (string): the rclone command to execute.
            - extra_args (list): extra arguments to be passed to the rclone command
        """
        if extra_args is None:
            extra_args = []
        command_with_args = ["rclone", command]
        if self.config_path:
            command_with_args.extend(["--config", self.config_path])
        command_with_args += extra_args
        command_result = self._execute(command_with_args)
        self._raise_exception(command_result)
        return command_result

    def meta(self, path):
        """
        Args:
        - path (string): A remote path
        """
        head, tail = os.path.split(path)
        return_values = self.ls(path)
        if len(return_values) == 1:
            file_info = return_values[0]
            if file_info["Name"] == tail or file_info["Path"] == tail:
                return file_info
            raise RcloneException(-1, "file not found")

        return_values = self.ls(head)
        for meta in return_values:
            if (meta["Name"] == tail or meta["Path"] == tail) and meta["IsDir"]:
                return meta
        raise RcloneException(-1, "directory not found")

    def exists(self, path):
        """
        Args:
        - path (string): A remote path
        """
        try:
            self.meta(path)
            return True
        except RcloneException as e:
            if "directory not found" in str(e) or "file not found" in str(e):
                return False
            raise e

    def size(self, path):
        file_size = self.meta(path)["Size"]
        if file_size < 0:
            raise RcloneException(-1, "not a valid file")
        return file_size

    def send_file(self, local_path, remote_path, flags=None):
        """
        Executes: rclone copy local_path {remote}:dirname(remote_path) [flags]
        Args:
        - local_path (string): A path of a local file
        - remote_path (string): A path indicates where the remote file will be saved
        - flags (list): Extra flags as per `rclone copy --help` flags.
        """
        if flags is None:
            flags = []
        if not os.path.isfile(local_path):
            raise RcloneException(-1, "send_file only accepts a local file.")
        return self.run_cmd(command="copy",
                            extra_args=[local_path] + [
                                self._remote_prefix(os.path.dirname(remote_path))] + flags)

    def get_file(self, remote_path, local_path, flags=None):
        """
        Executes: rclone copy {remote}:dirname(remote_path) local_path [flags]
        Args:
        - remote_path : A path of a remote file
        - local_path: A path indicates where the local file will be saved
        - flags (list): Extra flags as per `rclone copy --help` flags.
        """
        if flags is None:
            flags = []
        if self.meta(remote_path)["IsDir"]:
            raise RcloneException(-1, "get_file does not accept remote directory.")
        if not os.path.isdir(os.path.dirname(local_path)):
            raise RcloneException(-1, "get_file only accepts a valid local path.")
        return self.run_cmd(command="copy", extra_args=[self._remote_prefix(remote_path)] + [
            os.path.dirname(local_path)] + flags)

    def ls(self, remote_path, flags=None):
        """
        Executes: rclone lsjson {remote}:path [flags]
        Args:
        - dest (string): A string representing the location to list.
        """
        if flags is None:
            flags = []
        return json.loads(self.run_cmd(command="lsjson", extra_args=[self._remote_prefix(remote_path)] + flags)["out"])

    def delete(self, path, flags=None):
        """
        Executes: rclone delete {remote}:path
        Args:
        - dest (string): A string representing the location to delete.
        """
        if flags is None:
            flags = []
        self.run_cmd(command="delete", extra_args=[self._remote_prefix(path)] + flags)
