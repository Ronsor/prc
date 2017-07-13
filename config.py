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
import os.path

class Main():
	def __init__ (self, config_file, logger):
		self.file = config_file
		self.logger = logger
		self.rehash()

	def rehash (self):
		self.NAME = "prc.gateway"
		self.VERSION = "alpha"

		# defaults
		self.MOTD = "prc.motd"
		self.BOOTSTRAP = ""
		self.CHANNELLEN = 64
		self.LOCAL_BIND = []
		self.NETWORK = "PRCnet"
		self.NICKLEN = 9
		self.OPERATOR = {}
		self.REMOTE_BIND = ("0.0.0.0", 16700)
		self.HOSTNAME = None

		with open(os.path.join("config", self.file)) as f:
			print "config.py: Opening %s for parsing" % self.file
			lines = f.read().split("\n")

			for line in lines:
				line = line.split()
				if len(line) >= 2: line[0] = line[0].upper()

				if len(line) < 2:
					pass
				elif line[0] == "BOOTSTRAP":
					self.BOOTSTRAP = str(" ".join(line[1:]))
					self.logger.log_line("INFO", "config.py: BOOTSTRAP = %s" %
					 self.BOOTSTRAP)

				elif line[0] == "CHANNELLEN":
					self.CHANNELLEN = int(line[1])
					self.logger.log_line("INFO", "config.py: CHANNELLEN = %d" %
					 self.CHANNELLEN)

				elif line[0] == "HOSTNAME":
					self.HOSTNAME = str(line[1])
					self.logger.log_line("INFO", "config.py: HOSTNAME = %s" %
					 self.HOSTNAME)
				elif line[0] == "MOTD":
					self.MOTD = str(line[1])

				elif line[0] in ("LOCAL_BIND", "REMOTE_BIND"):
					if len(line) < 3:
						# we're expecting a tuple of 2 values: host and port
						self.logger.log_line("ERROR", "config.py: %s is not in format '%s host port'" %
						 line[0])
						exit()
					if line[0] == "LOCAL_BIND":
						self.LOCAL_BIND.append((str(line[1]), int(line[2])))
						self.logger.log_line("INFO",
						 "config.py: LOCAL_BIND += %s" % (self.LOCAL_BIND[-1],))
					elif line[0] == "REMOTE_BIND":
						self.REMOTE_BIND = (str(line[1]), int(line[2]))
						self.logger.log_line("INFO",
						 "config.py: REMOTE_BIND = %s" % (self.REMOTE_BIND,))

				elif line[0] == "LOG_LEVEL":
					self.logger.set_level( str(line[1]) )
					self.logger.log_line("INFO",
					 "config.py: LOG level = %d (%s)" %
					 (self.logger.loglevel, line[1]))

				elif line[0] == "NETWORK":
					self.NETWORK = str(line[1])
					self.logger.log_line("INFO", "config.py: NETWORK = %s" %
					 self.NETWORK)

				elif line[0] == "NICKLEN":
					self.NICKLEN = int(line[1])
					self.logger.log_line("INFO", "config.py: NICKLEN = %d" %
					 self.NICKLEN)

				elif line[0] == "OPERATOR":
					self.OPERATOR[str(line[1])] = str(line[2])
					self.logger.log_line("INFO",
					 "config.py: OPERATOR[%s] = ********" % line[1])

				elif line[0] == "SPOOF_HOSTS":
					self.SPOOF_HOSTS = bool(eval(line[1]))
					self.logger.log_line("INFO", "config.py: SPOOF_HOSTS = %d"
					 % self.SPOOF_HOSTS)

		if not self.LOCAL_BIND:
			self.LOCAL_BIND.append(("127.0.0.1", 6777))
