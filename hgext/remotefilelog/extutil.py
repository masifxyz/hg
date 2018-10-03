# extutil.py - useful utility methods for extensions
#
# Copyright 2016 Facebook
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

from __future__ import absolute_import

import contextlib
import errno
import os
import subprocess
import time

from mercurial import (
    error,
    lock as lockmod,
    pycompat,
    util,
    vfs as vfsmod,
)

if pycompat.iswindows:
    # no fork on Windows, but we can create a detached process
    # https://msdn.microsoft.com/en-us/library/windows/desktop/ms684863.aspx
    # No stdlib constant exists for this value
    DETACHED_PROCESS = 0x00000008
    _creationflags = DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    def runbgcommand(script, env, shell=False, stdout=None, stderr=None):
        '''Spawn a command without waiting for it to finish.'''
        # we can't use close_fds *and* redirect stdin. I'm not sure that we
        # need to because the detached process has no console connection.
        subprocess.Popen(
            script, shell=shell, env=env, close_fds=True,
            creationflags=_creationflags, stdout=stdout, stderr=stderr)
else:
    def runbgcommand(cmd, env, shell=False, stdout=None, stderr=None):
        '''Spawn a command without waiting for it to finish.'''
        # double-fork to completely detach from the parent process
        # based on http://code.activestate.com/recipes/278731
        pid = os.fork()
        if pid:
            # Parent process
            (_pid, status) = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                returncode = os.WEXITSTATUS(status)
            else:
                returncode = -os.WTERMSIG(status)
            if returncode != 0:
                # The child process's return code is 0 on success, an errno
                # value on failure, or 255 if we don't have a valid errno
                # value.
                #
                # (It would be slightly nicer to return the full exception info
                # over a pipe as the subprocess module does.  For now it
                # doesn't seem worth adding that complexity here, though.)
                if returncode == 255:
                    returncode = errno.EINVAL
                raise OSError(returncode, 'error running %r: %s' %
                              (cmd, os.strerror(returncode)))
            return

        returncode = 255
        try:
            # Start a new session
            os.setsid()

            stdin = open(os.devnull, 'r')
            if stdout is None:
                stdout = open(os.devnull, 'w')
            if stderr is None:
                stderr = open(os.devnull, 'w')

            # connect stdin to devnull to make sure the subprocess can't
            # muck up that stream for mercurial.
            subprocess.Popen(
                cmd, shell=shell, env=env, close_fds=True,
                stdin=stdin, stdout=stdout, stderr=stderr)
            returncode = 0
        except EnvironmentError as ex:
            returncode = (ex.errno & 0xff)
            if returncode == 0:
                # This shouldn't happen, but just in case make sure the
                # return code is never 0 here.
                returncode = 255
        except Exception:
            returncode = 255
        finally:
            # mission accomplished, this child needs to exit and not
            # continue the hg process here.
            os._exit(returncode)

@contextlib.contextmanager
def flock(lockpath, description, timeout=-1):
    """A flock based lock object. Currently it is always non-blocking.

    Note that since it is flock based, you can accidentally take it multiple
    times within one process and the first one to be released will release all
    of them. So the caller needs to be careful to not create more than one
    instance per lock.
    """

    # best effort lightweight lock
    try:
        import fcntl
        fcntl.flock
    except ImportError:
        # fallback to Mercurial lock
        vfs = vfsmod.vfs(os.path.dirname(lockpath))
        with lockmod.lock(vfs, os.path.basename(lockpath), timeout=timeout):
            yield
        return
    # make sure lock file exists
    util.makedirs(os.path.dirname(lockpath))
    with open(lockpath, 'a'):
        pass
    lockfd = os.open(lockpath, os.O_RDONLY, 0o664)
    start = time.time()
    while True:
        try:
            fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except IOError as ex:
            if ex.errno == errno.EAGAIN:
                if timeout != -1 and time.time() - start > timeout:
                    raise error.LockHeld(errno.EAGAIN, lockpath, description,
                                         '')
                else:
                    time.sleep(0.05)
                    continue
            raise

    try:
        yield
    finally:
        fcntl.flock(lockfd, fcntl.LOCK_UN)
        os.close(lockfd)
