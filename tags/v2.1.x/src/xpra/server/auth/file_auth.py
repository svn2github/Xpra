# This file is part of Xpra.
# Copyright (C) 2013-2017 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

#authentication from a file containing just the password

import binascii
import hmac

from xpra.os_util import strtobytes
from xpra.net.crypto import get_digest_module
from xpra.server.auth.file_auth_base import FileAuthenticatorBase, init, log
from xpra.util import nonl


#will be called when we init the module
assert init


class Authenticator(FileAuthenticatorBase):

    def authenticate_hmac(self, challenge_response, client_salt):
        if not self.salt:
            log.error("Error: illegal challenge response received - salt cleared or unset")
            return None
        salt = self.get_response_salt(client_salt)
        password = self.get_password()
        if not password:
            log.error("Error: authentication failed")
            log.error(" no password for '%s' in '%s'", self.username, self.password_filename)
            return False
        digestmod = get_digest_module(self.digest)
        if not digestmod:
            log.error("Error: %s authentication failed", self)
            log.error(" digest module '%s' is invalid", self.digest)
            return False
        verify = hmac.HMAC(strtobytes(password), strtobytes(salt), digestmod=digestmod).hexdigest()
        log("file authenticate(%s) password='%s', salt=%s, hash=%s", nonl(challenge_response), nonl(password), binascii.hexlify(strtobytes(salt)), verify)
        if not hmac.compare_digest(verify, challenge_response):
            log("expected '%s' but got '%s'", verify, challenge_response)
            log.error("Error: hmac password challenge for '%s' does not match", self.username)
            return False
        return True

    def __repr__(self):
        return "password file"
