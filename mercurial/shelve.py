# shelve.py - save/restore working directory state
#
# Copyright 2013 Facebook, Inc.
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

"""save and restore changes to the working directory

The "hg shelve" command saves changes made to the working directory
and reverts those changes, resetting the working directory to a clean
state.

Later on, the "hg unshelve" command restores the changes saved by "hg
shelve". Changes can be restored even after updating to a different
parent, in which case Mercurial's merge machinery will resolve any
conflicts if necessary.

You can have more than one shelved change outstanding at a time; each
shelved change has a distinct name. For details, see the help for "hg
shelve".
"""
from __future__ import absolute_import

import collections
import errno
import itertools
import stat

from .i18n import _
from . import (
    bookmarks,
    bundle2,
    bundlerepo,
    changegroup,
    cmdutil,
    discovery,
    error,
    exchange,
    hg,
    lock as lockmod,
    mdiff,
    merge,
    node as nodemod,
    patch,
    phases,
    pycompat,
    repair,
    scmutil,
    templatefilters,
    util,
    vfs as vfsmod,
)
from .utils import (
    dateutil,
    stringutil,
)

backupdir = 'shelve-backup'
shelvedir = 'shelved'
shelvefileextensions = ['hg', 'patch', 'shelve']
# universal extension is present in all types of shelves
patchextension = 'patch'

# we never need the user, so we use a
# generic user for all shelve operations
shelveuser = 'shelve@localhost'

class shelvedfile(object):
    """Helper for the file storing a single shelve

    Handles common functions on shelve files (.hg/.patch) using
    the vfs layer"""
    def __init__(self, repo, name, filetype=None):
        self.repo = repo
        self.name = name
        self.vfs = vfsmod.vfs(repo.vfs.join(shelvedir))
        self.backupvfs = vfsmod.vfs(repo.vfs.join(backupdir))
        self.ui = self.repo.ui
        if filetype:
            self.fname = name + '.' + filetype
        else:
            self.fname = name

    def exists(self):
        return self.vfs.exists(self.fname)

    def filename(self):
        return self.vfs.join(self.fname)

    def backupfilename(self):
        def gennames(base):
            yield base
            base, ext = base.rsplit('.', 1)
            for i in itertools.count(1):
                yield '%s-%d.%s' % (base, i, ext)

        name = self.backupvfs.join(self.fname)
        for n in gennames(name):
            if not self.backupvfs.exists(n):
                return n

    def movetobackup(self):
        if not self.backupvfs.isdir():
            self.backupvfs.makedir()
        util.rename(self.filename(), self.backupfilename())

    def stat(self):
        return self.vfs.stat(self.fname)

    def opener(self, mode='rb'):
        try:
            return self.vfs(self.fname, mode)
        except IOError as err:
            if err.errno != errno.ENOENT:
                raise
            raise error.Abort(_("shelved change '%s' not found") % self.name)

    def applybundle(self, tr):
        fp = self.opener()
        try:
            targetphase = phases.internal
            if not phases.supportinternal(self.repo):
                targetphase = phases.secret
            gen = exchange.readbundle(self.repo.ui, fp, self.fname, self.vfs)
            pretip = self.repo['tip']
            bundle2.applybundle(self.repo, gen, tr,
                                source='unshelve',
                                url='bundle:' + self.vfs.join(self.fname),
                                targetphase=targetphase)
            shelvectx = self.repo['tip']
            if pretip == shelvectx:
                shelverev = tr.changes['revduplicates'][-1]
                shelvectx = self.repo[shelverev]
            return shelvectx
        finally:
            fp.close()

    def bundlerepo(self):
        path = self.vfs.join(self.fname)
        return bundlerepo.instance(self.repo.baseui,
                                   'bundle://%s+%s' % (self.repo.root, path))

    def writebundle(self, bases, node):
        cgversion = changegroup.safeversion(self.repo)
        if cgversion == '01':
            btype = 'HG10BZ'
            compression = None
        else:
            btype = 'HG20'
            compression = 'BZ'

        repo = self.repo.unfiltered()

        outgoing = discovery.outgoing(repo, missingroots=bases,
                                      missingheads=[node])
        cg = changegroup.makechangegroup(repo, outgoing, cgversion, 'shelve')

        bundle2.writebundle(self.ui, cg, self.fname, btype, self.vfs,
                                compression=compression)

    def writeinfo(self, info):
        scmutil.simplekeyvaluefile(self.vfs, self.fname).write(info)

    def readinfo(self):
        return scmutil.simplekeyvaluefile(self.vfs, self.fname).read()

class shelvedstate(object):
    """Handle persistence during unshelving operations.

    Handles saving and restoring a shelved state. Ensures that different
    versions of a shelved state are possible and handles them appropriately.
    """
    _version = 2
    _filename = 'shelvedstate'
    _keep = 'keep'
    _nokeep = 'nokeep'
    # colon is essential to differentiate from a real bookmark name
    _noactivebook = ':no-active-bookmark'
    _interactive = 'interactive'

    @classmethod
    def _verifyandtransform(cls, d):
        """Some basic shelvestate syntactic verification and transformation"""
        try:
            d['originalwctx'] = nodemod.bin(d['originalwctx'])
            d['pendingctx'] = nodemod.bin(d['pendingctx'])
            d['parents'] = [nodemod.bin(h)
                            for h in d['parents'].split(' ')]
            d['nodestoremove'] = [nodemod.bin(h)
                                  for h in d['nodestoremove'].split(' ')]
        except (ValueError, TypeError, KeyError) as err:
            raise error.CorruptedState(pycompat.bytestr(err))

    @classmethod
    def _getversion(cls, repo):
        """Read version information from shelvestate file"""
        fp = repo.vfs(cls._filename)
        try:
            version = int(fp.readline().strip())
        except ValueError as err:
            raise error.CorruptedState(pycompat.bytestr(err))
        finally:
            fp.close()
        return version

    @classmethod
    def _readold(cls, repo):
        """Read the old position-based version of a shelvestate file"""
        # Order is important, because old shelvestate file uses it
        # to detemine values of fields (i.g. name is on the second line,
        # originalwctx is on the third and so forth). Please do not change.
        keys = ['version', 'name', 'originalwctx', 'pendingctx', 'parents',
                'nodestoremove', 'branchtorestore', 'keep', 'activebook']
        # this is executed only seldomly, so it is not a big deal
        # that we open this file twice
        fp = repo.vfs(cls._filename)
        d = {}
        try:
            for key in keys:
                d[key] = fp.readline().strip()
        finally:
            fp.close()
        return d

    @classmethod
    def load(cls, repo):
        version = cls._getversion(repo)
        if version < cls._version:
            d = cls._readold(repo)
        elif version == cls._version:
            d = scmutil.simplekeyvaluefile(
                repo.vfs, cls._filename).read(firstlinenonkeyval=True)
        else:
            raise error.Abort(_('this version of shelve is incompatible '
                                'with the version used in this repo'))

        cls._verifyandtransform(d)
        try:
            obj = cls()
            obj.name = d['name']
            obj.wctx = repo[d['originalwctx']]
            obj.pendingctx = repo[d['pendingctx']]
            obj.parents = d['parents']
            obj.nodestoremove = d['nodestoremove']
            obj.branchtorestore = d.get('branchtorestore', '')
            obj.keep = d.get('keep') == cls._keep
            obj.activebookmark = ''
            if d.get('activebook', '') != cls._noactivebook:
                obj.activebookmark = d.get('activebook', '')
            obj.interactive = d.get('interactive') == cls._interactive
        except (error.RepoLookupError, KeyError) as err:
            raise error.CorruptedState(pycompat.bytestr(err))

        return obj

    @classmethod
    def save(cls, repo, name, originalwctx, pendingctx, nodestoremove,
             branchtorestore, keep=False, activebook='', interactive=False):
        info = {
            "name": name,
            "originalwctx": nodemod.hex(originalwctx.node()),
            "pendingctx": nodemod.hex(pendingctx.node()),
            "parents": ' '.join([nodemod.hex(p)
                                 for p in repo.dirstate.parents()]),
            "nodestoremove": ' '.join([nodemod.hex(n)
                                      for n in nodestoremove]),
            "branchtorestore": branchtorestore,
            "keep": cls._keep if keep else cls._nokeep,
            "activebook": activebook or cls._noactivebook
        }
        if interactive:
            info['interactive'] = cls._interactive
        scmutil.simplekeyvaluefile(
            repo.vfs, cls._filename).write(info,
                                           firstline=("%d" % cls._version))

    @classmethod
    def clear(cls, repo):
        repo.vfs.unlinkpath(cls._filename, ignoremissing=True)

def cleanupoldbackups(repo):
    vfs = vfsmod.vfs(repo.vfs.join(backupdir))
    maxbackups = repo.ui.configint('shelve', 'maxbackups')
    hgfiles = [f for f in vfs.listdir()
               if f.endswith('.' + patchextension)]
    hgfiles = sorted([(vfs.stat(f)[stat.ST_MTIME], f) for f in hgfiles])
    if maxbackups > 0 and maxbackups < len(hgfiles):
        bordermtime = hgfiles[-maxbackups][0]
    else:
        bordermtime = None
    for mtime, f in hgfiles[:len(hgfiles) - maxbackups]:
        if mtime == bordermtime:
            # keep it, because timestamp can't decide exact order of backups
            continue
        base = f[:-(1 + len(patchextension))]
        for ext in shelvefileextensions:
            vfs.tryunlink(base + '.' + ext)

def _backupactivebookmark(repo):
    activebookmark = repo._activebookmark
    if activebookmark:
        bookmarks.deactivate(repo)
    return activebookmark

def _restoreactivebookmark(repo, mark):
    if mark:
        bookmarks.activate(repo, mark)

def _aborttransaction(repo, tr):
    '''Abort current transaction for shelve/unshelve, but keep dirstate
    '''
    dirstatebackupname = 'dirstate.shelve'
    repo.dirstate.savebackup(tr, dirstatebackupname)
    tr.abort()
    repo.dirstate.restorebackup(None, dirstatebackupname)

def getshelvename(repo, parent, opts):
    """Decide on the name this shelve is going to have"""
    def gennames():
        yield label
        for i in itertools.count(1):
            yield '%s-%02d' % (label, i)
    name = opts.get('name')
    label = repo._activebookmark or parent.branch() or 'default'
    # slashes aren't allowed in filenames, therefore we rename it
    label = label.replace('/', '_')
    label = label.replace('\\', '_')
    # filenames must not start with '.' as it should not be hidden
    if label.startswith('.'):
        label = label.replace('.', '_', 1)

    if name:
        if shelvedfile(repo, name, patchextension).exists():
            e = _("a shelved change named '%s' already exists") % name
            raise error.Abort(e)

        # ensure we are not creating a subdirectory or a hidden file
        if '/' in name or '\\' in name:
            raise error.Abort(_('shelved change names can not contain slashes'))
        if name.startswith('.'):
            raise error.Abort(_("shelved change names can not start with '.'"))

    else:
        for n in gennames():
            if not shelvedfile(repo, n, patchextension).exists():
                name = n
                break

    return name

def mutableancestors(ctx):
    """return all mutable ancestors for ctx (included)

    Much faster than the revset ancestors(ctx) & draft()"""
    seen = {nodemod.nullrev}
    visit = collections.deque()
    visit.append(ctx)
    while visit:
        ctx = visit.popleft()
        yield ctx.node()
        for parent in ctx.parents():
            rev = parent.rev()
            if rev not in seen:
                seen.add(rev)
                if parent.mutable():
                    visit.append(parent)

def getcommitfunc(extra, interactive, editor=False):
    def commitfunc(ui, repo, message, match, opts):
        hasmq = util.safehasattr(repo, 'mq')
        if hasmq:
            saved, repo.mq.checkapplied = repo.mq.checkapplied, False

        targetphase = phases.internal
        if not phases.supportinternal(repo):
            targetphase = phases.secret
        overrides = {('phases', 'new-commit'): targetphase}
        try:
            editor_ = False
            if editor:
                editor_ = cmdutil.getcommiteditor(editform='shelve.shelve',
                                                  **pycompat.strkwargs(opts))
            with repo.ui.configoverride(overrides):
                return repo.commit(message, shelveuser, opts.get('date'),
                                   match, editor=editor_, extra=extra)
        finally:
            if hasmq:
                repo.mq.checkapplied = saved

    def interactivecommitfunc(ui, repo, *pats, **opts):
        opts = pycompat.byteskwargs(opts)
        match = scmutil.match(repo['.'], pats, {})
        message = opts['message']
        return commitfunc(ui, repo, message, match, opts)

    return interactivecommitfunc if interactive else commitfunc

def _nothingtoshelvemessaging(ui, repo, pats, opts):
    stat = repo.status(match=scmutil.match(repo[None], pats, opts))
    if stat.deleted:
        ui.status(_("nothing changed (%d missing files, see "
                    "'hg status')\n") % len(stat.deleted))
    else:
        ui.status(_("nothing changed\n"))

def _shelvecreatedcommit(repo, node, name, match):
    info = {'node': nodemod.hex(node)}
    shelvedfile(repo, name, 'shelve').writeinfo(info)
    bases = list(mutableancestors(repo[node]))
    shelvedfile(repo, name, 'hg').writebundle(bases, node)
    with shelvedfile(repo, name, patchextension).opener('wb') as fp:
        cmdutil.exportfile(repo, [node], fp, opts=mdiff.diffopts(git=True),
                           match=match)

def _includeunknownfiles(repo, pats, opts, extra):
    s = repo.status(match=scmutil.match(repo[None], pats, opts),
                    unknown=True)
    if s.unknown:
        extra['shelve_unknown'] = '\0'.join(s.unknown)
        repo[None].add(s.unknown)

def _finishshelve(repo, tr):
    if phases.supportinternal(repo):
        tr.close()
    else:
        _aborttransaction(repo, tr)

def createcmd(ui, repo, pats, opts):
    """subcommand that creates a new shelve"""
    with repo.wlock():
        cmdutil.checkunfinished(repo)
        return _docreatecmd(ui, repo, pats, opts)

def _docreatecmd(ui, repo, pats, opts):
    wctx = repo[None]
    parents = wctx.parents()
    parent = parents[0]
    origbranch = wctx.branch()

    if parent.node() != nodemod.nullid:
        desc = "changes to: %s" % parent.description().split('\n', 1)[0]
    else:
        desc = '(changes in empty repository)'

    if not opts.get('message'):
        opts['message'] = desc

    lock = tr = activebookmark = None
    try:
        lock = repo.lock()

        # use an uncommitted transaction to generate the bundle to avoid
        # pull races. ensure we don't print the abort message to stderr.
        tr = repo.transaction('shelve', report=lambda x: None)

        interactive = opts.get('interactive', False)
        includeunknown = (opts.get('unknown', False) and
                          not opts.get('addremove', False))

        name = getshelvename(repo, parent, opts)
        activebookmark = _backupactivebookmark(repo)
        extra = {'internal': 'shelve'}
        if includeunknown:
            _includeunknownfiles(repo, pats, opts, extra)

        if _iswctxonnewbranch(repo) and not _isbareshelve(pats, opts):
            # In non-bare shelve we don't store newly created branch
            # at bundled commit
            repo.dirstate.setbranch(repo['.'].branch())

        commitfunc = getcommitfunc(extra, interactive, editor=True)
        if not interactive:
            node = cmdutil.commit(ui, repo, commitfunc, pats, opts)
        else:
            node = cmdutil.dorecord(ui, repo, commitfunc, None,
                                    False, cmdutil.recordfilter, *pats,
                                    **pycompat.strkwargs(opts))
        if not node:
            _nothingtoshelvemessaging(ui, repo, pats, opts)
            return 1

        # Create a matcher so that prefetch doesn't attempt to fetch
        # the entire repository pointlessly, and as an optimisation
        # for movedirstate, if needed.
        match = scmutil.matchfiles(repo, repo[node].files())
        _shelvecreatedcommit(repo, node, name, match)

        if ui.formatted():
            desc = stringutil.ellipsis(desc, ui.termwidth())
        ui.status(_('shelved as %s\n') % name)
        if opts['keep']:
            with repo.dirstate.parentchange():
                scmutil.movedirstate(repo, parent, match)
        else:
            hg.update(repo, parent.node())
        if origbranch != repo['.'].branch() and not _isbareshelve(pats, opts):
            repo.dirstate.setbranch(origbranch)

        _finishshelve(repo, tr)
    finally:
        _restoreactivebookmark(repo, activebookmark)
        lockmod.release(tr, lock)

def _isbareshelve(pats, opts):
    return (not pats
            and not opts.get('interactive', False)
            and not opts.get('include', False)
            and not opts.get('exclude', False))

def _iswctxonnewbranch(repo):
    return repo[None].branch() != repo['.'].branch()

def cleanupcmd(ui, repo):
    """subcommand that deletes all shelves"""

    with repo.wlock():
        for (name, _type) in repo.vfs.readdir(shelvedir):
            suffix = name.rsplit('.', 1)[-1]
            if suffix in shelvefileextensions:
                shelvedfile(repo, name).movetobackup()
            cleanupoldbackups(repo)

def deletecmd(ui, repo, pats):
    """subcommand that deletes a specific shelve"""
    if not pats:
        raise error.Abort(_('no shelved changes specified!'))
    with repo.wlock():
        try:
            for name in pats:
                for suffix in shelvefileextensions:
                    shfile = shelvedfile(repo, name, suffix)
                    # patch file is necessary, as it should
                    # be present for any kind of shelve,
                    # but the .hg file is optional as in future we
                    # will add obsolete shelve with does not create a
                    # bundle
                    if shfile.exists() or suffix == patchextension:
                        shfile.movetobackup()
            cleanupoldbackups(repo)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
            raise error.Abort(_("shelved change '%s' not found") % name)

def listshelves(repo):
    """return all shelves in repo as list of (time, filename)"""
    try:
        names = repo.vfs.readdir(shelvedir)
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise
        return []
    info = []
    for (name, _type) in names:
        pfx, sfx = name.rsplit('.', 1)
        if not pfx or sfx != patchextension:
            continue
        st = shelvedfile(repo, name).stat()
        info.append((st[stat.ST_MTIME], shelvedfile(repo, pfx).filename()))
    return sorted(info, reverse=True)

def listcmd(ui, repo, pats, opts):
    """subcommand that displays the list of shelves"""
    pats = set(pats)
    width = 80
    if not ui.plain():
        width = ui.termwidth()
    namelabel = 'shelve.newest'
    ui.pager('shelve')
    for mtime, name in listshelves(repo):
        sname = util.split(name)[1]
        if pats and sname not in pats:
            continue
        ui.write(sname, label=namelabel)
        namelabel = 'shelve.name'
        if ui.quiet:
            ui.write('\n')
            continue
        ui.write(' ' * (16 - len(sname)))
        used = 16
        date = dateutil.makedate(mtime)
        age = '(%s)' % templatefilters.age(date, abbrev=True)
        ui.write(age, label='shelve.age')
        ui.write(' ' * (12 - len(age)))
        used += 12
        with open(name + '.' + patchextension, 'rb') as fp:
            while True:
                line = fp.readline()
                if not line:
                    break
                if not line.startswith('#'):
                    desc = line.rstrip()
                    if ui.formatted():
                        desc = stringutil.ellipsis(desc, width - used)
                    ui.write(desc)
                    break
            ui.write('\n')
            if not (opts['patch'] or opts['stat']):
                continue
            difflines = fp.readlines()
            if opts['patch']:
                for chunk, label in patch.difflabel(iter, difflines):
                    ui.write(chunk, label=label)
            if opts['stat']:
                for chunk, label in patch.diffstatui(difflines, width=width):
                    ui.write(chunk, label=label)

def patchcmds(ui, repo, pats, opts):
    """subcommand that displays shelves"""
    if len(pats) == 0:
        shelves = listshelves(repo)
        if not shelves:
            raise error.Abort(_("there are no shelves to show"))
        mtime, name = shelves[0]
        sname = util.split(name)[1]
        pats = [sname]

    for shelfname in pats:
        if not shelvedfile(repo, shelfname, patchextension).exists():
            raise error.Abort(_("cannot find shelf %s") % shelfname)

    listcmd(ui, repo, pats, opts)

def checkparents(repo, state):
    """check parent while resuming an unshelve"""
    if state.parents != repo.dirstate.parents():
        raise error.Abort(_('working directory parents do not match unshelve '
                           'state'))

def _loadshelvedstate(ui, repo, opts):
    try:
        state = shelvedstate.load(repo)
        if opts.get('keep') is None:
            opts['keep'] = state.keep
    except IOError as err:
        if err.errno != errno.ENOENT:
            raise
        cmdutil.wrongtooltocontinue(repo, _('unshelve'))
    except error.CorruptedState as err:
        ui.debug(pycompat.bytestr(err) + '\n')
        if opts.get('continue'):
            msg = _('corrupted shelved state file')
            hint = _('please run hg unshelve --abort to abort unshelve '
                     'operation')
            raise error.Abort(msg, hint=hint)
        elif opts.get('abort'):
            shelvedstate.clear(repo)
            raise error.Abort(_('could not read shelved state file, your '
                                'working copy may be in an unexpected state\n'
                                'please update to some commit\n'))
    return state

def unshelveabort(ui, repo, state):
    """subcommand that abort an in-progress unshelve"""
    with repo.lock():
        try:
            checkparents(repo, state)

            merge.update(repo, state.pendingctx, branchmerge=False, force=True)
            if (state.activebookmark
                    and state.activebookmark in repo._bookmarks):
                bookmarks.activate(repo, state.activebookmark)
            mergefiles(ui, repo, state.wctx, state.pendingctx)
            if not phases.supportinternal(repo):
                repair.strip(ui, repo, state.nodestoremove, backup=False,
                             topic='shelve')
        finally:
            shelvedstate.clear(repo)
            ui.warn(_("unshelve of '%s' aborted\n") % state.name)

def hgabortunshelve(ui, repo):
    """logic to  abort unshelve using 'hg abort"""
    with repo.wlock():
        state = _loadshelvedstate(ui, repo, {'abort' : True})
        return unshelveabort(ui, repo, state)

def mergefiles(ui, repo, wctx, shelvectx):
    """updates to wctx and merges the changes from shelvectx into the
    dirstate."""
    with ui.configoverride({('ui', 'quiet'): True}):
        hg.update(repo, wctx.node())
        ui.pushbuffer(True)
        cmdutil.revert(ui, repo, shelvectx, repo.dirstate.parents())
        ui.popbuffer()

def restorebranch(ui, repo, branchtorestore):
    if branchtorestore and branchtorestore != repo.dirstate.branch():
        repo.dirstate.setbranch(branchtorestore)
        ui.status(_('marked working directory as branch %s\n')
                  % branchtorestore)

def unshelvecleanup(ui, repo, name, opts):
    """remove related files after an unshelve"""
    if not opts.get('keep'):
        for filetype in shelvefileextensions:
            shfile = shelvedfile(repo, name, filetype)
            if shfile.exists():
                shfile.movetobackup()
        cleanupoldbackups(repo)
def unshelvecontinue(ui, repo, state, opts):
    """subcommand to continue an in-progress unshelve"""
    # We're finishing off a merge. First parent is our original
    # parent, second is the temporary "fake" commit we're unshelving.
    interactive = state.interactive
    basename = state.name
    with repo.lock():
        checkparents(repo, state)
        ms = merge.mergestate.read(repo)
        if list(ms.unresolved()):
            raise error.Abort(
                _("unresolved conflicts, can't continue"),
                hint=_("see 'hg resolve', then 'hg unshelve --continue'"))

        shelvectx = repo[state.parents[1]]
        pendingctx = state.pendingctx

        with repo.dirstate.parentchange():
            repo.setparents(state.pendingctx.node(), nodemod.nullid)
            repo.dirstate.write(repo.currenttransaction())

        targetphase = phases.internal
        if not phases.supportinternal(repo):
            targetphase = phases.secret
        overrides = {('phases', 'new-commit'): targetphase}
        with repo.ui.configoverride(overrides, 'unshelve'):
            with repo.dirstate.parentchange():
                repo.setparents(state.parents[0], nodemod.nullid)
                newnode, ispartialunshelve = _createunshelvectx(ui,
                        repo, shelvectx, basename, interactive, opts)

        if newnode is None:
            # If it ended up being a no-op commit, then the normal
            # merge state clean-up path doesn't happen, so do it
            # here. Fix issue5494
            merge.mergestate.clean(repo)
            shelvectx = state.pendingctx
            msg = _('note: unshelved changes already existed '
                    'in the working copy\n')
            ui.status(msg)
        else:
            # only strip the shelvectx if we produced one
            state.nodestoremove.append(newnode)
            shelvectx = repo[newnode]

        hg.updaterepo(repo, pendingctx.node(), overwrite=False)
        mergefiles(ui, repo, state.wctx, shelvectx)
        restorebranch(ui, repo, state.branchtorestore)

        if not phases.supportinternal(repo):
            repair.strip(ui, repo, state.nodestoremove, backup=False,
                         topic='shelve')
        shelvedstate.clear(repo)
        if not ispartialunshelve:
            unshelvecleanup(ui, repo, state.name, opts)
        _restoreactivebookmark(repo, state.activebookmark)
        ui.status(_("unshelve of '%s' complete\n") % state.name)

def hgcontinueunshelve(ui, repo):
    """logic to resume unshelve using 'hg continue'"""
    with repo.wlock():
        state = _loadshelvedstate(ui, repo, {'continue' : True})
        return unshelvecontinue(ui, repo, state, {'keep' : state.keep})

def _commitworkingcopychanges(ui, repo, opts, tmpwctx):
    """Temporarily commit working copy changes before moving unshelve commit"""
    # Store pending changes in a commit and remember added in case a shelve
    # contains unknown files that are part of the pending change
    s = repo.status()
    addedbefore = frozenset(s.added)
    if not (s.modified or s.added or s.removed):
        return tmpwctx, addedbefore
    ui.status(_("temporarily committing pending changes "
                "(restore with 'hg unshelve --abort')\n"))
    extra = {'internal': 'shelve'}
    commitfunc = getcommitfunc(extra=extra, interactive=False,
                               editor=False)
    tempopts = {}
    tempopts['message'] = "pending changes temporary commit"
    tempopts['date'] = opts.get('date')
    with ui.configoverride({('ui', 'quiet'): True}):
        node = cmdutil.commit(ui, repo, commitfunc, [], tempopts)
    tmpwctx = repo[node]
    return tmpwctx, addedbefore

def _unshelverestorecommit(ui, repo, tr, basename):
    """Recreate commit in the repository during the unshelve"""
    repo = repo.unfiltered()
    node = None
    if shelvedfile(repo, basename, 'shelve').exists():
        node = shelvedfile(repo, basename, 'shelve').readinfo()['node']
    if node is None or node not in repo:
        with ui.configoverride({('ui', 'quiet'): True}):
            shelvectx = shelvedfile(repo, basename, 'hg').applybundle(tr)
        # We might not strip the unbundled changeset, so we should keep track of
        # the unshelve node in case we need to reuse it (eg: unshelve --keep)
        if node is None:
            info = {'node': nodemod.hex(shelvectx.node())}
            shelvedfile(repo, basename, 'shelve').writeinfo(info)
    else:
        shelvectx = repo[node]

    return repo, shelvectx

def _createunshelvectx(ui, repo, shelvectx, basename, interactive, opts):
    """Handles the creation of unshelve commit and updates the shelve if it
    was partially unshelved.

    If interactive is:

      * False: Commits all the changes in the working directory.
      * True: Prompts the user to select changes to unshelve and commit them.
              Update the shelve with remaining changes.

    Returns the node of the new commit formed and a bool indicating whether
    the shelve was partially unshelved.Creates a commit ctx to unshelve
    interactively or non-interactively.

    The user might want to unshelve certain changes only from the stored
    shelve in interactive. So, we would create two commits. One with requested
    changes to unshelve at that time and the latter is shelved for future.

    Here, we return both the newnode which is created interactively and a
    bool to know whether the shelve is partly done or completely done.
    """
    opts['message'] = shelvectx.description()
    opts['interactive-unshelve'] = True
    pats = []
    if not interactive:
        newnode = repo.commit(text=shelvectx.description(),
                              extra=shelvectx.extra(),
                              user=shelvectx.user(),
                              date=shelvectx.date())
        return newnode, False

    commitfunc = getcommitfunc(shelvectx.extra(), interactive=True,
                               editor=True)
    newnode = cmdutil.dorecord(ui, repo, commitfunc, None, False,
                               cmdutil.recordfilter, *pats,
                               **pycompat.strkwargs(opts))
    snode = repo.commit(text=shelvectx.description(),
                        extra=shelvectx.extra(),
                        user=shelvectx.user())
    if snode:
        m = scmutil.matchfiles(repo, repo[snode].files())
        _shelvecreatedcommit(repo, snode, basename, m)

    return newnode, bool(snode)

def _rebaserestoredcommit(ui, repo, opts, tr, oldtiprev, basename, pctx,
                          tmpwctx, shelvectx, branchtorestore,
                          activebookmark):
    """Rebase restored commit from its original location to a destination"""
    # If the shelve is not immediately on top of the commit
    # we'll be merging with, rebase it to be on top.
    interactive = opts.get('interactive')
    if tmpwctx.node() == shelvectx.p1().node() and not interactive:
        # We won't skip on interactive mode because, the user might want to
        # unshelve certain changes only.
        return shelvectx, False

    overrides = {
        ('ui', 'forcemerge'): opts.get('tool', ''),
        ('phases', 'new-commit'): phases.secret,
    }
    with repo.ui.configoverride(overrides, 'unshelve'):
        ui.status(_('rebasing shelved changes\n'))
        stats = merge.graft(repo, shelvectx, shelvectx.p1(),
                           labels=['shelve', 'working-copy'],
                           keepconflictparent=True)
        if stats.unresolvedcount:
            tr.close()

            nodestoremove = [repo.changelog.node(rev)
                             for rev in pycompat.xrange(oldtiprev, len(repo))]
            shelvedstate.save(repo, basename, pctx, tmpwctx, nodestoremove,
                              branchtorestore, opts.get('keep'), activebookmark,
                              interactive)
            raise error.InterventionRequired(
                _("unresolved conflicts (see 'hg resolve', then "
                  "'hg unshelve --continue')"))

        with repo.dirstate.parentchange():
            repo.setparents(tmpwctx.node(), nodemod.nullid)
            newnode, ispartialunshelve = _createunshelvectx(ui, repo,
                                       shelvectx, basename, interactive, opts)

        if newnode is None:
            # If it ended up being a no-op commit, then the normal
            # merge state clean-up path doesn't happen, so do it
            # here. Fix issue5494
            merge.mergestate.clean(repo)
            shelvectx = tmpwctx
            msg = _('note: unshelved changes already existed '
                    'in the working copy\n')
            ui.status(msg)
        else:
            shelvectx = repo[newnode]
            hg.updaterepo(repo, tmpwctx.node(), False)

    return shelvectx, ispartialunshelve

def _forgetunknownfiles(repo, shelvectx, addedbefore):
    # Forget any files that were unknown before the shelve, unknown before
    # unshelve started, but are now added.
    shelveunknown = shelvectx.extra().get('shelve_unknown')
    if not shelveunknown:
        return
    shelveunknown = frozenset(shelveunknown.split('\0'))
    addedafter = frozenset(repo.status().added)
    toforget = (addedafter & shelveunknown) - addedbefore
    repo[None].forget(toforget)

def _finishunshelve(repo, oldtiprev, tr, activebookmark):
    _restoreactivebookmark(repo, activebookmark)
    # The transaction aborting will strip all the commits for us,
    # but it doesn't update the inmemory structures, so addchangegroup
    # hooks still fire and try to operate on the missing commits.
    # Clean up manually to prevent this.
    repo.unfiltered().changelog.strip(oldtiprev, tr)
    _aborttransaction(repo, tr)

def _checkunshelveuntrackedproblems(ui, repo, shelvectx):
    """Check potential problems which may result from working
    copy having untracked changes."""
    wcdeleted = set(repo.status().deleted)
    shelvetouched = set(shelvectx.files())
    intersection = wcdeleted.intersection(shelvetouched)
    if intersection:
        m = _("shelved change touches missing files")
        hint = _("run hg status to see which files are missing")
        raise error.Abort(m, hint=hint)

def dounshelve(ui, repo, *shelved, **opts):
    opts = pycompat.byteskwargs(opts)
    abortf = opts.get('abort')
    continuef = opts.get('continue')
    interactive = opts.get('interactive')
    if not abortf and not continuef:
        cmdutil.checkunfinished(repo)
    shelved = list(shelved)
    if opts.get("name"):
        shelved.append(opts["name"])

    if abortf or continuef:
        if abortf and continuef:
            raise error.Abort(_('cannot use both abort and continue'))
        if shelved:
            raise error.Abort(_('cannot combine abort/continue with '
                               'naming a shelved change'))
        if abortf and opts.get('tool', False):
            ui.warn(_('tool option will be ignored\n'))

        state = _loadshelvedstate(ui, repo, opts)
        if abortf:
            return unshelveabort(ui, repo, state)
        elif continuef and interactive:
            raise error.Abort(_('cannot use both continue and interactive'))
        elif continuef:
            return unshelvecontinue(ui, repo, state, opts)
    elif len(shelved) > 1:
        raise error.Abort(_('can only unshelve one change at a time'))
    elif not shelved:
        shelved = listshelves(repo)
        if not shelved:
            raise error.Abort(_('no shelved changes to apply!'))
        basename = util.split(shelved[0][1])[1]
        ui.status(_("unshelving change '%s'\n") % basename)
    else:
        basename = shelved[0]

    if not shelvedfile(repo, basename, patchextension).exists():
        raise error.Abort(_("shelved change '%s' not found") % basename)

    repo = repo.unfiltered()
    lock = tr = None
    try:
        lock = repo.lock()
        tr = repo.transaction('unshelve', report=lambda x: None)
        oldtiprev = len(repo)

        pctx = repo['.']
        tmpwctx = pctx
        # The goal is to have a commit structure like so:
        # ...-> pctx -> tmpwctx -> shelvectx
        # where tmpwctx is an optional commit with the user's pending changes
        # and shelvectx is the unshelved changes. Then we merge it all down
        # to the original pctx.

        activebookmark = _backupactivebookmark(repo)
        tmpwctx, addedbefore = _commitworkingcopychanges(ui, repo, opts,
                                                         tmpwctx)
        repo, shelvectx = _unshelverestorecommit(ui, repo, tr, basename)
        _checkunshelveuntrackedproblems(ui, repo, shelvectx)
        branchtorestore = ''
        if shelvectx.branch() != shelvectx.p1().branch():
            branchtorestore = shelvectx.branch()

        shelvectx, ispartialunshelve = _rebaserestoredcommit(ui, repo, opts,
            tr, oldtiprev, basename, pctx, tmpwctx, shelvectx,
            branchtorestore, activebookmark)
        overrides = {('ui', 'forcemerge'): opts.get('tool', '')}
        with ui.configoverride(overrides, 'unshelve'):
            mergefiles(ui, repo, pctx, shelvectx)
        restorebranch(ui, repo, branchtorestore)
        shelvedstate.clear(repo)
        _finishunshelve(repo, oldtiprev, tr, activebookmark)
        if not ispartialunshelve:
            _forgetunknownfiles(repo, shelvectx, addedbefore)
            unshelvecleanup(ui, repo, basename, opts)
    finally:
        if tr:
            tr.release()
        lockmod.release(lock)