      (integer '5')
      (integer '2'))
    (string ' ')
      (symbol 'mod')
        (integer '5')
        (integer '2')))
    (string '\n'))
      (integer '5')
        (integer '2')))
    (string ' ')
      (symbol 'mod')
        (integer '5')
          (integer '2'))))
    (string '\n'))
        (integer '5'))
      (integer '2'))
    (string ' ')
      (symbol 'mod')
          (integer '5'))
        (integer '2')))
    (string '\n'))
        (integer '5'))
        (integer '2')))
    (string ' ')
      (symbol 'mod')
          (integer '5'))
          (integer '2'))))
    (string '\n'))
          (symbol 'revset')
          (string '.'))
        (symbol 'count'))
      (integer '1'))
    (string '\n'))
      (integer '1')
        (integer '3')
        (symbol 'stringify')))
    (string '\n'))
        (integer '3'))
      (symbol 'stringify'))
    (string '\n'))
Filters bind as close as map operator:

  $ hg debugtemplate -r0 -v '{desc|splitlines % "{line}\n"}'
  (template
    (%
      (|
        (symbol 'desc')
        (symbol 'splitlines'))
      (template
        (symbol 'line')
        (string '\n'))))
  line 1
  line 2

      (symbol 'foo')
        (symbol 'bar')
        (symbol 'baz'))))
Internal resources shouldn't be exposed (issue5699):

  $ hg log -r. -T '{cache}{ctx}{repo}{revcache}{templ}{ui}'

Never crash on internal resource not available:

  $ hg --cwd .. debugtemplate '{"c0bebeef"|shortest}\n'
  abort: template resource not available: ctx
  [255]

  $ hg config -T '{author}'

  $ cat <<'EOF' >> .hg/hgrc
  > [templates]
  > simple = "{rev}\n"
  > simple2 = {rev}\n
  > rev = "should not precede {rev} keyword\n"
  > EOF
  $ hg log -l1 -Trev
  should not precede 8 keyword
  $ hg log -l1 -T '{simple}'
  8

Map file shouldn't see user templates:

  $ cat <<EOF > tmpl
  > changeset = 'nothing expanded:{simple}\n'
  > EOF
  $ hg log -l1 --style ./tmpl
  nothing expanded:
 a map file may have [templates] and [templatealias] sections:

  $ cat <<'EOF' > map-simple
  > [templates]
  > changeset = "{a}\n"
  > [templatealias]
  > a = rev
  > EOF
  $ hg log -l1 -T./map-simple
  8

 so it can be included in hgrc

  $ cat <<EOF > myhgrc
  > %include $HGRCPATH
  > %include map-simple
  > [templates]
  > foo = "{changeset}"
  > EOF
  $ HGRCPATH=./myhgrc hg log -l1 -Tfoo
  8
  $ HGRCPATH=./myhgrc hg log -l1 -T'{a}\n'
  8

Test docheader, docfooter and separator in template map

  $ cat <<'EOF' > map-myjson
  > docheader = '\{\n'
  > docfooter = '\n}\n'
  > separator = ',\n'
  > changeset = ' {dict(rev, node|short)|json}'
  > EOF
  $ hg log -l2 -T./map-myjson
  {
   {"node": "95c24699272e", "rev": 8},
   {"node": "29114dbae42b", "rev": 7}
  }

Test docheader, docfooter and separator in [templates] section

  $ cat <<'EOF' >> .hg/hgrc
  > [templates]
  > myjson = ' {dict(rev, node|short)|json}'
  > myjson:docheader = '\{\n'
  > myjson:docfooter = '\n}\n'
  > myjson:separator = ',\n'
  > :docheader = 'should not be selected as a docheader for literal templates\n'
  > EOF
  $ hg log -l2 -Tmyjson
  {
   {"node": "95c24699272e", "rev": 8},
   {"node": "29114dbae42b", "rev": 7}
  }
  $ hg log -l1 -T'{rev}\n'
  8

  [
  ]
    "node": "95c24699272ef57d062b8bccc32c878bf841784a",
    "rev": 8
    "bookmarks": [],
    "diff": "diff -r 29114dbae42b -r 95c24699272e fourth\n--- /dev/null\tThu Jan 01 00:00:00 1970 +0000\n+++ b/fourth\tWed Jan 01 10:01:00 2020 +0000\n@@ -0,0 +1,1 @@\n+second\ndiff -r 29114dbae42b -r 95c24699272e second\n--- a/second\tMon Jan 12 13:46:40 1970 +0000\n+++ /dev/null\tThu Jan 01 00:00:00 1970 +0000\n@@ -1,1 +0,0 @@\n-second\ndiff -r 29114dbae42b -r 95c24699272e third\n--- /dev/null\tThu Jan 01 00:00:00 1970 +0000\n+++ b/third\tWed Jan 01 10:01:00 2020 +0000\n@@ -0,0 +1,1 @@\n+third\n",
    "files": ["fourth", "second", "third"],
    "node": "95c24699272ef57d062b8bccc32c878bf841784a",
    "parents": ["29114dbae42b9f078cf2714dbe3a86bba8ec7453"],
    "phase": "draft",
    "rev": 8,
    "tags": ["tip"],
    "user": "test"
    "bookmarks": [],
    "diff": "diff --git a/second b/fourth\nrename from second\nrename to fourth\ndiff --git a/third b/third\nnew file mode 100644\n--- /dev/null\n+++ b/third\n@@ -0,0 +1,1 @@\n+third\n",
    "node": "95c24699272ef57d062b8bccc32c878bf841784a",
    "parents": ["29114dbae42b9f078cf2714dbe3a86bba8ec7453"],
    "phase": "draft",
    "rev": 8,
    "tags": ["tip"],
    "user": "test"
    "bookmarks": [],
    "node": "95c24699272ef57d062b8bccc32c878bf841784a",
    "parents": ["29114dbae42b9f078cf2714dbe3a86bba8ec7453"],
    "phase": "draft",
    "rev": 8,
    "user": "test"
    "bookmarks": [],
    "node": "29114dbae42b9f078cf2714dbe3a86bba8ec7453",
    "parents": ["0000000000000000000000000000000000000000"],
    "phase": "draft",
    "rev": 7,
    "user": "User Name <user@hostname>"
    "bookmarks": [],
    "node": "d41e714fe50d9e4a5f11b4d595d543481b5f980b",
    "parents": ["13207e5a10d9fd28ec424934298e176197f2c67f", "bbe44766e73d5f11ed2177f1838de10c53ef3e74"],
    "phase": "draft",
    "rev": 6,
    "user": "person"
    "bookmarks": [],
    "node": "13207e5a10d9fd28ec424934298e176197f2c67f",
    "parents": ["10e46f2dcbf4823578cf180f33ecf0b957964c47"],
    "phase": "draft",
    "rev": 5,
    "user": "person"
    "bookmarks": [],
    "node": "bbe44766e73d5f11ed2177f1838de10c53ef3e74",
    "parents": ["10e46f2dcbf4823578cf180f33ecf0b957964c47"],
    "phase": "draft",
    "rev": 4,
    "user": "person"
    "bookmarks": [],
    "node": "10e46f2dcbf4823578cf180f33ecf0b957964c47",
    "parents": ["97054abb4ab824450e9164180baf491ae0078465"],
    "phase": "draft",
    "rev": 3,
    "user": "person"
    "bookmarks": [],
    "node": "97054abb4ab824450e9164180baf491ae0078465",
    "parents": ["b608e9d1a3f0273ccf70fb85fd6866b3482bf965"],
    "phase": "draft",
    "rev": 2,
    "user": "other@place"
    "bookmarks": [],
    "node": "b608e9d1a3f0273ccf70fb85fd6866b3482bf965",
    "parents": ["1e4e1b8f71e05681d422154f5421e385fec3454f"],
    "phase": "draft",
    "rev": 1,
    "user": "A. N. Other <other@place>"
    "bookmarks": [],
    "node": "1e4e1b8f71e05681d422154f5421e385fec3454f",
    "parents": ["0000000000000000000000000000000000000000"],
    "phase": "draft",
    "rev": 0,
    "user": "User Name <user@hostname>"
    "bookmarks": [],
    "files": ["fourth", "second", "third"],
    "node": "95c24699272ef57d062b8bccc32c878bf841784a",
    "phase": "draft",
    "rev": 8,
    "tags": ["tip"],
    "user": "test"
    "bookmarks": [],
    "files": [],
    "node": "d41e714fe50d9e4a5f11b4d595d543481b5f980b",
    "phase": "draft",
    "rev": 6,
    "tags": [],
    "user": "person"
    "bookmarks": [],
    "files": [],
    "node": "bbe44766e73d5f11ed2177f1838de10c53ef3e74",
    "phase": "draft",
    "rev": 4,
    "tags": [],
    "user": "person"
    "added": ["fourth", "third"],
    "bookmarks": [],
    "manifest": "94961b75a2da554b4df6fb599e5bfc7d48de0c64",
    "node": "95c24699272ef57d062b8bccc32c878bf841784a",
    "parents": ["29114dbae42b9f078cf2714dbe3a86bba8ec7453"],
    "phase": "draft",
    "removed": ["second"],
    "rev": 8,
    "tags": ["tip"],
    "user": "test"
    "added": ["second"],
    "bookmarks": [],
    "manifest": "f2dbc354b94e5ec0b4f10680ee0cee816101d0bf",
    "node": "29114dbae42b9f078cf2714dbe3a86bba8ec7453",
    "parents": ["0000000000000000000000000000000000000000"],
    "phase": "draft",
    "removed": [],
    "rev": 7,
    "tags": [],
    "user": "User Name <user@hostname>"
    "added": [],
    "bookmarks": [],
    "manifest": "4dc3def4f9b4c6e8de820f6ee74737f91e96a216",
    "node": "d41e714fe50d9e4a5f11b4d595d543481b5f980b",
    "parents": ["13207e5a10d9fd28ec424934298e176197f2c67f", "bbe44766e73d5f11ed2177f1838de10c53ef3e74"],
    "phase": "draft",
    "removed": [],
    "rev": 6,
    "tags": [],
    "user": "person"
    "added": ["d"],
    "bookmarks": [],
    "manifest": "4dc3def4f9b4c6e8de820f6ee74737f91e96a216",
    "node": "13207e5a10d9fd28ec424934298e176197f2c67f",
    "parents": ["10e46f2dcbf4823578cf180f33ecf0b957964c47"],
    "phase": "draft",
    "removed": [],
    "rev": 5,
    "tags": [],
    "user": "person"
    "added": [],
    "bookmarks": [],
    "manifest": "cb5a1327723bada42f117e4c55a303246eaf9ccc",
    "node": "bbe44766e73d5f11ed2177f1838de10c53ef3e74",
    "parents": ["10e46f2dcbf4823578cf180f33ecf0b957964c47"],
    "phase": "draft",
    "removed": [],
    "rev": 4,
    "tags": [],
    "user": "person"
    "added": [],
    "bookmarks": [],
    "manifest": "cb5a1327723bada42f117e4c55a303246eaf9ccc",
    "node": "10e46f2dcbf4823578cf180f33ecf0b957964c47",
    "parents": ["97054abb4ab824450e9164180baf491ae0078465"],
    "phase": "draft",
    "removed": [],
    "rev": 3,
    "tags": [],
    "user": "person"
    "added": ["c"],
    "bookmarks": [],
    "manifest": "6e0e82995c35d0d57a52aca8da4e56139e06b4b1",
    "node": "97054abb4ab824450e9164180baf491ae0078465",
    "parents": ["b608e9d1a3f0273ccf70fb85fd6866b3482bf965"],
    "phase": "draft",
    "removed": [],
    "rev": 2,
    "tags": [],
    "user": "other@place"
    "added": ["b"],
    "branch": "default",
    "date": [1100000, 0],
    "desc": "other 1\nother 2\n\nother 3",
    "manifest": "4e8d705b1e53e3f9375e0e60dc7b525d8211fe55",
    "node": "b608e9d1a3f0273ccf70fb85fd6866b3482bf965",
    "parents": ["1e4e1b8f71e05681d422154f5421e385fec3454f"],
    "phase": "draft",
    "removed": [],
    "rev": 1,
    "tags": [],
    "user": "A. N. Other <other@place>"
    "added": ["a"],
    "bookmarks": [],
    "manifest": "a0c8bcbbb45c63b90b70ad007bf38961f64f2af0",
    "node": "1e4e1b8f71e05681d422154f5421e385fec3454f",
    "parents": ["0000000000000000000000000000000000000000"],
    "phase": "draft",
    "removed": [],
    "rev": 0,
    "tags": [],
    "user": "User Name <user@hostname>"
  $ cat << EOF > issue4758
  > changeset = '{changeset}\n'
  > EOF
  $ hg log --style ./issue4758
  $ cat << EOF > issue4758
  > changeset = '{files % changeset}\n'
  > EOF
  $ hg log --style ./issue4758
  >>> from __future__ import absolute_import
  >>> import datetime
  >>> fp = open('a', 'wb')
  >>> n = datetime.datetime.now() + datetime.timedelta(366 * 7)
  >>> fp.write(b'%d-%d-%d 00:00' % (n.year, n.month, n.day)) and None
Filename filters:

  $ hg debugtemplate '{"foo/bar"|basename}|{"foo/"|basename}|{"foo"|basename}|\n'
  bar||foo|
  $ hg debugtemplate '{"foo/bar"|dirname}|{"foo/"|dirname}|{"foo"|dirname}|\n'
  foo|foo||
  $ hg debugtemplate '{"foo/bar"|stripdir}|{"foo/"|stripdir}|{"foo"|stripdir}|\n'
  foo|foo|foo|

  $ hg log -l1 -T '{termwidth|count}\n'
  hg: parse error: not countable
  (template filter 'count' is not compatible with keyword 'termwidth')
  [255]

  1000000.00
  ({date
    ^ here)
  [255]
  $ hg log -T '{date(}'
  hg: parse error at 6: not a prefix: end
  ({date(}
         ^ here)
  [255]
  $ hg log -T '{date)}'
  hg: parse error at 5: invalid token
  ({date)}
        ^ here)
  [255]
  $ hg log -T '{date date}'
  hg: parse error at 6: invalid token
  ({date date}
         ^ here)
  [255]

  $ hg log -T '{}'
  hg: parse error at 1: not a prefix: end
  ({}
    ^ here)
  [255]
  $ hg debugtemplate -v '{()}'
  (template
    (group
      None))
  hg: parse error: missing argument
Behind the scenes, this would throw TypeError without intype=bytes
  &#48;&#46;&#48;&#48;
  &#48;&#46;&#48;&#48;
  &#49;&#53;&#55;&#55;&#56;&#55;&#50;&#56;&#54;&#48;&#46;&#48;&#48;
  hg: parse error: invalid date: 'Modify, add, remove, rename'
  (template filter 'shortdate' is not compatible with keyword 'desc')
Behind the scenes, this would throw AttributeError without intype=bytes
  line: 0.00
  line: 0.00
  line: 1577872860.00
  hg: parse error: invalid date: 'test'
  (template filter 'shortdate' is not compatible with keyword 'author')
  hg: parse error: invalid date: 'default'
  (incompatible use of template filter 'shortdate')
  ({"date
     ^ here)
  ({"foo{date|?}"}
              ^ here)
ui verbosity:

  $ hg log -l1 -T '{verbosity}\n'
  
  $ hg log -l1 -T '{verbosity}\n' --debug
  debug
  $ hg log -l1 -T '{verbosity}\n' --quiet
  quiet
  $ hg log -l1 -T '{verbosity}\n' --verbose
  verbose

  $ hg log -G --template '{rev}: {latesttag}+{latesttagdistance}\n'
  @    5: null+5
  |\
  | o  4: null+4
  | |
  | o  3: null+3
  | |
  o |  2: null+3
  |/
  o  1: null+2
  |
  o  0: null+1
  
One common tag: longest path wins for {latesttagdistance}:
  $ hg log -G --template '{rev}: {latesttag}+{latesttagdistance}\n'
  @  6: t1+4
  |
  o    5: t1+3
  |\
  | o  4: t1+2
  | |
  | o  3: t1+1
  | |
  o |  2: t1+1
  |/
  o  1: t1+0
  |
  o  0: null+1
  
One ancestor tag: closest wins:
  $ hg log -G --template '{rev}: {latesttag}+{latesttagdistance}\n'
  @  7: t2+3
  |
  o  6: t2+2
  |
  o    5: t2+1
  |\
  | o  4: t1+2
  | |
  | o  3: t1+1
  | |
  o |  2: t2+0
  |/
  o  1: t1+0
  |
  o  0: null+1
  

Two branch tags: more recent wins if same number of changes:
  $ hg log -G --template '{rev}: {latesttag}+{latesttagdistance}\n'
  @  8: t3+5
  |
  o  7: t3+4
  |
  o  6: t3+3
  |
  o    5: t3+2
  |\
  | o  4: t3+1
  | |
  | o  3: t3+0
  | |
  o |  2: t2+0
  |/
  o  1: t1+0
  |
  o  0: null+1
  

Two branch tags: fewest changes wins:

  $ hg tag -r 4 -m t4 -d '4 0' t4 # older than t2, but should not matter
  $ hg log -G --template "{rev}: {latesttag % '{tag}+{distance},{changes} '}\n"
  @  9: t4+5,6
  |
  o  8: t4+4,5
  |
  o  7: t4+3,4
  |
  o  6: t4+2,3
  |
  o    5: t4+1,2
  |\
  | o  4: t4+0,0
  | |
  | o  3: t3+0,0
  | |
  o |  2: t2+0,0
  |/
  o  1: t1+0,0
  |
  o  0: null+1,1
  
  $ hg log -G --template '{rev}: {latesttag}+{latesttagdistance}\n'
  @  11: t5+6
  |
  o  10: t5+5
  |
  o  9: t5+4
  |
  o  8: t5+3
  |
  o  7: t5+2
  |
  o  6: t5+1
  |
  o    5: t5+0
  |\
  | o  4: t4+0
  | |
  | o  3: at3:t3+0
  | |
  o |  2: t2+0
  |/
  o  1: t1+0
  |
  o  0: null+1
  

  $ hg log -G --template "{rev}: {latesttag % '{tag}+{distance},{changes} '}\n"
  @  11: t5+6,6
  |
  o  10: t5+5,5
  |
  o  9: t5+4,4
  |
  o  8: t5+3,3
  |
  o  7: t5+2,2
  |
  o  6: t5+1,1
  |
  o    5: t5+0,0
  |\
  | o  4: t4+0,0
  | |
  | o  3: at3+0,0 t3+0,0
  | |
  o |  2: t2+0,0
  |/
  o  1: t1+0,0
  |
  o  0: null+1,1
  

  $ hg log -G --template "{rev}: {latesttag('re:^t[13]$') % '{tag}, C: {changes}, D: {distance}'}\n"
  @  11: t3, C: 9, D: 8
  |
  o  10: t3, C: 8, D: 7
  |
  o  9: t3, C: 7, D: 6
  |
  o  8: t3, C: 6, D: 5
  |
  o  7: t3, C: 5, D: 4
  |
  o  6: t3, C: 4, D: 3
  |
  o    5: t3, C: 3, D: 2
  |\
  | o  4: t3, C: 1, D: 1
  | |
  | o  3: t3, C: 0, D: 0
  | |
  o |  2: t1, C: 1, D: 1
  |/
  o  1: t1, C: 0, D: 0
  |
  o  0: null, C: 1, D: 1
  
  test 11:97e5943b523a
  11,test
  hg: parse error: keyword 'rev' is not iterable of mappings
  hg: parse error: None is not iterable of mappings
  [255]
  $ hg log -R latesttag -r tip -T '{extras % "{key}\n" % "{key}\n"}'
  hg: parse error: list of strings is not mappable
  [255]

Test new-style inline templating of non-list/dict type:

  $ hg log -R latesttag -r tip -T '{manifest}\n'
  11:2bc6e9006ce2
  $ hg log -R latesttag -r tip -T 'string length: {manifest|count}\n'
  string length: 15
  $ hg log -R latesttag -r tip -T '{manifest % "{rev}:{node}"}\n'
  11:2bc6e9006ce29882383a22d39fd1f4e66dd3e2fc

  $ hg log -R latesttag -r tip -T '{get(extras, "branch") % "{key}: {value}\n"}'
  branch: default
  $ hg log -R latesttag -r tip -T '{get(extras, "unknown") % "{key}\n"}'
  hg: parse error: None is not iterable of mappings
  [255]
  $ hg log -R latesttag -r tip -T '{min(extras) % "{key}: {value}\n"}'
  branch: default
  $ hg log -R latesttag -l1 -T '{min(revset("0:9")) % "{rev}:{node|short}\n"}'
  0:ce3cec86e6c2
  $ hg log -R latesttag -l1 -T '{max(revset("0:9")) % "{rev}:{node|short}\n"}'
  9:fbc7cd862e9c

Test manifest/get() can be join()-ed as before, though it's silly:

  $ hg log -R latesttag -r tip -T '{join(manifest, "")}\n'
  11:2bc6e9006ce2
  $ hg log -R latesttag -r tip -T '{join(get(extras, "branch"), "")}\n'
  default

Test min/max of integers

  $ hg log -R latesttag -l1 -T '{min(revset("9:10"))}\n'
  9
  $ hg log -R latesttag -l1 -T '{max(revset("9:10"))}\n'
  10

Test min/max over map operation:

  $ hg log -R latesttag -r3 -T '{min(tags % "{tag}")}\n'
  at3
  $ hg log -R latesttag -r3 -T '{max(tags % "{tag}")}\n'
  t3

Test min/max of if() result

  $ cd latesttag
  $ hg log -l1 -T '{min(if(true, revset("9:10"), ""))}\n'
  9
  $ hg log -l1 -T '{max(if(false, "", revset("9:10")))}\n'
  10
  $ hg log -l1 -T '{min(ifcontains("a", "aa", revset("9:10"), ""))}\n'
  9
  $ hg log -l1 -T '{max(ifcontains("a", "bb", "", revset("9:10")))}\n'
  10
  $ hg log -l1 -T '{min(ifeq(0, 0, revset("9:10"), ""))}\n'
  9
  $ hg log -l1 -T '{max(ifeq(0, 1, "", revset("9:10")))}\n'
  10
  $ cd ..

Test laziness of if() then/else clause

  $ hg debugtemplate '{count(0)}'
  hg: parse error: not countable
  (incompatible use of template filter 'count')
  [255]
  $ hg debugtemplate '{if(true, "", count(0))}'
  $ hg debugtemplate '{if(false, count(0), "")}'
  $ hg debugtemplate '{ifcontains("a", "aa", "", count(0))}'
  $ hg debugtemplate '{ifcontains("a", "bb", count(0), "")}'
  $ hg debugtemplate '{ifeq(0, 0, "", count(0))}'
  $ hg debugtemplate '{ifeq(0, 1, count(0), "")}'

Test dot operator precedence:

  $ hg debugtemplate -R latesttag -r0 -v '{manifest.node|short}\n'
  (template
    (|
      (.
        (symbol 'manifest')
        (symbol 'node'))
      (symbol 'short'))
    (string '\n'))
  89f4071fec70

 (the following examples are invalid, but seem natural in parsing POV)

  $ hg debugtemplate -R latesttag -r0 -v '{foo|bar.baz}\n' 2> /dev/null
  (template
    (|
      (symbol 'foo')
      (.
        (symbol 'bar')
        (symbol 'baz')))
    (string '\n'))
  [255]
  $ hg debugtemplate -R latesttag -r0 -v '{foo.bar()}\n' 2> /dev/null
  (template
    (.
      (symbol 'foo')
      (func
        (symbol 'bar')
        None))
    (string '\n'))
  [255]

Test evaluation of dot operator:

  $ hg log -R latesttag -l1 -T '{min(revset("0:9")).node}\n'
  ce3cec86e6c26bd9bdfc590a6b92abc9680f1796
  $ hg log -R latesttag -r0 -T '{extras.branch}\n'
  default

  $ hg log -R latesttag -l1 -T '{author.invalid}\n'
  hg: parse error: keyword 'author' has no member
  [255]
  $ hg log -R latesttag -l1 -T '{min("abc").invalid}\n'
  hg: parse error: 'a' has no member
  t4
  4
  date: 70 01 01 04 +0000
      (integer '0'))
    (string '\n'))
      (integer '123'))
    (string '\n'))
        (integer '4')))
    (string '\n'))
  ({(-)}\n
      ^ here)
    (integer '1')
    (string '\n'))
      (symbol 'if')
        (string 't')
          (integer '1'))))
    (string '\n'))
      (integer '1')
      (symbol 'stringify'))
    (string '\n'))
    (string 'string with no template fragment')
    (string '\n'))
      (string 'template: ')
      (symbol 'rev'))
    (string '\n'))
    (string 'rawstring: {rev}')
    (string '\n'))
      (symbol 'files')
      (string 'rawstring: {file}'))
    (string '\n'))
  ({if(rev, "{if(rev, \")}")}\n
                        ^ here)
Test json filter applied to map result:

  $ hg log -r0 -T '{json(extras % "{key}")}\n'
  ["branch"]

  $ hg log -r 'wdir()' -T '{node|shortest}\n'
  ffff

  $ hg log --template '{shortest("f")}\n' -l1
  f

  $ hg log --template '{shortest("0123456789012345678901234567890123456789")}\n' -l1
  0123456789012345678901234567890123456789

  $ hg log --template '{shortest("01234567890123456789012345678901234567890123456789")}\n' -l1
  01234567890123456789012345678901234567890123456789

  $ hg log --template '{shortest("not a hex string")}\n' -l1
  not a hex string

  $ hg log --template '{shortest("not a hex string, but it'\''s 40 bytes long")}\n' -l1
  not a hex string, but it's 40 bytes long

  $ hg log --template '{shortest("ffffffffffffffffffffffffffffffffffffffff")}\n' -l1
  ffff

  $ hg log --template '{shortest("fffffff")}\n' -l1
  ffff

  $ hg log --template '{shortest("ff")}\n' -l1
  ffff

  > evolution.createmarkers=True
  obsoleted 1 changesets
  obsoleted 1 changesets
  obsoleted 1 changesets
  $ hg log -T '{ifcontains(desc, revset(":"), "", "type not match")}\n' -l1
  type not match

Invalid arguments passed to revset()

  $ hg log -T '{revset("%whatever", 0)}\n'
  hg: parse error: unexpected revspec format character w
  [255]
  $ hg log -T '{revset("%lwhatever", files)}\n'
  hg: parse error: unexpected revspec format character w
  [255]
  $ hg log -T '{revset("%s %s", 0)}\n'
  hg: parse error: missing argument for revspec
  [255]
  $ hg log -T '{revset("", 0)}\n'
  hg: parse error: too many revspec arguments specified
  [255]
  $ hg log -T '{revset("%s", 0, 1)}\n'
  hg: parse error: too many revspec arguments specified
  [255]
  $ hg log -T '{revset("%", 0)}\n'
  hg: parse error: incomplete revspec format character
  [255]
  $ hg log -T '{revset("%l", 0)}\n'
  hg: parse error: incomplete revspec format character
  [255]
  $ hg log -T '{revset("%d", 'foo')}\n'
  hg: parse error: invalid argument for revspec
  [255]
  $ hg log -T '{revset("%ld", files)}\n'
  hg: parse error: invalid argument for revspec
  [255]
  $ hg log -T '{revset("%ls", 0)}\n'
  hg: parse error: invalid argument for revspec
  [255]
  $ hg log -T '{revset("%b", 'foo')}\n'
  hg: parse error: invalid argument for revspec
  [255]
  $ hg log -T '{revset("%lb", files)}\n'
  hg: parse error: invalid argument for revspec
  [255]
  $ hg log -T '{revset("%r", 0)}\n'
  hg: parse error: invalid argument for revspec
  [255]

Test 'originalnode'

  $ hg log -r 1 -T '{revset("null") % "{node|short} {originalnode|short}"}\n'
  000000000000 bcc7ff960b8e
  $ hg log -r 0 -T '{manifest % "{node} {originalnode}"}\n'
  a0c8bcbbb45c63b90b70ad007bf38961f64f2af0 f7769ec2ab975ad19684098ad1ffd9b81ecc71a1

  $ hg --config extensions.revnamesext=$TESTDIR/revnamesext.py log -T '{rev}\n{namespaces % " {namespace} color={colorname} builtin={builtin}\n  {join(names, ",")}\n"}\n'
  2
   bookmarks color=bookmark builtin=True
    bar,foo
   tags color=tag builtin=True
    tip
   branches color=branch builtin=True
    text.{rev}
   revnames color=revname builtin=False
    r2
  
  1
   bookmarks color=bookmark builtin=True
    baz
   tags color=tag builtin=True
    
   branches color=branch builtin=True
    text.{rev}
   revnames color=revname builtin=False
    r1
  
  0
   bookmarks color=bookmark builtin=True
    
   tags color=tag builtin=True
    
   branches color=branch builtin=True
    default
   revnames color=revname builtin=False
    r0
  
  $ hg log -r2 -T '{namespaces.bookmarks % "{bookmark}\n"}'
  bar
  foo
  $ hg log -R a -r0 -T '{desc|splitlines}\n'
  line 1 line 2
  $ hg log -R a -r0 -T '{join(desc|splitlines, "|")}\n'
  line 1|line 2

  hg: parse error: invalid \x escape* (glob)
    (symbol 'rn')
    (string ' ')
        (symbol 'utcdate')
        (symbol 'date'))
      (symbol 'isodate'))
    (string '\n'))
      (symbol 'rev')
      (string ':')
        (symbol 'node')
        (symbol 'short')))
    (string ' ')
        (symbol 'localdate')
          (symbol 'date')
          (string 'UTC')))
      (symbol 'isodate'))
    (string '\n'))
      (symbol 'status')
        (string 'A')
        (symbol 'file_adds'))))
      (symbol 'file_adds')
        (string 'A')
        (string ' ')
        (symbol 'file')
        (string '\n'))))
        (symbol 'date')
        (symbol 'utcdate'))
      (symbol 'isodate'))
    (string '\n'))
        (symbol 'localdate')
          (symbol 'date')
          (string 'UTC')))
      (symbol 'isodate'))
    (string '\n'))
    (symbol 'bad'))
  $ $PYTHON <<EOF
  > open('latin1', 'wb').write(b'\xe9')
  > open('utf-8', 'wb').write(b'\xc3\xa9')
json filter should take input as utf-8 if it was converted from utf-8:

  $ HGENCODING=latin-1 hg log -T "{branch|json}\n" -r0
  "\u00e9"
  $ HGENCODING=latin-1 hg log -T "{desc|json}\n" -r0
  "non-ascii branch: \u00e9"

  $ hg log -T "coerced to string: {rev|utf8}\n" -r0
  coerced to string: 0
  > @templatefunc(b'custom()')
  >     return b'custom'

Test 'graphwidth' in 'hg log' on various topologies. The key here is that the
printed graphwidths 3, 5, 7, etc. should all line up in their respective
columns. We don't care about other aspects of the graph rendering here.

  $ hg init graphwidth
  $ cd graphwidth

  $ wrappabletext="a a a a a a a a a a a a"

  $ printf "first\n" > file
  $ hg add file
  $ hg commit -m "$wrappabletext"

  $ printf "first\nsecond\n" > file
  $ hg commit -m "$wrappabletext"

  $ hg checkout 0
  1 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ printf "third\nfirst\n" > file
  $ hg commit -m "$wrappabletext"
  created new head

  $ hg merge
  merging file
  0 files updated, 1 files merged, 0 files removed, 0 files unresolved
  (branch merge, don't forget to commit)

  $ hg log --graph -T "{graphwidth}"
  @  3
  |
  | @  5
  |/
  o  3
  
  $ hg commit -m "$wrappabletext"

  $ hg log --graph -T "{graphwidth}"
  @    5
  |\
  | o  5
  | |
  o |  5
  |/
  o  3
  

  $ hg checkout 0
  1 files updated, 0 files merged, 0 files removed, 0 files unresolved
  $ printf "third\nfirst\nsecond\n" > file
  $ hg commit -m "$wrappabletext"
  created new head

  $ hg log --graph -T "{graphwidth}"
  @  3
  |
  | o    7
  | |\
  +---o  7
  | |
  | o  5
  |/
  o  3
  

  $ hg log --graph -T "{graphwidth}" -r 3
  o    5
  |\
  ~ ~

  $ hg log --graph -T "{graphwidth}" -r 1
  o  3
  |
  ~

  $ hg merge
  1 files updated, 0 files merged, 0 files removed, 0 files unresolved
  (branch merge, don't forget to commit)
  $ hg commit -m "$wrappabletext"

  $ printf "seventh\n" >> file
  $ hg commit -m "$wrappabletext"

  $ hg log --graph -T "{graphwidth}"
  @  3
  |
  o    5
  |\
  | o  5
  | |
  o |    7
  |\ \
  | o |  7
  | |/
  o /  5
  |/
  o  3
  

The point of graphwidth is to allow wrapping that accounts for the space taken
by the graph.

  $ COLUMNS=10 hg log --graph -T "{fill(desc, termwidth - graphwidth)}"
  @  a a a a
  |  a a a a
  |  a a a a
  o    a a a
  |\   a a a
  | |  a a a
  | |  a a a
  | o  a a a
  | |  a a a
  | |  a a a
  | |  a a a
  o |    a a
  |\ \   a a
  | | |  a a
  | | |  a a
  | | |  a a
  | | |  a a
  | o |  a a
  | |/   a a
  | |    a a
  | |    a a
  | |    a a
  | |    a a
  o |  a a a
  |/   a a a
  |    a a a
  |    a a a
  o  a a a a
     a a a a
     a a a a

Something tricky happens when there are elided nodes; the next drawn row of
edges can be more than one column wider, but the graph width only increases by
one column. The remaining columns are added in between the nodes.

  $ hg log --graph -T "{graphwidth}" -r "0|2|4|5"
  o    5
  |\
  | \
  | :\
  o : :  7
  :/ /
  : o  5
  :/
  o  3
  

  $ cd ..
