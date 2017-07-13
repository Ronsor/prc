#!/usr/bin/env python
# Copyright (c) 2014, wowaname
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing official
# policies, either expressed or implied, of the FreeBSD Project.

import log

class User ():
	def __init__ (self, socket, address, local, nick, ident, logger,
	 gecos = "", localconn = None):
		self.sock = socket
		self.localconn = localconn
		self.address = address
		self.local = local
		self.nick = nick
		self.ident = ident
		self.gecos = gecos
		self.logger = logger
		self.host = address
		self.channels = []
		self.away = None
		self.isoper = False
		self.logger.log_line("DEBUG", "user %s created" % self.nick)

	def full_hostmask (self):
		return "%s!%s@%s" % (self.nick, self.ident, self.address[0])

	def send (self, line):
		self.logger.log_line("DEBUG",
		 "\x1b[31;1m->\x1b[0;1m  to  %s\x1b[0m %s" % (self.nick, line))
		#try:
		self.sock.send("%s\r\n" % line)
		#except:
		#	self.logger.log_line("DEBUG", "sending data to a dead sock %s" %
		#	 self.nick)

	def __del__ (self):
		self.logger.log_line("DEBUG", "user %s deleted" % self.nick)
		for channel in self.channels[:]:
			channel.quit_user(self)
