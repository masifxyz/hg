#!/bin/sh
#
# Use this script to generate move.svndump
#

mkdir temp
cd temp

mkdir project-orig
cd project-orig
mkdir trunk
echo a > trunk/a
mkdir trunk/d1
mkdir trunk/d2
echo b > trunk/d1/b
echo c > trunk/d1/c
echo d > trunk/d2/d
cd ..

svnadmin create svn-repo
svnurl=file://`pwd`/svn-repo
svn import project-orig $svnurl -m "init projA"

svn co $svnurl project
cd project
# Build a module renaming chain which used to confuse the converter.
# Update svn repository
echo a >> trunk/a
echo c >> trunk/d1/c
svn ci -m commitbeforemove
svn mv $svnurl/trunk $svnurl/subproject -m movedtrunk
svn up
mkdir subproject/trunk
svn add subproject/trunk
svn ci -m createtrunk
mkdir subproject/branches
svn add subproject/branches
svn ci -m createbranches
svn mv $svnurl/subproject/d1 $svnurl/subproject/trunk/d1 -m moved1
svn mv $svnurl/subproject/d2 $svnurl/subproject/trunk/d2 -m moved2
svn up
echo b >> subproject/trunk/d1/b

svn rm subproject/trunk/d2
svn ci -m "changeb and rm d2"
svn mv $svnurl/subproject/trunk/d1 $svnurl/subproject/branches/d1 -m moved1again

if svn help copy | grep 'SRC\[@REV\]' > /dev/null 2>&1; then
    # SVN >= 1.5 replaced the -r REV syntax with @REV
    # Copy a file from a past revision
    svn copy $svnurl/subproject/trunk/d2/d@7 $svnurl/subproject/trunk -m copyfilefrompast
    # Copy a directory from a past revision
    svn copy $svnurl/subproject/trunk/d2@7 $svnurl/subproject/trunk -m copydirfrompast
else
    # Copy a file from a past revision
    svn copy -r 7 $svnurl/subproject/trunk/d2/d $svnurl/subproject/trunk -m copyfilefrompast
    # Copy a directory from a past revision
    svn copy -r 7 $svnurl/subproject/trunk/d2 $svnurl/subproject/trunk -m copydirfrompast
fi
cd ..

svnadmin dump svn-repo > ../move.svndump