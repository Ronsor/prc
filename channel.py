#!/usr/bin/env python
# Copyright (c) 2017, Ronsor-OpenStar
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
import fnmatch
class ChannelUser ():
	def __init__ (self, user):
		self.user = user
		self.status = 0
	def set_status (self, num):
		self.status = num

class Channel ():
	status_prefixes = [ str(), "+", "%", "@", "!" ]
	status_modes = [ str(), "v", "h", "o", "a" ]
	def __init__ (self, name, immutable = False):
		self.name = name
		self.members = []
		self.unique = {}
		self.topic = ""
		self.immutable = immutable
		self.modeflags = set()
		self.blist = {}
		self.blist["I"] = set()
		self.blist["b"] = set()
		self.blist["e"] = set()
		#self.logger.log_line("DEBUG", "channel %s created" % self.name)
	def mode_to_status (self, mode):
		return self.status_modes.index(mode)
	def get_userbyname (self, name):
		name = name.lower()
		for member in self.members:
			if member.user.nick.lower() == name:
				return member
		return None
	def get_channeluser (self, user):
		if user in self.members: return user
		for member in self.members:
			if member.user is user:
				return member
		return None
	def is_banned (self, user):
		for ban in self.blist["b"]:
			if fnmatch.fnmatchcase(user.full_hostmask().lower(), ban.lower()):
				return True
		return False
	def is_exception (self, user):
		for ex in self.blist["e"]:
			if fnmatch.fnmatchcase(user.full_hostmask().lower(), ex.lower()):
				return True
		return False
	def is_really_banned (self, user):
		return (self.is_banned(user) and (not self.is_exception(user)))
	def is_invex (self, user):
		for invex in self.blist["I"]:
			if fnmatch.fnmatchcase(user.full_hostmask().lower(), invex.lower()):
				return True
		return False

	def set_status (self, user, num):
		user = self.get_channeluser(user)
		if num == -1: num = len(self.status_prefixes) - 1
		user.set_status(num)
	def send (self, line, local, omit = None):
		for member in self.members:
		# first send to local users
			if not member.user.local:
				continue
			if member is omit:
			# don't send privmsg/notice to oneself
				continue
			member.user.send(line)

		if not local:
		# we don't need to send to remote users if this is a remote
		# message; they already did that
			return

		for client in self.unique.itervalues():
		# then send to remote CONNECTIONS, not users, otherwise we get
		# duplicate messages
			client[0].user.send(line)

	def send_mode_change (self, user, string):
		user = self.get_channeluser(user)
		self.send(":%s MODE %s %s" % (user.user.full_hostmask() if user else "-server-!server@server", self.name, string), user.user.local if user else None, None)
	def send_message (self, user, type, message):
		user = self.get_channeluser(user)
		self.send(":%s %s %s :%s" % (user.user.full_hostmask() if user else
		 "-server-!server@server", type, self.name,
		 message), user.user.local if user else None, user)

	def send_names (self, user):
		# TODO # should loop for long NAMES lists >512bytes
		user.send_numeric(353, "= %s :%s" %
		 (self.name, " ".join(["%s%s" % (self.status_prefixes[member.status], member.user.nick) for member in self.members])))
		user.send_numeric(366, "%s :End of NAMES" % (self.name))

	def join_user (self, raw_user, local = None, status = 0):
		user = ChannelUser(raw_user)
		self.members.append(user)
		if not user.user.local:
			if not user.user.sock in self.unique:
				self.unique[user.user.sock] = []
			self.unique[user.user.sock].append(user)
		user.user.channels.append(self.name.lower())
		self.send(":%s JOIN %s" % (user.user.full_hostmask(), self.name),
		 user.user.local)
		if not local:
			for member in self.members:
			# tell the (remote) joining user about all our local users
				if not member.user.local:
					continue
				user.user.send(":%s JOIN %s" % (member.user.full_hostmask(), self.name))
				if member.status > 0:
					user.user.send(":%s MODE %s +%s %s" % (member.user.full_hostmask(), self.name, self.status_modes[member.status], member.user.nick))
			for mode in self.modeflags:
				user.user.send(":%s MODE %s +%s" % (user.user.full_hostmask(), self.name, mode))
			for type in self.blist:
				for entry in self.blist[type]:
					user.user.send(":%s MODE %s +%s %s" % (user.user.full_hostmask(), self.name, type, entry))
			return
		if self.topic:
			local.send_numeric(332, "%s :%s" % (self.name, self.topic))
		self.set_status(user, status)
		self.send_names(local)

	def quit_user (self, user):
		user = self.get_channeluser(user)
		if self.name.lower() not in user.user.channels: return
		user.user.channels.remove(self.name.lower())
		# QUIT was already sent
		self.members.remove(user)
		if user.user.local:
			return
		self.unique[user.user.sock].remove(user)
		if not self.unique[user.user.sock]:
			del self.unique[user.user.sock]

	def part_user (self, user, message = None):
		user = self.get_channeluser(user)
		self.send(":%s PART %s%s" % (user.user.full_hostmask(), self.name,
			 " :" + message if message else ""), user.user.local)
		self.quit_user(user)
	def kick_user (self, source, user, message = None):
		user = self.get_channeluser(user)
		source = self.get_channeluser(source)
		self.send(":%s KICK %s %s%s" % (source.user.full_hostmask(), self.name, user.user.nick,
			 " :" + message if message else ""), source.user.local)
		self.quit_user(user)

	def change_topic (self, user, message):
		self.topic = message
		user = self.get_channeluser(user)
		self.send(":%s TOPIC %s :%s" % (user.user.full_hostmask(), self.name,
			 self.topic), user.user.local)

	#def __del__ (self):
		#self.logger.log_line("DEBUG", "channel %s deleted" % self.name)
