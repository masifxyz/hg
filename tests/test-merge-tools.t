  $ hg init
  $ PATH="$BINDIR:/usr/sbin" $PYTHON "$BINDIR"/hg merge -r 2
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  $ PATH="`pwd`:$BINDIR:/usr/sbin" $PYTHON "$BINDIR"/hg merge -r 2
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  $ PATH="`pwd`:$BINDIR:/usr/sbin" $PYTHON "$BINDIR"/hg merge -r 2
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  couldn't find merge tool true specified for f
  couldn't find merge tool true specified for f
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  couldn't find merge tool true specified for f
  couldn't find merge tool true specified for f
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  no tool found to merge f
  keep (l)ocal [working copy], take (o)ther [merge rev], or leave (u)nresolved? u
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  no tool found to merge f
  keep (l)ocal [working copy], take (o)ther [merge rev], or leave (u)nresolved? u
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  no tool found to merge f
  keep (l)ocal [working copy], take (o)ther [merge rev], or leave (u)nresolved? 
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  no tool found to merge f
  keep (l)ocal [working copy], take (o)ther [merge rev], or leave (u)nresolved? 
  no tool found to merge f
  keep (l)ocal [working copy], take (o)ther [merge rev], or leave (u)nresolved? 
  no tool found to merge f
  keep (l)ocal [working copy], take (o)ther [merge rev], or leave (u)nresolved? u
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
#if symlink
internal merge cannot handle symlinks and shouldn't try:
  use 'hg resolve' to retry unresolved file merges or 'hg update -C .' to abandon
#endif

  */f~base.?????? $TESTTMP/f.txt.orig */f~other.??????.txt $TESTTMP/f.txt (glob)