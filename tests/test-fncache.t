#require repofncache

  adding a.i/b
  adding a.i.hg/c
  .hg/fsmonitor.state (fsmonitor !)
  .hg/fsmonitor.state (fsmonitor !)
  > from __future__ import absolute_import
  > from mercurial import commands, error, extensions
  >     extensions.wrapfunction(repo, '_lock', lockexception)
  >     extensions.wrapcommand(commands.table, b"commit", commitwrap)
  > from __future__ import absolute_import
  > from mercurial import commands, error, extensions, localrepo
  >         raise error.Abort(b"forced transaction failure")
  >     tr.addfinalize(b'zzz-forcefails', fail)
  >     extensions.wrapfunction(
  >         localrepo.localrepository, b'transaction', wrapper)

Clean cached version
  $ rm -Rf "`dirname $extpath`/__pycache__"

  > from __future__ import absolute_import
  > from mercurial import (
  >   commands,
  >   error,
  >   extensions,
  >   localrepo,
  >   transaction,
  > )
  >     extensions.wrapfunction(localrepo.localrepository, 'transaction',
  >                             trwrapper)
  >     extensions.wrapfunction(transaction.transaction, '_abort',
  >                             abortwrapper)

Clean cached versions
  $ rm -Rf "`dirname $extpath`/__pycache__"
