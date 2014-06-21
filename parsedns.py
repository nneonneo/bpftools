#!/usr/bin/env python

import struct
import sys

import utils


def usage():
    print """
parsedns.py [ hex string... ]

Read the hex string as a network packet and parse it as it were a DNS
request. Decode it and pretty print it.
""".lstrip()
    sys.exit(2)


def unpack_domain(off, l5, rr=False):
    off1 = None

    while True:
        c, = struct.unpack_from('!B', l5, off)
        if c == 0x00:
            print '.'
            off += 1
            break
        elif (c & 0xC0):
            c, = struct.unpack_from('!H', l5, off)
            ptr = c ^ 0xc000
            off += 2
            print 'ptr->#%i'  % (ptr,),
            if off1 == None:
                off1 = off
            off = ptr
        else:
            print '%r' % (l5[off+1:off+1+c],),
            off += c + 1

    qtype, qclass = struct.unpack_from('!HH', l5, off)
    off += 4
    print '                    type=0x%04x class=0x%04x'  % (qtype, qclass)
    if not rr:
        return off
    ttl, rlength = struct.unpack_from('!IH', l5, off)
    off += 6
    print '                    ttl=%i rrlen=%i %s' % (ttl, rlength, l5[off:off+rlength].encode('hex'))
    off += rlength
    return off


def parsedns(raw):

    l2len = utils.find_ip_offset(raw)
    assert l2len is not None
    l2, l3 = raw[:l2len], raw[l2len:]

    print '[.] l2: %s' % l2.encode('hex')

    v_len, = struct.unpack_from('!B', l3)
    if v_len & 0xf0 == 0x40:
        l3len = (v_len & 0x0F) * 4
        l3, l4 = l3[:l3len], l3[l3len:]
        print '[.] l3: %s' % l3.encode('hex')

        v_len, dscp_ecn, total_length, ip_id, fragment, ttl, protocol, _checksum, sip, dip = struct.unpack_from('!BBHHHBBHII', l3)
        ip_extra = l3[20:]

        print '              ver: 0x%02x' % ((v_len & 0xf0) >> 4,)
        print '              hdl: 0x%02x' % ((v_len & 0x0f),)
        print '            ip_id: 0x%04x' % (ip_id,)
        print '         fragment: 0x%04x' % (fragment,)
        print '         protocol: 0x%02x' % (protocol,)
        print '           source: 0x%04x' % (sip,)
        print '      destination: 0x%04x' % (dip,)
        if ip_extra:
            print '         ip_extra: %s' % (ip_extra.encode('hex'),)
    elif v_len & 0xf0 == 0x60:
        l3len = 40
        l3, l4 = l3[:l3len], l3[l3len:]
        print '[.] l3: %s' % l3.encode('hex')

        v_ttl, _class, _flow, payload_length, next_header, ttl = struct.unpack_from('!BBHHBB', l3)
        print '              ver: 0x%02x' % ((v_len & 0xf0) >> 4,)
        print '   payload_length: 0x%04x' % (payload_length,)
        print '      next_header: 0x%02x' % (next_header,)
        print '              ttl: 0x%02x' % (ttl,)
        print '           source: %s' % (l3[8:24].encode('hex'),)
        print '      destination: %s' % (l3[24:40].encode('hex'),)
    else:
        assert False

    l4, l5 = l4[:8], l4[8:]

    print '[.] l4: %s' % l4.encode('hex')

    spt, dpt, l4len, _checksum = struct.unpack_from('!HHHH', l4)

    print '      source port: %s' % (spt,)
    print ' destination port: %s' % (dpt,)
    print '           length: %s' % (l4len,)

    print '[.] l5: %s' % l5.encode('hex')

    dns_id, flags, qdcnt, anscnt, authcnt, extracnt = struct.unpack_from('!HHHHHH', l5)

    print '               id: 0x%04x' % (dns_id,)
    print '            flags: 0x%04x' % (flags,),
    f = []
    f.append('response' if flags & (1<<15) else 'query')
    if flags & (1<<10):
        f.append('authoritative')
    if flags & (1<<9):
        f.append('truncated')
    if flags & (1<<8):
        f.append('recursion_desired')
    if flags & (1<<7):
        f.append('recursion_available')
    if flags & (1<<6):
        f.append('z')
    if flags & (1<<5):
        f.append('authenticated_data')
    if flags & (1<<4):
        f.append('checking_disabled')
    f.append( 'op=%x' % ((flags>>11) & 0xF))
    f.append( 'rcode=%x' % ((flags) & 0xF))
    print ' '.join(f)
    print '        questions: %s' % (qdcnt,)
    print '          answers: %s' % (anscnt,)
    print '             auth: %s' % (authcnt,)
    print '            extra: %s' % (extracnt,)

    off = 12
    for i in xrange(qdcnt):
        print '#%3i         q[%i]:' % (off-len(l5), i,),
        off = unpack_domain(off, l5)

    for cnt, n in (anscnt, 'answer'), (authcnt, 'auth'), (extracnt, 'extra'):
        for i in xrange(cnt):
            print '%14s[%i]:' % (n, i, ),
            off = unpack_domain(off, l5, rr=True)

    if len(l5) > off:
        print '  trailing: %s' % (l5[off:].encode('hex'),)


if __name__ == "__main__":
    if not sys.argv[1:]:
        usage()

    for hexstr in sys.argv[1:]:
        parsedns(hexstr.decode('hex'))
        print
