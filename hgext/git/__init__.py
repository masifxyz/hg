"""grant Mercurial the ability to operate on Git repositories. (EXPERIMENTAL)

This is currently super experimental. It probably will consume your
firstborn a la Rumpelstiltskin, etc.
"""

from __future__ import absolute_import

import os

from mercurial.i18n import _

from mercurial import (
    commands,
    error,
    extensions,
    localrepo,
    pycompat,
    store,
    util,
)

from . import (
    dirstate,
    gitlog,
    gitutil,
    index,
)

# TODO: extract an interface for this in core
class gitstore(object):  # store.basicstore):
    def __init__(self, path, vfstype):
        self.vfs = vfstype(path)
        self.path = self.vfs.base
        self.createmode = store._calcmode(self.vfs)
        # above lines should go away in favor of:
        # super(gitstore, self).__init__(path, vfstype)

        self.git = gitutil.get_pygit2().Repository(
            os.path.normpath(os.path.join(path, b'..', b'.git'))
        )
        self._progress_factory = lambda *args, **kwargs: None

    @util.propertycache
    def _db(self):
        # We lazy-create the database because we want to thread a
        # progress callback down to the indexing process if it's
        # required, and we don't have a ui handle in makestore().
        return index.get_index(self.git, self._progress_factory)

    def join(self, f):
        """Fake store.join method for git repositories.

        For the most part, store.join is used for @storecache
        decorators to invalidate caches when various files
        change. We'll map the ones we care about, and ignore the rest.
        """
        if f in (b'00changelog.i', b'00manifest.i'):
            # This is close enough: in order for the changelog cache
            # to be invalidated, HEAD will have to change.
            return os.path.join(self.path, b'HEAD')
        elif f == b'lock':
            # TODO: we probably want to map this to a git lock, I
            # suspect index.lock. We should figure out what the
            # most-alike file is in git-land. For now we're risking
            # bad concurrency errors if another git client is used.
            return os.path.join(self.path, b'hgit-bogus-lock')
        elif f in (b'obsstore', b'phaseroots', b'narrowspec', b'bookmarks'):
            return os.path.join(self.path, b'..', b'.hg', f)
        raise NotImplementedError(b'Need to pick file for %s.' % f)

    def changelog(self, trypending):
        # TODO we don't have a plan for trypending in hg's git support yet
        return gitlog.changelog(self.git, self._db)

    def manifestlog(self, repo, storenarrowmatch):
        # TODO handle storenarrowmatch and figure out if we need the repo arg
        return gitlog.manifestlog(self.git, self._db)

    def invalidatecaches(self):
        pass

    def write(self, tr=None):
        # normally this handles things like fncache writes, which we don't have
        pass


def _makestore(orig, requirements, storebasepath, vfstype):
    # Check for presence of pygit2 only here. The assumption is that we'll
    # run this code iff we'll later need pygit2.
    if gitutil.get_pygit2() is None:
        raise error.Abort(
            _(
                b'the git extension requires the Python '
                b'pygit2 library to be installed'
            )
        )

    if os.path.exists(
        os.path.join(storebasepath, b'this-is-git')
    ) and os.path.exists(os.path.join(storebasepath, b'..', b'.git')):
        return gitstore(storebasepath, vfstype)
    return orig(requirements, storebasepath, vfstype)


class gitfilestorage(object):
    def file(self, path):
        if path[0:1] == b'/':
            path = path[1:]
        return gitlog.filelog(self.store.git, self.store._db, path)


def _makefilestorage(orig, requirements, features, **kwargs):
    store = kwargs['store']
    if isinstance(store, gitstore):
        return gitfilestorage
    return orig(requirements, features, **kwargs)


def _setupdothg(ui, path):
    dothg = os.path.join(path, b'.hg')
    if os.path.exists(dothg):
        ui.warn(_(b'git repo already initialized for hg\n'))
    else:
        os.mkdir(os.path.join(path, b'.hg'))
        # TODO is it ok to extend .git/info/exclude like this?
        with open(
            os.path.join(path, b'.git', b'info', b'exclude'), 'ab'
        ) as exclude:
            exclude.write(b'\n.hg\n')
    with open(os.path.join(dothg, b'this-is-git'), 'wb') as f:
        pass
    with open(os.path.join(dothg, b'requirements'), 'wb') as f:
        f.write(b'git\n')


_BMS_PREFIX = 'refs/heads/'


class gitbmstore(object):
    def __init__(self, gitrepo):
        self.gitrepo = gitrepo

    def __contains__(self, name):
        return (
            _BMS_PREFIX + pycompat.fsdecode(name)
        ) in self.gitrepo.references

    def __iter__(self):
        for r in self.gitrepo.listall_references():
            if r.startswith(_BMS_PREFIX):
                yield pycompat.fsencode(r[len(_BMS_PREFIX) :])

    def __getitem__(self, k):
        return (
            self.gitrepo.references[_BMS_PREFIX + pycompat.fsdecode(k)]
            .peel()
            .id.raw
        )

    def get(self, k, default=None):
        try:
            if k in self:
                return self[k]
            return default
        except gitutil.get_pygit2().InvalidSpecError:
            return default

    @property
    def active(self):
        h = self.gitrepo.references['HEAD']
        if not isinstance(h.target, str) or not h.target.startswith(
            _BMS_PREFIX
        ):
            return None
        return pycompat.fsencode(h.target[len(_BMS_PREFIX) :])

    @active.setter
    def active(self, mark):
        raise NotImplementedError

    def names(self, node):
        r = []
        for ref in self.gitrepo.listall_references():
            if not ref.startswith(_BMS_PREFIX):
                continue
            if self.gitrepo.references[ref].peel().id.raw != node:
                continue
            r.append(pycompat.fsencode(ref[len(_BMS_PREFIX) :]))
        return r

    # Cleanup opportunity: this is *identical* to core's bookmarks store.
    def expandname(self, bname):
        if bname == b'.':
            if self.active:
                return self.active
            raise error.RepoLookupError(_(b"no active bookmark"))
        return bname

    def applychanges(self, repo, tr, changes):
        """Apply a list of changes to bookmarks
        """
        # TODO: this should respect transactions, but that's going to
        # require enlarging the gitbmstore to know how to do in-memory
        # temporary writes and read those back prior to transaction
        # finalization.
        for name, node in changes:
            if node is None:
                self.gitrepo.references.delete(
                    _BMS_PREFIX + pycompat.fsdecode(name)
                )
            else:
                self.gitrepo.references.create(
                    _BMS_PREFIX + pycompat.fsdecode(name),
                    gitutil.togitnode(node),
                    force=True,
                )


def init(orig, ui, dest=b'.', **opts):
    if opts.get('git', False):
        path = os.path.abspath(dest)
        # TODO: walk up looking for the git repo
        _setupdothg(ui, path)
        return 0
    return orig(ui, dest=dest, **opts)


def reposetup(ui, repo):
    if isinstance(repo.store, gitstore):
        orig = repo.__class__
        repo.store._progress_factory = repo.ui.makeprogress

        class gitlocalrepo(orig):
            def _makedirstate(self):
                # TODO narrow support here
                return dirstate.gitdirstate(
                    self.ui, self.vfs.base, self.store.git
                )

            def commit(self, *args, **kwargs):
                ret = orig.commit(self, *args, **kwargs)
                tid = self.store.git[gitutil.togitnode(ret)].tree.id
                # DANGER! This will flush any writes staged to the
                # index in Git, but we're sidestepping the index in a
                # way that confuses git when we commit. Alas.
                self.store.git.index.read_tree(tid)
                self.store.git.index.write()
                return ret

            @property
            def _bookmarks(self):
                return gitbmstore(self.store.git)

        repo.__class__ = gitlocalrepo
    return repo


def extsetup(ui):
    extensions.wrapfunction(localrepo, b'makestore', _makestore)
    extensions.wrapfunction(localrepo, b'makefilestorage', _makefilestorage)
    # Inject --git flag for `hg init`
    entry = extensions.wrapcommand(commands.table, b'init', init)
    entry[1].extend(
        [(b'', b'git', None, b'setup up a git repository instead of hg')]
    )
