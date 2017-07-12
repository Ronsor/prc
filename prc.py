#!/usr/bin/env python

import config
import connections
import log
from time import sleep
from sys import argv

class PRCGateway ():
	def __init__ (self, logger):
		self.logger = logger
		self.conf = config.Main(argv[1], self.logger)
		self.local = connections.LocalConnections(
		 self.conf.NAME,
		 self.conf.LOCAL_BIND,
		 self.conf.OPERATOR,
		 self.logger)
		self.remote = connections.RemoteConnections(
		 self.conf.NETWORK,
		 self.conf.BOOTSTRAP,
		 self.conf.REMOTE_BIND,
		 self.conf.HOSTNAME if self.conf.HOSTNAME else None,
		 self.logger)

	def loop (self):
		self.local.loop()
		self.remote.loop()
		sleep(.1)

	def run (self):
		try:
			while True:
				self.loop()
		except KeyboardInterrupt:
			[listener.close() for listener in self.local.listeners]
			self.remote.sock.close()

if len(argv) < 2:
	exit("syntax: python %s (config filename)" % argv[0])

gateway = PRCGateway(log.logger("ERROR")).run()
