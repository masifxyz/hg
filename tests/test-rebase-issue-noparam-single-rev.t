  $ cat >> $HGRCPATH <<EOF
  > [extensions]
  > rebase=
  > 
  > [phases]
  > publish=False
  > 
  > [alias]
  > tglog = log -G --template "{rev}: {node|short} '{desc}' {branches}\n"
  > EOF


  $ hg init a
  $ cd a

  $ echo c1 > c1
  $ hg ci -Am c1
  adding c1

  $ echo c2 > c2
  $ hg ci -Am c2
  adding c2

  $ echo l1 > l1
  $ hg ci -Am l1
  adding l1

  $ hg up -q -C 1

  $ echo r1 > r1
  $ hg ci -Am r1
  adding r1
  created new head

  $ echo r2 > r2
  $ hg ci -Am r2
  adding r2

  $ hg tglog
  @  4: 225af64d03e6 'r2'
  |
  o  3: 8d0a8c99b309 'r1'
  |
  | o  2: 87c180a611f2 'l1'
  |/
  o  1: 56daeba07f4b 'c2'
  |
  o  0: e8faad3d03ff 'c1'
  
Rebase with no arguments - single revision in source branch:

  $ hg up -q -C 2

  $ hg rebase
  rebasing 2:87c180a611f2 "l1"
  saved backup bundle to $TESTTMP/a/.hg/strip-backup/87c180a611f2-a5be192d-rebase.hg

  $ hg tglog
  @  4: b1152cc99655 'l1'
  |
  o  3: 225af64d03e6 'r2'
  |
  o  2: 8d0a8c99b309 'r1'
  |
  o  1: 56daeba07f4b 'c2'
  |
  o  0: e8faad3d03ff 'c1'
  
  $ cd ..


  $ hg init b
  $ cd b

  $ echo c1 > c1
  $ hg ci -Am c1
  adding c1

  $ echo c2 > c2
  $ hg ci -Am c2
  adding c2

  $ echo l1 > l1
  $ hg ci -Am l1
  adding l1

  $ echo l2 > l2
  $ hg ci -Am l2
  adding l2

  $ hg up -q -C 1

  $ echo r1 > r1
  $ hg ci -Am r1
  adding r1
  created new head

  $ hg tglog
  @  4: 8d0a8c99b309 'r1'
  |
  | o  3: 1ac923b736ef 'l2'
  | |
  | o  2: 87c180a611f2 'l1'
  |/
  o  1: 56daeba07f4b 'c2'
  |
  o  0: e8faad3d03ff 'c1'
  
Rebase with no arguments - single revision in target branch:

  $ hg up -q -C 3

  $ hg rebase
  rebasing 2:87c180a611f2 "l1"
  rebasing 3:1ac923b736ef "l2"
  saved backup bundle to $TESTTMP/b/.hg/strip-backup/87c180a611f2-b980535c-rebase.hg

  $ hg tglog
  @  4: 023181307ed0 'l2'
  |
  o  3: 913ab52b43b4 'l1'
  |
  o  2: 8d0a8c99b309 'r1'
  |
  o  1: 56daeba07f4b 'c2'
  |
  o  0: e8faad3d03ff 'c1'
  

  $ cd ..
