# commit.py - fonction to perform commit
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

from __future__ import absolute_import

import errno

from .i18n import _
from .node import (
    hex,
    nullid,
    nullrev,
)

from . import (
    context,
    mergestate,
    metadata,
    phases,
    scmutil,
    subrepoutil,
)


def _write_copy_meta(repo):
    """return a (changelog, filelog) boolean tuple

    changelog: copy related information should be stored in the changeset
    filelof:   copy related information should be written in the file revision
    """
    if repo.filecopiesmode == b'changeset-sidedata':
        writechangesetcopy = True
        writefilecopymeta = True
    else:
        writecopiesto = repo.ui.config(b'experimental', b'copies.write-to')
        writefilecopymeta = writecopiesto != b'changeset-only'
        writechangesetcopy = writecopiesto in (
            b'changeset-only',
            b'compatibility',
        )
    return writechangesetcopy, writefilecopymeta


def commitctx(repo, ctx, error=False, origctx=None):
    """Add a new revision to the target repository.
    Revision information is passed via the context argument.

    ctx.files() should list all files involved in this commit, i.e.
    modified/added/removed files. On merge, it may be wider than the
    ctx.files() to be committed, since any file nodes derived directly
    from p1 or p2 are excluded from the committed ctx.files().

    origctx is for convert to work around the problem that bug
    fixes to the files list in changesets change hashes. For
    convert to be the identity, it can pass an origctx and this
    function will use the same files list when it makes sense to
    do so.
    """
    repo = repo.unfiltered()

    p1, p2 = ctx.p1(), ctx.p2()
    user = ctx.user()

    with repo.lock(), repo.transaction(b"commit") as tr:
        r = _prepare_files(tr, ctx, error=error, origctx=origctx)
        mn, files, p1copies, p2copies, filesadded, filesremoved = r

        # update changelog
        repo.ui.note(_(b"committing changelog\n"))
        repo.changelog.delayupdate(tr)
        n = repo.changelog.add(
            mn,
            files,
            ctx.description(),
            tr,
            p1.node(),
            p2.node(),
            user,
            ctx.date(),
            ctx.extra().copy(),
            p1copies,
            p2copies,
            filesadded,
            filesremoved,
        )
        xp1, xp2 = p1.hex(), p2 and p2.hex() or b''
        repo.hook(
            b'pretxncommit', throw=True, node=hex(n), parent1=xp1, parent2=xp2,
        )
        # set the new commit is proper phase
        targetphase = subrepoutil.newcommitphase(repo.ui, ctx)
        if targetphase:
            # retract boundary do not alter parent changeset.
            # if a parent have higher the resulting phase will
            # be compliant anyway
            #
            # if minimal phase was 0 we don't need to retract anything
            phases.registernew(repo, tr, targetphase, [n])
        return n


def _prepare_files(tr, ctx, error=False, origctx=None):
    repo = ctx.repo()
    p1 = ctx.p1()

    writechangesetcopy, writefilecopymeta = _write_copy_meta(repo)

    p1copies, p2copies = None, None
    if writechangesetcopy:
        p1copies = ctx.p1copies()
        p2copies = ctx.p2copies()
    filesadded, filesremoved = None, None
    if ctx.manifestnode():
        # reuse an existing manifest revision
        repo.ui.debug(b'reusing known manifest\n')
        mn = ctx.manifestnode()
        files = ctx.files()
        if writechangesetcopy:
            filesadded = ctx.filesadded()
            filesremoved = ctx.filesremoved()
    elif not ctx.files():
        repo.ui.debug(b'reusing manifest from p1 (no file change)\n')
        mn = p1.manifestnode()
        files = []
    else:
        mn, files, added, removed = _process_files(tr, ctx, error=error)
        if writechangesetcopy:
            filesremoved = removed
            filesadded = added

    if origctx and origctx.manifestnode() == mn:
        files = origctx.files()

    if not writefilecopymeta:
        # If writing only to changeset extras, use None to indicate that
        # no entry should be written. If writing to both, write an empty
        # entry to prevent the reader from falling back to reading
        # filelogs.
        p1copies = p1copies or None
        p2copies = p2copies or None
        filesadded = filesadded or None
        filesremoved = filesremoved or None

    return mn, files, p1copies, p2copies, filesadded, filesremoved


def _process_files(tr, ctx, error=False):
    repo = ctx.repo()
    p1 = ctx.p1()
    p2 = ctx.p2()

    writechangesetcopy, writefilecopymeta = _write_copy_meta(repo)

    m1ctx = p1.manifestctx()
    m2ctx = p2.manifestctx()
    mctx = m1ctx.copy()

    m = mctx.read()
    m1 = m1ctx.read()
    m2 = m2ctx.read()

    # check in files
    added = []
    filesadded = []
    removed = list(ctx.removed())
    touched = []
    linkrev = len(repo)
    repo.ui.note(_(b"committing files:\n"))
    uipathfn = scmutil.getuipathfn(repo)
    for f in sorted(ctx.modified() + ctx.added()):
        repo.ui.note(uipathfn(f) + b"\n")
        try:
            fctx = ctx[f]
            if fctx is None:
                removed.append(f)
            else:
                added.append(f)
                m[f], is_touched = _filecommit(
                    repo, fctx, m1, m2, linkrev, tr, writefilecopymeta,
                )
                if is_touched:
                    touched.append(f)
                    if is_touched == 'added':
                        filesadded.append(f)
                m.setflag(f, fctx.flags())
        except OSError:
            repo.ui.warn(_(b"trouble committing %s!\n") % uipathfn(f))
            raise
        except IOError as inst:
            errcode = getattr(inst, 'errno', errno.ENOENT)
            if error or errcode and errcode != errno.ENOENT:
                repo.ui.warn(_(b"trouble committing %s!\n") % uipathfn(f))
            raise

    # update manifest
    removed = [f for f in removed if f in m1 or f in m2]
    drop = sorted([f for f in removed if f in m])
    for f in drop:
        del m[f]
    if p2.rev() != nullrev:
        rf = metadata.get_removal_filter(ctx, (p1, p2, m1, m2))
        removed = [f for f in removed if not rf(f)]

    touched.extend(removed)

    files = touched
    mn = _commit_manifest(tr, linkrev, ctx, mctx, files, added, drop)

    return mn, files, filesadded, removed


def _filecommit(
    repo, fctx, manifest1, manifest2, linkrev, tr, includecopymeta,
):
    """
    commit an individual file as part of a larger transaction

    input:

        fctx:       a file context with the content we are trying to commit
        manifest1:  manifest of changeset first parent
        manifest2:  manifest of changeset second parent
        linkrev:    revision number of the changeset being created
        tr:         current transation
        individual: boolean, set to False to skip storing the copy data
                    (only used by the Google specific feature of using
                    changeset extra as copy source of truth).

    output: (filenode, touched)

        filenode: the filenode that should be used by this changeset
        touched:  one of: None (mean untouched), 'added' or 'modified'
    """

    fname = fctx.path()
    fparent1 = manifest1.get(fname, nullid)
    fparent2 = manifest2.get(fname, nullid)
    touched = None
    if fparent1 == fparent2 == nullid:
        touched = 'added'

    if isinstance(fctx, context.filectx):
        # This block fast path most comparisons which are usually done. It
        # assumes that bare filectx is used and no merge happened, hence no
        # need to create a new file revision in this case.
        node = fctx.filenode()
        if node in [fparent1, fparent2]:
            repo.ui.debug(b'reusing %s filelog entry\n' % fname)
            if (
                fparent1 != nullid and manifest1.flags(fname) != fctx.flags()
            ) or (
                fparent2 != nullid and manifest2.flags(fname) != fctx.flags()
            ):
                touched = 'modified'
            return node, touched

    flog = repo.file(fname)
    meta = {}
    cfname = fctx.copysource()
    fnode = None

    if cfname and cfname != fname:
        # Mark the new revision of this file as a copy of another
        # file.  This copy data will effectively act as a parent
        # of this new revision.  If this is a merge, the first
        # parent will be the nullid (meaning "look up the copy data")
        # and the second one will be the other parent.  For example:
        #
        # 0 --- 1 --- 3   rev1 changes file foo
        #   \       /     rev2 renames foo to bar and changes it
        #    \- 2 -/      rev3 should have bar with all changes and
        #                      should record that bar descends from
        #                      bar in rev2 and foo in rev1
        #
        # this allows this merge to succeed:
        #
        # 0 --- 1 --- 3   rev4 reverts the content change from rev2
        #   \       /     merging rev3 and rev4 should use bar@rev2
        #    \- 2 --- 4        as the merge base
        #

        cnode = manifest1.get(cfname)
        newfparent = fparent2

        if manifest2:  # branch merge
            if fparent2 == nullid or cnode is None:  # copied on remote side
                if cfname in manifest2:
                    cnode = manifest2[cfname]
                    newfparent = fparent1

        # Here, we used to search backwards through history to try to find
        # where the file copy came from if the source of a copy was not in
        # the parent directory. However, this doesn't actually make sense to
        # do (what does a copy from something not in your working copy even
        # mean?) and it causes bugs (eg, issue4476). Instead, we will warn
        # the user that copy information was dropped, so if they didn't
        # expect this outcome it can be fixed, but this is the correct
        # behavior in this circumstance.

        if cnode:
            repo.ui.debug(b" %s: copy %s:%s\n" % (fname, cfname, hex(cnode)))
            if includecopymeta:
                meta[b"copy"] = cfname
                meta[b"copyrev"] = hex(cnode)
            fparent1, fparent2 = nullid, newfparent
        else:
            repo.ui.warn(
                _(
                    b"warning: can't find ancestor for '%s' "
                    b"copied from '%s'!\n"
                )
                % (fname, cfname)
            )

    elif fparent1 == nullid:
        fparent1, fparent2 = fparent2, nullid
    elif fparent2 != nullid:
        # is one parent an ancestor of the other?
        fparentancestors = flog.commonancestorsheads(fparent1, fparent2)
        if fparent1 in fparentancestors:
            fparent1, fparent2 = fparent2, nullid
        elif fparent2 in fparentancestors:
            fparent2 = nullid
        elif not fparentancestors:
            # TODO: this whole if-else might be simplified much more
            ms = mergestate.mergestate.read(repo)
            if (
                fname in ms
                and ms[fname] == mergestate.MERGE_RECORD_MERGED_OTHER
            ):
                fparent1, fparent2 = fparent2, nullid

    # is the file changed?
    text = fctx.data()
    if fparent2 != nullid or meta or flog.cmp(fparent1, text):
        if touched is None:  # do not overwrite added
            touched = 'modified'
        fnode = flog.add(text, meta, tr, linkrev, fparent1, fparent2)
    # are just the flags changed during merge?
    elif fname in manifest1 and manifest1.flags(fname) != fctx.flags():
        touched = 'modified'
        fnode = fparent1
    else:
        fnode = fparent1
    return fnode, touched


def _commit_manifest(tr, linkrev, ctx, mctx, files, added, drop):
    """make a new manifest entry (or reuse a new one)

    given an initialised manifest context and precomputed list of
    - files: files affected by the commit
    - added: new entries in the manifest
    - drop:  entries present in parents but absent of this one

    Create a new manifest revision, reuse existing ones if possible.

    Return the nodeid of the manifest revision.
    """
    repo = ctx.repo()

    md = None

    # all this is cached, so it is find to get them all from the ctx.
    p1 = ctx.p1()
    p2 = ctx.p2()
    m1ctx = p1.manifestctx()

    m1 = m1ctx.read()

    manifest = mctx.read()

    if not files:
        # if no "files" actually changed in terms of the changelog,
        # try hard to detect unmodified manifest entry so that the
        # exact same commit can be reproduced later on convert.
        md = m1.diff(manifest, scmutil.matchfiles(repo, ctx.files()))
    if not files and md:
        repo.ui.debug(
            b'not reusing manifest (no file change in '
            b'changelog, but manifest differs)\n'
        )
    if files or md:
        repo.ui.note(_(b"committing manifest\n"))
        # we're using narrowmatch here since it's already applied at
        # other stages (such as dirstate.walk), so we're already
        # ignoring things outside of narrowspec in most cases. The
        # one case where we might have files outside the narrowspec
        # at this point is merges, and we already error out in the
        # case where the merge has files outside of the narrowspec,
        # so this is safe.
        mn = mctx.write(
            tr,
            linkrev,
            p1.manifestnode(),
            p2.manifestnode(),
            added,
            drop,
            match=repo.narrowmatch(),
        )
    else:
        repo.ui.debug(
            b'reusing manifest from p1 (listed files ' b'actually unchanged)\n'
        )
        mn = p1.manifestnode()

    return mn