# templatekw.py - common changeset template keywords
#
# Copyright 2005-2009 Matt Mackall <mpm@selenic.com>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

from __future__ import absolute_import

from .i18n import _
from .node import (
    hex,
    nullid,
)

from . import (
    encoding,
    error,
    hbisect,
    i18n,
    obsutil,
    patch,
    pycompat,
    registrar,
    scmutil,
    util,
)

class _hybrid(object):
    """Wrapper for list or dict to support legacy template

    This class allows us to handle both:
    - "{files}" (legacy command-line-specific list hack) and
    - "{files % '{file}\n'}" (hgweb-style with inlining and function support)
    and to access raw values:
    - "{ifcontains(file, files, ...)}", "{ifcontains(key, extras, ...)}"
    - "{get(extras, key)}"
    - "{files|json}"
    """

    def __init__(self, gen, values, makemap, joinfmt, keytype=None):
        if gen is not None:
            self.gen = gen  # generator or function returning generator
        self._values = values
        self._makemap = makemap
        self.joinfmt = joinfmt
        self.keytype = keytype  # hint for 'x in y' where type(x) is unresolved
    def gen(self):
        """Default generator to stringify this as {join(self, ' ')}"""
        for i, x in enumerate(self._values):
            if i > 0:
                yield ' '
            yield self.joinfmt(x)
    def itermaps(self):
        makemap = self._makemap
        for x in self._values:
            yield makemap(x)
    def __contains__(self, x):
        return x in self._values
    def __getitem__(self, key):
        return self._values[key]
    def __len__(self):
        return len(self._values)
    def __iter__(self):
        return iter(self._values)
    def __getattr__(self, name):
        if name not in (r'get', r'items', r'iteritems', r'iterkeys',
                        r'itervalues', r'keys', r'values'):
            raise AttributeError(name)
        return getattr(self._values, name)

class _mappable(object):
    """Wrapper for non-list/dict object to support map operation

    This class allows us to handle both:
    - "{manifest}"
    - "{manifest % '{rev}:{node}'}"
    - "{manifest.rev}"

    Unlike a _hybrid, this does not simulate the behavior of the underling
    value. Use unwrapvalue() or unwraphybrid() to obtain the inner object.
    """

    def __init__(self, gen, key, value, makemap):
        if gen is not None:
            self.gen = gen  # generator or function returning generator
        self._key = key
        self._value = value  # may be generator of strings
        self._makemap = makemap

    def gen(self):
        yield pycompat.bytestr(self._value)

    def tomap(self):
        return self._makemap(self._key)

    def itermaps(self):
        yield self.tomap()

def hybriddict(data, key='key', value='value', fmt=None, gen=None):
    """Wrap data to support both dict-like and string-like operations"""
    if fmt is None:
        fmt = '%s=%s'
    return _hybrid(gen, data, lambda k: {key: k, value: data[k]},
                   lambda k: fmt % (k, data[k]))

def hybridlist(data, name, fmt=None, gen=None):
    """Wrap data to support both list-like and string-like operations"""
    if fmt is None:
        fmt = '%s'
    return _hybrid(gen, data, lambda x: {name: x}, lambda x: fmt % x)

def unwraphybrid(thing):
    """Return an object which can be stringified possibly by using a legacy
    template"""
    gen = getattr(thing, 'gen', None)
    if gen is None:
        return thing
    if callable(gen):
        return gen()
    return gen

def unwrapvalue(thing):
    """Move the inner value object out of the wrapper"""
    if not util.safehasattr(thing, '_value'):
        return thing
    return thing._value

def wraphybridvalue(container, key, value):
    """Wrap an element of hybrid container to be mappable

    The key is passed to the makemap function of the given container, which
    should be an item generated by iter(container).
    """
    makemap = getattr(container, '_makemap', None)
    if makemap is None:
        return value
    if util.safehasattr(value, '_makemap'):
        # a nested hybrid list/dict, which has its own way of map operation
        return value
    return _mappable(None, key, value, makemap)

def compatdict(context, mapping, name, data, key='key', value='value',
               fmt=None, plural=None, separator=' '):
    """Wrap data like hybriddict(), but also supports old-style list template

    This exists for backward compatibility with the old-style template. Use
    hybriddict() for new template keywords.
    """
    c = [{key: k, value: v} for k, v in data.iteritems()]
    t = context.resource(mapping, 'templ')
    f = _showlist(name, c, t, mapping, plural, separator)
    return hybriddict(data, key=key, value=value, fmt=fmt, gen=f)

def compatlist(context, mapping, name, data, element=None, fmt=None,
               plural=None, separator=' '):
    """Wrap data like hybridlist(), but also supports old-style list template

    This exists for backward compatibility with the old-style template. Use
    hybridlist() for new template keywords.
    """
    t = context.resource(mapping, 'templ')
    f = _showlist(name, data, t, mapping, plural, separator)
    return hybridlist(data, name=element or name, fmt=fmt, gen=f)

def showdict(name, data, mapping, plural=None, key='key', value='value',
             fmt=None, separator=' '):
    ui = mapping.get('ui')
    if ui:
        ui.deprecwarn("templatekw.showdict() is deprecated, use compatdict()",
                      '4.6')
    c = [{key: k, value: v} for k, v in data.iteritems()]
    f = _showlist(name, c, mapping['templ'], mapping, plural, separator)
    return hybriddict(data, key=key, value=value, fmt=fmt, gen=f)

def showlist(name, values, mapping, plural=None, element=None, separator=' '):
    ui = mapping.get('ui')
    if ui:
        ui.deprecwarn("templatekw.showlist() is deprecated, use compatlist()",
                      '4.6')
    if not element:
        element = name
    f = _showlist(name, values, mapping['templ'], mapping, plural, separator)
    return hybridlist(values, name=element, gen=f)

def _showlist(name, values, templ, mapping, plural=None, separator=' '):
    '''expand set of values.
    name is name of key in template map.
    values is list of strings or dicts.
    plural is plural of name, if not simply name + 's'.
    separator is used to join values as a string

    expansion works like this, given name 'foo'.

    if values is empty, expand 'no_foos'.

    if 'foo' not in template map, return values as a string,
    joined by 'separator'.

    expand 'start_foos'.

    for each value, expand 'foo'. if 'last_foo' in template
    map, expand it instead of 'foo' for last key.

    expand 'end_foos'.
    '''
    strmapping = pycompat.strkwargs(mapping)
    if not plural:
        plural = name + 's'
    if not values:
        noname = 'no_' + plural
        if noname in templ:
            yield templ(noname, **strmapping)
        return
    if name not in templ:
        if isinstance(values[0], bytes):
            yield separator.join(values)
        else:
            for v in values:
                r = dict(v)
                r.update(mapping)
                yield r
        return
    startname = 'start_' + plural
    if startname in templ:
        yield templ(startname, **strmapping)
    vmapping = mapping.copy()
    def one(v, tag=name):
        try:
            vmapping.update(v)
        # Python 2 raises ValueError if the type of v is wrong. Python
        # 3 raises TypeError.
        except (AttributeError, TypeError, ValueError):
            try:
                # Python 2 raises ValueError trying to destructure an e.g.
                # bytes. Python 3 raises TypeError.
                for a, b in v:
                    vmapping[a] = b
            except (TypeError, ValueError):
                vmapping[name] = v
        return templ(tag, **pycompat.strkwargs(vmapping))
    lastname = 'last_' + name
    if lastname in templ:
        last = values.pop()
    else:
        last = None
    for v in values:
        yield one(v)
    if last is not None:
        yield one(last, tag=lastname)
    endname = 'end_' + plural
    if endname in templ:
        yield templ(endname, **strmapping)

def getlatesttags(context, mapping, pattern=None):
    '''return date, distance and name for the latest tag of rev'''
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    cache = context.resource(mapping, 'cache')

    cachename = 'latesttags'
    if pattern is not None:
        cachename += '-' + pattern
        match = util.stringmatcher(pattern)[2]
    else:
        match = util.always

    if cachename not in cache:
        # Cache mapping from rev to a tuple with tag date, tag
        # distance and tag name
        cache[cachename] = {-1: (0, 0, ['null'])}
    latesttags = cache[cachename]

    rev = ctx.rev()
    todo = [rev]
    while todo:
        rev = todo.pop()
        if rev in latesttags:
            continue
        ctx = repo[rev]
        tags = [t for t in ctx.tags()
                if (repo.tagtype(t) and repo.tagtype(t) != 'local'
                    and match(t))]
        if tags:
            latesttags[rev] = ctx.date()[0], 0, [t for t in sorted(tags)]
            continue
        try:
            ptags = [latesttags[p.rev()] for p in ctx.parents()]
            if len(ptags) > 1:
                if ptags[0][2] == ptags[1][2]:
                    # The tuples are laid out so the right one can be found by
                    # comparison in this case.
                    pdate, pdist, ptag = max(ptags)
                else:
                    def key(x):
                        changessincetag = len(repo.revs('only(%d, %s)',
                                                        ctx.rev(), x[2][0]))
                        # Smallest number of changes since tag wins. Date is
                        # used as tiebreaker.
                        return [-changessincetag, x[0]]
                    pdate, pdist, ptag = max(ptags, key=key)
            else:
                pdate, pdist, ptag = ptags[0]
        except KeyError:
            # Cache miss - recurse
            todo.append(rev)
            todo.extend(p.rev() for p in ctx.parents())
            continue
        latesttags[rev] = pdate, pdist + 1, ptag
    return latesttags[rev]

def getrenamedfn(repo, endrev=None):
    rcache = {}
    if endrev is None:
        endrev = len(repo)

    def getrenamed(fn, rev):
        '''looks up all renames for a file (up to endrev) the first
        time the file is given. It indexes on the changerev and only
        parses the manifest if linkrev != changerev.
        Returns rename info for fn at changerev rev.'''
        if fn not in rcache:
            rcache[fn] = {}
            fl = repo.file(fn)
            for i in fl:
                lr = fl.linkrev(i)
                renamed = fl.renamed(fl.node(i))
                rcache[fn][lr] = renamed
                if lr >= endrev:
                    break
        if rev in rcache[fn]:
            return rcache[fn][rev]

        # If linkrev != rev (i.e. rev not found in rcache) fallback to
        # filectx logic.
        try:
            return repo[rev][fn].renamed()
        except error.LookupError:
            return None

    return getrenamed

def getlogcolumns():
    """Return a dict of log column labels"""
    _ = pycompat.identity  # temporarily disable gettext
    # i18n: column positioning for "hg log"
    columns = _('bookmark:    %s\n'
                'branch:      %s\n'
                'changeset:   %s\n'
                'copies:      %s\n'
                'date:        %s\n'
                'extra:       %s=%s\n'
                'files+:      %s\n'
                'files-:      %s\n'
                'files:       %s\n'
                'instability: %s\n'
                'manifest:    %s\n'
                'obsolete:    %s\n'
                'parent:      %s\n'
                'phase:       %s\n'
                'summary:     %s\n'
                'tag:         %s\n'
                'user:        %s\n')
    return dict(zip([s.split(':', 1)[0] for s in columns.splitlines()],
                    i18n._(columns).splitlines(True)))

# default templates internally used for rendering of lists
defaulttempl = {
    'parent': '{rev}:{node|formatnode} ',
    'manifest': '{rev}:{node|formatnode}',
    'file_copy': '{name} ({source})',
    'envvar': '{key}={value}',
    'extra': '{key}={value|stringescape}'
}
# filecopy is preserved for compatibility reasons
defaulttempl['filecopy'] = defaulttempl['file_copy']

# keywords are callables (see registrar.templatekeyword for details)
keywords = {}
templatekeyword = registrar.templatekeyword(keywords)

@templatekeyword('author', requires={'ctx'})
def showauthor(context, mapping):
    """String. The unmodified author of the changeset."""
    ctx = context.resource(mapping, 'ctx')
    return ctx.user()

@templatekeyword('bisect', requires={'repo', 'ctx'})
def showbisect(context, mapping):
    """String. The changeset bisection status."""
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    return hbisect.label(repo, ctx.node())

@templatekeyword('branch', requires={'ctx'})
def showbranch(context, mapping):
    """String. The name of the branch on which the changeset was
    committed.
    """
    ctx = context.resource(mapping, 'ctx')
    return ctx.branch()

@templatekeyword('branches', requires={'ctx', 'templ'})
def showbranches(context, mapping):
    """List of strings. The name of the branch on which the
    changeset was committed. Will be empty if the branch name was
    default. (DEPRECATED)
    """
    ctx = context.resource(mapping, 'ctx')
    branch = ctx.branch()
    if branch != 'default':
        return compatlist(context, mapping, 'branch', [branch],
                          plural='branches')
    return compatlist(context, mapping, 'branch', [], plural='branches')

@templatekeyword('bookmarks', requires={'repo', 'ctx', 'templ'})
def showbookmarks(context, mapping):
    """List of strings. Any bookmarks associated with the
    changeset. Also sets 'active', the name of the active bookmark.
    """
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    templ = context.resource(mapping, 'templ')
    bookmarks = ctx.bookmarks()
    active = repo._activebookmark
    makemap = lambda v: {'bookmark': v, 'active': active, 'current': active}
    f = _showlist('bookmark', bookmarks, templ, mapping)
    return _hybrid(f, bookmarks, makemap, pycompat.identity)

@templatekeyword('children', requires={'ctx', 'templ'})
def showchildren(context, mapping):
    """List of strings. The children of the changeset."""
    ctx = context.resource(mapping, 'ctx')
    childrevs = ['%d:%s' % (cctx.rev(), cctx) for cctx in ctx.children()]
    return compatlist(context, mapping, 'children', childrevs, element='child')

# Deprecated, but kept alive for help generation a purpose.
@templatekeyword('currentbookmark', requires={'repo', 'ctx'})
def showcurrentbookmark(context, mapping):
    """String. The active bookmark, if it is associated with the changeset.
    (DEPRECATED)"""
    return showactivebookmark(context, mapping)

@templatekeyword('activebookmark', requires={'repo', 'ctx'})
def showactivebookmark(context, mapping):
    """String. The active bookmark, if it is associated with the changeset."""
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    active = repo._activebookmark
    if active and active in ctx.bookmarks():
        return active
    return ''

@templatekeyword('date', requires={'ctx'})
def showdate(context, mapping):
    """Date information. The date when the changeset was committed."""
    ctx = context.resource(mapping, 'ctx')
    return ctx.date()

@templatekeyword('desc', requires={'ctx'})
def showdescription(context, mapping):
    """String. The text of the changeset description."""
    ctx = context.resource(mapping, 'ctx')
    s = ctx.description()
    if isinstance(s, encoding.localstr):
        # try hard to preserve utf-8 bytes
        return encoding.tolocal(encoding.fromlocal(s).strip())
    else:
        return s.strip()

@templatekeyword('diffstat', requires={'ctx'})
def showdiffstat(context, mapping):
    """String. Statistics of changes with the following format:
    "modified files: +added/-removed lines"
    """
    ctx = context.resource(mapping, 'ctx')
    stats = patch.diffstatdata(util.iterlines(ctx.diff(noprefix=False)))
    maxname, maxtotal, adds, removes, binary = patch.diffstatsum(stats)
    return '%d: +%d/-%d' % (len(stats), adds, removes)

@templatekeyword('envvars', requires={'ui', 'templ'})
def showenvvars(context, mapping):
    """A dictionary of environment variables. (EXPERIMENTAL)"""
    ui = context.resource(mapping, 'ui')
    env = ui.exportableenviron()
    env = util.sortdict((k, env[k]) for k in sorted(env))
    return compatdict(context, mapping, 'envvar', env, plural='envvars')

@templatekeyword('extras', requires={'ctx', 'templ'})
def showextras(context, mapping):
    """List of dicts with key, value entries of the 'extras'
    field of this changeset."""
    ctx = context.resource(mapping, 'ctx')
    templ = context.resource(mapping, 'templ')
    extras = ctx.extra()
    extras = util.sortdict((k, extras[k]) for k in sorted(extras))
    makemap = lambda k: {'key': k, 'value': extras[k]}
    c = [makemap(k) for k in extras]
    f = _showlist('extra', c, templ, mapping, plural='extras')
    return _hybrid(f, extras, makemap,
                   lambda k: '%s=%s' % (k, util.escapestr(extras[k])))

def _showfilesbystat(context, mapping, name, index):
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    revcache = context.resource(mapping, 'revcache')
    if 'files' not in revcache:
        revcache['files'] = repo.status(ctx.p1(), ctx)[:3]
    files = revcache['files'][index]
    return compatlist(context, mapping, name, files, element='file')

@templatekeyword('file_adds', requires={'repo', 'ctx', 'revcache', 'templ'})
def showfileadds(context, mapping):
    """List of strings. Files added by this changeset."""
    return _showfilesbystat(context, mapping, 'file_add', 1)

@templatekeyword('file_copies',
                 requires={'repo', 'ctx', 'cache', 'revcache', 'templ'})
def showfilecopies(context, mapping):
    """List of strings. Files copied in this changeset with
    their sources.
    """
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    cache = context.resource(mapping, 'cache')
    copies = context.resource(mapping, 'revcache').get('copies')
    if copies is None:
        if 'getrenamed' not in cache:
            cache['getrenamed'] = getrenamedfn(repo)
        copies = []
        getrenamed = cache['getrenamed']
        for fn in ctx.files():
            rename = getrenamed(fn, ctx.rev())
            if rename:
                copies.append((fn, rename[0]))

    copies = util.sortdict(copies)
    return compatdict(context, mapping, 'file_copy', copies,
                      key='name', value='source', fmt='%s (%s)',
                      plural='file_copies')

# showfilecopiesswitch() displays file copies only if copy records are
# provided before calling the templater, usually with a --copies
# command line switch.
@templatekeyword('file_copies_switch', requires={'revcache', 'templ'})
def showfilecopiesswitch(context, mapping):
    """List of strings. Like "file_copies" but displayed
    only if the --copied switch is set.
    """
    copies = context.resource(mapping, 'revcache').get('copies') or []
    copies = util.sortdict(copies)
    return compatdict(context, mapping, 'file_copy', copies,
                      key='name', value='source', fmt='%s (%s)',
                      plural='file_copies')

@templatekeyword('file_dels', requires={'repo', 'ctx', 'revcache', 'templ'})
def showfiledels(context, mapping):
    """List of strings. Files removed by this changeset."""
    return _showfilesbystat(context, mapping, 'file_del', 2)

@templatekeyword('file_mods', requires={'repo', 'ctx', 'revcache', 'templ'})
def showfilemods(context, mapping):
    """List of strings. Files modified by this changeset."""
    return _showfilesbystat(context, mapping, 'file_mod', 0)

@templatekeyword('files', requires={'ctx', 'templ'})
def showfiles(context, mapping):
    """List of strings. All files modified, added, or removed by this
    changeset.
    """
    ctx = context.resource(mapping, 'ctx')
    return compatlist(context, mapping, 'file', ctx.files())

@templatekeyword('graphnode', requires={'repo', 'ctx'})
def showgraphnode(context, mapping):
    """String. The character representing the changeset node in an ASCII
    revision graph."""
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    return getgraphnode(repo, ctx)

def getgraphnode(repo, ctx):
    wpnodes = repo.dirstate.parents()
    if wpnodes[1] == nullid:
        wpnodes = wpnodes[:1]
    if ctx.node() in wpnodes:
        return '@'
    elif ctx.obsolete():
        return 'x'
    elif ctx.isunstable():
        return '*'
    elif ctx.closesbranch():
        return '_'
    else:
        return 'o'

@templatekeyword('graphwidth', requires=())
def showgraphwidth(context, mapping):
    """Integer. The width of the graph drawn by 'log --graph' or zero."""
    # just hosts documentation; should be overridden by template mapping
    return 0

@templatekeyword('index', requires=())
def showindex(context, mapping):
    """Integer. The current iteration of the loop. (0 indexed)"""
    # just hosts documentation; should be overridden by template mapping
    raise error.Abort(_("can't use index in this context"))

@templatekeyword('latesttag', requires={'repo', 'ctx', 'cache', 'templ'})
def showlatesttag(context, mapping):
    """List of strings. The global tags on the most recent globally
    tagged ancestor of this changeset.  If no such tags exist, the list
    consists of the single string "null".
    """
    return showlatesttags(context, mapping, None)

def showlatesttags(context, mapping, pattern):
    """helper method for the latesttag keyword and function"""
    latesttags = getlatesttags(context, mapping, pattern)

    # latesttag[0] is an implementation detail for sorting csets on different
    # branches in a stable manner- it is the date the tagged cset was created,
    # not the date the tag was created.  Therefore it isn't made visible here.
    makemap = lambda v: {
        'changes': _showchangessincetag,
        'distance': latesttags[1],
        'latesttag': v,   # BC with {latesttag % '{latesttag}'}
        'tag': v
    }

    tags = latesttags[2]
    templ = context.resource(mapping, 'templ')
    f = _showlist('latesttag', tags, templ, mapping, separator=':')
    return _hybrid(f, tags, makemap, pycompat.identity)

@templatekeyword('latesttagdistance', requires={'repo', 'ctx', 'cache'})
def showlatesttagdistance(context, mapping):
    """Integer. Longest path to the latest tag."""
    return getlatesttags(context, mapping)[1]

@templatekeyword('changessincelatesttag', requires={'repo', 'ctx', 'cache'})
def showchangessincelatesttag(context, mapping):
    """Integer. All ancestors not in the latest tag."""
    mapping = mapping.copy()
    mapping['tag'] = getlatesttags(context, mapping)[2][0]
    return _showchangessincetag(context, mapping)

def _showchangessincetag(context, mapping):
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    offset = 0
    revs = [ctx.rev()]
    tag = context.symbol(mapping, 'tag')

    # The only() revset doesn't currently support wdir()
    if ctx.rev() is None:
        offset = 1
        revs = [p.rev() for p in ctx.parents()]

    return len(repo.revs('only(%ld, %s)', revs, tag)) + offset

# teach templater latesttags.changes is switched to (context, mapping) API
_showchangessincetag._requires = {'repo', 'ctx'}

@templatekeyword('manifest', requires={'repo', 'ctx', 'templ'})
def showmanifest(context, mapping):
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    templ = context.resource(mapping, 'templ')
    mnode = ctx.manifestnode()
    if mnode is None:
        # just avoid crash, we might want to use the 'ff...' hash in future
        return
    mrev = repo.manifestlog._revlog.rev(mnode)
    mhex = hex(mnode)
    mapping = mapping.copy()
    mapping.update({'rev': mrev, 'node': mhex})
    f = templ('manifest', **pycompat.strkwargs(mapping))
    # TODO: perhaps 'ctx' should be dropped from mapping because manifest
    # rev and node are completely different from changeset's.
    return _mappable(f, None, f, lambda x: {'rev': mrev, 'node': mhex})

@templatekeyword('obsfate', requires={'ui', 'repo', 'ctx', 'templ'})
def showobsfate(context, mapping):
    # this function returns a list containing pre-formatted obsfate strings.
    #
    # This function will be replaced by templates fragments when we will have
    # the verbosity templatekw available.
    succsandmarkers = showsuccsandmarkers(context, mapping)

    ui = context.resource(mapping, 'ui')
    values = []

    for x in succsandmarkers:
        values.append(obsutil.obsfateprinter(x['successors'], x['markers'], ui))

    return compatlist(context, mapping, "fate", values)

def shownames(context, mapping, namespace):
    """helper method to generate a template keyword for a namespace"""
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    ns = repo.names[namespace]
    names = ns.names(repo, ctx.node())
    return compatlist(context, mapping, ns.templatename, names,
                      plural=namespace)

@templatekeyword('namespaces', requires={'repo', 'ctx', 'templ'})
def shownamespaces(context, mapping):
    """Dict of lists. Names attached to this changeset per
    namespace."""
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    templ = context.resource(mapping, 'templ')

    namespaces = util.sortdict()
    def makensmapfn(ns):
        # 'name' for iterating over namespaces, templatename for local reference
        return lambda v: {'name': v, ns.templatename: v}

    for k, ns in repo.names.iteritems():
        names = ns.names(repo, ctx.node())
        f = _showlist('name', names, templ, mapping)
        namespaces[k] = _hybrid(f, names, makensmapfn(ns), pycompat.identity)

    f = _showlist('namespace', list(namespaces), templ, mapping)

    def makemap(ns):
        return {
            'namespace': ns,
            'names': namespaces[ns],
            'builtin': repo.names[ns].builtin,
            'colorname': repo.names[ns].colorname,
        }

    return _hybrid(f, namespaces, makemap, pycompat.identity)

@templatekeyword('node', requires={'ctx'})
def shownode(context, mapping):
    """String. The changeset identification hash, as a 40 hexadecimal
    digit string.
    """
    ctx = context.resource(mapping, 'ctx')
    return ctx.hex()

@templatekeyword('obsolete', requires={'ctx'})
def showobsolete(context, mapping):
    """String. Whether the changeset is obsolete. (EXPERIMENTAL)"""
    ctx = context.resource(mapping, 'ctx')
    if ctx.obsolete():
        return 'obsolete'
    return ''

@templatekeyword('peerurls', requires={'repo'})
def showpeerurls(context, mapping):
    """A dictionary of repository locations defined in the [paths] section
    of your configuration file."""
    repo = context.resource(mapping, 'repo')
    # see commands.paths() for naming of dictionary keys
    paths = repo.ui.paths
    urls = util.sortdict((k, p.rawloc) for k, p in sorted(paths.iteritems()))
    def makemap(k):
        p = paths[k]
        d = {'name': k, 'url': p.rawloc}
        d.update((o, v) for o, v in sorted(p.suboptions.iteritems()))
        return d
    return _hybrid(None, urls, makemap, lambda k: '%s=%s' % (k, urls[k]))

@templatekeyword("predecessors", requires={'repo', 'ctx'})
def showpredecessors(context, mapping):
    """Returns the list if the closest visible successors. (EXPERIMENTAL)"""
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    predecessors = sorted(obsutil.closestpredecessors(repo, ctx.node()))
    predecessors = map(hex, predecessors)

    return _hybrid(None, predecessors,
                   lambda x: {'ctx': repo[x], 'revcache': {}},
                   lambda x: scmutil.formatchangeid(repo[x]))

@templatekeyword('reporoot', requires={'repo'})
def showreporoot(context, mapping):
    """String. The root directory of the current repository."""
    repo = context.resource(mapping, 'repo')
    return repo.root

@templatekeyword("successorssets", requires={'repo', 'ctx'})
def showsuccessorssets(context, mapping):
    """Returns a string of sets of successors for a changectx. Format used
    is: [ctx1, ctx2], [ctx3] if ctx has been splitted into ctx1 and ctx2
    while also diverged into ctx3. (EXPERIMENTAL)"""
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    if not ctx.obsolete():
        return ''

    ssets = obsutil.successorssets(repo, ctx.node(), closest=True)
    ssets = [[hex(n) for n in ss] for ss in ssets]

    data = []
    for ss in ssets:
        h = _hybrid(None, ss, lambda x: {'ctx': repo[x], 'revcache': {}},
                    lambda x: scmutil.formatchangeid(repo[x]))
        data.append(h)

    # Format the successorssets
    def render(d):
        t = []
        for i in d.gen():
            t.append(i)
        return "".join(t)

    def gen(data):
        yield "; ".join(render(d) for d in data)

    return _hybrid(gen(data), data, lambda x: {'successorset': x},
                   pycompat.identity)

@templatekeyword("succsandmarkers", requires={'repo', 'ctx', 'templ'})
def showsuccsandmarkers(context, mapping):
    """Returns a list of dict for each final successor of ctx. The dict
    contains successors node id in "successors" keys and the list of
    obs-markers from ctx to the set of successors in "markers".
    (EXPERIMENTAL)
    """
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    templ = context.resource(mapping, 'templ')

    values = obsutil.successorsandmarkers(repo, ctx)

    if values is None:
        values = []

    # Format successors and markers to avoid exposing binary to templates
    data = []
    for i in values:
        # Format successors
        successors = i['successors']

        successors = [hex(n) for n in successors]
        successors = _hybrid(None, successors,
                             lambda x: {'ctx': repo[x], 'revcache': {}},
                             lambda x: scmutil.formatchangeid(repo[x]))

        # Format markers
        finalmarkers = []
        for m in i['markers']:
            hexprec = hex(m[0])
            hexsucs = tuple(hex(n) for n in m[1])
            hexparents = None
            if m[5] is not None:
                hexparents = tuple(hex(n) for n in m[5])
            newmarker = (hexprec, hexsucs) + m[2:5] + (hexparents,) + m[6:]
            finalmarkers.append(newmarker)

        data.append({'successors': successors, 'markers': finalmarkers})

    f = _showlist('succsandmarkers', data, templ, mapping)
    return _hybrid(f, data, lambda x: x, pycompat.identity)

@templatekeyword('p1rev', requires={'ctx'})
def showp1rev(context, mapping):
    """Integer. The repository-local revision number of the changeset's
    first parent, or -1 if the changeset has no parents."""
    ctx = context.resource(mapping, 'ctx')
    return ctx.p1().rev()

@templatekeyword('p2rev', requires={'ctx'})
def showp2rev(context, mapping):
    """Integer. The repository-local revision number of the changeset's
    second parent, or -1 if the changeset has no second parent."""
    ctx = context.resource(mapping, 'ctx')
    return ctx.p2().rev()

@templatekeyword('p1node', requires={'ctx'})
def showp1node(context, mapping):
    """String. The identification hash of the changeset's first parent,
    as a 40 digit hexadecimal string. If the changeset has no parents, all
    digits are 0."""
    ctx = context.resource(mapping, 'ctx')
    return ctx.p1().hex()

@templatekeyword('p2node', requires={'ctx'})
def showp2node(context, mapping):
    """String. The identification hash of the changeset's second
    parent, as a 40 digit hexadecimal string. If the changeset has no second
    parent, all digits are 0."""
    ctx = context.resource(mapping, 'ctx')
    return ctx.p2().hex()

@templatekeyword('parents', requires={'repo', 'ctx', 'templ'})
def showparents(context, mapping):
    """List of strings. The parents of the changeset in "rev:node"
    format. If the changeset has only one "natural" parent (the predecessor
    revision) nothing is shown."""
    repo = context.resource(mapping, 'repo')
    ctx = context.resource(mapping, 'ctx')
    templ = context.resource(mapping, 'templ')
    pctxs = scmutil.meaningfulparents(repo, ctx)
    prevs = [p.rev() for p in pctxs]
    parents = [[('rev', p.rev()),
                ('node', p.hex()),
                ('phase', p.phasestr())]
               for p in pctxs]
    f = _showlist('parent', parents, templ, mapping)
    return _hybrid(f, prevs, lambda x: {'ctx': repo[x], 'revcache': {}},
                   lambda x: scmutil.formatchangeid(repo[x]), keytype=int)

@templatekeyword('phase', requires={'ctx'})
def showphase(context, mapping):
    """String. The changeset phase name."""
    ctx = context.resource(mapping, 'ctx')
    return ctx.phasestr()

@templatekeyword('phaseidx', requires={'ctx'})
def showphaseidx(context, mapping):
    """Integer. The changeset phase index. (ADVANCED)"""
    ctx = context.resource(mapping, 'ctx')
    return ctx.phase()

@templatekeyword('rev', requires={'ctx'})
def showrev(context, mapping):
    """Integer. The repository-local changeset revision number."""
    ctx = context.resource(mapping, 'ctx')
    return scmutil.intrev(ctx)

def showrevslist(context, mapping, name, revs):
    """helper to generate a list of revisions in which a mapped template will
    be evaluated"""
    repo = context.resource(mapping, 'repo')
    templ = context.resource(mapping, 'templ')
    f = _showlist(name, ['%d' % r for r in revs], templ, mapping)
    return _hybrid(f, revs,
                   lambda x: {name: x, 'ctx': repo[x], 'revcache': {}},
                   pycompat.identity, keytype=int)

@templatekeyword('subrepos', requires={'ctx', 'templ'})
def showsubrepos(context, mapping):
    """List of strings. Updated subrepositories in the changeset."""
    ctx = context.resource(mapping, 'ctx')
    substate = ctx.substate
    if not substate:
        return compatlist(context, mapping, 'subrepo', [])
    psubstate = ctx.parents()[0].substate or {}
    subrepos = []
    for sub in substate:
        if sub not in psubstate or substate[sub] != psubstate[sub]:
            subrepos.append(sub) # modified or newly added in ctx
    for sub in psubstate:
        if sub not in substate:
            subrepos.append(sub) # removed in ctx
    return compatlist(context, mapping, 'subrepo', sorted(subrepos))

# don't remove "showtags" definition, even though namespaces will put
# a helper function for "tags" keyword into "keywords" map automatically,
# because online help text is built without namespaces initialization
@templatekeyword('tags', requires={'repo', 'ctx', 'templ'})
def showtags(context, mapping):
    """List of strings. Any tags associated with the changeset."""
    return shownames(context, mapping, 'tags')

@templatekeyword('termwidth', requires={'ui'})
def showtermwidth(context, mapping):
    """Integer. The width of the current terminal."""
    ui = context.resource(mapping, 'ui')
    return ui.termwidth()

@templatekeyword('instabilities', requires={'ctx', 'templ'})
def showinstabilities(context, mapping):
    """List of strings. Evolution instabilities affecting the changeset.
    (EXPERIMENTAL)
    """
    ctx = context.resource(mapping, 'ctx')
    return compatlist(context, mapping, 'instability', ctx.instabilities(),
                      plural='instabilities')

@templatekeyword('verbosity', requires={'ui'})
def showverbosity(context, mapping):
    """String. The current output verbosity in 'debug', 'quiet', 'verbose',
    or ''."""
    ui = context.resource(mapping, 'ui')
    # see logcmdutil.changesettemplater for priority of these flags
    if ui.debugflag:
        return 'debug'
    elif ui.quiet:
        return 'quiet'
    elif ui.verbose:
        return 'verbose'
    return ''

def loadkeyword(ui, extname, registrarobj):
    """Load template keyword from specified registrarobj
    """
    for name, func in registrarobj._table.iteritems():
        keywords[name] = func

# tell hggettext to extract docstrings from these functions:
i18nfunctions = keywords.values()
