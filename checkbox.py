# This file is part of OtfBot.
#
# OtfBot is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# OtfBot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OtfBot; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
# (c) 2012 by Alexander Schier
# neTear thought (2014) true checkboxes as option will increase the entropy oO
# so now it is [ ] "multi"-checkboxes and a one radiobox () to be filled.
# Any number ahead in checkbox-list will be treaten as a maximum qty of checkboxes to be checked randomly,
# but there's no "minimum" value at the moment, so possibly 'bitwise' it could be "0" as nothing checked
"""
marks randomly checkboxes [ ] (or not) - and or - one radiobox ( ) from a list of checkboxes&|radioboxes
NEW: makes decisions either by given bot-command parameters "decision choice1 choice2 choiceN
or configurable keywords:lists
just put a decision.txt into plugindir. Format key=choice1 choice2 choiceN ...
called by "decision key | decision cb key"
"""
from otfbot.lib import chatMod
from otfbot.lib.pluginSupport.decorators import callback
import random, re, os
BOLD="\x02"
COLOR="\x035"
RESET="\x0F"

channel_blacklist=['#none']
class Plugin(chatMod.chatMod):
	""" checkbox radiobox plugin """
	def __init__(self, bot):
		self.bot = bot
	
	@callback
	def start(self):
		self.decide_config=datadir+'/decision.txt'
		self.decide={}
		if (not os.path.isdir(os.path.dirname(datadir+'/'))):
			try:
				os.makedirs(os.path.dirname(datadir+'/'))
			except:
				pass
		self.load_config()

	@callback
	def reload(self):
		self.start()

	def load_config(self):
		try:
			c=open(self.decide_config, "r")
			d=c.read()
			c.close()
			for l in d.split("\n"):
				if len(l) > 1:
					pair=l.split("=",1)
					self.decide[pair[0]]=pair[1].split(',')
		except:
			pass

	@callback
	def msg(self, user, channel, msg):
		""" temp ignore list for testing plugin with mulitple bots """
		if channel in channel_blacklist:
			return False
		decide_msg=msg.split()
		if decide_msg[0] == 'decide':
			w='( )'
			d_key=''
			nmsg=''
			try:
				if decide_msg[1]=='cb':
					w='[ ]'
				if decide_msg[1] in self.decide:
					d_key=decide_msg[1]
				if decide_msg[2] in self.decide:
					d_key=decide_msg[2]
			except:
				pass
			if d_key=='':
				for decision in decide_msg:
					if decision!='decide' and decision!='cb':
						nmsg=nmsg+decision+w+' '
			else:
				for decision in self.decide[d_key]:
					if decision!='decide' and decision!='cb' and decision!=d_key:
						nmsg=nmsg+decision+w+' '
			if nmsg == '':
				nmsg = "ja( ) nein( ) vielleicht( ) nachher( ) niemals( ) sofort( )"
			msg = nmsg 
		if self.bot.nickname.lower() != user.getNick().lower() and ( "[ ]" in msg or "( )" in msg):
				""" radiobox () """
				if "( )" in msg:
					parts = re.split("\( \)", msg)
					check = random.randint(1, len(parts) -1)
					count=1
					msg=parts[0]
					for part in parts[1:]:
						if check == count:
								msg += "("+BOLD+COLOR+"X"+RESET+")"
						else:
								msg += "( )"
						msg += parts[count]
						count += 1
				""" checkboxes [] """
				parts = re.split("\[ \]", msg)
				toptions = []
				bf=len(parts)-1
				try:
					bm=int(msg.split(" ")[0])
				except:
					pass
					bm=bf 
				x = 0
				while (x < bm) :
					toptions.append(random.randint(0, bf))
					x += 1
				count=1
				msg=parts[0]
				for part in parts[1:]:
					if count in toptions:
						msg += "["+BOLD+COLOR+"X"+RESET+"]"
					else:
						msg += "[ ]"
					msg += parts[count]
					count += 1
				self.bot.sendmsg(channel, msg)
	
	@callback
	def query(self, user, channel, msg):
		if msg[0:8]=='checkbox':
			self.bot.logger.info("checkbox:"+str(user)+str(channel)+str(msg))
			msg=msg.replace("%","") #FIXME
			msg=msg[8:]
			c_channel=''
			if len(msg) > 2:
				c_channel=msg.split()[0]
			if len(c_channel) > 2:
				if c_channel in blacklist:
					blacklist.remove(c_channel)
				else:
					if c_channel in self.bot.channels:
						blacklist.append(c_channel.encode('ascii'))
			self.bot.sendmsg(user.getNick(),str(blacklist))
			
			