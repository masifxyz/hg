  $ . $TESTDIR/wireprotohelpers.sh

  $ hg init server
  $ enablehttpv2 server
  $ cd server
  $ echo a0 > a
  $ echo b0 > b

  $ hg -q commit -A -m 'commit 0'

  $ echo a1 > a
  $ echo b1 > b
  $ hg commit -m 'commit 1'
  $ echo b2 > b
  $ hg commit -m 'commit 2'

  $ hg -q up -r 0
  $ echo a2 > a
  $ hg commit -m 'commit 3'
  created new head

  $ hg log -G -T '{rev}:{node} {desc}\n'
  @  3:eae5f82c2e622368d27daecb76b7e393d0f24211 commit 3
  |
  | o  2:0bb8ad894a15b15380b2a2a5b183e20f2a4b28dd commit 2
  | |
  | o  1:7592917e1c3e82677cb0a4bc715ca25dd12d28c1 commit 1
  |/
  o  0:3390ef850073fbc2f0dfff2244342c8e9229013a commit 0
  

  $ hg serve -p $HGPORT -d --pid-file hg.pid -E error.log
  $ cat hg.pid > $DAEMON_PIDS

No arguments is an invalid request

  $ sendhttpv2peer << EOF
  > command changesetdata
  > EOF
  creating http peer for wire protocol version 2
  sending changesetdata command
  s>     POST /api/exp-http-v2-0001/ro/changesetdata HTTP/1.1\r\n
  s>     Accept-Encoding: identity\r\n
  s>     accept: application/mercurial-exp-framing-0005\r\n
  s>     content-type: application/mercurial-exp-framing-0005\r\n
  s>     content-length: 28\r\n
  s>     host: $LOCALIP:$HGPORT\r\n (glob)
  s>     user-agent: Mercurial debugwireproto\r\n
  s>     \r\n
  s>     \x14\x00\x00\x01\x00\x01\x01\x11\xa1DnameMchangesetdata
  s> makefile('rb', None)
  s>     HTTP/1.1 200 OK\r\n
  s>     Server: testing stub value\r\n
  s>     Date: $HTTP_DATE$\r\n
  s>     Content-Type: application/mercurial-exp-framing-0005\r\n
  s>     Transfer-Encoding: chunked\r\n
  s>     \r\n
  s>     49\r\n
  s>     A\x00\x00\x01\x00\x02\x012
  s>     \xa2Eerror\xa1GmessageX"noderange or nodes must be definedFstatusEerror
  s>     \r\n
  received frame(size=65; request=1; stream=2; streamflags=stream-begin; type=command-response; flags=eos)
  s>     0\r\n
  s>     \r\n
  abort: noderange or nodes must be defined!
  [255]

Empty noderange heads results in an error

  $ sendhttpv2peer << EOF
  > command changesetdata
  >     noderange eval:[[],[]]
  > EOF
  creating http peer for wire protocol version 2
  sending changesetdata command
  s>     POST /api/exp-http-v2-0001/ro/changesetdata HTTP/1.1\r\n
  s>     Accept-Encoding: identity\r\n
  s>     accept: application/mercurial-exp-framing-0005\r\n
  s>     content-type: application/mercurial-exp-framing-0005\r\n
  s>     content-length: 47\r\n
  s>     host: $LOCALIP:$HGPORT\r\n (glob)
  s>     user-agent: Mercurial debugwireproto\r\n
  s>     \r\n
  s>     \'\x00\x00\x01\x00\x01\x01\x11\xa2Dargs\xa1Inoderange\x82\x80\x80DnameMchangesetdata
  s> makefile('rb', None)
  s>     HTTP/1.1 200 OK\r\n
  s>     Server: testing stub value\r\n
  s>     Date: $HTTP_DATE$\r\n
  s>     Content-Type: application/mercurial-exp-framing-0005\r\n
  s>     Transfer-Encoding: chunked\r\n
  s>     \r\n
  s>     51\r\n
  s>     I\x00\x00\x01\x00\x02\x012
  s>     \xa2Eerror\xa1GmessageX*heads in noderange request cannot be emptyFstatusEerror
  s>     \r\n
  received frame(size=73; request=1; stream=2; streamflags=stream-begin; type=command-response; flags=eos)
  s>     0\r\n
  s>     \r\n
  abort: heads in noderange request cannot be empty!
  [255]

Sending just noderange heads sends all revisions

  $ sendhttpv2peer << EOF
  > command changesetdata
  >     noderange eval:[[], [b'\x0b\xb8\xad\x89\x4a\x15\xb1\x53\x80\xb2\xa2\xa5\xb1\x83\xe2\x0f\x2a\x4b\x28\xdd', b'\xea\xe5\xf8\x2c\x2e\x62\x23\x68\xd2\x7d\xae\xcb\x76\xb7\xe3\x93\xd0\xf2\x42\x11']]
  > EOF
  creating http peer for wire protocol version 2
  sending changesetdata command
  s>     POST /api/exp-http-v2-0001/ro/changesetdata HTTP/1.1\r\n
  s>     Accept-Encoding: identity\r\n
  s>     accept: application/mercurial-exp-framing-0005\r\n
  s>     content-type: application/mercurial-exp-framing-0005\r\n
  s>     content-length: 89\r\n
  s>     host: $LOCALIP:$HGPORT\r\n (glob)
  s>     user-agent: Mercurial debugwireproto\r\n
  s>     \r\n
  s>     Q\x00\x00\x01\x00\x01\x01\x11\xa2Dargs\xa1Inoderange\x82\x80\x82T\x0b\xb8\xad\x89J\x15\xb1S\x80\xb2\xa2\xa5\xb1\x83\xe2\x0f*K(\xddT\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11DnameMchangesetdata
  s> makefile('rb', None)
  s>     HTTP/1.1 200 OK\r\n
  s>     Server: testing stub value\r\n
  s>     Date: $HTTP_DATE$\r\n
  s>     Content-Type: application/mercurial-exp-framing-0005\r\n
  s>     Transfer-Encoding: chunked\r\n
  s>     \r\n
  s>     13\r\n
  s>     \x0b\x00\x00\x01\x00\x02\x011
  s>     \xa1FstatusBok
  s>     \r\n
  received frame(size=11; request=1; stream=2; streamflags=stream-begin; type=command-response; flags=continuation)
  s>     81\r\n
  s>     y\x00\x00\x01\x00\x02\x001
  s>     \xa1Jtotalitems\x04\xa1DnodeT3\x90\xef\x85\x00s\xfb\xc2\xf0\xdf\xff"D4,\x8e\x92)\x01:\xa1DnodeTu\x92\x91~\x1c>\x82g|\xb0\xa4\xbcq\\\xa2]\xd1-(\xc1\xa1DnodeT\x0b\xb8\xad\x89J\x15\xb1S\x80\xb2\xa2\xa5\xb1\x83\xe2\x0f*K(\xdd\xa1DnodeT\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11
  s>     \r\n
  received frame(size=121; request=1; stream=2; streamflags=; type=command-response; flags=continuation)
  s>     8\r\n
  s>     \x00\x00\x00\x01\x00\x02\x002
  s>     \r\n
  s>     0\r\n
  s>     \r\n
  received frame(size=0; request=1; stream=2; streamflags=; type=command-response; flags=eos)
  response: gen[
    {
      b'totalitems': 4
    },
    {
      b'node': b'3\x90\xef\x85\x00s\xfb\xc2\xf0\xdf\xff"D4,\x8e\x92)\x01:'
    },
    {
      b'node': b'u\x92\x91~\x1c>\x82g|\xb0\xa4\xbcq\\\xa2]\xd1-(\xc1'
    },
    {
      b'node': b'\x0b\xb8\xad\x89J\x15\xb1S\x80\xb2\xa2\xa5\xb1\x83\xe2\x0f*K(\xdd'
    },
    {
      b'node': b'\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11'
    }
  ]

Sending root nodes limits what data is sent

  $ sendhttpv2peer << EOF
  > command changesetdata
  >     noderange eval:[[b'\x33\x90\xef\x85\x00\x73\xfb\xc2\xf0\xdf\xff\x22\x44\x34\x2c\x8e\x92\x29\x01\x3a'], [b'\x0b\xb8\xad\x89\x4a\x15\xb1\x53\x80\xb2\xa2\xa5\xb1\x83\xe2\x0f\x2a\x4b\x28\xdd']]
  > EOF
  creating http peer for wire protocol version 2
  sending changesetdata command
  s>     POST /api/exp-http-v2-0001/ro/changesetdata HTTP/1.1\r\n
  s>     Accept-Encoding: identity\r\n
  s>     accept: application/mercurial-exp-framing-0005\r\n
  s>     content-type: application/mercurial-exp-framing-0005\r\n
  s>     content-length: 89\r\n
  s>     host: $LOCALIP:$HGPORT\r\n (glob)
  s>     user-agent: Mercurial debugwireproto\r\n
  s>     \r\n
  s>     Q\x00\x00\x01\x00\x01\x01\x11\xa2Dargs\xa1Inoderange\x82\x81T3\x90\xef\x85\x00s\xfb\xc2\xf0\xdf\xff"D4,\x8e\x92)\x01:\x81T\x0b\xb8\xad\x89J\x15\xb1S\x80\xb2\xa2\xa5\xb1\x83\xe2\x0f*K(\xddDnameMchangesetdata
  s> makefile('rb', None)
  s>     HTTP/1.1 200 OK\r\n
  s>     Server: testing stub value\r\n
  s>     Date: $HTTP_DATE$\r\n
  s>     Content-Type: application/mercurial-exp-framing-0005\r\n
  s>     Transfer-Encoding: chunked\r\n
  s>     \r\n
  s>     13\r\n
  s>     \x0b\x00\x00\x01\x00\x02\x011
  s>     \xa1FstatusBok
  s>     \r\n
  received frame(size=11; request=1; stream=2; streamflags=stream-begin; type=command-response; flags=continuation)
  s>     4b\r\n
  s>     C\x00\x00\x01\x00\x02\x001
  s>     \xa1Jtotalitems\x02\xa1DnodeTu\x92\x91~\x1c>\x82g|\xb0\xa4\xbcq\\\xa2]\xd1-(\xc1\xa1DnodeT\x0b\xb8\xad\x89J\x15\xb1S\x80\xb2\xa2\xa5\xb1\x83\xe2\x0f*K(\xdd
  s>     \r\n
  received frame(size=67; request=1; stream=2; streamflags=; type=command-response; flags=continuation)
  s>     8\r\n
  s>     \x00\x00\x00\x01\x00\x02\x002
  s>     \r\n
  s>     0\r\n
  s>     \r\n
  received frame(size=0; request=1; stream=2; streamflags=; type=command-response; flags=eos)
  response: gen[
    {
      b'totalitems': 2
    },
    {
      b'node': b'u\x92\x91~\x1c>\x82g|\xb0\xa4\xbcq\\\xa2]\xd1-(\xc1'
    },
    {
      b'node': b'\x0b\xb8\xad\x89J\x15\xb1S\x80\xb2\xa2\xa5\xb1\x83\xe2\x0f*K(\xdd'
    }
  ]

Requesting data on a single node by node works

  $ sendhttpv2peer << EOF
  > command changesetdata
  >     nodes eval:[b'\x33\x90\xef\x85\x00\x73\xfb\xc2\xf0\xdf\xff\x22\x44\x34\x2c\x8e\x92\x29\x01\x3a']
  > EOF
  creating http peer for wire protocol version 2
  sending changesetdata command
  s>     POST /api/exp-http-v2-0001/ro/changesetdata HTTP/1.1\r\n
  s>     Accept-Encoding: identity\r\n
  s>     accept: application/mercurial-exp-framing-0005\r\n
  s>     content-type: application/mercurial-exp-framing-0005\r\n
  s>     content-length: 62\r\n
  s>     host: $LOCALIP:$HGPORT\r\n (glob)
  s>     user-agent: Mercurial debugwireproto\r\n
  s>     \r\n
  s>     6\x00\x00\x01\x00\x01\x01\x11\xa2Dargs\xa1Enodes\x81T3\x90\xef\x85\x00s\xfb\xc2\xf0\xdf\xff"D4,\x8e\x92)\x01:DnameMchangesetdata
  s> makefile('rb', None)
  s>     HTTP/1.1 200 OK\r\n
  s>     Server: testing stub value\r\n
  s>     Date: $HTTP_DATE$\r\n
  s>     Content-Type: application/mercurial-exp-framing-0005\r\n
  s>     Transfer-Encoding: chunked\r\n
  s>     \r\n
  s>     13\r\n
  s>     \x0b\x00\x00\x01\x00\x02\x011
  s>     \xa1FstatusBok
  s>     \r\n
  received frame(size=11; request=1; stream=2; streamflags=stream-begin; type=command-response; flags=continuation)
  s>     30\r\n
  s>     (\x00\x00\x01\x00\x02\x001
  s>     \xa1Jtotalitems\x01\xa1DnodeT3\x90\xef\x85\x00s\xfb\xc2\xf0\xdf\xff"D4,\x8e\x92)\x01:
  s>     \r\n
  received frame(size=40; request=1; stream=2; streamflags=; type=command-response; flags=continuation)
  s>     8\r\n
  s>     \x00\x00\x00\x01\x00\x02\x002
  s>     \r\n
  s>     0\r\n
  s>     \r\n
  received frame(size=0; request=1; stream=2; streamflags=; type=command-response; flags=eos)
  response: gen[
    {
      b'totalitems': 1
    },
    {
      b'node': b'3\x90\xef\x85\x00s\xfb\xc2\xf0\xdf\xff"D4,\x8e\x92)\x01:'
    }
  ]

Specifying a noderange and nodes takes union

  $ sendhttpv2peer << EOF
  > command changesetdata
  >     noderange eval:[[b'\x75\x92\x91\x7e\x1c\x3e\x82\x67\x7c\xb0\xa4\xbc\x71\x5c\xa2\x5d\xd1\x2d\x28\xc1'], [b'\x0b\xb8\xad\x89\x4a\x15\xb1\x53\x80\xb2\xa2\xa5\xb1\x83\xe2\x0f\x2a\x4b\x28\xdd']]
  >     nodes eval:[b'\xea\xe5\xf8\x2c\x2e\x62\x23\x68\xd2\x7d\xae\xcb\x76\xb7\xe3\x93\xd0\xf2\x42\x11']
  > EOF
  creating http peer for wire protocol version 2
  sending changesetdata command
  s>     POST /api/exp-http-v2-0001/ro/changesetdata HTTP/1.1\r\n
  s>     Accept-Encoding: identity\r\n
  s>     accept: application/mercurial-exp-framing-0005\r\n
  s>     content-type: application/mercurial-exp-framing-0005\r\n
  s>     content-length: 117\r\n
  s>     host: $LOCALIP:$HGPORT\r\n (glob)
  s>     user-agent: Mercurial debugwireproto\r\n
  s>     \r\n
  s>     m\x00\x00\x01\x00\x01\x01\x11\xa2Dargs\xa2Inoderange\x82\x81Tu\x92\x91~\x1c>\x82g|\xb0\xa4\xbcq\\\xa2]\xd1-(\xc1\x81T\x0b\xb8\xad\x89J\x15\xb1S\x80\xb2\xa2\xa5\xb1\x83\xe2\x0f*K(\xddEnodes\x81T\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11DnameMchangesetdata
  s> makefile('rb', None)
  s>     HTTP/1.1 200 OK\r\n
  s>     Server: testing stub value\r\n
  s>     Date: $HTTP_DATE$\r\n
  s>     Content-Type: application/mercurial-exp-framing-0005\r\n
  s>     Transfer-Encoding: chunked\r\n
  s>     \r\n
  s>     13\r\n
  s>     \x0b\x00\x00\x01\x00\x02\x011
  s>     \xa1FstatusBok
  s>     \r\n
  received frame(size=11; request=1; stream=2; streamflags=stream-begin; type=command-response; flags=continuation)
  s>     4b\r\n
  s>     C\x00\x00\x01\x00\x02\x001
  s>     \xa1Jtotalitems\x02\xa1DnodeT\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11\xa1DnodeT\x0b\xb8\xad\x89J\x15\xb1S\x80\xb2\xa2\xa5\xb1\x83\xe2\x0f*K(\xdd
  s>     \r\n
  received frame(size=67; request=1; stream=2; streamflags=; type=command-response; flags=continuation)
  s>     8\r\n
  s>     \x00\x00\x00\x01\x00\x02\x002
  s>     \r\n
  s>     0\r\n
  s>     \r\n
  received frame(size=0; request=1; stream=2; streamflags=; type=command-response; flags=eos)
  response: gen[
    {
      b'totalitems': 2
    },
    {
      b'node': b'\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11'
    },
    {
      b'node': b'\x0b\xb8\xad\x89J\x15\xb1S\x80\xb2\xa2\xa5\xb1\x83\xe2\x0f*K(\xdd'
    }
  ]

Parents data is transferred upon request

  $ sendhttpv2peer << EOF
  > command changesetdata
  >     fields eval:[b'parents']
  >     nodes eval:[b'\xea\xe5\xf8\x2c\x2e\x62\x23\x68\xd2\x7d\xae\xcb\x76\xb7\xe3\x93\xd0\xf2\x42\x11']
  > EOF
  creating http peer for wire protocol version 2
  sending changesetdata command
  s>     POST /api/exp-http-v2-0001/ro/changesetdata HTTP/1.1\r\n
  s>     Accept-Encoding: identity\r\n
  s>     accept: application/mercurial-exp-framing-0005\r\n
  s>     content-type: application/mercurial-exp-framing-0005\r\n
  s>     content-length: 78\r\n
  s>     host: $LOCALIP:$HGPORT\r\n (glob)
  s>     user-agent: Mercurial debugwireproto\r\n
  s>     \r\n
  s>     F\x00\x00\x01\x00\x01\x01\x11\xa2Dargs\xa2Ffields\x81GparentsEnodes\x81T\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11DnameMchangesetdata
  s> makefile('rb', None)
  s>     HTTP/1.1 200 OK\r\n
  s>     Server: testing stub value\r\n
  s>     Date: $HTTP_DATE$\r\n
  s>     Content-Type: application/mercurial-exp-framing-0005\r\n
  s>     Transfer-Encoding: chunked\r\n
  s>     \r\n
  s>     13\r\n
  s>     \x0b\x00\x00\x01\x00\x02\x011
  s>     \xa1FstatusBok
  s>     \r\n
  received frame(size=11; request=1; stream=2; streamflags=stream-begin; type=command-response; flags=continuation)
  s>     63\r\n
  s>     [\x00\x00\x01\x00\x02\x001
  s>     \xa1Jtotalitems\x01\xa2DnodeT\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11Gparents\x82T3\x90\xef\x85\x00s\xfb\xc2\xf0\xdf\xff"D4,\x8e\x92)\x01:T\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00
  s>     \r\n
  received frame(size=91; request=1; stream=2; streamflags=; type=command-response; flags=continuation)
  s>     8\r\n
  s>     \x00\x00\x00\x01\x00\x02\x002
  s>     \r\n
  s>     0\r\n
  s>     \r\n
  received frame(size=0; request=1; stream=2; streamflags=; type=command-response; flags=eos)
  response: gen[
    {
      b'totalitems': 1
    },
    {
      b'node': b'\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11',
      b'parents': [
        b'3\x90\xef\x85\x00s\xfb\xc2\xf0\xdf\xff"D4,\x8e\x92)\x01:',
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
      ]
    }
  ]

Revision data is transferred upon request

  $ sendhttpv2peer << EOF
  > command changesetdata
  >     fields eval:[b'revision']
  >     nodes eval:[b'\xea\xe5\xf8\x2c\x2e\x62\x23\x68\xd2\x7d\xae\xcb\x76\xb7\xe3\x93\xd0\xf2\x42\x11']
  > EOF
  creating http peer for wire protocol version 2
  sending changesetdata command
  s>     POST /api/exp-http-v2-0001/ro/changesetdata HTTP/1.1\r\n
  s>     Accept-Encoding: identity\r\n
  s>     accept: application/mercurial-exp-framing-0005\r\n
  s>     content-type: application/mercurial-exp-framing-0005\r\n
  s>     content-length: 79\r\n
  s>     host: $LOCALIP:$HGPORT\r\n (glob)
  s>     user-agent: Mercurial debugwireproto\r\n
  s>     \r\n
  s>     G\x00\x00\x01\x00\x01\x01\x11\xa2Dargs\xa2Ffields\x81HrevisionEnodes\x81T\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11DnameMchangesetdata
  s> makefile('rb', None)
  s>     HTTP/1.1 200 OK\r\n
  s>     Server: testing stub value\r\n
  s>     Date: $HTTP_DATE$\r\n
  s>     Content-Type: application/mercurial-exp-framing-0005\r\n
  s>     Transfer-Encoding: chunked\r\n
  s>     \r\n
  s>     13\r\n
  s>     \x0b\x00\x00\x01\x00\x02\x011
  s>     \xa1FstatusBok
  s>     \r\n
  received frame(size=11; request=1; stream=2; streamflags=stream-begin; type=command-response; flags=continuation)
  s>     7e\r\n
  s>     v\x00\x00\x01\x00\x02\x001
  s>     \xa1Jtotalitems\x01\xa2DnodeT\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11Lrevisionsize\x18=X=1b74476799ec8318045db759b1b4bcc9b839d0aa\n
  s>     test\n
  s>     0 0\n
  s>     a\n
  s>     \n
  s>     commit 3
  s>     \r\n
  received frame(size=118; request=1; stream=2; streamflags=; type=command-response; flags=continuation)
  s>     8\r\n
  s>     \x00\x00\x00\x01\x00\x02\x002
  s>     \r\n
  s>     0\r\n
  s>     \r\n
  received frame(size=0; request=1; stream=2; streamflags=; type=command-response; flags=eos)
  response: gen[
    {
      b'totalitems': 1
    },
    {
      b'node': b'\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11',
      b'revisionsize': 61
    },
    b'1b74476799ec8318045db759b1b4bcc9b839d0aa\ntest\n0 0\na\n\ncommit 3'
  ]

Multiple fields can be transferred

  $ sendhttpv2peer << EOF
  > command changesetdata
  >     fields eval:[b'parents', b'revision']
  >     nodes eval:[b'\xea\xe5\xf8\x2c\x2e\x62\x23\x68\xd2\x7d\xae\xcb\x76\xb7\xe3\x93\xd0\xf2\x42\x11']
  > EOF
  creating http peer for wire protocol version 2
  sending changesetdata command
  s>     POST /api/exp-http-v2-0001/ro/changesetdata HTTP/1.1\r\n
  s>     Accept-Encoding: identity\r\n
  s>     accept: application/mercurial-exp-framing-0005\r\n
  s>     content-type: application/mercurial-exp-framing-0005\r\n
  s>     content-length: 87\r\n
  s>     host: $LOCALIP:$HGPORT\r\n (glob)
  s>     user-agent: Mercurial debugwireproto\r\n
  s>     \r\n
  s>     O\x00\x00\x01\x00\x01\x01\x11\xa2Dargs\xa2Ffields\x82GparentsHrevisionEnodes\x81T\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11DnameMchangesetdata
  s> makefile('rb', None)
  s>     HTTP/1.1 200 OK\r\n
  s>     Server: testing stub value\r\n
  s>     Date: $HTTP_DATE$\r\n
  s>     Content-Type: application/mercurial-exp-framing-0005\r\n
  s>     Transfer-Encoding: chunked\r\n
  s>     \r\n
  s>     13\r\n
  s>     \x0b\x00\x00\x01\x00\x02\x011
  s>     \xa1FstatusBok
  s>     \r\n
  received frame(size=11; request=1; stream=2; streamflags=stream-begin; type=command-response; flags=continuation)
  s>     b1\r\n
  s>     \xa9\x00\x00\x01\x00\x02\x001
  s>     \xa1Jtotalitems\x01\xa3DnodeT\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11Gparents\x82T3\x90\xef\x85\x00s\xfb\xc2\xf0\xdf\xff"D4,\x8e\x92)\x01:T\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00Lrevisionsize\x18=X=1b74476799ec8318045db759b1b4bcc9b839d0aa\n
  s>     test\n
  s>     0 0\n
  s>     a\n
  s>     \n
  s>     commit 3
  s>     \r\n
  received frame(size=169; request=1; stream=2; streamflags=; type=command-response; flags=continuation)
  s>     8\r\n
  s>     \x00\x00\x00\x01\x00\x02\x002
  s>     \r\n
  s>     0\r\n
  s>     \r\n
  received frame(size=0; request=1; stream=2; streamflags=; type=command-response; flags=eos)
  response: gen[
    {
      b'totalitems': 1
    },
    {
      b'node': b'\xea\xe5\xf8,.b#h\xd2}\xae\xcbv\xb7\xe3\x93\xd0\xf2B\x11',
      b'parents': [
        b'3\x90\xef\x85\x00s\xfb\xc2\xf0\xdf\xff"D4,\x8e\x92)\x01:',
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
      ],
      b'revisionsize': 61
    },
    b'1b74476799ec8318045db759b1b4bcc9b839d0aa\ntest\n0 0\na\n\ncommit 3'
  ]

  $ cat error.log
