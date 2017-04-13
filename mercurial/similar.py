# similar.py - mechanisms for finding similar files
#
# Copyright 2005-2007 Matt Mackall <mpm@selenic.com>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

from __future__ import absolute_import

from .i18n import _
from . import (
    bdiff,
    mdiff,
)

def _findexactmatches(repo, added, removed):
    '''find renamed files that have no changes

    Takes a list of new filectxs and a list of removed filectxs, and yields
    (before, after) tuples of exact matches.
    '''
    numfiles = len(added) + len(removed)

    # Build table of removed files: {hash(fctx.data()): [fctx, ...]}.
    # We use hash() to discard fctx.data() from memory.
    hashes = {}
    for i, fctx in enumerate(removed):
        repo.ui.progress(_('searching for exact renames'), i, total=numfiles,
                         unit=_('files'))
        h = hash(fctx.data())
        if h not in hashes:
            hashes[h] = [fctx]
        else:
            hashes[h].append(fctx)

    # For each added file, see if it corresponds to a removed file.
    for i, fctx in enumerate(added):
        repo.ui.progress(_('searching for exact renames'), i + len(removed),
                total=numfiles, unit=_('files'))
        adata = fctx.data()
        h = hash(adata)
        for rfctx in hashes.get(h, []):
            # compare between actual file contents for exact identity
            if adata == rfctx.data():
                yield (rfctx, fctx)
                break

    # Done
    repo.ui.progress(_('searching for exact renames'), None)

def _ctxdata(fctx):
    # lazily load text
    orig = fctx.data()
    return orig, mdiff.splitnewlines(orig)

def _score(fctx, otherdata):
    orig, lines = otherdata
    text = fctx.data()
    # bdiff.blocks() returns blocks of matching lines
    # count the number of bytes in each
    equal = 0
    matches = bdiff.blocks(text, orig)
    for x1, x2, y1, y2 in matches:
        for line in lines[y1:y2]:
            equal += len(line)

    lengths = len(text) + len(orig)
    return equal * 2.0 / lengths

def score(fctx1, fctx2):
    return _score(fctx1, _ctxdata(fctx2))

def _findsimilarmatches(repo, added, removed, threshold):
    '''find potentially renamed files based on similar file content

    Takes a list of new filectxs and a list of removed filectxs, and yields
    (before, after, score) tuples of partial matches.
    '''
    copies = {}
    for i, r in enumerate(removed):
        repo.ui.progress(_('searching for similar files'), i,
                         total=len(removed), unit=_('files'))

        data = None
        for a in added:
            bestscore = copies.get(a, (None, threshold))[1]
            if data is None:
                data = _ctxdata(r)
            myscore = _score(a, data)
            if myscore > bestscore:
                copies[a] = (r, myscore)
    repo.ui.progress(_('searching'), None)

    for dest, v in copies.iteritems():
        source, bscore = v
        yield source, dest, bscore

def _dropempty(fctxs):
    return [x for x in fctxs if x.size() > 0]

def findrenames(repo, added, removed, threshold):
    '''find renamed files -- yields (before, after, score) tuples'''
    wctx = repo[None]
    pctx = wctx.p1()

    # Zero length files will be frequently unrelated to each other, and
    # tracking the deletion/addition of such a file will probably cause more
    # harm than good. We strip them out here to avoid matching them later on.
    addedfiles = _dropempty(wctx[fp] for fp in sorted(added))
    removedfiles = _dropempty(pctx[fp] for fp in sorted(removed) if fp in pctx)

    # Find exact matches.
    matchedfiles = set()
    for (a, b) in _findexactmatches(repo, addedfiles, removedfiles):
        matchedfiles.add(b)
        yield (a.path(), b.path(), 1.0)

    # If the user requested similar files to be matched, search for them also.
    if threshold < 1.0:
        addedfiles = [x for x in addedfiles if x not in matchedfiles]
        for (a, b, score) in _findsimilarmatches(repo, addedfiles,
                                                 removedfiles, threshold):
            yield (a.path(), b.path(), score)
