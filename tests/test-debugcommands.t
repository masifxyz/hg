  $ cat << EOF >> $HGRCPATH
  > [ui]
  > interactive=yes
  > EOF

  $ hg init debugrevlog
  $ cd debugrevlog
  $ echo a > a
  $ hg ci -Am adda
  adding a
  $ hg rm .
  removing a
  $ hg ci -Am make-it-empty
  $ hg revert --all -r 0
  adding a
  $ hg ci -Am make-it-full
#if reporevlogstore
  $ hg debugrevlog -m
  format : 1
  flags  : inline, generaldelta
  
  revisions     :  3
      merges    :  0 ( 0.00%)
      normal    :  3 (100.00%)
  revisions     :  3
      full      :  3 (100.00%)
      deltas    :  0 ( 0.00%)
  revision size : 88
      full      : 88 (100.00%)
      deltas    :  0 ( 0.00%)
  
  chunks        :  3
      empty     :  1 (33.33%)
      0x75 (u)  :  2 (66.67%)
  chunks size   : 88
      empty     :  0 ( 0.00%)
      0x75 (u)  : 88 (100.00%)
  
  avg chain length  :  0
  max chain length  :  0
  max chain reach   : 44
  compression ratio :  0
  
  uncompressed data size (min/max/avg) : 0 / 43 / 28
  full revision size (min/max/avg)     : 0 / 44 / 29
  delta size (min/max/avg)             : 0 / 0 / 0
#endif

Test debugindex, with and without the --verbose/--debug flag
  $ hg debugindex a
     rev linkrev nodeid       p1           p2
       0       0 b789fdd96dc2 000000000000 000000000000

#if no-reposimplestore
  $ hg --verbose debugindex a
     rev    offset  length linkrev nodeid       p1           p2
       0         0       3       0 b789fdd96dc2 000000000000 000000000000

  $ hg --debug debugindex a
     rev    offset  length linkrev nodeid                                   p1                                       p2
       0         0       3       0 b789fdd96dc2f3bd229c1dd8eedf0fc60e2b68e3 0000000000000000000000000000000000000000 0000000000000000000000000000000000000000
#endif

  $ hg debugindex -f 1 a
     rev flag     size   link     p1     p2       nodeid
       0 0000        2      0     -1     -1 b789fdd96dc2

#if no-reposimplestore
  $ hg --verbose debugindex -f 1 a
     rev flag   offset   length     size   link     p1     p2       nodeid
       0 0000        0        3        2      0     -1     -1 b789fdd96dc2

  $ hg --debug debugindex -f 1 a
     rev flag   offset   length     size   link     p1     p2                                   nodeid
       0 0000        0        3        2      0     -1     -1 b789fdd96dc2f3bd229c1dd8eedf0fc60e2b68e3
#endif

debugdelta chain basic output

#if reporevlogstore
  $ hg debugdeltachain -m
      rev  chain# chainlen     prev   delta       size    rawsize  chainsize     ratio   lindist extradist extraratio
        0       1        1       -1    base         44         43         44   1.02326        44         0    0.00000
        1       2        1       -1    base          0          0          0   0.00000         0         0    0.00000
        2       3        1       -1    base         44         43         44   1.02326        44         0    0.00000

  $ hg debugdeltachain -m -T '{rev} {chainid} {chainlen}\n'
  0 1 1
  1 2 1
  2 3 1

  $ hg debugdeltachain -m -Tjson
  [
   {
    "chainid": 1,
    "chainlen": 1,
    "chainratio": 1.02325581395,
    "chainsize": 44,
    "compsize": 44,
    "deltatype": "base",
    "extradist": 0,
    "extraratio": 0.0,
    "lindist": 44,
    "prevrev": -1,
    "rev": 0,
    "uncompsize": 43
   },
   {
    "chainid": 2,
    "chainlen": 1,
    "chainratio": 0,
    "chainsize": 0,
    "compsize": 0,
    "deltatype": "base",
    "extradist": 0,
    "extraratio": 0,
    "lindist": 0,
    "prevrev": -1,
    "rev": 1,
    "uncompsize": 0
   },
   {
    "chainid": 3,
    "chainlen": 1,
    "chainratio": 1.02325581395,
    "chainsize": 44,
    "compsize": 44,
    "deltatype": "base",
    "extradist": 0,
    "extraratio": 0.0,
    "lindist": 44,
    "prevrev": -1,
    "rev": 2,
    "uncompsize": 43
   }
  ]

debugdelta chain with sparse read enabled

  $ cat >> $HGRCPATH <<EOF
  > [experimental]
  > sparse-read = True
  > EOF
  $ hg debugdeltachain -m
      rev  chain# chainlen     prev   delta       size    rawsize  chainsize     ratio   lindist extradist extraratio   readsize largestblk rddensity srchunks
        0       1        1       -1    base         44         43         44   1.02326        44         0    0.00000         44         44   1.00000        1
        1       2        1       -1    base          0          0          0   0.00000         0         0    0.00000          0          0   1.00000        1
        2       3        1       -1    base         44         43         44   1.02326        44         0    0.00000         44         44   1.00000        1

  $ hg debugdeltachain -m -T '{rev} {chainid} {chainlen} {readsize} {largestblock} {readdensity}\n'
  0 1 1 44 44 1.0
  1 2 1 0 0 1
  2 3 1 44 44 1.0

  $ hg debugdeltachain -m -Tjson
  [
   {
    "chainid": 1,
    "chainlen": 1,
    "chainratio": 1.02325581395,
    "chainsize": 44,
    "compsize": 44,
    "deltatype": "base",
    "extradist": 0,
    "extraratio": 0.0,
    "largestblock": 44,
    "lindist": 44,
    "prevrev": -1,
    "readdensity": 1.0,
    "readsize": 44,
    "rev": 0,
    "srchunks": 1,
    "uncompsize": 43
   },
   {
    "chainid": 2,
    "chainlen": 1,
    "chainratio": 0,
    "chainsize": 0,
    "compsize": 0,
    "deltatype": "base",
    "extradist": 0,
    "extraratio": 0,
    "largestblock": 0,
    "lindist": 0,
    "prevrev": -1,
    "readdensity": 1,
    "readsize": 0,
    "rev": 1,
    "srchunks": 1,
    "uncompsize": 0
   },
   {
    "chainid": 3,
    "chainlen": 1,
    "chainratio": 1.02325581395,
    "chainsize": 44,
    "compsize": 44,
    "deltatype": "base",
    "extradist": 0,
    "extraratio": 0.0,
    "largestblock": 44,
    "lindist": 44,
    "prevrev": -1,
    "readdensity": 1.0,
    "readsize": 44,
    "rev": 2,
    "srchunks": 1,
    "uncompsize": 43
   }
  ]

  $ printf "This test checks things.\n" >> a
  $ hg ci -m a
  $ hg branch other
  marked working directory as branch other
  (branches are permanent and global, did you want a bookmark?)
  $ for i in `$TESTDIR/seq.py 5`; do
  >   printf "shorter ${i}" >> a
  >   hg ci -m "a other:$i"
  >   hg up -q default
  >   printf "for the branch default we want longer chains: ${i}" >> a
  >   hg ci -m "a default:$i"
  >   hg up -q other
  > done
  $ hg debugdeltachain a -T '{rev} {srchunks}\n' \
  >    --config experimental.sparse-read.density-threshold=0.50 \
  >    --config experimental.sparse-read.min-gap-size=0
  0 1
  1 1
  2 1
  3 1
  4 1
  5 1
  6 1
  7 1
  8 1
  9 1
  10 2
  11 1
  $ hg --config extensions.strip= strip --no-backup -r 1
  1 files updated, 0 files merged, 0 files removed, 0 files unresolved

Test max chain len
  $ cat >> $HGRCPATH << EOF
  > [format]
  > maxchainlen=4
  > EOF

  $ printf "This test checks if maxchainlen config value is respected also it can serve as basic test for debugrevlog -d <file>.\n" >> a
  $ hg ci -m a
  $ printf "b\n" >> a
  $ hg ci -m a
  $ printf "c\n" >> a
  $ hg ci -m a
  $ printf "d\n" >> a
  $ hg ci -m a
  $ printf "e\n" >> a
  $ hg ci -m a
  $ printf "f\n" >> a
  $ hg ci -m a
  $ printf 'g\n' >> a
  $ hg ci -m a
  $ printf 'h\n' >> a
  $ hg ci -m a

  $ hg debugrevlog -d a
  # rev p1rev p2rev start   end deltastart base   p1   p2 rawsize totalsize compression heads chainlen
      0    -1    -1     0   ???          0    0    0    0     ???      ????           ?     1        0 (glob)
      1     0    -1   ???   ???          0    0    0    0     ???      ????           ?     1        1 (glob)
      2     1    -1   ???   ???        ???  ???  ???    0     ???      ????           ?     1        2 (glob)
      3     2    -1   ???   ???        ???  ???  ???    0     ???      ????           ?     1        3 (glob)
      4     3    -1   ???   ???        ???  ???  ???    0     ???      ????           ?     1        4 (glob)
      5     4    -1   ???   ???        ???  ???  ???    0     ???      ????           ?     1        0 (glob)
      6     5    -1   ???   ???        ???  ???  ???    0     ???      ????           ?     1        1 (glob)
      7     6    -1   ???   ???        ???  ???  ???    0     ???      ????           ?     1        2 (glob)
      8     7    -1   ???   ???        ???  ???  ???    0     ???      ????           ?     1        3 (glob)
#endif

Test debuglocks command:

  $ hg debuglocks
  lock:  free
  wlock: free

* Test setting the lock

waitlock <file> will wait for file to be created. If it isn't in a reasonable
amount of time, displays error message and returns 1
  $ waitlock() {
  >     start=`date +%s`
  >     timeout=5
  >     while [ \( ! -f $1 \) -a \( ! -L $1 \) ]; do
  >         now=`date +%s`
  >         if [ "`expr $now - $start`" -gt $timeout ]; then
  >             echo "timeout: $1 was not created in $timeout seconds"
  >             return 1
  >         fi
  >         sleep 0.1
  >     done
  > }
  $ dolock() {
  >     {
  >         waitlock .hg/unlock
  >         rm -f .hg/unlock
  >         echo y
  >     } | hg debuglocks "$@" > /dev/null
  > }
  $ dolock -s &
  $ waitlock .hg/store/lock

  $ hg debuglocks
  lock:  user *, process * (*s) (glob)
  wlock: free
  [1]
  $ touch .hg/unlock
  $ wait
  $ [ -f .hg/store/lock ] || echo "There is no lock"
  There is no lock

* Test setting the wlock

  $ dolock -S &
  $ waitlock .hg/wlock

  $ hg debuglocks
  lock:  free
  wlock: user *, process * (*s) (glob)
  [1]
  $ touch .hg/unlock
  $ wait
  $ [ -f .hg/wlock ] || echo "There is no wlock"
  There is no wlock

* Test setting both locks

  $ dolock -Ss &
  $ waitlock .hg/wlock && waitlock .hg/store/lock

  $ hg debuglocks
  lock:  user *, process * (*s) (glob)
  wlock: user *, process * (*s) (glob)
  [2]

* Test failing to set a lock

  $ hg debuglocks -s
  abort: lock is already held
  [255]

  $ hg debuglocks -S
  abort: wlock is already held
  [255]

  $ touch .hg/unlock
  $ wait

  $ hg debuglocks
  lock:  free
  wlock: free

* Test forcing the lock

  $ dolock -s &
  $ waitlock .hg/store/lock

  $ hg debuglocks
  lock:  user *, process * (*s) (glob)
  wlock: free
  [1]

  $ hg debuglocks -L

  $ hg debuglocks
  lock:  free
  wlock: free

  $ touch .hg/unlock
  $ wait

* Test forcing the wlock

  $ dolock -S &
  $ waitlock .hg/wlock

  $ hg debuglocks
  lock:  free
  wlock: user *, process * (*s) (glob)
  [1]

  $ hg debuglocks -W

  $ hg debuglocks
  lock:  free
  wlock: free

  $ touch .hg/unlock
  $ wait

Test WdirUnsupported exception

  $ hg debugdata -c ffffffffffffffffffffffffffffffffffffffff
  abort: working directory revision cannot be specified
  [255]

Test cache warming command

  $ rm -rf .hg/cache/
  $ hg debugupdatecaches --debug
  updating the branch cache
  $ ls -r .hg/cache/*
  .hg/cache/rbc-revs-v1
  .hg/cache/rbc-names-v1
  .hg/cache/manifestfulltextcache
  .hg/cache/branch2-served

Test debugcolor

#if no-windows
  $ hg debugcolor --style --color always | egrep 'mode|style|log\.'
  color mode: 'ansi'
  available style:
  \x1b[0;33mlog.changeset\x1b[0m:                      \x1b[0;33myellow\x1b[0m (esc)
#endif

  $ hg debugcolor --style --color never
  color mode: None
  available style:

  $ cd ..

Test internal debugstacktrace command

  $ cat > debugstacktrace.py << EOF
  > from __future__ import absolute_import
  > import sys
  > from mercurial import util
  > def f():
  >     util.debugstacktrace(f=sys.stdout)
  >     g()
  > def g():
  >     util.dst('hello from g\\n', skip=1)
  >     h()
  > def h():
  >     util.dst('hi ...\\nfrom h hidden in g', 1, depth=2)
  > f()
  > EOF
  $ $PYTHON debugstacktrace.py
  stacktrace at:
   debugstacktrace.py:12 in * (glob)
   debugstacktrace.py:5  in f
  hello from g at:
   debugstacktrace.py:12 in * (glob)
   debugstacktrace.py:6  in f
  hi ...
  from h hidden in g at:
   debugstacktrace.py:6 in f
   debugstacktrace.py:9 in g

Test debugcapabilities command:

  $ hg debugcapabilities ./debugrevlog/
  Main capabilities:
    branchmap
    $USUAL_BUNDLE2_CAPS$
    getbundle
    known
    lookup
    pushkey
    unbundle
  Bundle2 capabilities:
    HG20
    bookmarks
    changegroup
      01
      02
    digests
      md5
      sha1
      sha512
    error
      abort
      unsupportedcontent
      pushraced
      pushkey
    hgtagsfnodes
    listkeys
    phases
      heads
    pushkey
    remote-changegroup
      http
      https
    rev-branch-cache
    stream
      v2

Test debugpeer

  $ hg --config ui.ssh="\"$PYTHON\" \"$TESTDIR/dummyssh\"" debugpeer ssh://user@dummy/debugrevlog
  url: ssh://user@dummy/debugrevlog
  local: no
  pushable: yes

  $ hg --config ui.ssh="\"$PYTHON\" \"$TESTDIR/dummyssh\"" --debug debugpeer ssh://user@dummy/debugrevlog
  running "*" "*/tests/dummyssh" 'user@dummy' 'hg -R debugrevlog serve --stdio' (glob) (no-windows !)
  running "*" "*\tests/dummyssh" "user@dummy" "hg -R debugrevlog serve --stdio" (glob) (windows !)
  devel-peer-request: hello+between
  devel-peer-request:   pairs: 81 bytes
  sending hello command
  sending between command
  remote: 413
  remote: capabilities: batch branchmap $USUAL_BUNDLE2_CAPS_SERVER$ changegroupsubset getbundle known lookup protocaps pushkey streamreqs=generaldelta,revlogv1 unbundle=HG10GZ,HG10BZ,HG10UN unbundlehash
  remote: 1
  devel-peer-request: protocaps
  devel-peer-request:   caps: * bytes (glob)
  sending protocaps command
  url: ssh://user@dummy/debugrevlog
  local: no
  pushable: yes
