  $ hg init
  $ echo a > a
  $ hg add a
  $ hg commit -m test

Do we ever miss a sub-second change?:

  $ for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  >     hg co -qC 0
  >     echo b > a
  >     hg st
  > done
  M a
  M a
  M a
  M a
  M a
  M a
  M a
  M a
  M a
  M a
  M a
  M a
  M a
  M a
  M a
  M a
  M a
  M a
  M a
  M a

