import os
import uuid
import shutil


class WorkingDirectory(object):
    """
    A convenience class which syntactic sugar, allowing the user to change the directories.
    Can also be nested.
    """

    def __init__(self, name=None, prefix=None, delete=False):
        """
        Constructs a working_directory object
        :param name: (str) name of the directory if None is given os.getcwd() will be used (default: None)
        :param prefix: (str) a prefix where to locate the directory (default: None)
        :param delete: (bool) wether to delete the directory after a with clause (default: False)
        """
        self._name = str(uuid.uuid4()) if not name else name
        self._delete = delete
        self._curr_dir = os.getcwd()
        self._active = False
        if prefix is not None:
            self._name = os.path.join(prefix, self._name)

    def __enter__(self):
        if not os.path.exists(self._name):
            os.mkdir(self._name)
        os.chdir(self._name)
        self._active = True

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self._curr_dir)
        if self._delete:
            shutil.rmtree(self._name)
        self._active = False

    @property
    def name(self):
        return self._name

    @property
    def active(self):
        return self._active

cd = WorkingDirectory


def ensure_iterable_of_type(t, o):
    return o if isinstance(o, t) else (o if o is None else t([o]))
