#
# Copyright 21 May 2005 - (c) 2005 Jake Edge <jake@edge2.net>
# Copyright 2005-2007 Matt Mackall <mpm@selenic.com>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

from __future__ import absolute_import

import cgi

from .common import (
    HTTP_OK,
)

from .. import (
    util,
    wireproto,
)
stringio = util.stringio

urlerr = util.urlerr
urlreq = util.urlreq

HGTYPE = 'application/mercurial-0.1'
HGERRTYPE = 'application/hg-error'

class webproto(wireproto.abstractserverproto):
    def __init__(self, req, ui):
        self.req = req
        self.response = ''
        self.ui = ui
        self.name = 'http'

    def getargs(self, args):
        knownargs = self._args()
        data = {}
        keys = args.split()
        for k in keys:
            if k == '*':
                star = {}
                for key in knownargs.keys():
                    if key != 'cmd' and key not in keys:
                        star[key] = knownargs[key][0]
                data['*'] = star
            else:
                data[k] = knownargs[k][0]
        return [data[k] for k in keys]
    def _args(self):
        args = self.req.form.copy()
        postlen = int(self.req.env.get('HTTP_X_HGARGS_POST', 0))
        if postlen:
            args.update(cgi.parse_qs(
                self.req.read(postlen), keep_blank_values=True))
            return args
        chunks = []
        i = 1
        while True:
            h = self.req.env.get('HTTP_X_HGARG_' + str(i))
            if h is None:
                break
            chunks += [h]
            i += 1
        args.update(cgi.parse_qs(''.join(chunks), keep_blank_values=True))
        return args
    def getfile(self, fp):
        length = int(self.req.env['CONTENT_LENGTH'])
        for s in util.filechunkiter(self.req, limit=length):
            fp.write(s)
    def redirect(self):
        self.oldio = self.ui.fout, self.ui.ferr
        self.ui.ferr = self.ui.fout = stringio()
    def restore(self):
        val = self.ui.fout.getvalue()
        self.ui.ferr, self.ui.fout = self.oldio
        return val

    def compresschunks(self, chunks):
        # Don't allow untrusted settings because disabling compression or
        # setting a very high compression level could lead to flooding
        # the server's network or CPU.
        opts = {'level': self.ui.configint('server', 'zliblevel', -1)}
        return util.compengines['zlib'].compressstream(chunks, opts)

    def _client(self):
        return 'remote:%s:%s:%s' % (
            self.req.env.get('wsgi.url_scheme') or 'http',
            urlreq.quote(self.req.env.get('REMOTE_HOST', '')),
            urlreq.quote(self.req.env.get('REMOTE_USER', '')))

def iscmd(cmd):
    return cmd in wireproto.commands

def call(repo, req, cmd):
    p = webproto(req, repo.ui)
    rsp = wireproto.dispatch(repo, p, cmd)
    if isinstance(rsp, str):
        req.respond(HTTP_OK, HGTYPE, body=rsp)
        return []
    elif isinstance(rsp, wireproto.streamres):
        if rsp.reader:
            gen = iter(lambda: rsp.reader.read(32768), '')
        else:
            gen = rsp.gen

        if rsp.v1compressible:
            gen = p.compresschunks(gen)

        req.respond(HTTP_OK, HGTYPE)
        return gen
    elif isinstance(rsp, wireproto.pushres):
        val = p.restore()
        rsp = '%d\n%s' % (rsp.res, val)
        req.respond(HTTP_OK, HGTYPE, body=rsp)
        return []
    elif isinstance(rsp, wireproto.pusherr):
        # drain the incoming bundle
        req.drain()
        p.restore()
        rsp = '0\n%s\n' % rsp.res
        req.respond(HTTP_OK, HGTYPE, body=rsp)
        return []
    elif isinstance(rsp, wireproto.ooberror):
        rsp = rsp.message
        req.respond(HTTP_OK, HGERRTYPE, body=rsp)
        return []