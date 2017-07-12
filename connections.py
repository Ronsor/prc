#!/usr/bin/env python

import channel
import log
import os.path
import socket
import time
import user
from errno import EAGAIN

users = {}
servers = []
channels = {
	"&errors": channel.Channel("&errors", immutable = True),
	"&eval": channel.Channel("&eval", immutable = True),
	"&rawlog": channel.Channel("&rawlog", immutable = True),
}

nick_chars = (
	"abcdefghijklmnopqrstuvwxyz"
	"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
	"0123456789"
	"\\[]|{}_-^`"
)

class LocalConnections ():
	"""IRC to PRC interface"""
	def __init__ (self, name, bind_addresses, olines, logger):
		self.name = name
		self.olines = olines
		self.logger = logger
		self.connections = []
		self.listeners = []

		for bind_address in bind_addresses:
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

			try:
				sock.bind(bind_address)
			except socket.error as e:
				exit("error in LOCAL_BIND address %s:%d (%s)" %
				 (bind_address[0], bind_address[1], e))

			sock.setblocking(0)
			sock.listen(5)
			self.listeners.append(sock)

	def loop (self):
		prune = []

		for connection in self.connections:
			try:
				connection.sock.type
				connection.loop()
			except socket.error as e:
				if e.errno == EAGAIN:
					now = time.time()
					if (connection.lastseen < now - 128 and
					 not connection.pinged):
					 # 128 will be replaced by a config var
						connection.user.send("PING :%s" % connection.name)
						connection.pinged = True
					if connection.lastseen < now - (128 * 2):
						try:
							connection.error("Ping timeout: %d seconds" %
							 (now - connection.lastseen - 128))
						except socket.error:
							pass
					continue
				if e.errno:
					e.message = os.strerror(e.errno)
				for u in users.itervalues():
					found = False
					if not u.local or u == connection.user:
						continue
					for c in connection.user.channels:
						if u in channels[c].members:
							found = True
							break
					if found:
						connection.send(":%s QUIT :%s" %
						 (connection.user.full_hostmask(), e.message))

				for u in servers:
					u.send(":%s QUIT :%s" %
					 (connection.user.full_hostmask(), e.message))

				for c in connection.user.channels[:]:
					channels[c].quit_user(connection.user)
					if not channels[c].members and not channels[c].immutable:
						del channels[c]

				if connection.user.nick.lower() in users:
					del users[connection.user.nick.lower()]

				self.connections.remove(connection)

		# check connection queue
		for listener in self.listeners:
			try:
				sock, address = listener.accept()
				self.connections.append( LocalConnection(
				 self.name,
				 sock,
				 address,
				 self.olines,
				 self.logger) )
			except socket.error:
				pass # todo

class RemoteConnections ():
	"""PRC to PRC interface"""
	def __init__ (self, network, bootstrap, bind_address, hostname, logger):
		self.connections = []
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.name = network
		self.hostname = hostname
		self.bind_port = bind_address[1]
		self.logger = logger
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		try:
			self.sock.bind(bind_address)
		except socket.error as e:
			exit("error in LOCAL_BIND address %s:%d (%s)" % (bind_address[0],
			 bind_address[1], e))
		self.sock.setblocking(0)
		self.sock.listen(5)
		self.socket_queue = []

		try:
			if os.path.isfile(os.path.join("hostcache", self.name)):
				with open(os.path.join("hostcache", self.name)) as hostcache:
					hosts = hostcache.read().split("\n")
			elif bootstrap:
				hosts = [bootstrap]
			else:
				hosts = []

			for host in hosts:
				try:
					host = host.split()
					if len(host) < 2: continue
					address = (host[0], int(host[1]))
					self.logger.log_line("DEBUG",
					 "bootstrapping, trying host %s" % str(address))
					bootsock = socket.socket(socket.AF_INET,
					 socket.SOCK_STREAM)
					bootsock.connect(address)
					bootsock.setblocking(0)
					if not self.hostname:
						self.hostname = bootsock.getsockname()[0]
					conn = RemoteConnection(
					 bootsock,
					 address,
					 self.socket_queue,
					 self.logger)
					self.connections.append(conn)
					servers.append(conn)
					conn.send("BOOTSTRAP %s %s %d :%s"
					 % ("*", self.hostname, self.bind_port, "PRC gateway"))
					break

				except socket.error as e:
					pass # todo

			else:
				self.logger.log_line("NOTICE",
				 "all hosts in hostcache file are down; not bootstrapping")

		except IOError:
			self.logger.log_line("NOTICE",
			 "no hostcache file found; not bootstrapping")
			return


	def loop (self):
		prune = []

		for connection in self.connections:
			try:
				connection.sock.type
				connection.loop()
			except socket.error as e:
				if e.errno == EAGAIN:
					continue
				for nick in connection.users:
					del users[nick]
				servers.remove(connection)
				self.connections.remove(connection)

		# args[1 - fp , 2 - host , 3 - port , 4 - gecos]
		if self.socket_queue:
			try:
				args = self.socket_queue.pop(0)
				self.logger.log_line("DEBUG",
				 "creating new connection to %s:%s" % (args[2], args[3]))
				sock = socket.socket
				sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				address = (args[2], int(args[3]))
				sock.connect(address)
				# todo: we need to setblocking before connect
				# todo: with ssl check against socket_queue[1]
				# todo: gecos
				sock.setblocking(0)
				conn = RemoteConnection(
				 sock,
				 address,
				 self.socket_queue,
				 self.logger)

				conn.send("SERVER %s %s %d :%s" %
				 ("*",
				 self.hostname,
				 self.bind_port,
				 "PRC gateway"))

				self.connections.append(conn)
				servers.append(conn)

			except socket.error:
				pass # todo

		# check connection queue
		try:
			sock, address = self.sock.accept()
			conn = RemoteConnection(
			 sock,
			 None,
			 self.socket_queue,
			 self.logger)
			self.connections.append(conn)
			servers.append(conn)
		except socket.error:
			pass # todo

class LocalConnection ():
	# one nick per connection
	def __init__ (self, name, socket, address, olines, logger):
		self.name = name
		self.sock = socket
		self.sock.setblocking(0)
		self.olines = olines
		self.logger = logger
		self.data_in = ""
		self.lastseen = time.time()
		self.pinged = False

		self.user = user.User(
		 socket = self.sock,
		 address = address,
		 local = True,
		 nick = "*",
		 ident = "*",
		 logger = self.logger)

		self.registered = 0

	def send (self, message):
		"""sends a line to the user"""
		try:
			self.user.send(message)
		except socket.error:
			self.logger.log_line("DEBUG", "sending data to a dead sock %s" %
			 self.user.address[0])
			self.sock.close()
			raise socket.error, "Sending failed"

	def send_numeric (self, numeric, message = None):
		"""sends a numeric to the user"""
		self.send(":%s %03d %s %s" % (
		 self.name,
		 numeric,
		 self.user.nick,
		 message if message else ":Reply %03d" % numeric))

	def error (self, message):
		"""closes the connection after sending a message with reason"""
		self.send("ERROR :%s" % message)
		self.sock.close()
		raise socket.error, message

	def broadcast_remote (self, line):
		"""broadcasts a message to all connected remote servers"""
		for s in servers:
			s.send(line)

	def send_welcome (self):
		"""send welcome banner on connect"""
		self.send_numeric(001, ":Welcome to PRC!")
		self.send_numeric(002, ":Your host is %s, running version "
		 "PRC-Gateway-??" % (self.name))
		self.send_numeric(004, "%s PRC-Gateway-?? aBcsw abehiklmoptv" %
		 (self.name))
		self.send_numeric(005, "CASEMAPPING=rfc1459 CHANMODES=beI,k,l,imprstu "
		 "CHANNELLEN=? CHANTYPES=&+ EXCEPTS=e INVEX=I "
		 ":are supported by this server")
		self.send_numeric(005, "NETWORK=PRC NICKLEN=? PREFIX=(ov)@+ "
		 ":are supported by this server")
		self.broadcast_remote(":%s USER * * * :%s" %
		 (self.user.full_hostmask(),
		 self.user.gecos))
		self.registered = 4

	def on_user (self, args):
		"""USER command"""
		if self.registered & 2:
			self.send_numeric(462, ":Already registered")
			return
		for letter in args[1]:
			if letter not in nick_chars:
				self.send_numeric(461, "%s :Erroneous username" % args[1])
				return
		self.registered |= 2
		self.user.ident = args[1]
		self.user.gecos = args[4]
		if self.registered == 3:
			self.send_welcome()

	def on_nick (self, args):
		"""NICK command"""
		if not args[1]:
			self.send_numeric(432, "%s :Erroneous nickname" % args[1])
			return

		for letter in args[1]:
			if letter not in nick_chars:
				self.send_numeric(432, "%s :Erroneous nickname" % args[1])
				return

		if args[1] == self.user.nick:
			return

		if (args[1].lower() in users and
		 args[1].lower() != self.user.nick.lower()):
			self.send_numeric(433, "%s :Nickname already in use" % args[1])
			return

		if self.registered >= 3:
			self.user.send(":%s NICK %s" % (self.user.full_hostmask(), args[1]))
			self.broadcast_remote(":%s NICK %s" %
			 (self.user.full_hostmask(), args[1]))

			for u in users.itervalues():
				if not u.local or u == self.user:
					continue
				else:
					found = False
					for c in self.user.channels:
						if u in channels[c].members:
							found = True
							break
				if found:
					u.send(":%s NICK %s" %
					 (self.user.full_hostmask(), args[1]))

			self.broadcast_remote(":%s NICK %s" %
			 (self.user.full_hostmask(), args[1]))
			del users[self.user.nick.lower()]

		self.user.nick = args[1]
		users[self.user.nick.lower()] = self.user

		self.registered |= 1
		if self.registered == 3:
			self.send_welcome()

	def on_away (self, args):
		"""AWAY command"""
		if len(args) > 1: # setting away
			self.send_numeric(306, ":Now away")
			self.broadcast_remote(":%s AWAY :%s" %
			 (self.user.full_hostmask(), args[1]))
			self.user.away = args[1]
		else: # setting back
			self.send_numeric(305, ":Welcome back")
			self.broadcast_remote(":%s AWAY" %
			 self.user.full_hostmask())
			self.user.away = None

	def on_message (self, args):
		"""PRIVMSG/NOTICE commands"""
		type = args[0].upper()
		target = args[1].lower()
		message = args[2]
		assert type in ["PRIVMSG", "NOTICE"]

		if not message and type == "PRIVMSG":
			self.send_numeric(412, "%s :No text to send" % target)
			return

		if target in channels:
			if self.user not in channels[target].members:
				if type == "PRIVMSG":
					self.send_numeric(404, "%s :Cannot send to channel" %
					 target)
				return
			channels[target].send_message(self.user, type, message)

			if target == "&eval":
				try:
					channels["&eval"].send_message(None, "PRIVMSG",
					 eval(message))
				except BaseException as e:
					channels["&eval"].send_message(None, "NOTICE", str(e))

			return

		if target in users:
			users[target].send(":%s %s %s :%s" % (self.user.full_hostmask(),
			 type, target, message))
			return

		if type == "PRIVMSG":
			self.send_numeric(401, "%s :No such target" % target)

	def on_topic (self, args):
		"""TOPIC command"""
		target = args[1].lower()

		if target not in channels:
			self.send_numeric(403, "%s :No such channel" % target)
			return

		if len(args) > 2:
			message = args[2]
			channels[target].change_topic(self.user, message)
			return

		self.send_numeric(332, "%s :%s" % (target, channels[target].topic))

	def on_invite (self, args):
		"""INVITE command"""
		target = args[1].lower()
		channel = args[2].lower()

		if target not in users:
			self.send_numeric(401, "%s :No such target" % target)
			return

		if channel not in channels:
			self.send_numeric(403, "%s :No such channel" % channel)
			return

		users[target].send(":%s INVITE %s :%s" % (self.user.full_hostmask(),
		 target, channel))

	def on_join (self, args):
		"""JOIN command"""
		targets = args[1].split(",")
		for Target in targets:
			if not Target:
				continue
			target = Target.lower()
			if target == "0":
				for i in self.user.channels[:]:
					channels[i].part_user(
						user = self.user,
						message = "Left all channels")
					if (not channels[i].members and not
					 channels[i].immutable):
						del channels[i]
				continue
			if target[0] not in "+&":
				self.send_numeric(403, "%s :No such channel" % Target)
				continue
			if not target in channels:
				channels[target] = channel.Channel(Target)
			if self.user in channels[target].members:
				continue
			if (target in ("&errors", "&eval", "&rawlog") and self.olines and
			 not self.user.isoper):
				self.send_numeric(471, "%s :Permission denied" % Target)
				continue
			channels[target].join_user(self.user, self)
			self.broadcast_remote(":%s JOIN %s" %
			 (self.user.full_hostmask(), target))

	def on_part (self, args):
		"""PART command"""
		targets = args[1].lower().split(",")
		for target in targets:
			if not target in channels:
				self.send_numeric(403, "%s :No such channel" % target)
				return
			channels[target].part_user(
			 user = self.user,
			 message = args[2] if len(args) > 2 else None)
			if (not channels[target].members and not
			 channels[target].immutable):
				del channels[target]
			self.broadcast_remote(":%s PART %s%s" %
			 (self.user.full_hostmask(),
			 target,
			 " :" + args[2] if len(args) > 2 else ""))

	def on_ping (self, args):
		"""PING command; makes lag-checking clients happy"""
		self.user.send(":%s PONG :%s" % (self.name, args[1]))

	def on_quit (self, args):
		"""QUIT command"""
		reason = "Exited" + (": %s" % args[1] if len(args) > 1 else "")

		self.error(reason)

	def on_oper (self, args):
		"""OPER command used to authenticate for protected commands"""
		username = args[1]
		password = args[2]

		if username not in self.olines:
			self.send_numeric(463, ":No O:lines match your host")
			return

		if self.olines[username] != password:
			self.send_numeric(464, ":Invalid password")
			return

		self.user.isoper = True
		self.send_numeric(381, ":You are now an operator")
		self.user.send(":%s MODE %s +o" % (self.name, self.user.nick))

	def on_die (self, args):
		"""DIE command; kills the server"""
		if self.olines and not self.user.isoper:
			self.send_numeric(481, ":Permission denied")
		else:
			exit(0)


	def on_who (self, args):
		"""WHO command"""
		target = args[1].lower()

		if target in channels:
			targets = channels[target].members
		elif target in users:
			targets = [users[target]]
		else:
			self.send_numeric(315, "%s :End of WHO" % target)
			return

		for u in targets:
			self.send_numeric(352, " ".join( (
			 target,
			 u.ident,
			 u.address[0],
			 self.name,
			 u.nick,
			 ("G" if u.away else "H") +
			 ("*" if u.isoper else ""),
			 ":0" if u.local else ":1",
			 u.gecos
			 ) ))

		self.send_numeric(315, "%s :End of WHO" % target)

	def on_whois (self, args):
		"""WHOIS command"""
		targets = args[-1].lower().split(",")

		for target in targets:
			if target not in users:
				self.send_numeric(401, "%s :No such nick" % target)
				continue
			self.send_numeric(311, "%s %s %s * :%s" %
			 (users[target].nick,
			 users[target].ident,
			 users[target].address[0],
			 users[target].gecos))
			#self.send_numeric(312, "%s %s :%s" %
			# (users[target].nick,
			# ~server~,
			# ~server.gecos~))
			#self.send_numeric(276, "%s :has client certificate fingerprint %s" %
			# (users[target].nick,
			# users[target].~fp~)
			if users[target].isoper:
				self.send_numeric(313, "%s :is a local operator" %
				 users[target].nick)
			if users[target].away:
				self.send_numeric(301, "%s :%s" %
				 (users[target].nick, users[target].away))

		self.send_numeric(318, "%s :End of WHOIS" % args[-1])

	def on_names (self, args):
		channel = args[1].lower()

		if channel not in channels:
			self.send_numeric(403, "%s :No such channel" % target)
			return

		channels[channel].send_names(self)

	def on_links (self, args):
		for server in servers:
			self.send_numeric(364, "%s %s :1 %s" %
			 (server.address[0], self.name, server.gecos))
		self.send_numeric(364, "%s %s :1 %s" %
		 (self.name, self.name, "PRC gateway"))
		self.send_numeric(365, "%s :End of LINKS" %
		 (args[1] if len(args) > 1 else "*"))

	def on_mode (self, args):
		"""MODE command"""
		target = args[1].lower()
		modes = args[2] if len(args) > 2 else ""

		add = True
		change = (set(), set())
		catch = False
		for mode in modes:
			if mode == "+":
				add = True
			elif mode == "-":
				add = False
			elif mode == "o" and add:
				self.send_numeric(484, "Use the OPER command to set umode o")
				catch = True
			elif mode == "o" and not add:
				self.user.isoper = False
				change[add].add("o")

		if change[0] or change[1]:
			self.user.send(":%s MODE %s %s%s%s%s" % (self.name, self.user.nick,
			 "+" if change[1] else "", "".join(change[1]),
			 "-" if change[0] else "", "".join(change[0])))
			return

		elif catch:
			return

		if target == self.user.nick.lower():
			modes = "+"
			modes += "o" if self.user.isoper else ""
			self.send_numeric(221, modes)
			return

		if target in channels:
			self.send_numeric(477, "%s :Channel doesn't support modes" % target)
			return

		if target in users:
			self.send_numeric(502, "Snooping through others' usermodes is bad!")
			return

		self.send_numeric(401, "%s :No such target" % target)

	def on_unimplemented (self, args):
		"""Commands that we don't want to give errors on but we still want to
		recognise"""
		pass

	def irc_callback (self, command, line, min_args, cb, pre_register = False):
		if command != line[0].upper():
			return False

		if not pre_register and self.registered < 3:
			self.send_numeric(451, ":Connection not registered")
			return True

		if len(line) < min_args + 1:
			self.send_numeric(461, ":Too few arguments")
			return True

		args = line

		for i in xrange(len(line)):
			if line[i].startswith(":"):
				args = line[:i] + [" ".join(line[i:])[1:]]
				break

		cb(args)
		return True

	def handle_line (self, line):
		channels["&rawlog"].send_message(None, "PRIVMSG",
		 self.user.nick + " " + line)
		line = line.split(" ")
		if not line:
			return

		for i in (
			#(command, min_args, cb, pre_register = False)
			("USER", 4, self.on_user, True),
			("NICK", 1, self.on_nick, True),
			("AWAY", 0, self.on_away),
			("PRIVMSG", 2, self.on_message),
			("NOTICE", 2, self.on_message),
			("TOPIC", 1, self.on_topic),
			("INVITE", 2, self.on_invite),
			("JOIN", 1, self.on_join),
			("PART", 1, self.on_part),
			("PING", 1, self.on_ping),
			("QUIT", 0, self.on_quit, True),
			("OPER", 2, self.on_oper),
			("DIE", 0, self.on_die),
			("WHO", 1, self.on_who),
			("WHOIS", 1, self.on_whois),
			("NAMES", 1, self.on_names),
			("LINKS", 0, self.on_links),
			("MODE", 1, self.on_mode),
			("PONG", 0, self.on_unimplemented, True),
			("CAP", 0, self.on_unimplemented, True),
		):
			if self.irc_callback(i[0], line, i[1], i[2],
			 i[3] if len(i) > 3 else False):
				break
		else:
			self.send_numeric(421, "%s :Unknown command" % line[0].upper())

	def loop (self):
		self.data_in += self.sock.recv(512)
		# be compatible with all shitty irc clients
		lines = self.data_in.replace("\r\n", "\n").replace("\n\r",
		 "\n").replace("\r", "\n").split("\n")
		self.data_in = lines.pop()

		for line in lines:
			self.logger.log_line("DEBUG",
			 "\x1b[32;1m<-\x1b[0;1m from %s\x1b[0m %s" % (self.user.nick, line))
			self.handle_line(line)
			self.lastseen = time.time()
			self.pinged = False

class RemoteConnection ():
	# these are "servers" and may have more than one nick / client
	def __init__ (self, socket, address, socket_queue, logger):
		self.sock = socket
		self.sock.setblocking(0)
		self.address = address
		self.gecos = "*"
		self.socket_queue = socket_queue
		self.logger = logger
		self.data_in = ""
		self.users = {}
		self.logger.log_line("DEBUG", "remote %s created" %
		 (self.address[0] if self.address else "*"))

	def broadcast_local (self, user, line):
		"""sends a remote message to local users who share at least one
		channel with the remote user"""
		for u in users.itervalues():
			if not u.local:
				continue
			if u == user:
				continue
			found = False
			for c in user.channels:
				if u in channels[c].members:
					found = True
					break
			if found:
				u.send(":%s %s" % (user.full_hostmask(), line))

	def send (self, line):
		"""sends a line to the remote client"""
		self.logger.log_line("DEBUG", "\x1b[31;2m>>\x1b[0;1m from %s\x1b[0m %s"
		 % (self.address[0] if self.address else "*", line))
		try:
			self.sock.send("%s\n" % line)
		except:
			self.logger.log_line("DEBUG", "sending data to a dead sock %s" %
			 self.address[0])
			self.sock.close()
			raise socket.error, "Sending failed"

	def send_numeric (self, numeric, message = None):
		"""sends a numeric to the remote client"""
		self.send("%03d %s" % (
		 numeric,
		 message if message else ":Reply %03d" % numeric))

	def error (self, message = None):
		self.send("ERROR :%s" % message if message else "Killed")
		self.sock.close()
		raise socket.error, message

	# SERVER ssl-sha256-fingerprint host port :gecos
	def on_server (self, args):
		"""SERVER command that registers the connection"""

		type = args[0].upper()
		assert type in ("BOOTSTRAP", "SERVER")

		try:
			int(args[3])
		except:
			return

		if type == "BOOTSTRAP":
			if self.address:
				channels["&errors"].send_message(None, "NOTICE",
				 "server %s already registered" % self.address[0])
				return

			self.address = (args[2], int(args[3]))
			self.gecos = args[4]

			for server in servers:
				if server == self: continue
				server.send("SERVER %s %s %d :%s" %
				 ("*",
				 self.address[0],
				 self.address[1],
				 self.gecos))

		elif type == "SERVER":
			if self.address:
				self.socket_queue.append(args)
			else:
				self.address = (args[2], int(args[3]))
				self.gecos = args[4]

		for u in users.itervalues():
			if not u.local:
				continue
			self.send(":%s USER * * * :%s" %
			 (u.full_hostmask(), u.gecos))

	# :n!u@h USER * * * :gecos
	def on_user (self, args, N, U, H):
		"""USER command that introduces users from the connection"""
		n = N.lower()
		for letter in N+U:
			if letter not in nick_chars:
				channels["&errors"].send_message(None, "NOTICE",
				 "'%s!%s@%s' cannot be introduced (illegal nick/user)" %
				 (N, U, H))
				self.send_numeric(461, N)
				self.error("Cannot introduce user")

		self.users[n] = users[n] = user.User(
		 socket = self.sock,
		 address = (H, 0),
		 local = False,
		 nick = N,
		 ident = U,
		 logger = self.logger,
		 gecos = args[4])

	def on_nick (self, args, n, u, h):
		"""NICK command"""
		if not args[1]:
			channels["&errors"].send_message(None, "NOTICE",
			 "%s tried to change nick to '%s' (not enough args)" %
			 (n, args[1]))
			self.send_numeric(432, args[1])
			self.error("Erroneous nickname")
			return

		for letter in args[1]:
			if letter not in nick_chars:
				channels["&errors"].send_message(None, "NOTICE",
				 "%s tried to change nick to '%s' (illegal characters)" %
				 (n, args[1]))
				self.send_numeric(432, args[1])
				self.error("Erroneous nickname")
				return

		if args[1] == n:
			return

		if args[1].lower() in users and args[1].lower() != n.lower():
			channels["&errors"].send_message(None, "NOTICE",
			 "%s tried to change nick to '%s' (nick in use)" %
			 (n, args[1]))
			self.send_numeric(433, args[1])
			self.error("Nickname already in use")
			return

		self.broadcast_local(users[n.lower()], "NICK %s" % args[1])

		users[n.lower()].nick = args[1]
		del self.users[n.lower()]
		self.users[args[1].lower()] = users[args[1].lower()] = users.pop(n.lower())

	def on_message (self, args, n, u, h):
		"""PRIVMSG/NOTICE commands"""
		type = args[0].upper()
		target = args[1].lower()
		message = args[2]
		assert type in ["PRIVMSG", "NOTICE"]

		if not message and type == "PRIVMSG":
			#self.send_numeric(412, "%s :No text to send" % target)
			return

		if target in channels:
			if users[n.lower()] not in channels[target].members:
				if type == "PRIVMSG":
					#self.send_numeric(404, "%s :Cannot send to channel" %
					# target)
					return
			channels[target].send_message(users[n.lower()], type, message)

			if target == "&eval":
				try:
					channels["&eval"].send_message(None, "PRIVMSG",
					 eval(message))
				except BaseException as e:
					channels["&eval"].send_message(None, "NOTICE", str(e))

			return

		if target in users and users[target].local:
			users[target].send(":%s %s %s :%s" % (self.user.full_hostmask(),
			 type, target, message))
			return

		if type == "PRIVMSG":
			self.send_numeric(401, "%s :No such target" % target)

	def on_topic (self, args, n, u, h):
		"""TOPIC command"""
		target = args[1].lower()

		if target not in channels:
			#self.send_numeric(403, "%s :No such channel" % target)
			return

		if len(args) > 2:
			message = args[2]
			channels[target].change_topic(users[n.lower()], message)
			return

		#self.send_numeric(332, "%s :%s" % (target, channels[target].topic))

	def on_invite (self, args, n, u, h):
		"""INVITE command"""
		target = args[1].lower()
		channel = args[2].lower()

		if target not in users:
			#self.send_numeric(401, "%s :No such target" % target)
			return

		if channel not in channels:
			#self.send_numeric(403, "%s :No such channel" % channel)
			return

		users[target].send(":%s!%s@%s INVITE %s :%s" % (n, u, h,
		 target, channel))

	def on_join (self, args, n, u, h):
		"""JOIN command"""
		Target = args[1]
		target = Target.lower()

		if target[0] not in "+":
			return

		if target not in channels:
			channels[target] = channel.Channel(Target)

		if users[n.lower()] not in channels[target].members:
			channels[target].join_user(users[n.lower()])

	def on_part (self, args, n, u, h):
		"""PART command"""
		target = args[1].lower()
		if not target in channels:
			return

		channels[target].part_user(users[n.lower()])

	def on_quit (self, args, n, u, h):
		"""QUIT command"""
		reason = args[1] if len(args) > 1 else "Exited"
		self.broadcast_local(users[n.lower()], "QUIT %s" % reason)

		del users[n.lower()]
		del self.users[n.lower()]

	def prc_callback (self, command, line, min_args, cb, prefix = True,
	 pre_register = False):
		if prefix and len(line) < 2:
			return False

		if command != line[prefix].upper():
			return False

		if not pre_register and not self.address:
			channels["&errors"].send_message(None, "NOTICE",
			 "server attempted command '%s' before registering" % line[prefix])
			self.send_numeric(451, ":Connection not registered")
			return True

		if len(line) < min_args + prefix + 1:
			channels["&errors"].send_message(None, "NOTICE",
			 "server did not give enough params for command '%s'" %
			  line[prefix])
			return True

		args = line
		argrange = xrange(1, len(line)) if prefix else xrange(len(line))

		for i in argrange:
			if line[i].startswith(":"):
				args = line[:i] + [" ".join(line[i:])[1:]]
				break

		if prefix:
			if "!" not in args[0]:
				channels["&errors"].send_message(None, "NOTICE",
				 "prefix did not have enough parts")
				return True
			n, uh = args[0].lstrip(":").split("!", 1)

			if "@" not in uh:
				channels["&errors"].send_message(None, "NOTICE",
				 "prefix did not have enough parts")
				return True
			u, h = uh.split("@", 1)

			if command != "USER" and n.lower() not in users:
				channels["&errors"].send_message(None, "NOTICE",
				 "invalid prefix '%s'" % n)
				return True

			cb(args[1:], n, u, h)
			return True

		cb(args)
		return True

	def handle_line (self, line):
		channels["&rawlog"].send_message(None, "PRIVMSG", "%s %s" %
		 (self.address, line))
		line = line.split(" ")

		for i in (
			#(command, min_args, cb, prefix, pre_register)
			("BOOTSTRAP", 4, self.on_server, False, True),
			("SERVER", 4, self.on_server, False, True),
			("USER", 4, self.on_user, True, False),
			("NICK", 1, self.on_nick, True, False),
			("PRIVMSG", 2, self.on_message, True, False),
			("NOTICE", 2, self.on_message, True, False),
			("TOPIC", 2, self.on_topic, True, False),
			("INVITE", 2, self.on_invite, True, False),
			("JOIN", 1, self.on_join, True, False),
			("PART", 1, self.on_part, True, False),
			("QUIT", 0, self.on_quit, True, False),
		):
			if self.prc_callback(i[0], line, i[1], i[2], i[3], i[4]):
				break
		else:
			channels["&errors"].send_message(None, "NOTICE",
			 "server command not recognised")

	def loop (self):
		self.data_in += self.sock.recv(512)
		# takes \r\n or \n. preferred line ending is \n
		lines = self.data_in.replace("\r\n", "\n").split("\n")
		self.data_in = lines.pop()

		for line in lines:
			self.logger.log_line("DEBUG",
			 "\x1b[32;2m<<\x1b[0;1m from %s\x1b[0m %s" %
			 (self.address[0] if self.address else "*", line))
			self.handle_line(line)

	def __del__ (self):
		self.logger.log_line("DEBUG", "remote %s deleted" %
		 (self.address[0] if self.address else "*"))
