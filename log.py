#!/usr/bin/env python

class logger ():
	levels = {
	 "DEBUG"  : 1,
	 "INFO"   : 2,
	 "NOTICE" : 3,
	 "WARN"   : 4,
	 "ERROR"  : 5,
	 "NONE"   : 0
	}

	def __init__ (self, loglevel):
		self.set_level(loglevel)

	def set_level (self, loglevel):
		assert loglevel in self.levels

		self.loglevel = self.levels[loglevel]

	def log_line (self, level, message):
		assert level in self.levels

		if self.loglevel <= self.levels[level]:
			print message
			return 0
		else:
			return 1
