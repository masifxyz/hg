  $ "$TESTDIR/hghave" serve || exit 80

initialize

  $ hg init a
  $ cd a
  $ echo 'test' > test
  $ hg commit -Am'test'
  adding test

set bookmarks

  $ hg bookmark X
  $ hg bookmark Y
  $ hg bookmark Z

import bookmark by name

  $ hg init ../b
  $ cd ../b
  $ hg book Y
  $ hg book
   * Y                         -1:000000000000
  $ hg pull ../a
  pulling from ../a
  requesting all changes
  adding changesets
  adding manifests
  adding file changes
  added 1 changesets with 1 changes to 1 files
  updating bookmark Y
  adding remote bookmark X
  adding remote bookmark Z
  (run 'hg update' to get a working copy)
  $ hg bookmarks
     X                         0:4e3505fd9583
     Y                         0:4e3505fd9583
     Z                         0:4e3505fd9583
  $ hg debugpushkey ../a namespaces
  bookmarks	
  phases	
  namespaces	
  obsolete	
  $ hg debugpushkey ../a bookmarks
  Y	4e3505fd95835d721066b76e75dbb8cc554d7f77
  X	4e3505fd95835d721066b76e75dbb8cc554d7f77
  Z	4e3505fd95835d721066b76e75dbb8cc554d7f77
  $ hg pull -B X ../a
  pulling from ../a
  no changes found
  importing bookmark X
  $ hg bookmark
     X                         0:4e3505fd9583
     Y                         0:4e3505fd9583
     Z                         0:4e3505fd9583

export bookmark by name

  $ hg bookmark W
  $ hg bookmark foo
  $ hg bookmark foobar
  $ hg push -B W ../a
  pushing to ../a
  searching for changes
  no changes found
  exporting bookmark W
  [1]
  $ hg -R ../a bookmarks
     W                         -1:000000000000
     X                         0:4e3505fd9583
     Y                         0:4e3505fd9583
   * Z                         0:4e3505fd9583

delete a remote bookmark

  $ hg book -d W
  $ hg push -B W ../a
  pushing to ../a
  searching for changes
  no changes found
  deleting remote bookmark W
  [1]

push/pull name that doesn't exist

  $ hg push -B badname ../a
  pushing to ../a
  searching for changes
  no changes found
  bookmark badname does not exist on the local or remote repository!
  [2]
  $ hg pull -B anotherbadname ../a
  pulling from ../a
  abort: remote bookmark anotherbadname not found!
  [255]

divergent bookmarks

  $ cd ../a
  $ echo c1 > f1
  $ hg ci -Am1
  adding f1
  $ hg book -f X
  $ hg book
   * X                         1:0d2164f0ce0d
     Y                         0:4e3505fd9583
     Z                         1:0d2164f0ce0d

  $ cd ../b
  $ hg up
  1 files updated, 0 files merged, 0 files removed, 0 files unresolved
  updating bookmark foobar
  $ echo c2 > f2
  $ hg ci -Am2
  adding f2
  $ hg book -f X
  $ hg book
   * X                         1:9b140be10808
     Y                         0:4e3505fd9583
     Z                         0:4e3505fd9583
     foo                       -1:000000000000
     foobar                    1:9b140be10808

  $ hg pull --config paths.foo=../a foo
  pulling from $TESTTMP/a (glob)
  searching for changes
  adding changesets
  adding manifests
  adding file changes
  added 1 changesets with 1 changes to 1 files (+1 heads)
  divergent bookmark X stored as X@foo
  updating bookmark Z
  (run 'hg heads' to see heads, 'hg merge' to merge)
  $ hg book
   * X                         1:9b140be10808
     X@foo                     2:0d2164f0ce0d
     Y                         0:4e3505fd9583
     Z                         2:0d2164f0ce0d
     foo                       -1:000000000000
     foobar                    1:9b140be10808
  $ hg push -f ../a
  pushing to ../a
  searching for changes
  adding changesets
  adding manifests
  adding file changes
  added 1 changesets with 1 changes to 1 files (+1 heads)
  $ hg -R ../a book
   * X                         1:0d2164f0ce0d
     Y                         0:4e3505fd9583
     Z                         1:0d2164f0ce0d

update a remote bookmark from a non-head to a head

  $ hg up -q Y
  $ echo c3 > f2
  $ hg ci -Am3
  adding f2
  created new head
  $ hg push ../a
  pushing to ../a
  searching for changes
  adding changesets
  adding manifests
  adding file changes
  added 1 changesets with 1 changes to 1 files (+1 heads)
  updating bookmark Y
  $ hg -R ../a book
   * X                         1:0d2164f0ce0d
     Y                         3:f6fc62dde3c0
     Z                         1:0d2164f0ce0d

diverging a remote bookmark fails

  $ hg up -q 4e3505fd9583
  $ echo c4 > f2
  $ hg ci -Am4
  adding f2
  created new head
  $ hg book -f Y

  $ cat <<EOF > ../a/.hg/hgrc
  > [web]
  > push_ssl = false
  > allow_push = *
  > EOF

  $ hg -R ../a serve -p $HGPORT2 -d --pid-file=../hg2.pid
  $ cat ../hg2.pid >> $DAEMON_PIDS

  $ hg push http://localhost:$HGPORT2/
  pushing to http://localhost:$HGPORT2/
  searching for changes
  abort: push creates new remote head 4efff6d98829!
  (did you forget to merge? use push -f to force)
  [255]
  $ hg -R ../a book
   * X                         1:0d2164f0ce0d
     Y                         3:f6fc62dde3c0
     Z                         1:0d2164f0ce0d

hgweb

  $ cat <<EOF > .hg/hgrc
  > [web]
  > push_ssl = false
  > allow_push = *
  > EOF

  $ hg serve -p $HGPORT -d --pid-file=../hg.pid -E errors.log
  $ cat ../hg.pid >> $DAEMON_PIDS
  $ cd ../a

  $ hg debugpushkey http://localhost:$HGPORT/ namespaces 
  bookmarks	
  phases	
  namespaces	
  obsolete	
  $ hg debugpushkey http://localhost:$HGPORT/ bookmarks
  Y	4efff6d98829d9c824c621afd6e3f01865f5439f
  foobar	9b140be1080824d768c5a4691a564088eede71f9
  Z	0d2164f0ce0d8f1d6f94351eba04b794909be66c
  foo	0000000000000000000000000000000000000000
  X	9b140be1080824d768c5a4691a564088eede71f9
  $ hg out -B http://localhost:$HGPORT/
  comparing with http://localhost:$HGPORT/
  searching for changed bookmarks
  no changed bookmarks found
  [1]
  $ hg push -B Z http://localhost:$HGPORT/
  pushing to http://localhost:$HGPORT/
  searching for changes
  no changes found
  exporting bookmark Z
  [1]
  $ hg book -d Z
  $ hg in -B http://localhost:$HGPORT/
  comparing with http://localhost:$HGPORT/
  searching for changed bookmarks
     Z                         0d2164f0ce0d
     foo                       000000000000
     foobar                    9b140be10808
  $ hg pull -B Z http://localhost:$HGPORT/
  pulling from http://localhost:$HGPORT/
  no changes found
  adding remote bookmark foobar
  adding remote bookmark Z
  adding remote bookmark foo
  divergent bookmark X stored as X@1
  importing bookmark Z
  $ hg clone http://localhost:$HGPORT/ cloned-bookmarks
  requesting all changes
  adding changesets
  adding manifests
  adding file changes
  added 5 changesets with 5 changes to 3 files (+3 heads)
  updating to branch default
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ hg -R cloned-bookmarks bookmarks
     X                         1:9b140be10808
     Y                         4:4efff6d98829
     Z                         2:0d2164f0ce0d
     foo                       -1:000000000000
     foobar                    1:9b140be10808

  $ cd ..
