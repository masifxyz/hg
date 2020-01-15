# nodemap.py - nodemap related code and utilities
#
# Copyright 2019 Pierre-Yves David <pierre-yves.david@octobus.net>
# Copyright 2019 George Racinet <georges.racinet@octobus.net>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

from __future__ import absolute_import

import struct

from .. import (
    error,
    node as nodemod,
    pycompat,
)


class NodeMap(dict):
    def __missing__(self, x):
        raise error.RevlogError(b'unknown node: %s' % x)


def persisted_data(revlog):
    """read the nodemap for a revlog from disk"""
    if revlog.nodemap_file is None:
        return None
    return revlog.opener.tryread(revlog.nodemap_file)


def setup_persistent_nodemap(tr, revlog):
    """Install whatever is needed transaction side to persist a nodemap on disk

    (only actually persist the nodemap if this is relevant for this revlog)
    """
    if revlog.nodemap_file is None:
        return  # we do not use persistent_nodemap on this revlog
    callback_id = b"revlog-persistent-nodemap-%s" % revlog.nodemap_file
    if tr.hasfinalize(callback_id):
        return  # no need to register again
    tr.addfinalize(callback_id, lambda tr: _persist_nodemap(tr, revlog))


def _persist_nodemap(tr, revlog):
    """Write nodemap data on disk for a given revlog
    """
    if getattr(revlog, 'filteredrevs', ()):
        raise error.ProgrammingError(
            "cannot persist nodemap of a filtered changelog"
        )
    if revlog.nodemap_file is None:
        msg = "calling persist nodemap on a revlog without the feature enableb"
        raise error.ProgrammingError(msg)
    data = persistent_data(revlog.index)
    # EXP-TODO: if this is a cache, this should use a cache vfs, not a
    # store vfs
    with revlog.opener(revlog.nodemap_file, b'w') as f:
        f.write(data)
    # EXP-TODO: if the transaction abort, we should remove the new data and
    # reinstall the old one. (This will be simpler when the file format get a
    # bit more advanced)


### Nodemap Trie
#
# This is a simple reference implementation to compute and persist a nodemap
# trie. This reference implementation is write only. The python version of this
# is not expected to be actually used, since it wont provide performance
# improvement over existing non-persistent C implementation.
#
# The nodemap is persisted as Trie using 4bits-address/16-entries block. each
# revision can be adressed using its node shortest prefix.
#
# The trie is stored as a sequence of block. Each block contains 16 entries
# (signed 64bit integer, big endian). Each entry can be one of the following:
#
#  * value >=  0 -> index of sub-block
#  * value == -1 -> no value
#  * value <  -1 -> a revision value: rev = -(value+10)
#
# The implementation focus on simplicity, not on performance. A Rust
# implementation should provide a efficient version of the same binary
# persistence. This reference python implementation is never meant to be
# extensively use in production.


def persistent_data(index):
    """return the persistent binary form for a nodemap for a given index
    """
    trie = _build_trie(index)
    return _persist_trie(trie)


S_BLOCK = struct.Struct(">" + ("l" * 16))

NO_ENTRY = -1
# rev 0 need to be -2 because 0 is used by block, -1 is a special value.
REV_OFFSET = 2


def _transform_rev(rev):
    """Return the number used to represent the rev in the tree.

    (or retrieve a rev number from such representation)

    Note that this is an involution, a function equal to its inverse (i.e.
    which gives the identity when applied to itself).
    """
    return -(rev + REV_OFFSET)


def _to_int(hex_digit):
    """turn an hexadecimal digit into a proper integer"""
    return int(hex_digit, 16)


def _build_trie(index):
    """build a nodemap trie

    The nodemap stores revision number for each unique prefix.

    Each block is a dictionary with keys in `[0, 15]`. Values are either
    another block or a revision number.
    """
    root = {}
    for rev in range(len(index)):
        hex = nodemod.hex(index[rev][7])
        _insert_into_block(index, 0, root, rev, hex)
    return root


def _insert_into_block(index, level, block, current_rev, current_hex):
    """insert a new revision in a block

    index: the index we are adding revision for
    level: the depth of the current block in the trie
    block: the block currently being considered
    current_rev: the revision number we are adding
    current_hex: the hexadecimal representation of the of that revision
    """
    hex_digit = _to_int(current_hex[level : level + 1])
    entry = block.get(hex_digit)
    if entry is None:
        # no entry, simply store the revision number
        block[hex_digit] = current_rev
    elif isinstance(entry, dict):
        # need to recurse to an underlying block
        _insert_into_block(index, level + 1, entry, current_rev, current_hex)
    else:
        # collision with a previously unique prefix, inserting new
        # vertices to fit both entry.
        other_hex = nodemod.hex(index[entry][7])
        other_rev = entry
        new = {}
        block[hex_digit] = new
        _insert_into_block(index, level + 1, new, other_rev, other_hex)
        _insert_into_block(index, level + 1, new, current_rev, current_hex)


def _persist_trie(root):
    """turn a nodemap trie into persistent binary data

    See `_build_trie` for nodemap trie structure"""
    block_map = {}
    chunks = []
    for tn in _walk_trie(root):
        block_map[id(tn)] = len(chunks)
        chunks.append(_persist_block(tn, block_map))
    return b''.join(chunks)


def _walk_trie(block):
    """yield all the block in a trie

    Children blocks are always yield before their parent block.
    """
    for (_, item) in sorted(block.items()):
        if isinstance(item, dict):
            for sub_block in _walk_trie(item):
                yield sub_block
    yield block


def _persist_block(block_node, block_map):
    """produce persistent binary data for a single block

    Children block are assumed to be already persisted and present in
    block_map.
    """
    data = tuple(_to_value(block_node.get(i), block_map) for i in range(16))
    return S_BLOCK.pack(*data)


def _to_value(item, block_map):
    """persist any value as an integer"""
    if item is None:
        return NO_ENTRY
    elif isinstance(item, dict):
        return block_map[id(item)]
    else:
        return _transform_rev(item)
