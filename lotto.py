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
####
# (c) 2014 2015 neTear
from otfbot.lib import chatMod
from otfbot.lib.pluginSupport.decorators import callback
import random, re

class Plugin(chatMod.chatMod):
	""" generates x {bm} random numbers of y {bf}  given range, this is an easteregg 'cause it may react on (!command like) """

	def __init__(self, bot):
		self.bot = bot

	def do_not_play_lotto(self,loptions,key=None):
		""" hybrid parsing (msg or option) """
		if not key:
			key='617573'.encode('hex') #keep that and similar in py3 please
		numbers = []
		ZZ_known=self.config.get(key)[0:loptions.count('+')-\
					len(re.findall("[+]\w+", loptions))]\
					+re.findall("[+]\w+", loptions) #*higgs*
		zz_qty=len(ZZ_known)
		try:
			a = re.findall("\d+(?= "+key+")", loptions)[0]
			rightpart=str(a)+ ' '+key+' ' ; rightpartlen=len(rightpart)
			outofi = loptions.index(rightpart)
			outof=loptions[outofi+rightpartlen:]
			b=outof.split(" ")[0]
		except:
			pass
		try:
			bm=int(a)
			bf=int(b)
		except:
			bm=6
			bf=49
			pass
		bm=int(str(bm)[:2])
		bf=int(str(bf)[:7])
		lastresort = 0; x = 0
		bm=bm+zz_qty
		while (x < bm) and (lastresort < 255):
			pling=random.randint(1, bf)
			if not pling in numbers:
				numbers.append(pling)
				x += 1
			lastresort += 1
		addstr=""
		for addnr in ZZ_known:
			if ( zz_qty <= 0 ) or (zz_qty >= len(numbers) ):
				break
			addnr=addnr.replace("+"," ")+":"+str(numbers[-1])+' '
			del numbers[-1]
			addstr=addstr+addnr
			zz_qty -= 1
		numbers.sort()
		return str(numbers).strip('[]')+addstr

	@callback
	def start(self):
		self.config = { "from" : ["+bonus number","+the better bonus number","+the metanumber","+the ultimative"],\
						"aus" : ["+Zusatzzahl","+Sonderzahl","+Metazahl","+Hyperzahl"],\
						"da" : ["+numereo suplimento","+numero additivo","+numbero metao","+numereo eccelenza"],\
						"de" : ["+espanol","+espanol2","+espanol3","+espanol4"],\
						"partir" : ["+numero complementaire","+numero complementaire","+numero complementaire","+numero complementaire"],\
						"foobar" : ["+translate me1","+translate me2","+translate me3","+translate me14"]\
					  } #TODO
		self.knowncmd=["lotto", "lotte","loter","ellot"]#TODO setting (language) key from here?
	@callback
	def command(self, user, channel, command, options):
		if command.lower()[0:5] in self.knowncmd and options != "":
			for key in list(self.config):
				if key in options.lower():
					self.bot.sendmsg(channel, self.do_not_play_lotto(options,key).strip())
					break

	@callback
	def msg(self, user, channel, msg):
		""" lotto.py cmd or easteregg """
		if msg[0] == "!":
			return 0
		if self.bot.nickname.lower() != user.getNick().lower():
			for kcmd in self.knowncmd:
				if kcmd in msg.lower():
					for key in list(self.config):
						if key in msg.lower():
							self.bot.sendmsg(channel, self.do_not_play_lotto(msg,key).strip())
							break
