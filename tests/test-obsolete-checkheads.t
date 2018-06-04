Check that obsolete properly strip heads
  $ cat >> $HGRCPATH << EOF
  > [phases]
  > # public changeset are not obsolete
  > publish=false
  > [ui]
  > logtemplate='{node|short} ({phase}) {desc|firstline}\n'
  > [experimental]
  > evolution.createmarkers=True
  > EOF
  $ mkcommit() {
  >    echo "$1" > "$1"
  >    hg add "$1"
  >    hg ci -m "add $1"
  > }
  $ getid() {
  >    hg id --debug -ir "desc('$1')"
  > }


  $ hg init remote
  $ cd remote
  $ mkcommit base
  $ hg phase --public .
  $ cd ..
  $ cp -R remote base
  $ hg clone remote local
  updating to branch default
  1 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ cd local

New head replaces old head
==========================

setup
(we add the 1 flags to prevent bumped error during the test)

  $ mkcommit old
  $ hg push
  pushing to $TESTTMP/remote
  searching for changes
  adding changesets
  adding manifests
  adding file changes
  added 1 changesets with 1 changes to 1 files
  $ hg up -q '.^'
  $ mkcommit new
  created new head
  $ hg debugobsolete --flags 1 `getid old` `getid new`
  obsoleted 1 changesets
  $ hg log -G --hidden
  @  71e3228bffe1 (draft) add new
  |
  | x  c70b08862e08 (draft) add old
  |/
  o  b4952fcf48cf (public) add base
  
  $ cp -R ../remote ../backup1

old exists remotely as draft. It is obsoleted by new that we now push.
Push should not warn about creating new head

  $ hg push
  pushing to $TESTTMP/remote
  searching for changes
  adding changesets
  adding manifests
  adding file changes
  added 1 changesets with 1 changes to 1 files (+1 heads)

old head is now public (public local version)
=============================================

setup

  $ rm -fr ../remote
  $ cp -R ../backup1 ../remote
  $ hg -R ../remote phase --public c70b08862e08
  $ hg pull -v
  pulling from $TESTTMP/remote
  searching for changes
  no changes found
  1 local changesets became public
  $ hg log -G --hidden
  @  71e3228bffe1 (draft) add new
  |
  | o  c70b08862e08 (public) add old
  |/
  o  b4952fcf48cf (public) add base
  

Abort: old will still be an head because it's public.

  $ hg push
  pushing to $TESTTMP/remote
  searching for changes
  abort: push creates new remote head 71e3228bffe1!
  (merge or see 'hg help push' for details about pushing new heads)
  [255]

old head is now public (public remote version)
==============================================

TODO: Not implemented yet.

# setup
#
#   $ rm -fr ../remote
#   $ cp -R ../backup1 ../remote
#   $ hg -R ../remote phase --public c70b08862e08
#   $ hg phase --draft --force c70b08862e08
#   $ hg log -G --hidden
#   @  71e3228bffe1 (draft) add new
#   |
#   | x  c70b08862e08 (draft) add old
#   |/
#   o  b4952fcf48cf (public) add base
#
#
#
# Abort: old will still be an head because it's public.
#
#   $ hg push
#   pushing to $TESTTMP/remote
#   searching for changes
#   abort: push creates new remote head 71e3228bffe1!
#   (merge or see 'hg help push' for details about pushing new heads)
#   [255]

old head is obsolete but replacement is not pushed
==================================================

setup

  $ rm -fr ../remote
  $ cp -R ../backup1 ../remote
  $ hg phase --draft --force '(0::) - 0'
  $ hg up -q '.^'
  $ mkcommit other
  created new head
  $ hg log -G --hidden
  @  d7d41ccbd4de (draft) add other
  |
  | o  71e3228bffe1 (draft) add new
  |/
  | x  c70b08862e08 (draft) add old
  |/
  o  b4952fcf48cf (public) add base
  

old exists remotely as draft. It is obsoleted by new but we don't push new.
Push should abort on new head

  $ hg push -r 'desc("other")'
  pushing to $TESTTMP/remote
  searching for changes
  abort: push creates new remote head d7d41ccbd4de!
  (merge or see 'hg help push' for details about pushing new heads)
  [255]



Both precursors and successors are already know remotely. Descendant adds heads
===============================================================================

setup. (The obsolete marker is known locally only

  $ cd ..
  $ rm -rf local
  $ hg clone remote local
  updating to branch default
  2 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ cd local
  $ mkcommit old
  old already tracked!
  nothing changed
  [1]
  $ hg up -q '.^'
  $ mkcommit new
  created new head
  $ hg push -f
  pushing to $TESTTMP/remote
  searching for changes
  adding changesets
  adding manifests
  adding file changes
  added 1 changesets with 1 changes to 1 files (+1 heads)
  $ mkcommit desc1
  $ hg up -q '.^'
  $ mkcommit desc2
  created new head
  $ hg debugobsolete `getid old` `getid new`
  obsoleted 1 changesets
  $ hg log -G --hidden
  @  5fe37041cc2b (draft) add desc2
  |
  | o  a3ef1d111c5f (draft) add desc1
  |/
  o  71e3228bffe1 (draft) add new
  |
  | x  c70b08862e08 (draft) add old
  |/
  o  b4952fcf48cf (public) add base
  
  $ hg log -G --hidden -R ../remote
  o  71e3228bffe1 (draft) add new
  |
  | o  c70b08862e08 (draft) add old
  |/
  @  b4952fcf48cf (public) add base
  
  $ cp -R ../remote ../backup2

Push should not warn about adding new heads. We create one, but we'll delete
one anyway.

  $ hg push
  pushing to $TESTTMP/remote
  searching for changes
  adding changesets
  adding manifests
  adding file changes
  added 2 changesets with 2 changes to 2 files (+1 heads)


Remote head is unknown but obsoleted by a local changeset
=========================================================

setup

  $ rm -fr ../remote
  $ cp -R ../backup1 ../remote
  $ cd ..
  $ rm -rf local
  $ hg clone remote local -r 0
  adding changesets
  adding manifests
  adding file changes
  added 1 changesets with 1 changes to 1 files
  new changesets b4952fcf48cf
  updating to branch default
  1 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ cd local
  $ mkcommit new
  $ hg -R ../remote id --debug -r tip
  c70b08862e0838ea6d7c59c85da2f1ed6c8d67da tip
  $ hg  id --debug -r tip
  71e3228bffe1886550777233d6c97bb5a6b2a650 tip
  $ hg debugobsolete c70b08862e0838ea6d7c59c85da2f1ed6c8d67da 71e3228bffe1886550777233d6c97bb5a6b2a650
  $ hg log -G --hidden
  @  71e3228bffe1 (draft) add new
  |
  o  b4952fcf48cf (public) add base
  
  $ hg log -G --hidden -R ../remote
  o  c70b08862e08 (draft) add old
  |
  @  b4952fcf48cf (public) add base
  

We do not have enought data to take the right decision, we should fail

  $ hg push
  pushing to $TESTTMP/remote
  searching for changes
  remote has heads on branch 'default' that are not known locally: c70b08862e08
  abort: push creates new remote head 71e3228bffe1!
  (pull and merge or see 'hg help push' for details about pushing new heads)
  [255]

Pulling the missing data makes it work

  $ hg pull
  pulling from $TESTTMP/remote
  searching for changes
  adding changesets
  adding manifests
  adding file changes
  added 1 changesets with 1 changes to 1 files (+1 heads)
  (run 'hg heads' to see heads)
  $ hg push
  pushing to $TESTTMP/remote
  searching for changes
  adding changesets
  adding manifests
  adding file changes
  added 1 changesets with 1 changes to 1 files (+1 heads)

Old head is pruned without parent data and new unrelated head added
===================================================================

setup

  $ cd ..
  $ rm -R remote local
  $ cp -R backup1 remote
  $ hg clone remote local -qr c70b08862e08
  $ cd local
  $ hg up -q '.^'
  $ mkcommit new-unrelated
  created new head
  $ hg debugobsolete `getid old`
  obsoleted 1 changesets
  $ hg log -G --hidden
  @  350a93b716be (draft) add new-unrelated
  |
  | x  c70b08862e08 (draft) add old
  |/
  o  b4952fcf48cf (public) add base
  

  $ hg push
  pushing to $TESTTMP/remote
  searching for changes
  abort: push creates new remote head 350a93b716be!
  (merge or see 'hg help push' for details about pushing new heads)
  [255]
