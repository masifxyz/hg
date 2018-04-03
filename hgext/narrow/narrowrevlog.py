# narrowrevlog.py - revlog storing irrelevant nodes as "ellipsis" nodes
#
# Copyright 2017 Google, Inc.
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

from __future__ import absolute_import

from mercurial import (
   manifest,
   revlog,
   util,
)

def readtransform(self, text):
    return text, False

def writetransform(self, text):
    return text, False

def rawtransform(self, text):
    return False

revlog.addflagprocessor(revlog.REVIDX_ELLIPSIS,
                        (readtransform, writetransform, rawtransform))

def setup():
    # We just wanted to add the flag processor, which is done at module
    # load time.
    pass

def makenarrowmanifestrevlog(mfrevlog, repo):
    if util.safehasattr(mfrevlog, '_narrowed'):
        return

    class narrowmanifestrevlog(mfrevlog.__class__):
        # This function is called via debug{revlog,index,data}, but also during
        # at least some push operations. This will be used to wrap/exclude the
        # child directories when using treemanifests.
        def dirlog(self, d):
            if not repo.narrowmatch().visitdir(d[:-1] or '.'):
                return manifest.excludedmanifestrevlog(d)
            result = super(narrowmanifestrevlog, self).dirlog(d)
            makenarrowmanifestrevlog(result, repo)
            return result

    mfrevlog.__class__ = narrowmanifestrevlog
    mfrevlog._narrowed = True

def makenarrowmanifestlog(mfl, repo):
    class narrowmanifestlog(mfl.__class__):
        def get(self, dir, node, verify=True):
            if not repo.narrowmatch().visitdir(dir[:-1] or '.'):
                return manifest.excludeddirmanifestctx(dir, node)
            return super(narrowmanifestlog, self).get(dir, node, verify=verify)
    mfl.__class__ = narrowmanifestlog

def makenarrowfilelog(fl, narrowmatch):
    class narrowfilelog(fl.__class__):
        def renamed(self, node):
            # Renames that come from outside the narrowspec are
            # problematic at least for git-diffs, because we lack the
            # base text for the rename. This logic was introduced in
            # 3cd72b1 of narrowhg (authored by martinvonz, reviewed by
            # adgar), but that revision doesn't have any additional
            # commentary on what problems we can encounter.
            m = super(narrowfilelog, self).renamed(node)
            if m and not narrowmatch(m[0]):
                return None
            return m

        def size(self, rev):
            # We take advantage of the fact that remotefilelog
            # lacks a node() method to just skip the
            # rename-checking logic when on remotefilelog. This
            # might be incorrect on other non-revlog-based storage
            # engines, but for now this seems to be fine.
            #
            # TODO: when remotefilelog is in core, improve this to
            # explicitly look for remotefilelog instead of cheating
            # with a hasattr check.
            if util.safehasattr(self, 'node'):
                node = self.node(rev)
                # Because renamed() is overridden above to
                # sometimes return None even if there is metadata
                # in the revlog, size can be incorrect for
                # copies/renames, so we need to make sure we call
                # the super class's implementation of renamed()
                # for the purpose of size calculation.
                if super(narrowfilelog, self).renamed(node):
                    return len(self.read(node))
            return super(narrowfilelog, self).size(rev)

        def cmp(self, node, text):
            different = super(narrowfilelog, self).cmp(node, text)
            if different:
                # Similar to size() above, if the file was copied from
                # a file outside the narrowspec, the super class's
                # would have returned True because we tricked it into
                # thinking that the file was not renamed.
                if super(narrowfilelog, self).renamed(node):
                    t2 = self.read(node)
                    return t2 != text
            return different

    fl.__class__ = narrowfilelog
