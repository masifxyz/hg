# Copyright 2009-2010 Gregory P. Ward
# Copyright 2009-2010 Intelerad Medical Systems Incorporated
# Copyright 2010-2011 Fog Creek Software
# Copyright 2010-2011 Unity Technologies
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

'''High-level command function for lfconvert, plus the cmdtable.'''
from __future__ import absolute_import

import errno
import hashlib
import os
import shutil

from mercurial.i18n import _

from mercurial import (
    cmdutil,
    context,
    error,
    hg,
    lock,
    match as matchmod,
    node,
    registrar,
    scmutil,
    util,
)

from ..convert import (
    convcmd,
    filemap,
)

from . import (
    lfutil,
    storefactory
)

release = lock.release

# -- Commands ----------------------------------------------------------

cmdtable = {}
command = registrar.command(cmdtable)

@command('lfconvert',
    [('s', 'size', '',
      _('minimum size (MB) for files to be converted as largefiles'), 'SIZE'),
    ('', 'to-normal', False,
     _('convert from a largefiles repo to a normal repo')),
    ],
    _('hg lfconvert SOURCE DEST [FILE ...]'),
    norepo=True,
    inferrepo=True)
def lfconvert(ui, src, dest, *pats, **opts):
    '''convert a normal repository to a largefiles repository

    Convert repository SOURCE to a new repository DEST, identical to
    SOURCE except that certain files will be converted as largefiles:
    specifically, any file that matches any PATTERN *or* whose size is
    above the minimum size threshold is converted as a largefile. The
    size used to determine whether or not to track a file as a
    largefile is the size of the first version of the file. The
    minimum size can be specified either with --size or in
    configuration as ``largefiles.size``.

    After running this command you will need to make sure that
    largefiles is enabled anywhere you intend to push the new
    repository.

    Use --to-normal to convert largefiles back to normal files; after
    this, the DEST repository can be used without largefiles at all.'''

    if opts['to_normal']:
        tolfile = False
    else:
        tolfile = True
        size = lfutil.getminsize(ui, True, opts.get('size'), default=None)

    if not hg.islocal(src):
        raise error.Abort(_('%s is not a local Mercurial repo') % src)
    if not hg.islocal(dest):
        raise error.Abort(_('%s is not a local Mercurial repo') % dest)

    rsrc = hg.repository(ui, src)
    ui.status(_('initializing destination %s\n') % dest)
    rdst = hg.repository(ui, dest, create=True)

    success = False
    dstwlock = dstlock = None
    try:
        # Get a list of all changesets in the source.  The easy way to do this
        # is to simply walk the changelog, using changelog.nodesbetween().
        # Take a look at mercurial/revlog.py:639 for more details.
        # Use a generator instead of a list to decrease memory usage
        ctxs = (rsrc[ctx] for ctx in rsrc.changelog.nodesbetween(None,
            rsrc.heads())[0])
        revmap = {node.nullid: node.nullid}
        if tolfile:
            # Lock destination to prevent modification while it is converted to.
            # Don't need to lock src because we are just reading from its
            # history which can't change.
            dstwlock = rdst.wlock()
            dstlock = rdst.lock()

            lfiles = set()
            normalfiles = set()
            if not pats:
                pats = ui.configlist(lfutil.longname, 'patterns')
            if pats:
                matcher = matchmod.match(rsrc.root, '', list(pats))
            else:
                matcher = None

            lfiletohash = {}
            for ctx in ctxs:
                ui.progress(_('converting revisions'), ctx.rev(),
                    unit=_('revisions'), total=rsrc['tip'].rev())
                _lfconvert_addchangeset(rsrc, rdst, ctx, revmap,
                    lfiles, normalfiles, matcher, size, lfiletohash)
            ui.progress(_('converting revisions'), None)

            if rdst.wvfs.exists(lfutil.shortname):
                rdst.wvfs.rmtree(lfutil.shortname)

            for f in lfiletohash.keys():
                if rdst.wvfs.isfile(f):
                    rdst.wvfs.unlink(f)
                try:
                    rdst.wvfs.removedirs(rdst.wvfs.dirname(f))
                except OSError:
                    pass

            # If there were any files converted to largefiles, add largefiles
            # to the destination repository's requirements.
            if lfiles:
                rdst.requirements.add('largefiles')
                rdst._writerequirements()
        else:
            class lfsource(filemap.filemap_source):
                def __init__(self, ui, source):
                    super(lfsource, self).__init__(ui, source, None)
                    self.filemapper.rename[lfutil.shortname] = '.'

                def getfile(self, name, rev):
                    realname, realrev = rev
                    f = super(lfsource, self).getfile(name, rev)

                    if (not realname.startswith(lfutil.shortnameslash)
                            or f[0] is None):
                        return f

                    # Substitute in the largefile data for the hash
                    hash = f[0].strip()
                    path = lfutil.findfile(rsrc, hash)

                    if path is None:
                        raise error.Abort(_("missing largefile for '%s' in %s")
                                          % (realname, realrev))
                    return util.readfile(path), f[1]

            class converter(convcmd.converter):
                def __init__(self, ui, source, dest, revmapfile, opts):
                    src = lfsource(ui, source)

                    super(converter, self).__init__(ui, src, dest, revmapfile,
                                                    opts)

            found, missing = downloadlfiles(ui, rsrc)
            if missing != 0:
                raise error.Abort(_("all largefiles must be present locally"))

            orig = convcmd.converter
            convcmd.converter = converter

            try:
                convcmd.convert(ui, src, dest)
            finally:
                convcmd.converter = orig
        success = True
    finally:
        if tolfile:
            rdst.dirstate.clear()
            release(dstlock, dstwlock)
        if not success:
            # we failed, remove the new directory
            shutil.rmtree(rdst.root)

def _lfconvert_addchangeset(rsrc, rdst, ctx, revmap, lfiles, normalfiles,
        matcher, size, lfiletohash):
    # Convert src parents to dst parents
    parents = _convertparents(ctx, revmap)

    # Generate list of changed files
    files = _getchangedfiles(ctx, parents)

    dstfiles = []
    for f in files:
        if f not in lfiles and f not in normalfiles:
            islfile = _islfile(f, ctx, matcher, size)
            # If this file was renamed or copied then copy
            # the largefile-ness of its predecessor
            if f in ctx.manifest():
                fctx = ctx.filectx(f)
                renamed = fctx.renamed()
                renamedlfile = renamed and renamed[0] in lfiles
                islfile |= renamedlfile
                if 'l' in fctx.flags():
                    if renamedlfile:
                        raise error.Abort(
                            _('renamed/copied largefile %s becomes symlink')
                            % f)
                    islfile = False
            if islfile:
                lfiles.add(f)
            else:
                normalfiles.add(f)

        if f in lfiles:
            fstandin = lfutil.standin(f)
            dstfiles.append(fstandin)
            # largefile in manifest if it has not been removed/renamed
            if f in ctx.manifest():
                fctx = ctx.filectx(f)
                if 'l' in fctx.flags():
                    renamed = fctx.renamed()
                    if renamed and renamed[0] in lfiles:
                        raise error.Abort(_('largefile %s becomes symlink') % f)

                # largefile was modified, update standins
                m = hashlib.sha1('')
                m.update(ctx[f].data())
                hash = m.hexdigest()
                if f not in lfiletohash or lfiletohash[f] != hash:
                    rdst.wwrite(f, ctx[f].data(), ctx[f].flags())
                    executable = 'x' in ctx[f].flags()
                    lfutil.writestandin(rdst, fstandin, hash,
                        executable)
                    lfiletohash[f] = hash
        else:
            # normal file
            dstfiles.append(f)

    def getfilectx(repo, memctx, f):
        srcfname = lfutil.splitstandin(f)
        if srcfname is not None:
            # if the file isn't in the manifest then it was removed
            # or renamed, return None to indicate this
            try:
                fctx = ctx.filectx(srcfname)
            except error.LookupError:
                return None
            renamed = fctx.renamed()
            if renamed:
                # standin is always a largefile because largefile-ness
                # doesn't change after rename or copy
                renamed = lfutil.standin(renamed[0])

            return context.memfilectx(repo, f, lfiletohash[srcfname] + '\n',
                                      'l' in fctx.flags(), 'x' in fctx.flags(),
                                      renamed)
        else:
            return _getnormalcontext(repo, ctx, f, revmap)

    # Commit
    _commitcontext(rdst, parents, ctx, dstfiles, getfilectx, revmap)

def _commitcontext(rdst, parents, ctx, dstfiles, getfilectx, revmap):
    mctx = context.memctx(rdst, parents, ctx.description(), dstfiles,
                          getfilectx, ctx.user(), ctx.date(), ctx.extra())
    ret = rdst.commitctx(mctx)
    lfutil.copyalltostore(rdst, ret)
    rdst.setparents(ret)
    revmap[ctx.node()] = rdst.changelog.tip()

# Generate list of changed files
def _getchangedfiles(ctx, parents):
    files = set(ctx.files())
    if node.nullid not in parents:
        mc = ctx.manifest()
        mp1 = ctx.parents()[0].manifest()
        mp2 = ctx.parents()[1].manifest()
        files |= (set(mp1) | set(mp2)) - set(mc)
        for f in mc:
            if mc[f] != mp1.get(f, None) or mc[f] != mp2.get(f, None):
                files.add(f)
    return files

# Convert src parents to dst parents
def _convertparents(ctx, revmap):
    parents = []
    for p in ctx.parents():
        parents.append(revmap[p.node()])
    while len(parents) < 2:
        parents.append(node.nullid)
    return parents

# Get memfilectx for a normal file
def _getnormalcontext(repo, ctx, f, revmap):
    try:
        fctx = ctx.filectx(f)
    except error.LookupError:
        return None
    renamed = fctx.renamed()
    if renamed:
        renamed = renamed[0]

    data = fctx.data()
    if f == '.hgtags':
        data = _converttags (repo.ui, revmap, data)
    return context.memfilectx(repo, f, data, 'l' in fctx.flags(),
                              'x' in fctx.flags(), renamed)

# Remap tag data using a revision map
def _converttags(ui, revmap, data):
    newdata = []
    for line in data.splitlines():
        try:
            id, name = line.split(' ', 1)
        except ValueError:
            ui.warn(_('skipping incorrectly formatted tag %s\n')
                % line)
            continue
        try:
            newid = node.bin(id)
        except TypeError:
            ui.warn(_('skipping incorrectly formatted id %s\n')
                % id)
            continue
        try:
            newdata.append('%s %s\n' % (node.hex(revmap[newid]),
                name))
        except KeyError:
            ui.warn(_('no mapping for id %s\n') % id)
            continue
    return ''.join(newdata)

def _islfile(file, ctx, matcher, size):
    '''Return true if file should be considered a largefile, i.e.
    matcher matches it or it is larger than size.'''
    # never store special .hg* files as largefiles
    if file == '.hgtags' or file == '.hgignore' or file == '.hgsigs':
        return False
    if matcher and matcher(file):
        return True
    try:
        return ctx.filectx(file).size() >= size * 1024 * 1024
    except error.LookupError:
        return False

def uploadlfiles(ui, rsrc, rdst, files):
    '''upload largefiles to the central store'''

    if not files:
        return

    store = storefactory.openstore(rsrc, rdst, put=True)

    at = 0
    ui.debug("sending statlfile command for %d largefiles\n" % len(files))
    retval = store.exists(files)
    files = filter(lambda h: not retval[h], files)
    ui.debug("%d largefiles need to be uploaded\n" % len(files))

    for hash in files:
        ui.progress(_('uploading largefiles'), at, unit=_('files'),
                    total=len(files))
        source = lfutil.findfile(rsrc, hash)
        if not source:
            raise error.Abort(_('largefile %s missing from store'
                               ' (needs to be uploaded)') % hash)
        # XXX check for errors here
        store.put(source, hash)
        at += 1
    ui.progress(_('uploading largefiles'), None)

def verifylfiles(ui, repo, all=False, contents=False):
    '''Verify that every largefile revision in the current changeset
    exists in the central store.  With --contents, also verify that
    the contents of each local largefile file revision are correct (SHA-1 hash
    matches the revision ID).  With --all, check every changeset in
    this repository.'''
    if all:
        revs = repo.revs('all()')
    else:
        revs = ['.']

    store = storefactory.openstore(repo)
    return store.verify(revs, contents=contents)

def cachelfiles(ui, repo, node, filelist=None):
    '''cachelfiles ensures that all largefiles needed by the specified revision
    are present in the repository's largefile cache.

    returns a tuple (cached, missing).  cached is the list of files downloaded
    by this operation; missing is the list of files that were needed but could
    not be found.'''
    lfiles = lfutil.listlfiles(repo, node)
    if filelist:
        lfiles = set(lfiles) & set(filelist)
    toget = []

    ctx = repo[node]
    for lfile in lfiles:
        try:
            expectedhash = lfutil.readasstandin(ctx[lfutil.standin(lfile)])
        except IOError as err:
            if err.errno == errno.ENOENT:
                continue # node must be None and standin wasn't found in wctx
            raise
        if not lfutil.findfile(repo, expectedhash):
            toget.append((lfile, expectedhash))

    if toget:
        store = storefactory.openstore(repo)
        ret = store.get(toget)
        return ret

    return ([], [])

def downloadlfiles(ui, repo, rev=None):
    match = scmutil.match(repo[None], [repo.wjoin(lfutil.shortname)], {})
    def prepare(ctx, fns):
        pass
    totalsuccess = 0
    totalmissing = 0
    if rev != []: # walkchangerevs on empty list would return all revs
        for ctx in cmdutil.walkchangerevs(repo, match, {'rev' : rev},
                                          prepare):
            success, missing = cachelfiles(ui, repo, ctx.node())
            totalsuccess += len(success)
            totalmissing += len(missing)
    ui.status(_("%d additional largefiles cached\n") % totalsuccess)
    if totalmissing > 0:
        ui.status(_("%d largefiles failed to download\n") % totalmissing)
    return totalsuccess, totalmissing

def updatelfiles(ui, repo, filelist=None, printmessage=None,
                 normallookup=False):
    '''Update largefiles according to standins in the working directory

    If ``printmessage`` is other than ``None``, it means "print (or
    ignore, for false) message forcibly".
    '''
    statuswriter = lfutil.getstatuswriter(ui, repo, printmessage)
    with repo.wlock():
        lfdirstate = lfutil.openlfdirstate(ui, repo)
        lfiles = set(lfutil.listlfiles(repo)) | set(lfdirstate)

        if filelist is not None:
            filelist = set(filelist)
            lfiles = [f for f in lfiles if f in filelist]

        update = {}
        updated, removed = 0, 0
        wvfs = repo.wvfs
        wctx = repo[None]
        for lfile in lfiles:
            rellfile = lfile
            rellfileorig = os.path.relpath(
                scmutil.origpath(ui, repo, wvfs.join(rellfile)),
                start=repo.root)
            relstandin = lfutil.standin(lfile)
            relstandinorig = os.path.relpath(
                scmutil.origpath(ui, repo, wvfs.join(relstandin)),
                start=repo.root)
            if wvfs.exists(relstandin):
                if (wvfs.exists(relstandinorig) and
                    wvfs.exists(rellfile)):
                    shutil.copyfile(wvfs.join(rellfile),
                                    wvfs.join(rellfileorig))
                    wvfs.unlinkpath(relstandinorig)
                expecthash = lfutil.readasstandin(wctx[relstandin])
                if expecthash != '':
                    if lfile not in wctx: # not switched to normal file
                        wvfs.unlinkpath(rellfile, ignoremissing=True)
                    # use normallookup() to allocate an entry in largefiles
                    # dirstate to prevent lfilesrepo.status() from reporting
                    # missing files as removed.
                    lfdirstate.normallookup(lfile)
                    update[lfile] = expecthash
            else:
                # Remove lfiles for which the standin is deleted, unless the
                # lfile is added to the repository again. This happens when a
                # largefile is converted back to a normal file: the standin
                # disappears, but a new (normal) file appears as the lfile.
                if (wvfs.exists(rellfile) and
                    repo.dirstate.normalize(lfile) not in wctx):
                    wvfs.unlinkpath(rellfile)
                    removed += 1

        # largefile processing might be slow and be interrupted - be prepared
        lfdirstate.write()

        if lfiles:
            statuswriter(_('getting changed largefiles\n'))
            cachelfiles(ui, repo, None, lfiles)

        for lfile in lfiles:
            update1 = 0

            expecthash = update.get(lfile)
            if expecthash:
                if not lfutil.copyfromcache(repo, expecthash, lfile):
                    # failed ... but already removed and set to normallookup
                    continue
                # Synchronize largefile dirstate to the last modified
                # time of the file
                lfdirstate.normal(lfile)
                update1 = 1

            # copy the exec mode of largefile standin from the repository's
            # dirstate to its state in the lfdirstate.
            rellfile = lfile
            relstandin = lfutil.standin(lfile)
            if wvfs.exists(relstandin):
                # exec is decided by the users permissions using mask 0o100
                standinexec = wvfs.stat(relstandin).st_mode & 0o100
                st = wvfs.stat(rellfile)
                mode = st.st_mode
                if standinexec != mode & 0o100:
                    # first remove all X bits, then shift all R bits to X
                    mode &= ~0o111
                    if standinexec:
                        mode |= (mode >> 2) & 0o111 & ~util.umask
                    wvfs.chmod(rellfile, mode)
                    update1 = 1

            updated += update1

            lfutil.synclfdirstate(repo, lfdirstate, lfile, normallookup)

        lfdirstate.write()
        if lfiles:
            statuswriter(_('%d largefiles updated, %d removed\n') % (updated,
                removed))

@command('lfpull',
    [('r', 'rev', [], _('pull largefiles for these revisions'))
    ] + cmdutil.remoteopts,
    _('-r REV... [-e CMD] [--remotecmd CMD] [SOURCE]'))
def lfpull(ui, repo, source="default", **opts):
    """pull largefiles for the specified revisions from the specified source

    Pull largefiles that are referenced from local changesets but missing
    locally, pulling from a remote repository to the local cache.

    If SOURCE is omitted, the 'default' path will be used.
    See :hg:`help urls` for more information.

    .. container:: verbose

      Some examples:

      - pull largefiles for all branch heads::

          hg lfpull -r "head() and not closed()"

      - pull largefiles on the default branch::

          hg lfpull -r "branch(default)"
    """
    repo.lfpullsource = source

    revs = opts.get('rev', [])
    if not revs:
        raise error.Abort(_('no revisions specified'))
    revs = scmutil.revrange(repo, revs)

    numcached = 0
    for rev in revs:
        ui.note(_('pulling largefiles for revision %s\n') % rev)
        (cached, missing) = cachelfiles(ui, repo, rev)
        numcached += len(cached)
    ui.status(_("%d largefiles cached\n") % numcached)
