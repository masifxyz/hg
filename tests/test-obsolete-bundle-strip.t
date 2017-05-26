==================================================
Test obsmarkers interaction with bundle and strip
==================================================

The file currently only contains test for bundle.
Testing of strip will happen some time soon (tm).

Setup a repository with various case
====================================

Config setup
------------

  $ cat >> $HGRCPATH <<EOF
  > [ui]
  > # simpler log output
  > logtemplate = "{node|short}: {desc}\n"
  > 
  > [experimental]
  > # enable evolution
  > evolution = all
  > 
  > # include obsmarkers in bundle
  > evolution.bundle-obsmarker = yes
  > 
  > [extensions]
  > # needed for some tests
  > strip =
  > [defaults]
  > # we'll query many hidden changeset
  > debugobsolete = --hidden
  > EOF

  $ mkcommit() {
  >    echo "$1" > "$1"
  >    hg add "$1"
  >    hg ci -m "$1"
  > }

  $ getid() {
  >    hg log --hidden --template '{node}\n' --rev "$1"
  > }

  $ mktestrepo () {
  >     [ -n "$1" ] || exit 1
  >     cd $TESTTMP
  >     hg init $1
  >     cd $1
  >     mkcommit ROOT
  > }

Function to compare the expected bundled obsmarkers with the actually bundled
obsmarkers.

  $ testrevs () {
  >     revs="$1"
  >     testname=`basename \`pwd\``
  >     revsname=`hg --hidden log -T '-{desc}\n' --rev "${revs}"`
  >     prefix="${TESTTMP}/${testname}${revsname}"
  >     markersfile="${prefix}-relevant-markers.txt"
  >     bundlefile="${prefix}-bundle.hg"
  >     contentfile="${prefix}-bundle-markers.hg"
  >     hg debugobsolete --hidden --rev "${revs}" | sed 's/^/    /' > "${markersfile}"
  >     echo '### Matched revisions###'
  >     hg log --hidden --rev "${revs}" | sort
  >     echo '### Relevant markers ###'
  >     cat "${markersfile}"
  >     printf "# bundling: "
  >     hg bundle --hidden --base "parents(roots(${revs}))" --rev "${revs}" "${bundlefile}"
  >     hg debugbundle "${bundlefile}" | grep "obsmarkers --" -A 100 | sed 1,2d > "${contentfile}"
  >     echo '### Bundled markers ###'
  >     cat "${contentfile}"
  >     echo '### diff <relevant> <bundled> ###'
  >     cmp "${markersfile}" "${contentfile}" || diff -u "${markersfile}" "${contentfile}"
  >     echo '#################################'
  > }

root setup
-------------

simple chain
============

.    A0
.   ⇠ø⇠◔ A1
.    |/
.    ●

setup
-----

  $ mktestrepo simple-chain
  $ mkcommit 'C-A0'
  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 1 files removed, 0 files unresolved
  $ mkcommit 'C-A1'
  created new head
  $ hg debugobsolete a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 `getid 'desc("C-A0")'`
  $ hg debugobsolete `getid 'desc("C-A0")'` a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1
  $ hg debugobsolete a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1 `getid 'desc("C-A1")'`

  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 1 files removed, 0 files unresolved
  $ hg log --hidden -G
  o  cf2c22470d67: C-A1
  |
  | x  84fcb0dfe17b: C-A0
  |/
  @  ea207398892e: ROOT
  
  $ hg debugobsolete
  a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  84fcb0dfe17b256ebae52e05572993b9194c018a a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1 cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}

Actual testing
--------------

  $ testrevs 'desc("C-A0")'
  ### Matched revisions###
  84fcb0dfe17b: C-A0
  ### Relevant markers ###
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  # bundling: 1 changesets found
  ### Bundled markers ###
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  ### diff <relevant> <bundled> ###
  #################################

  $ testrevs 'desc("C-A1")'
  ### Matched revisions###
  cf2c22470d67: C-A1
  ### Relevant markers ###
      84fcb0dfe17b256ebae52e05572993b9194c018a a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1 cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  # bundling: 1 changesets found
  ### Bundled markers ###
      84fcb0dfe17b256ebae52e05572993b9194c018a a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1 cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  ### diff <relevant> <bundled> ###
  #################################

  $ testrevs 'desc("C-A")'
  ### Matched revisions###
  84fcb0dfe17b: C-A0
  cf2c22470d67: C-A1
  ### Relevant markers ###
      84fcb0dfe17b256ebae52e05572993b9194c018a a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1 cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  # bundling: 2 changesets found
  ### Bundled markers ###
      84fcb0dfe17b256ebae52e05572993b9194c018a a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1 cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  ### diff <relevant> <bundled> ###
  #################################

chain with prune children
=========================

.  ⇠⊗ B0
.   |
.  ⇠ø⇠◔ A1
.     |
.     ●

setup
-----

  $ mktestrepo prune
  $ mkcommit 'C-A0'
  $ mkcommit 'C-B0'
  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 2 files removed, 0 files unresolved
  $ mkcommit 'C-A1'
  created new head
  $ hg debugobsolete a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 `getid 'desc("C-A0")'`
  $ hg debugobsolete `getid 'desc("C-A0")'` `getid 'desc("C-A1")'`
  $ hg debugobsolete --record-parents `getid 'desc("C-B0")'`
  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 1 files removed, 0 files unresolved
  $ hg log --hidden -G
  o  cf2c22470d67: C-A1
  |
  | x  29f93b1df87b: C-B0
  | |
  | x  84fcb0dfe17b: C-A0
  |/
  @  ea207398892e: ROOT
  
  $ hg debugobsolete
  a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  29f93b1df87baee1824e014080d8adf145f81783 0 {84fcb0dfe17b256ebae52e05572993b9194c018a} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}

Actual testing
--------------

  $ testrevs 'desc("C-A0")'
  ### Matched revisions###
  84fcb0dfe17b: C-A0
  ### Relevant markers ###
      29f93b1df87baee1824e014080d8adf145f81783 0 {84fcb0dfe17b256ebae52e05572993b9194c018a} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  # bundling: 1 changesets found
  ### Bundled markers ###
      29f93b1df87baee1824e014080d8adf145f81783 0 {84fcb0dfe17b256ebae52e05572993b9194c018a} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  ### diff <relevant> <bundled> ###
  #################################

  $ testrevs 'desc("C-B0")'
  ### Matched revisions###
  29f93b1df87b: C-B0
  ### Relevant markers ###
      29f93b1df87baee1824e014080d8adf145f81783 0 {84fcb0dfe17b256ebae52e05572993b9194c018a} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  # bundling: 1 changesets found
  ### Bundled markers ###
      29f93b1df87baee1824e014080d8adf145f81783 0 {84fcb0dfe17b256ebae52e05572993b9194c018a} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  ### diff <relevant> <bundled> ###
  #################################

  $ testrevs 'desc("C-A1")'
  ### Matched revisions###
  cf2c22470d67: C-A1
  ### Relevant markers ###
      29f93b1df87baee1824e014080d8adf145f81783 0 {84fcb0dfe17b256ebae52e05572993b9194c018a} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  # bundling: 1 changesets found
  ### Bundled markers ###
      29f93b1df87baee1824e014080d8adf145f81783 0 {84fcb0dfe17b256ebae52e05572993b9194c018a} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  ### diff <relevant> <bundled> ###
  #################################

bundling multiple revisions

  $ testrevs 'desc("C-A")'
  ### Matched revisions###
  84fcb0dfe17b: C-A0
  cf2c22470d67: C-A1
  ### Relevant markers ###
      29f93b1df87baee1824e014080d8adf145f81783 0 {84fcb0dfe17b256ebae52e05572993b9194c018a} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  # bundling: 2 changesets found
  ### Bundled markers ###
      29f93b1df87baee1824e014080d8adf145f81783 0 {84fcb0dfe17b256ebae52e05572993b9194c018a} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  ### diff <relevant> <bundled> ###
  #################################

  $ testrevs 'desc("C-")'
  ### Matched revisions###
  29f93b1df87b: C-B0
  84fcb0dfe17b: C-A0
  cf2c22470d67: C-A1
  ### Relevant markers ###
      29f93b1df87baee1824e014080d8adf145f81783 0 {84fcb0dfe17b256ebae52e05572993b9194c018a} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  # bundling: 3 changesets found
  ### Bundled markers ###
      29f93b1df87baee1824e014080d8adf145f81783 0 {84fcb0dfe17b256ebae52e05572993b9194c018a} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  ### diff <relevant> <bundled> ###
  #################################

chain with precursors also pruned
=================================

.   A0 (also pruned)
.  ⇠ø⇠◔ A1
.     |
.     ●

setup
-----

  $ mktestrepo prune-inline
  $ mkcommit 'C-A0'
  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 1 files removed, 0 files unresolved
  $ mkcommit 'C-A1'
  created new head
  $ hg debugobsolete a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 `getid 'desc("C-A0")'`
  $ hg debugobsolete --record-parents `getid 'desc("C-A0")'`
  $ hg debugobsolete `getid 'desc("C-A0")'` `getid 'desc("C-A1")'`
  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 1 files removed, 0 files unresolved
  $ hg log --hidden -G
  o  cf2c22470d67: C-A1
  |
  | x  84fcb0dfe17b: C-A0
  |/
  @  ea207398892e: ROOT
  
  $ hg debugobsolete
  a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  84fcb0dfe17b256ebae52e05572993b9194c018a 0 {ea207398892eb49e06441f10dda2a731f0450f20} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}

Actual testing
--------------

  $ testrevs 'desc("C-A0")'
  ### Matched revisions###
  84fcb0dfe17b: C-A0
  ### Relevant markers ###
      84fcb0dfe17b256ebae52e05572993b9194c018a 0 {ea207398892eb49e06441f10dda2a731f0450f20} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  # bundling: 1 changesets found
  ### Bundled markers ###
      84fcb0dfe17b256ebae52e05572993b9194c018a 0 {ea207398892eb49e06441f10dda2a731f0450f20} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  ### diff <relevant> <bundled> ###
  #################################

  $ testrevs 'desc("C-A1")'
  ### Matched revisions###
  cf2c22470d67: C-A1
  ### Relevant markers ###
      84fcb0dfe17b256ebae52e05572993b9194c018a 0 {ea207398892eb49e06441f10dda2a731f0450f20} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  # bundling: 1 changesets found
  ### Bundled markers ###
      84fcb0dfe17b256ebae52e05572993b9194c018a 0 {ea207398892eb49e06441f10dda2a731f0450f20} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  ### diff <relevant> <bundled> ###
  #################################

  $ testrevs 'desc("C-A")'
  ### Matched revisions###
  84fcb0dfe17b: C-A0
  cf2c22470d67: C-A1
  ### Relevant markers ###
      84fcb0dfe17b256ebae52e05572993b9194c018a 0 {ea207398892eb49e06441f10dda2a731f0450f20} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  # bundling: 2 changesets found
  ### Bundled markers ###
      84fcb0dfe17b256ebae52e05572993b9194c018a 0 {ea207398892eb49e06441f10dda2a731f0450f20} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  ### diff <relevant> <bundled> ###
  #################################

chain with missing prune
========================

.   ⊗ B
.   |
.  ⇠◌⇠◔ A1
.   |
.   ●

setup
-----

  $ mktestrepo missing-prune
  $ mkcommit 'C-A0'
  $ mkcommit 'C-B0'
  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 2 files removed, 0 files unresolved
  $ mkcommit 'C-A1'
  created new head
  $ hg debugobsolete a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 `getid 'desc("C-A0")'`
  $ hg debugobsolete `getid 'desc("C-A0")'` `getid 'desc("C-A1")'`
  $ hg debugobsolete --record-parents `getid 'desc("C-B0")'`

(it is annoying to create prune with parent data without the changeset, so we strip it after the fact)

  $ hg strip --hidden --rev 'desc("C-A0")::' --no-backup

  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 1 files removed, 0 files unresolved
  $ hg log --hidden -G
  o  cf2c22470d67: C-A1
  |
  @  ea207398892e: ROOT
  
  $ hg debugobsolete
  a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  29f93b1df87baee1824e014080d8adf145f81783 0 {84fcb0dfe17b256ebae52e05572993b9194c018a} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}

Actual testing
--------------

  $ testrevs 'desc("C-A1")'
  ### Matched revisions###
  cf2c22470d67: C-A1
  ### Relevant markers ###
      29f93b1df87baee1824e014080d8adf145f81783 0 {84fcb0dfe17b256ebae52e05572993b9194c018a} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  # bundling: 1 changesets found
  ### Bundled markers ###
      29f93b1df87baee1824e014080d8adf145f81783 0 {84fcb0dfe17b256ebae52e05572993b9194c018a} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
      a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  ### diff <relevant> <bundled> ###
  #################################

chain with precursors also pruned
=================================

.   A0 (also pruned)
.  ⇠◌⇠◔ A1
.     |
.     ●

setup
-----

  $ mktestrepo prune-inline-missing
  $ mkcommit 'C-A0'
  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 1 files removed, 0 files unresolved
  $ mkcommit 'C-A1'
  created new head
  $ hg debugobsolete a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 `getid 'desc("C-A0")'`
  $ hg debugobsolete --record-parents `getid 'desc("C-A0")'`
  $ hg debugobsolete `getid 'desc("C-A0")'` `getid 'desc("C-A1")'`

(it is annoying to create prune with parent data without the changeset, so we strip it after the fact)

  $ hg strip --hidden --rev 'desc("C-A0")::' --no-backup

  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 1 files removed, 0 files unresolved
  $ hg log --hidden -G
  o  cf2c22470d67: C-A1
  |
  @  ea207398892e: ROOT
  
  $ hg debugobsolete
  a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  84fcb0dfe17b256ebae52e05572993b9194c018a 0 {ea207398892eb49e06441f10dda2a731f0450f20} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}

Actual testing
--------------

  $ hg debugobsolete --rev 'desc("C-A1")'
  84fcb0dfe17b256ebae52e05572993b9194c018a 0 {ea207398892eb49e06441f10dda2a731f0450f20} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  84fcb0dfe17b256ebae52e05572993b9194c018a cf2c22470d67233004e934a31184ac2b35389914 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 84fcb0dfe17b256ebae52e05572993b9194c018a 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}

Chain with fold and split
=========================

setup
-----

  $ mktestrepo split-fold
  $ mkcommit 'C-A'
  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 1 files removed, 0 files unresolved
  $ mkcommit 'C-B'
  created new head
  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 1 files removed, 0 files unresolved
  $ mkcommit 'C-C'
  created new head
  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 1 files removed, 0 files unresolved
  $ mkcommit 'C-D'
  created new head
  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 1 files removed, 0 files unresolved
  $ mkcommit 'C-E'
  created new head
  $ hg debugobsolete a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 `getid 'desc("C-A")'`
  $ hg debugobsolete `getid 'desc("C-A")'` `getid 'desc("C-B")'` `getid 'desc("C-C")'` # record split
  $ hg debugobsolete `getid 'desc("C-A")'` `getid 'desc("C-D")'` # other divergent
  $ hg debugobsolete `getid 'desc("C-A")'` b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0
  $ hg debugobsolete b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0 `getid 'desc("C-E")'`
  $ hg debugobsolete `getid 'desc("C-B")'` `getid 'desc("C-E")'`
  $ hg debugobsolete `getid 'desc("C-C")'` `getid 'desc("C-E")'`
  $ hg debugobsolete `getid 'desc("C-D")'` `getid 'desc("C-E")'`
  $ hg debugobsolete c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0 `getid 'desc("C-E")'`

  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 1 files removed, 0 files unresolved
  $ hg log --hidden -G
  o  2f20ff6509f0: C-E
  |
  | x  06dc9da25ef0: C-D
  |/
  | x  27ec657ca21d: C-C
  |/
  | x  a9b9da38ed96: C-B
  |/
  | x  9ac430e15fca: C-A
  |/
  @  ea207398892e: ROOT
  
  $ hg debugobsolete
  a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 9ac430e15fca923b0ba027ca85d4d75c5c9cb73c 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  9ac430e15fca923b0ba027ca85d4d75c5c9cb73c a9b9da38ed96f8c6c14f429441f625a344eb4696 27ec657ca21dd27c36c99fa75586f72ff0d442f1 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  9ac430e15fca923b0ba027ca85d4d75c5c9cb73c 06dc9da25ef03e1ff7864dded5fcba42eff2a3f0 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  9ac430e15fca923b0ba027ca85d4d75c5c9cb73c b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0 2f20ff6509f0e013e90c5c8efd996131c918b0ca 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  a9b9da38ed96f8c6c14f429441f625a344eb4696 2f20ff6509f0e013e90c5c8efd996131c918b0ca 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  27ec657ca21dd27c36c99fa75586f72ff0d442f1 2f20ff6509f0e013e90c5c8efd996131c918b0ca 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  06dc9da25ef03e1ff7864dded5fcba42eff2a3f0 2f20ff6509f0e013e90c5c8efd996131c918b0ca 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0 2f20ff6509f0e013e90c5c8efd996131c918b0ca 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}

Actual testing
--------------

  $ hg debugobsolete --rev 'desc("C-A")'
  a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 9ac430e15fca923b0ba027ca85d4d75c5c9cb73c 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  $ hg debugobsolete --rev 'desc("C-B")'
  9ac430e15fca923b0ba027ca85d4d75c5c9cb73c a9b9da38ed96f8c6c14f429441f625a344eb4696 27ec657ca21dd27c36c99fa75586f72ff0d442f1 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 9ac430e15fca923b0ba027ca85d4d75c5c9cb73c 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  $ hg debugobsolete --rev 'desc("C-C")'
  9ac430e15fca923b0ba027ca85d4d75c5c9cb73c a9b9da38ed96f8c6c14f429441f625a344eb4696 27ec657ca21dd27c36c99fa75586f72ff0d442f1 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 9ac430e15fca923b0ba027ca85d4d75c5c9cb73c 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  $ hg debugobsolete --rev 'desc("C-D")'
  9ac430e15fca923b0ba027ca85d4d75c5c9cb73c 06dc9da25ef03e1ff7864dded5fcba42eff2a3f0 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 9ac430e15fca923b0ba027ca85d4d75c5c9cb73c 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  $ hg debugobsolete --rev 'desc("C-E")'
  06dc9da25ef03e1ff7864dded5fcba42eff2a3f0 2f20ff6509f0e013e90c5c8efd996131c918b0ca 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  27ec657ca21dd27c36c99fa75586f72ff0d442f1 2f20ff6509f0e013e90c5c8efd996131c918b0ca 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  9ac430e15fca923b0ba027ca85d4d75c5c9cb73c 06dc9da25ef03e1ff7864dded5fcba42eff2a3f0 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  9ac430e15fca923b0ba027ca85d4d75c5c9cb73c a9b9da38ed96f8c6c14f429441f625a344eb4696 27ec657ca21dd27c36c99fa75586f72ff0d442f1 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  9ac430e15fca923b0ba027ca85d4d75c5c9cb73c b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0 9ac430e15fca923b0ba027ca85d4d75c5c9cb73c 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  a9b9da38ed96f8c6c14f429441f625a344eb4696 2f20ff6509f0e013e90c5c8efd996131c918b0ca 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0 2f20ff6509f0e013e90c5c8efd996131c918b0ca 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0 2f20ff6509f0e013e90c5c8efd996131c918b0ca 0 (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}

changeset pruned on its own
===========================

. ⊗ B
. |
. ◕ A
. |
. ●

setup
-----

  $ mktestrepo lonely-prune
  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ mkcommit 'C-A'
  $ mkcommit 'C-B'
  $ hg debugobsolete --record-parent `getid 'desc("C-B")'`

  $ hg up 'desc("ROOT")'
  0 files updated, 0 files merged, 2 files removed, 0 files unresolved
  $ hg log --hidden -G
  x  cefb651fc2fd: C-B
  |
  o  9ac430e15fca: C-A
  |
  @  ea207398892e: ROOT
  
  $ hg debugobsolete
  cefb651fc2fdc7bb75e588781de5e432c134e8a5 0 {9ac430e15fca923b0ba027ca85d4d75c5c9cb73c} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}

Actual testing
--------------
  $ hg debugobsolete --rev 'desc("C-A")'
  cefb651fc2fdc7bb75e588781de5e432c134e8a5 0 {9ac430e15fca923b0ba027ca85d4d75c5c9cb73c} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
  $ hg debugobsolete --hidden --rev 'desc("C-B")'
  cefb651fc2fdc7bb75e588781de5e432c134e8a5 0 {9ac430e15fca923b0ba027ca85d4d75c5c9cb73c} (Thu Jan 01 00:00:00 1970 +0000) {'user': 'test'}
