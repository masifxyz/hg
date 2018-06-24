# windows.py - Windows utility function implementations for Mercurial
#
#  Copyright 2005-2009 Matt Mackall <mpm@selenic.com> and others
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

from __future__ import absolute_import

import errno
import msvcrt
import os
import re
import stat
import string
import sys

from .i18n import _
from . import (
    encoding,
    error,
    policy,
    pycompat,
    win32,
)

try:
    import _winreg as winreg
    winreg.CloseKey
except ImportError:
    import winreg

osutil = policy.importmod(r'osutil')

getfsmountpoint = win32.getvolumename
getfstype = win32.getfstype
getuser = win32.getuser
hidewindow = win32.hidewindow
makedir = win32.makedir
nlinks = win32.nlinks
oslink = win32.oslink
samedevice = win32.samedevice
samefile = win32.samefile
setsignalhandler = win32.setsignalhandler
spawndetached = win32.spawndetached
split = os.path.split
testpid = win32.testpid
unlink = win32.unlink

umask = 0o022

class mixedfilemodewrapper(object):
    """Wraps a file handle when it is opened in read/write mode.

    fopen() and fdopen() on Windows have a specific-to-Windows requirement
    that files opened with mode r+, w+, or a+ make a call to a file positioning
    function when switching between reads and writes. Without this extra call,
    Python will raise a not very intuitive "IOError: [Errno 0] Error."

    This class wraps posixfile instances when the file is opened in read/write
    mode and automatically adds checks or inserts appropriate file positioning
    calls when necessary.
    """
    OPNONE = 0
    OPREAD = 1
    OPWRITE = 2

    def __init__(self, fp):
        object.__setattr__(self, r'_fp', fp)
        object.__setattr__(self, r'_lastop', 0)

    def __enter__(self):
        return self._fp.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._fp.__exit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name):
        return getattr(self._fp, name)

    def __setattr__(self, name, value):
        return self._fp.__setattr__(name, value)

    def _noopseek(self):
        self._fp.seek(0, os.SEEK_CUR)

    def seek(self, *args, **kwargs):
        object.__setattr__(self, r'_lastop', self.OPNONE)
        return self._fp.seek(*args, **kwargs)

    def write(self, d):
        if self._lastop == self.OPREAD:
            self._noopseek()

        object.__setattr__(self, r'_lastop', self.OPWRITE)
        return self._fp.write(d)

    def writelines(self, *args, **kwargs):
        if self._lastop == self.OPREAD:
            self._noopeseek()

        object.__setattr__(self, r'_lastop', self.OPWRITE)
        return self._fp.writelines(*args, **kwargs)

    def read(self, *args, **kwargs):
        if self._lastop == self.OPWRITE:
            self._noopseek()

        object.__setattr__(self, r'_lastop', self.OPREAD)
        return self._fp.read(*args, **kwargs)

    def readline(self, *args, **kwargs):
        if self._lastop == self.OPWRITE:
            self._noopseek()

        object.__setattr__(self, r'_lastop', self.OPREAD)
        return self._fp.readline(*args, **kwargs)

    def readlines(self, *args, **kwargs):
        if self._lastop == self.OPWRITE:
            self._noopseek()

        object.__setattr__(self, r'_lastop', self.OPREAD)
        return self._fp.readlines(*args, **kwargs)

def posixfile(name, mode='r', buffering=-1):
    '''Open a file with even more POSIX-like semantics'''
    try:
        fp = osutil.posixfile(name, mode, buffering) # may raise WindowsError

        # The position when opening in append mode is implementation defined, so
        # make it consistent with other platforms, which position at EOF.
        if 'a' in mode:
            fp.seek(0, os.SEEK_END)

        if '+' in mode:
            return mixedfilemodewrapper(fp)

        return fp
    except WindowsError as err:
        # convert to a friendlier exception
        raise IOError(err.errno, '%s: %s' % (
            name, encoding.strtolocal(err.strerror)))

# may be wrapped by win32mbcs extension
listdir = osutil.listdir

class winstdout(object):
    '''stdout on windows misbehaves if sent through a pipe'''

    def __init__(self, fp):
        self.fp = fp

    def __getattr__(self, key):
        return getattr(self.fp, key)

    def close(self):
        try:
            self.fp.close()
        except IOError:
            pass

    def write(self, s):
        try:
            # This is workaround for "Not enough space" error on
            # writing large size of data to console.
            limit = 16000
            l = len(s)
            start = 0
            self.softspace = 0
            while start < l:
                end = start + limit
                self.fp.write(s[start:end])
                start = end
        except IOError as inst:
            if inst.errno != 0:
                raise
            self.close()
            raise IOError(errno.EPIPE, 'Broken pipe')

    def flush(self):
        try:
            return self.fp.flush()
        except IOError as inst:
            if inst.errno != errno.EINVAL:
                raise
            raise IOError(errno.EPIPE, 'Broken pipe')

def _is_win_9x():
    '''return true if run on windows 95, 98 or me.'''
    try:
        return sys.getwindowsversion()[3] == 1
    except AttributeError:
        return 'command' in encoding.environ.get('comspec', '')

def openhardlinks():
    return not _is_win_9x()

def parsepatchoutput(output_line):
    """parses the output produced by patch and returns the filename"""
    pf = output_line[14:]
    if pf[0] == '`':
        pf = pf[1:-1] # Remove the quotes
    return pf

def sshargs(sshcmd, host, user, port):
    '''Build argument list for ssh or Plink'''
    pflag = 'plink' in sshcmd.lower() and '-P' or '-p'
    args = user and ("%s@%s" % (user, host)) or host
    if args.startswith('-') or args.startswith('/'):
        raise error.Abort(
            _('illegal ssh hostname or username starting with - or /: %s') %
            args)
    args = shellquote(args)
    if port:
        args = '%s %s %s' % (pflag, shellquote(port), args)
    return args

def setflags(f, l, x):
    pass

def copymode(src, dst, mode=None):
    pass

def checkexec(path):
    return False

def checklink(path):
    return False

def setbinary(fd):
    # When run without console, pipes may expose invalid
    # fileno(), usually set to -1.
    fno = getattr(fd, 'fileno', None)
    if fno is not None and fno() >= 0:
        msvcrt.setmode(fno(), os.O_BINARY)

def pconvert(path):
    return path.replace(pycompat.ossep, '/')

def localpath(path):
    return path.replace('/', '\\')

def normpath(path):
    return pconvert(os.path.normpath(path))

def normcase(path):
    return encoding.upper(path) # NTFS compares via upper()

# see posix.py for definitions
normcasespec = encoding.normcasespecs.upper
normcasefallback = encoding.upperfallback

def samestat(s1, s2):
    return False

def shelltocmdexe(path, env):
    r"""Convert shell variables in the form $var and ${var} inside ``path``
    to %var% form.  Existing Windows style variables are left unchanged.

    The variables are limited to the given environment.  Unknown variables are
    left unchanged.

    >>> e = {b'var1': b'v1', b'var2': b'v2', b'var3': b'v3'}
    >>> # Only valid values are expanded
    >>> shelltocmdexe(b'cmd $var1 ${var2} %var3% $missing ${missing} %missing%',
    ...               e)
    'cmd %var1% %var2% %var3% $missing ${missing} %missing%'
    >>> # Single quote prevents expansion, as does \$ escaping
    >>> shelltocmdexe(b"cmd '$var1 ${var2} %var3%' \$var1 \${var2} \\", e)
    "cmd '$var1 ${var2} %var3%' $var1 ${var2} \\"
    >>> # $$ -> $, %% is not special, but can be the end and start of variables
    >>> shelltocmdexe(b"cmd $$ %% %var1%%var2%", e)
    'cmd $ %% %var1%%var2%'
    >>> # No double substitution
    >>> shelltocmdexe(b"$var1 %var1%", {b'var1': b'%var2%', b'var2': b'boom'})
    '%var1% %var1%'
    """
    if b'$' not in path:
        return path

    varchars = pycompat.sysbytes(string.ascii_letters + string.digits) + b'_-'

    res = b''
    index = 0
    pathlen = len(path)
    while index < pathlen:
        c = path[index]
        if c == b'\'':   # no expansion within single quotes
            path = path[index + 1:]
            pathlen = len(path)
            try:
                index = path.index(b'\'')
                res += b'\'' + path[:index + 1]
            except ValueError:
                res += c + path
                index = pathlen - 1
        elif c == b'%':  # variable
            path = path[index + 1:]
            pathlen = len(path)
            try:
                index = path.index(b'%')
            except ValueError:
                res += b'%' + path
                index = pathlen - 1
            else:
                var = path[:index]
                res += b'%' + var + b'%'
        elif c == b'$':  # variable or '$$'
            if path[index + 1:index + 2] == b'$':
                res += c
                index += 1
            elif path[index + 1:index + 2] == b'{':
                path = path[index + 2:]
                pathlen = len(path)
                try:
                    index = path.index(b'}')
                    var = path[:index]

                    # See below for why empty variables are handled specially
                    if env.get(var, '') != '':
                        res += b'%' + var + b'%'
                    else:
                        res += b'${' + var + b'}'
                except ValueError:
                    res += b'${' + path
                    index = pathlen - 1
            else:
                var = b''
                index += 1
                c = path[index:index + 1]
                while c != b'' and c in varchars:
                    var += c
                    index += 1
                    c = path[index:index + 1]
                # Some variables (like HG_OLDNODE) may be defined, but have an
                # empty value.  Those need to be skipped because when spawning
                # cmd.exe to run the hook, it doesn't replace %VAR% for an empty
                # VAR, and that really confuses things like revset expressions.
                # OTOH, if it's left in Unix format and the hook runs sh.exe, it
                # will substitute to an empty string, and everything is happy.
                if env.get(var, '') != '':
                    res += b'%' + var + b'%'
                else:
                    res += b'$' + var

                if c != '':
                    index -= 1
        elif c == b'\\' and index + 1 < pathlen and path[index + 1] == b'$':
            # Skip '\', but only if it is escaping $
            res += b'$'
            index += 1
        else:
            res += c

        index += 1
    return res

# A sequence of backslashes is special iff it precedes a double quote:
# - if there's an even number of backslashes, the double quote is not
#   quoted (i.e. it ends the quoted region)
# - if there's an odd number of backslashes, the double quote is quoted
# - in both cases, every pair of backslashes is unquoted into a single
#   backslash
# (See http://msdn2.microsoft.com/en-us/library/a1y7w461.aspx )
# So, to quote a string, we must surround it in double quotes, double
# the number of backslashes that precede double quotes and add another
# backslash before every double quote (being careful with the double
# quote we've appended to the end)
_quotere = None
_needsshellquote = None
def shellquote(s):
    r"""
    >>> shellquote(br'C:\Users\xyz')
    '"C:\\Users\\xyz"'
    >>> shellquote(br'C:\Users\xyz/mixed')
    '"C:\\Users\\xyz/mixed"'
    >>> # Would be safe not to quote too, since it is all double backslashes
    >>> shellquote(br'C:\\Users\\xyz')
    '"C:\\\\Users\\\\xyz"'
    >>> # But this must be quoted
    >>> shellquote(br'C:\\Users\\xyz/abc')
    '"C:\\\\Users\\\\xyz/abc"'
    """
    global _quotere
    if _quotere is None:
        _quotere = re.compile(r'(\\*)("|\\$)')
    global _needsshellquote
    if _needsshellquote is None:
        # ":" is also treated as "safe character", because it is used as a part
        # of path name on Windows.  "\" is also part of a path name, but isn't
        # safe because shlex.split() (kind of) treats it as an escape char and
        # drops it.  It will leave the next character, even if it is another
        # "\".
        _needsshellquote = re.compile(r'[^a-zA-Z0-9._:/-]').search
    if s and not _needsshellquote(s) and not _quotere.search(s):
        # "s" shouldn't have to be quoted
        return s
    return '"%s"' % _quotere.sub(r'\1\1\\\2', s)

def _unquote(s):
    if s.startswith(b'"') and s.endswith(b'"'):
        return s[1:-1]
    return s

def shellsplit(s):
    """Parse a command string in cmd.exe way (best-effort)"""
    return pycompat.maplist(_unquote, pycompat.shlexsplit(s, posix=False))

def quotecommand(cmd):
    """Build a command string suitable for os.popen* calls."""
    if sys.version_info < (2, 7, 1):
        # Python versions since 2.7.1 do this extra quoting themselves
        return '"' + cmd + '"'
    return cmd

# if you change this stub into a real check, please try to implement the
# username and groupname functions above, too.
def isowner(st):
    return True

def findexe(command):
    '''Find executable for command searching like cmd.exe does.
    If command is a basename then PATH is searched for command.
    PATH isn't searched if command is an absolute or relative path.
    An extension from PATHEXT is found and added if not present.
    If command isn't found None is returned.'''
    pathext = encoding.environ.get('PATHEXT', '.COM;.EXE;.BAT;.CMD')
    pathexts = [ext for ext in pathext.lower().split(pycompat.ospathsep)]
    if os.path.splitext(command)[1].lower() in pathexts:
        pathexts = ['']

    def findexisting(pathcommand):
        'Will append extension (if needed) and return existing file'
        for ext in pathexts:
            executable = pathcommand + ext
            if os.path.exists(executable):
                return executable
        return None

    if pycompat.ossep in command:
        return findexisting(command)

    for path in encoding.environ.get('PATH', '').split(pycompat.ospathsep):
        executable = findexisting(os.path.join(path, command))
        if executable is not None:
            return executable
    return findexisting(os.path.expanduser(os.path.expandvars(command)))

_wantedkinds = {stat.S_IFREG, stat.S_IFLNK}

def statfiles(files):
    '''Stat each file in files. Yield each stat, or None if a file
    does not exist or has a type we don't care about.

    Cluster and cache stat per directory to minimize number of OS stat calls.'''
    dircache = {} # dirname -> filename -> status | None if file does not exist
    getkind = stat.S_IFMT
    for nf in files:
        nf  = normcase(nf)
        dir, base = os.path.split(nf)
        if not dir:
            dir = '.'
        cache = dircache.get(dir, None)
        if cache is None:
            try:
                dmap = dict([(normcase(n), s)
                             for n, k, s in listdir(dir, True)
                             if getkind(s.st_mode) in _wantedkinds])
            except OSError as err:
                # Python >= 2.5 returns ENOENT and adds winerror field
                # EINVAL is raised if dir is not a directory.
                if err.errno not in (errno.ENOENT, errno.EINVAL,
                                     errno.ENOTDIR):
                    raise
                dmap = {}
            cache = dircache.setdefault(dir, dmap)
        yield cache.get(base, None)

def username(uid=None):
    """Return the name of the user with the given uid.

    If uid is None, return the name of the current user."""
    return None

def groupname(gid=None):
    """Return the name of the group with the given gid.

    If gid is None, return the name of the current group."""
    return None

def removedirs(name):
    """special version of os.removedirs that does not remove symlinked
    directories or junction points if they actually contain files"""
    if listdir(name):
        return
    os.rmdir(name)
    head, tail = os.path.split(name)
    if not tail:
        head, tail = os.path.split(head)
    while head and tail:
        try:
            if listdir(head):
                return
            os.rmdir(head)
        except (ValueError, OSError):
            break
        head, tail = os.path.split(head)

def rename(src, dst):
    '''atomically rename file src to dst, replacing dst if it exists'''
    try:
        os.rename(src, dst)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
        unlink(dst)
        os.rename(src, dst)

def gethgcmd():
    return [sys.executable] + sys.argv[:1]

def groupmembers(name):
    # Don't support groups on Windows for now
    raise KeyError

def isexec(f):
    return False

class cachestat(object):
    def __init__(self, path):
        pass

    def cacheable(self):
        return False

def lookupreg(key, valname=None, scope=None):
    ''' Look up a key/value name in the Windows registry.

    valname: value name. If unspecified, the default value for the key
    is used.
    scope: optionally specify scope for registry lookup, this can be
    a sequence of scopes to look up in order. Default (CURRENT_USER,
    LOCAL_MACHINE).
    '''
    if scope is None:
        scope = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    elif not isinstance(scope, (list, tuple)):
        scope = (scope,)
    for s in scope:
        try:
            val = winreg.QueryValueEx(winreg.OpenKey(s, key), valname)[0]
            # never let a Unicode string escape into the wild
            return encoding.unitolocal(val)
        except EnvironmentError:
            pass

expandglobs = True

def statislink(st):
    '''check whether a stat result is a symlink'''
    return False

def statisexec(st):
    '''check whether a stat result is an executable file'''
    return False

def poll(fds):
    # see posix.py for description
    raise NotImplementedError()

def readpipe(pipe):
    """Read all available data from a pipe."""
    chunks = []
    while True:
        size = win32.peekpipe(pipe)
        if not size:
            break

        s = pipe.read(size)
        if not s:
            break
        chunks.append(s)

    return ''.join(chunks)

def bindunixsocket(sock, path):
    raise NotImplementedError('unsupported platform')
