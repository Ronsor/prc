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

class Channel ():
	def __init__ (self, name, immutable = False):
		self.name = name
		self.members = []
		self.unique = {}
		self.topic = ""
		self.immutable = immutable
		#self.logger.log_line("DEBUG", "channel %s created" % self.name)

	def send (self, line, local, omit = None):
		for member in self.members:
		# first send to local users
			if not member.local:
				continue
			if member is omit:
			# don't send privmsg/notice to oneself
				continue
			member.send(line)

		if not local:
		# we don't need to send to remote users if this is a remote
		# message; they already did that
			return

		for client in self.unique.itervalues():
		# then send to remote CONNECTIONS, not users, otherwise we get
		# duplicate messages
			client[0].send(line)

	def send_message (self, user, type, message):
		self.send(":%s %s %s :%s" % (user.full_hostmask() if user else
		 "-server-", type, self.name,
		 message), user.local if user else None, user)

	def send_names (self, user):
		# TODO # should loop for long NAMES lists >512bytes
		user.send_numeric(353, "= %s :%s" %
		 (self.name, " ".join([member.nick for member in self.members])))
		user.send_numeric(366, "%s :End of NAMES" % (self.name))

	def join_user (self, user, local = None):
		self.members.append(user)
		if not user.local:
			if not user.sock in self.unique:
				self.unique[user.sock] = []
			self.unique[user.sock].append(user)
		user.channels.append(self.name.lower())
		self.send(":%s JOIN %s" % (user.full_hostmask(), self.name),
		 user.local)
		if not local:
			for member in self.members:
			# tell the (remote) joining user about all our local users
				if not member.local:
					continue
				user.send(":%s JOIN %s" % (member.full_hostmask(), self.name))
			return
		if self.topic:
			local.send_numeric(332, "%s :%s" % (self.name, self.topic))
		self.send_names(local)

	def quit_user (self, user):
		if self.name.lower() not in user.channels: return
		user.channels.remove(self.name.lower())
		# QUIT was already sent
		self.members.remove(user)
		if user.local:
			return
		self.unique[user.sock].remove(user)
		if not self.unique[user.sock]:
			del self.unique[user.sock]

	def part_user (self, user, message = None):
		self.send(":%s PART %s%s" % (user.full_hostmask(), self.name,
			 " :" + message if message else ""), user.local)
		self.quit_user(user)

	def change_topic (self, user, message):
		self.topic = message

		self.send(":%s TOPIC %s :%s" % (user.full_hostmask(), self.name,
			 self.topic), user.local)

	#def __del__ (self):
		#self.logger.log_line("DEBUG", "channel %s deleted" % self.name)
