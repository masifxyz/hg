  adding a.i/b (glob)
  adding a.i.hg/c (glob)
  3 files, 3 changesets, 3 total revisions
  3 files, 3 changesets, 3 total revisions
  3 files, 3 changesets, 3 total revisions
  > from mercurial import commands, error
  > from mercurial.extensions import wrapcommand, wrapfunction
  >     wrapfunction(repo, '_lock', lockexception)
  >     wrapcommand(commands.table, "commit", commitwrap)
  > from mercurial import commands, error, localrepo
  > from mercurial.extensions import wrapfunction
  >         raise error.Abort("forced transaction failure")
  >     tr.addfinalize('zzz-forcefails', fail)
  >     wrapfunction(localrepo.localrepository, 'transaction', wrapper)
  > from mercurial import commands, error, transaction, localrepo
  > from mercurial.extensions import wrapfunction
  >         raise error.Abort("forced transaction failure")
  >     tr.addfinalize('zzz-forcefails', fail)
  >     raise error.Abort("forced transaction failure")
  >     wrapfunction(localrepo.localrepository, 'transaction', trwrapper)
  >     wrapfunction(transaction.transaction, '_abort', abortwrapper)
  1 files, 1 changesets, 1 total revisions