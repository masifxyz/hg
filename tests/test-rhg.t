#require rust

Define an rhg function that will only run if rhg exists
  $ rhg() {
  > if [ -f "$RUNTESTDIR/../rust/target/debug/rhg" ]; then
  >   "$RUNTESTDIR/../rust/target/debug/rhg" "$@"
  > else
  >   echo "skipped: Cannot find rhg. Try to run cargo build in rust/rhg."
  >   exit 80
  > fi
  > }

Unimplemented command
  $ rhg unimplemented-command
  error: Found argument 'unimplemented-command' which wasn't expected, or isn't valid in this context
  
  USAGE:
      rhg <SUBCOMMAND>
  
  For more information try --help
  [252]

Finding root
  $ rhg root
  abort: no repository found in '$TESTTMP' (.hg not found)!
  [255]

  $ hg init repository
  $ cd repository
  $ rhg root
  $TESTTMP/repository

Unwritable file descriptor
  $ rhg root > /dev/full
  abort: No space left on device (os error 28)
  [255]

Deleted repository
  $ rm -rf `pwd`
  $ rhg root
  abort: error getting current working directory: $ENOENT$
  [255]

Listing tracked files
  $ cd $TESTTMP
  $ hg init repository
  $ cd repository
  $ for i in 1 2 3; do
  >   echo $i >> file$i
  >   hg add file$i
  > done
  > hg commit -m "commit $i" -q

Listing tracked files from root
  $ rhg files
  file1
  file2
  file3

Listing tracked files from subdirectory
  $ mkdir -p path/to/directory
  $ cd path/to/directory
  $ rhg files
  ../../../file1
  ../../../file2
  ../../../file3

Listing tracked files through broken pipe
  $ rhg files | head -n 1
  ../../../file1

Debuging data in inline index
  $ cd $TESTTMP
  $ rm -rf repository
  $ hg init repository
  $ cd repository
  $ for i in 1 2 3; do
  >   echo $i >> file$i
  >   hg add file$i
  >   hg commit -m "commit $i" -q
  > done
  $ rhg debugdata -c 2
  e36fa63d37a576b27a69057598351db6ee5746bd
  test
  0 0
  file3
  
  commit 3 (no-eol)
  $ rhg debugdata -m 2
  file1\x00b8e02f6433738021a065f94175c7cd23db5f05be (esc)
  file2\x005d9299349fc01ddd25d0070d149b124d8f10411e (esc)
  file3\x002661d26c649684b482d10f91960cc3db683c38b4 (esc)

Debuging with full node id
  $ rhg debugdata -c `hg log -r 0 -T '{node}'`
  c8e64718e1ca0312eeee0f59d37f8dc612793856
  test
  0 0
  file1
  
  commit 1 (no-eol)

Cat files
  $ cd $TESTTMP
  $ rm -rf repository
  $ hg init repository
  $ cd repository
  $ echo "original content" > original
  $ hg add original
  $ hg commit -m "add original" original
  $ rhg cat -r 0 original
  original content
Cat copied file should not display copy metadata
  $ hg copy original copy_of_original
  $ hg commit -m "add copy of original"
  $ rhg cat -r 1 copy_of_original
  original content

Specifying revisions by changeset ID
  $ hg log
  changeset:   1:41263439dc17
  tag:         tip
  user:        test
  date:        Thu Jan 01 00:00:00 1970 +0000
  summary:     add copy of original
  
  changeset:   0:1c9e69808da7
  user:        test
  date:        Thu Jan 01 00:00:00 1970 +0000
  summary:     add original
  
  $ rhg files -r 41263439dc17
  abort: invalid revision identifier 41263439dc17
  [255]
  $ rhg cat -r 41263439dc17 original
  abort: invalid revision identifier 41263439dc17
  [255]

Requirements
  $ rhg debugrequirements
  dotencode
  fncache
  generaldelta
  revlogv1
  sparserevlog
  store

  $ echo indoor-pool >> .hg/requires
  $ rhg files
  [252]

  $ rhg cat -r 1 copy_of_original
  [252]

  $ rhg debugrequirements
  dotencode
  fncache
  generaldelta
  revlogv1
  sparserevlog
  store
  indoor-pool

  $ echo -e '\xFF' >> .hg/requires
  $ rhg debugrequirements
  abort: .hg/requires is corrupted
  [255]
