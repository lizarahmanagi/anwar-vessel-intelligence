#!/usr/bin/env python3
"""
SMTP NTLM authentication helper for Exchange servers that only advertise
AUTH NTLM (e.g. mail.anwargroup.net). Uses passlib's pure-Python MD4 so
NTLM works on Python builds where OpenSSL dropped MD4 (3.14+).
"""

import base64
import hashlib
import smtplib

from passlib.utils.md4 import md4 as _md4


class _MD4Hash:
    digest_size = 16
    block_size = 64

    def __init__(self, data=b''):
        self._data = b''
        self.update(data)

    def update(self, data):
        self._data += bytes(data)

    def digest(self):
        return _md4(self._data).digest()

    def hexdigest(self):
        return self.digest().hex()


class _HashShim:
    md4 = _MD4Hash
    md5 = hashlib.md5
    sha1 = hashlib.sha1
    sha256 = hashlib.sha256

    @staticmethod
    def new(name, data=b''):
        if name.lower() == 'md4':
            return _MD4Hash(data)
        return hashlib.new(name, data)


def _patch_ntlm_md4():
    """Point ntlm_auth's hashlib at the shim so MD4 resolves on any Python."""
    try:
        import ntlm_auth.compute_hash as _ch
        _ch.hashlib = _HashShim
    except ImportError:
        pass


_patch_ntlm_md4()


def ntlm_login(server, username, password):
    """Perform AUTH NTLM against an already-connected smtplib session."""
    from ntlm_auth.ntlm import NtlmContext

    domain, user = '', username
    if '\\' in username:
        domain, user = username.split('\\', 1)

    ctx = NtlmContext(user, password, domain)
    negotiate = base64.b64encode(ctx.step()).decode()
    code, resp = server.docmd('AUTH', 'NTLM ' + negotiate)
    if code != 334:
        raise smtplib.SMTPAuthenticationError(code, resp)

    authenticate = base64.b64encode(ctx.step(base64.b64decode(resp))).decode()
    code, resp = server.docmd(authenticate)
    if code != 235:
        raise smtplib.SMTPAuthenticationError(code, resp)
