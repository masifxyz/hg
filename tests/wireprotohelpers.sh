HTTPV2=exp-http-v2-0001
MEDIATYPE=application/mercurial-exp-framing-0003

sendhttpraw() {
  hg --verbose debugwireproto --peer raw http://$LOCALIP:$HGPORT/
}

sendhttpv2peer() {
  hg --verbose debugwireproto --nologhandshake --peer http2 http://$LOCALIP:$HGPORT/
}

sendhttpv2peerhandshake() {
  hg --verbose debugwireproto --peer http2 http://$LOCALIP:$HGPORT/
}

cat > dummycommands.py << EOF
from mercurial import (
    wireprototypes,
    wireproto,
)

@wireproto.wireprotocommand('customreadonly', permission='pull')
def customreadonlyv1(repo, proto):
    return wireprototypes.bytesresponse(b'customreadonly bytes response')

@wireproto.wireprotocommand('customreadonly', permission='pull',
                            transportpolicy=wireproto.POLICY_V2_ONLY)
def customreadonlyv2(repo, proto):
    return wireprototypes.bytesresponse(b'customreadonly bytes response')

@wireproto.wireprotocommand('customreadwrite', permission='push')
def customreadwrite(repo, proto):
    return wireprototypes.bytesresponse(b'customreadwrite bytes response')

@wireproto.wireprotocommand('customreadwrite', permission='push',
                            transportpolicy=wireproto.POLICY_V2_ONLY)
def customreadwritev2(repo, proto):
    return wireprototypes.bytesresponse(b'customreadwrite bytes response')
EOF

cat >> $HGRCPATH << EOF
[extensions]
drawdag = $TESTDIR/drawdag.py
EOF

enabledummycommands() {
  cat >> $HGRCPATH << EOF
[extensions]
dummycommands = $TESTTMP/dummycommands.py
EOF
}

enablehttpv2() {
  cat >> $1/.hg/hgrc << EOF
[experimental]
web.apiserver = true
web.api.http-v2 = true
EOF
}
