from __future__ import absolute_import, print_function

from mercurial import (
    error,
    pycompat,
    ui as uimod,
    util,
    wireproto,
    wireprototypes,
)
stringio = util.stringio

class proto(object):
    def __init__(self, args):
        self.args = args
        self.name = 'dummyproto'

    def getargs(self, spec):
        args = self.args
        args.setdefault(b'*', {})
        names = spec.split()
        return [args[n] for n in names]

    def checkperm(self, perm):
        pass

wireprototypes.TRANSPORTS['dummyproto'] = {
    'transport': 'dummy',
    'version': 1,
}

class clientpeer(wireproto.wirepeer):
    def __init__(self, serverrepo, ui):
        self.serverrepo = serverrepo
        self.ui = ui

    def url(self):
        return b'test'

    def local(self):
        return None

    def peer(self):
        return self

    def canpush(self):
        return True

    def close(self):
        pass

    def capabilities(self):
        return [b'batch']

    def _call(self, cmd, **args):
        args = pycompat.byteskwargs(args)
        res = wireproto.dispatch(self.serverrepo, proto(args), cmd)
        if isinstance(res, wireprototypes.bytesresponse):
            return res.data
        elif isinstance(res, bytes):
            return res
        else:
            raise error.Abort('dummy client does not support response type')

    def _callstream(self, cmd, **args):
        return stringio(self._call(cmd, **args))

    @wireproto.batchable
    def greet(self, name):
        f = wireproto.future()
        yield {b'name': mangle(name)}, f
        yield unmangle(f.value)

class serverrepo(object):
    def greet(self, name):
        return b"Hello, " + name

    def filtered(self, name):
        return self

def mangle(s):
    return b''.join(pycompat.bytechr(ord(c) + 1) for c in pycompat.bytestr(s))
def unmangle(s):
    return b''.join(pycompat.bytechr(ord(c) - 1) for c in pycompat.bytestr(s))

def greet(repo, proto, name):
    return mangle(repo.greet(unmangle(name)))

wireproto.commands[b'greet'] = (greet, b'name',)

srv = serverrepo()
clt = clientpeer(srv, uimod.ui())

print(clt.greet(b"Foobar"))
b = clt.iterbatch()
list(map(b.greet, (b'Fo, =;:<o', b'Bar')))
b.submit()
print([r for r in b.results()])
