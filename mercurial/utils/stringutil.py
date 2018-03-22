# stringutil.py - utility for generic string formatting, parsing, etc.
#
#  Copyright 2005 K. Thananchayan <thananck@yahoo.com>
#  Copyright 2005-2007 Matt Mackall <mpm@selenic.com>
#  Copyright 2006 Vadim Gelfer <vadim.gelfer@gmail.com>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

from __future__ import absolute_import

import codecs
import re as remod
import textwrap

from ..i18n import _

from .. import (
    encoding,
    error,
    pycompat,
)

_DATA_ESCAPE_MAP = {pycompat.bytechr(i): br'\x%02x' % i for i in range(256)}
_DATA_ESCAPE_MAP.update({
    b'\\': b'\\\\',
    b'\r': br'\r',
    b'\n': br'\n',
})
_DATA_ESCAPE_RE = remod.compile(br'[\x00-\x08\x0a-\x1f\\\x7f-\xff]')

def escapedata(s):
    if isinstance(s, bytearray):
        s = bytes(s)

    return _DATA_ESCAPE_RE.sub(lambda m: _DATA_ESCAPE_MAP[m.group(0)], s)

def binary(s):
    """return true if a string is binary data"""
    return bool(s and '\0' in s)

def stringmatcher(pattern, casesensitive=True):
    """
    accepts a string, possibly starting with 're:' or 'literal:' prefix.
    returns the matcher name, pattern, and matcher function.
    missing or unknown prefixes are treated as literal matches.

    helper for tests:
    >>> def test(pattern, *tests):
    ...     kind, pattern, matcher = stringmatcher(pattern)
    ...     return (kind, pattern, [bool(matcher(t)) for t in tests])
    >>> def itest(pattern, *tests):
    ...     kind, pattern, matcher = stringmatcher(pattern, casesensitive=False)
    ...     return (kind, pattern, [bool(matcher(t)) for t in tests])

    exact matching (no prefix):
    >>> test(b'abcdefg', b'abc', b'def', b'abcdefg')
    ('literal', 'abcdefg', [False, False, True])

    regex matching ('re:' prefix)
    >>> test(b're:a.+b', b'nomatch', b'fooadef', b'fooadefbar')
    ('re', 'a.+b', [False, False, True])

    force exact matches ('literal:' prefix)
    >>> test(b'literal:re:foobar', b'foobar', b're:foobar')
    ('literal', 're:foobar', [False, True])

    unknown prefixes are ignored and treated as literals
    >>> test(b'foo:bar', b'foo', b'bar', b'foo:bar')
    ('literal', 'foo:bar', [False, False, True])

    case insensitive regex matches
    >>> itest(b're:A.+b', b'nomatch', b'fooadef', b'fooadefBar')
    ('re', 'A.+b', [False, False, True])

    case insensitive literal matches
    >>> itest(b'ABCDEFG', b'abc', b'def', b'abcdefg')
    ('literal', 'ABCDEFG', [False, False, True])
    """
    if pattern.startswith('re:'):
        pattern = pattern[3:]
        try:
            flags = 0
            if not casesensitive:
                flags = remod.I
            regex = remod.compile(pattern, flags)
        except remod.error as e:
            raise error.ParseError(_('invalid regular expression: %s')
                                   % e)
        return 're', pattern, regex.search
    elif pattern.startswith('literal:'):
        pattern = pattern[8:]

    match = pattern.__eq__

    if not casesensitive:
        ipat = encoding.lower(pattern)
        match = lambda s: ipat == encoding.lower(s)
    return 'literal', pattern, match

def shortuser(user):
    """Return a short representation of a user name or email address."""
    f = user.find('@')
    if f >= 0:
        user = user[:f]
    f = user.find('<')
    if f >= 0:
        user = user[f + 1:]
    f = user.find(' ')
    if f >= 0:
        user = user[:f]
    f = user.find('.')
    if f >= 0:
        user = user[:f]
    return user

def emailuser(user):
    """Return the user portion of an email address."""
    f = user.find('@')
    if f >= 0:
        user = user[:f]
    f = user.find('<')
    if f >= 0:
        user = user[f + 1:]
    return user

def email(author):
    '''get email of author.'''
    r = author.find('>')
    if r == -1:
        r = None
    return author[author.find('<') + 1:r]

def ellipsis(text, maxlength=400):
    """Trim string to at most maxlength (default: 400) columns in display."""
    return encoding.trim(text, maxlength, ellipsis='...')

def escapestr(s):
    # call underlying function of s.encode('string_escape') directly for
    # Python 3 compatibility
    return codecs.escape_encode(s)[0]

def unescapestr(s):
    return codecs.escape_decode(s)[0]

def forcebytestr(obj):
    """Portably format an arbitrary object (e.g. exception) into a byte
    string."""
    try:
        return pycompat.bytestr(obj)
    except UnicodeEncodeError:
        # non-ascii string, may be lossy
        return pycompat.bytestr(encoding.strtolocal(str(obj)))

def uirepr(s):
    # Avoid double backslash in Windows path repr()
    return pycompat.byterepr(pycompat.bytestr(s)).replace(b'\\\\', b'\\')

# delay import of textwrap
def _MBTextWrapper(**kwargs):
    class tw(textwrap.TextWrapper):
        """
        Extend TextWrapper for width-awareness.

        Neither number of 'bytes' in any encoding nor 'characters' is
        appropriate to calculate terminal columns for specified string.

        Original TextWrapper implementation uses built-in 'len()' directly,
        so overriding is needed to use width information of each characters.

        In addition, characters classified into 'ambiguous' width are
        treated as wide in East Asian area, but as narrow in other.

        This requires use decision to determine width of such characters.
        """
        def _cutdown(self, ucstr, space_left):
            l = 0
            colwidth = encoding.ucolwidth
            for i in xrange(len(ucstr)):
                l += colwidth(ucstr[i])
                if space_left < l:
                    return (ucstr[:i], ucstr[i:])
            return ucstr, ''

        # overriding of base class
        def _handle_long_word(self, reversed_chunks, cur_line, cur_len, width):
            space_left = max(width - cur_len, 1)

            if self.break_long_words:
                cut, res = self._cutdown(reversed_chunks[-1], space_left)
                cur_line.append(cut)
                reversed_chunks[-1] = res
            elif not cur_line:
                cur_line.append(reversed_chunks.pop())

        # this overriding code is imported from TextWrapper of Python 2.6
        # to calculate columns of string by 'encoding.ucolwidth()'
        def _wrap_chunks(self, chunks):
            colwidth = encoding.ucolwidth

            lines = []
            if self.width <= 0:
                raise ValueError("invalid width %r (must be > 0)" % self.width)

            # Arrange in reverse order so items can be efficiently popped
            # from a stack of chucks.
            chunks.reverse()

            while chunks:

                # Start the list of chunks that will make up the current line.
                # cur_len is just the length of all the chunks in cur_line.
                cur_line = []
                cur_len = 0

                # Figure out which static string will prefix this line.
                if lines:
                    indent = self.subsequent_indent
                else:
                    indent = self.initial_indent

                # Maximum width for this line.
                width = self.width - len(indent)

                # First chunk on line is whitespace -- drop it, unless this
                # is the very beginning of the text (i.e. no lines started yet).
                if self.drop_whitespace and chunks[-1].strip() == r'' and lines:
                    del chunks[-1]

                while chunks:
                    l = colwidth(chunks[-1])

                    # Can at least squeeze this chunk onto the current line.
                    if cur_len + l <= width:
                        cur_line.append(chunks.pop())
                        cur_len += l

                    # Nope, this line is full.
                    else:
                        break

                # The current line is full, and the next chunk is too big to
                # fit on *any* line (not just this one).
                if chunks and colwidth(chunks[-1]) > width:
                    self._handle_long_word(chunks, cur_line, cur_len, width)

                # If the last chunk on this line is all whitespace, drop it.
                if (self.drop_whitespace and
                    cur_line and cur_line[-1].strip() == r''):
                    del cur_line[-1]

                # Convert current line back to a string and store it in list
                # of all lines (return value).
                if cur_line:
                    lines.append(indent + r''.join(cur_line))

            return lines

    global _MBTextWrapper
    _MBTextWrapper = tw
    return tw(**kwargs)

def wrap(line, width, initindent='', hangindent=''):
    maxindent = max(len(hangindent), len(initindent))
    if width <= maxindent:
        # adjust for weird terminal size
        width = max(78, maxindent + 1)
    line = line.decode(pycompat.sysstr(encoding.encoding),
                       pycompat.sysstr(encoding.encodingmode))
    initindent = initindent.decode(pycompat.sysstr(encoding.encoding),
                                   pycompat.sysstr(encoding.encodingmode))
    hangindent = hangindent.decode(pycompat.sysstr(encoding.encoding),
                                   pycompat.sysstr(encoding.encodingmode))
    wrapper = _MBTextWrapper(width=width,
                             initial_indent=initindent,
                             subsequent_indent=hangindent)
    return wrapper.fill(line).encode(pycompat.sysstr(encoding.encoding))

_booleans = {'1': True, 'yes': True, 'true': True, 'on': True, 'always': True,
             '0': False, 'no': False, 'false': False, 'off': False,
             'never': False}

def parsebool(s):
    """Parse s into a boolean.

    If s is not a valid boolean, returns None.
    """
    return _booleans.get(s.lower(), None)
