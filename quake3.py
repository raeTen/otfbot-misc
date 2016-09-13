# -*- coding: utf-8 -*-
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
#Parts taken and improved from
#http://misc.slowchop.com/misc/wiki/pyquake3
#Copyright (C) 2006-2007 Gerald Kaszuba
#Since the url isn't working, here is _another_ modified 'backup' :)
# (c) 2014-2016 neTear
""" id3 - engine server status + ircbot rcon plugin + "pyquake" "libfunctions
Update: you now need to be an authenticated user to set/change the channel->"game-server url"
Nevertheless, you might want FORCE_AUTH set to False, but think of the abusiveness, I recommend
not to do so.
The plugin handles one game-server per channel, but (only) one rconpassword per user as well.
Should be enough for most cases.
Setting the rconpassword implicates rcon-functionalities. Simple 'status' from server
will be queried without password while the gameserver isn't configured as "private"

New: polling for: mapchanges and left players too, some bugs and issues fixed
New: Holding list of maps from server, most times the pk3 complies to mapname (bsp), we take both,
the name of pk3 and bsp values from server as unique, so it may happen that a given mapname 
does not work.
But we could search for them according to the order of given letter(s)/digit(s)
"""
###############################################################################################
from otfbot.lib import chatMod
from otfbot.lib.pluginSupport.decorators import callback
import twisted.internet.task as timehook
from difflib import Differ
import time, pickle, atexit,os #bot
import re, socket,sys #IOuake
FORCE_AUTH=True
INFORM_ABOUT_JOINED_GAMERS=True
INFORM_ABOUT_LEFT_GAMERS=True
INFORM_ABOUT_MAPCHANGES=True

POLLTIME_TIMER=4
POLLTIME_SERVER_MINIMUM=8 #32
POLLTIME_SERVER_DEFAULT=30
DEFAULT_GAME_BOT = "sarge"
DEFAULT_GAME_BOT_TEAM ="BLUE"
class Gamer:
	def __init__(self, name, frags, ping, num='n/a', address='n/a', qport='n/a', qrate='n/a'):
		self.name = name
		self.frags = frags
		self.ping = ping
		self.num = num
		self.address = address
		self.qport = qport
		self.qrate = qrate
	def __str__(self):
		return self.name
	def __repr__(self):
		return str(self)

class IOQuake:
	pre='\xff\xff\xff\xff'
	gamer_reo = re.compile(r'^([+-]?(?<!\.)\b[0-9]+\b(?!\.[0-9])) (\d+) "(.*)"')
	com_error=''
	def __init__(self, server, rcon_password=''):
		self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.set_server(server)
		self.set_rcon_password(rcon_password)
	def set_server(self, server):
		self.address, self.port = server.split(':')
		self.port = int(self.port)
		try:
			self.s.connect((self.address, self.port))
		except:
			pass
	def get_address(self):
		return '%s:%s' % (self.address, self.port)
	def set_rcon_password(self, rcon_password):
		self.rcon_password = rcon_password
	def send_packet(self, data):
		try:
			self.s.send('%s%s\n' % (self.pre, data))
		except:
			pass

	def recv(self, timeout=1):
		self.s.settimeout(timeout)
		try:
			return self.s.recv(4096)
		except socket.error, e:
			raise Exception('Fatal error receiving the packet: %s' % e[1] )
	def set_com_error(self,err):
		if not self.com_error:
			self.com_error=err
	def q3command(self, cmd, timeout=1, retries=3):
		while retries:
			self.send_packet(cmd)
			try:
				data = self.recv(timeout)
			except:
				self.set_com_error('Socket time out, Server not available <'+\
						str(self.address)+':'+str(self.port)+'>')
				return None, None
			if data:
				return self.parse_packet(data)
			retries -= 1
	def rcon(self, cmd):
		return self.q3command('rcon "%s" %s' % (self.rcon_password, cmd))
	def parse_packet(self, data):
		if data.find(self.pre) != 0:
			self.set_com_error('Invalid packet <check server:port>')
		first_line_length = data.find('\n')
		if first_line_length == -1:
			self.set_com_error('Invalid packet <check server:port>')
			#type data style
		return data[len(self.pre):first_line_length], data[first_line_length+1:]
	def parse_status(self, data):
		split = data[1:].split('\\')
		values = dict(zip(split[::2], split[1::2]))
		# \n parts gamernames
		for var, val in values.items():
			pos = val.find('\n')
			if pos == -1:
				continue
			split = val.split('\n', 1)
			values[var] = split[0]
			self.parse_gamers(split[1])
		return values
	def parse_gamers(self, data):
		self.gamers = []
		for player in data.split('\n'):
			if not player:
				continue
			match = self.gamer_reo.match(player)
			if not match:
				print 'couldnt match', player
				continue
			frags, ping, name = match.groups()
			self.gamers.append(Gamer(name, frags, ping))
	##################################################################
	def get_sv_vars(self):
		cmd, data = self.q3command('getstatus')
		if self.com_error=='':
			self.vars = self.parse_status(data)
		else:
			self.vars={}
	def get_sv_var(self,varname):
		cmd, data = self.rcon(varname)
		if data:
			if varname in data:
				data=data.split(':')
				rt=data[1].split('"')
				return rt[1]
		return False
	def get_gamer_status(self):
		cmd, data = self.rcon('status')
		if not cmd:
			return False
		lines = data.split('\n')
		if lines[0].lower()[:8]=='bad rcon':
			return 'bad rcon'
		players = lines[3:]
		self.gamers = []
		for p in players:
			while p.find('  ') != -1:
				p = p.replace('  ', ' ')
			while p.find(' ') == 0:
				p = p[1:]
			if p == '':
				continue
			p = p.split(' ')
			#                         name,      frags,ping, num ,addr  qport qrate
			self.gamers.append(Gamer(p[3][:-2], p[1], p[2], p[0],p[5], p[6], p[7]))
		return True

###################################################################################
######################### q3-server-rcon LIBRRARY PARTS ABOVE #####################
######################### bot plugin part below ###################################
###################################################################################
class Plugin(chatMod.chatMod):
	def __init__(self, bot):
		self.bot = bot
		self.q3_2_mirc_color_init()
		self.q3server=self.serverdata()
		self.nTimer=timehook.LoopingCall(self.nTimerhook)
		self.datadir=self.check_datapath(datadir+'/')
		atexit.register(self.exithook)
		self.q3server.load(self.datadir,self.bot.network)
		self.nHook=0
		self.consoleCommands=self.load_console_commands()

	def load_console_commands(self):
		""" 
		The txt file should be a tab-separated like  
		<varname> [whitespace] <varvalue> \t <description> \t [<optional info>]
		You could simply produce it from http://www.joz3d.net/html/q3console.html
		by storing it as text-file from your beloved browser
		The text-file should be present in the plugin datadir, otherwise the command-feature won't work.
		In respect of copyright, I don't distribute it here since there are a lot of good overviews at all.
		"""
		txtf=datadir+'/quake3.console.txt'
		rtdict={}
		if os.path.isfile(txtf):
			for l in open(txtf).readlines():
				l=l.replace("\n","")
				if len(l) > 5 and l[0]!='#':
					detabbed=l.split('\t')
					gvars=detabbed[0].split(" ",1)
					dictvals = [gvars[1]]
					for n in range(0,len(detabbed)):
						if n > 0:
							dictvals.append(detabbed[n].strip())
					while len(dictvals) < 5:
						dictvals.append(" ")
					if not gvars[0] in rtdict:
						rtdict[gvars[0]] = dictvals
		return rtdict

	def handle_console_commands(self, searchFor):
		searchFor=searchFor.encode('ascii')
		rt = []
		qty = 0
		for gcommand in self.consoleCommands:
			if gcommand[0:len(searchFor)] == searchFor:
				if not gcommand in rt:
					rt.append(gcommand)
			if (self.consoleCommands[gcommand])[1].count(searchFor) > 0:
				if not gcommand in rt:
					rt.append(gcommand)
		return rt

	def exithook(self):
		self.q3server.save(self.datadir,self.bot.network)

	def check_datapath(self,chkpath):
		if (not os.path.isdir(os.path.dirname(chkpath))):
			try:
				os.makedirs(os.path.dirname(chkpath))
			except:
				self.bot.logger.error("Error, creating "+chkpath)
		if (os.path.isdir(os.path.dirname(chkpath))):
			return chkpath

	class serverdata():
		def __init__(self):
			self.userdict={}
			self.serverdict={}
			self.maplist=[]
			self.polldict={}
			self.poll_ts={}
		def addpassw(self, user, rconpw):
			self.userdict[str(user)] = rconpw
		def getpassw(self, user):
			return self.userdict.get(str(user),'').encode('ascii')
		def addsv(self,channel,serverlink):
			self.serverdict[channel]=serverlink
		def getsv(self, channel):
			return self.serverdict.get(channel,'').encode('ascii')
			return self.serverdict.get(channel,'')[0][0].encode('ascii')
		def set_poll_ts(self, channel,ts):
			self.poll_ts[channel]=ts
		def get_poll_ts(self,channel):
			return int(self.poll_ts[channel])
		def pollsv(self, channel, user, polltime):
			if polltime < POLLTIME_SERVER_MINIMUM:
				if channel in self.polldict:
					del self.polldict[channel]
					return False
			else:
				svlink=self.getsv(channel)
				if svlink:
					rpw=self.getpassw(user)
					if rpw:
						q=IOQuake(svlink, rpw)
						hostname=q.get_sv_var('sv_hostname')
						mapname=q.get_sv_var('mapname')
						if hostname: #ensure correct rconpass initially
							self.polldict[channel]={
								'channel':channel,\
								'user':user,\
								'hostname':hostname,\
								'actgamers':[],\
								'polltime':polltime,\
								'actmap':mapname,\
								}
							self.set_poll_ts(channel,int(time.time())+polltime)
							self.pollupdate(q,channel,True)
							return True
		def pollupdate(self,q,channel,init=False):
			status=q.get_gamer_status() #polling via rcon status has to be with given rconpassw
			if status:
				if status=='bad rcon':
					return "error","bad rcon - Polling off"
				else:
					actlist=[]
					for gamer in q.gamers:
						actlist.append(gamer.name)
					diff = self.polldiff(channel, actlist)
					self.polldict[channel]['actgamers'] = actlist
					return diff
			else:
				return "error","connection not established - Polling off"
		def polldiff(self, channel, actlist):
			rtlist=[] #newplayers since last poll
			for new in Differ().compare(self.polldict[channel]['actgamers'],actlist):
				new=new.split(' ')
				if new[0]=='+':
					rtlist.append('+'+new[1])
				if new[0] == '-':
					rtlist.append('-'+new[1])
			return rtlist
		def getchannels(self):
			channellist=[]
			for k in self.polldict.keys():
				channellist.append(self.polldict[k]['channel'])
			return channellist,self.polldict
		def pollstopall(self):
			self.q3server.polldict={}
			self.q3server.poll_ts={}
		def pollstop(self,channel):
			try:
				del self.polldict[channel]
				del self.poll_ts[channel]
			except:
				pass
		def reset(self, user, channel):
			try:
				del self.serverdict[channel]
				self.addpassw(user,'')
			except:
				pass
			return "Done"
		def save(self,datadir,network):
			try:
				with open(datadir+network+'_user.dat', 'w') as ufile:
					pickle.dump(self.userdict,ufile)
					ufile.close()
			except:
				pass
			try:
				with open(datadir+network+'_server.dat', 'w') as sfile:
					pickle.dump(self.serverdict,sfile)
					sfile.close()
			except:
				pass
		def load(self, datadir,network):
			try:
				with open(datadir+network+'_user.dat', "r") as ufile:
					self.userdict=pickle.load(ufile)
					ufile.close()
			except:
				pass
			try:
				with open(datadir+network+'_server.dat', "r") as sfile:
					self.serverdict=pickle.load(sfile)
					sfile.close()
			except:
				pass

	def q3_2_mirc_color_init(self):
		"""
		red = \x034 x035 | green = x033 x039 | yellow = x038 x037 is known as ^8 orange
		blue  = x032 x0312  | cyan = x0310 x0311 | magenta = x036 x0313 | white = x0315 0314 grey
		orange alias darkyellow
		"""
		self.colors={}
		colors={'^1':4,'^2':3,'^3':7,'^4':2,'^5':10,'^6':13,'^7':17,'^8':7}
		for color in colors:
			self.colors[color]="\x03"+str(colors[color]).encode('utf-8')

	def q3_update(self,user,channel):
		q=IOQuake(self.q3server.getsv(channel), self.q3server.getpassw(user))
		q.get_sv_vars()
		if q.com_error:
			return q.com_error #str else instance
		return q

	def q3_clean_string(self,astring):
		cleanfrom=[]
		cleanfrom = re.findall('\^[0-9]', astring)
		cleanfrom.append('"')
		cleanfrom.append('\\n')
		for match in cleanfrom:
			astring=astring.replace(match,'')
		return astring.strip()

	def q3_send_rcon(self,q3_cmd, user,channel, complete=False):
		q=IOQuake(self.q3server.getsv(channel), self.q3server.getpassw(user))
		if not q:
			return "Given network not reachable"
		rtcmd, rtdata = q.rcon(q3_cmd.encode('ascii'))
		if complete:
			return rtdata
		if rtcmd:
			rt=''
			lines=rtdata.split("\n")
			for line in lines:
				if line:
					if line.find('kicked') != -1 or line.find('entered') != -1 or line.find('Server') != -1:
						line=line.replace('was kicked\n','')
						line=line.replace('broadcast:','')
						line=line.replace('print','')
						line=line.replace('\n','')
						rt=rt+line
					if line.lower()[0:8] == 'bad rcon':
						self.q3server.addpassw(user, "")
			if len(rt)==0:
				for line in lines:
					rt=rt+' '+line.strip()
			#irc limit
			add=''
			if len(rt)>422:
				add='[...]'
			return (self.q3_clean_string(rt)[0:422]+add) #.encode('ascii')

	def q3color2irc(self, astring):
		astring.replace('\n','')
		for color in self.colors.keys():
			if astring.count(color):
				val=self.colors.get(color, "")
				astring = astring.replace(color,val)
		return '\x02\x037,16'+astring+'\x0F'

	def q3players2irc(self,q):
		allgamers=''
		for gamer in q.gamers:
			if gamer.ping=='0':
				if gamer.name.find('.') != -1:
					gamer.name=gamer.name.split('.')[1]
			allgamers=allgamers+'%s%s  ' % (self.q3color2irc(gamer.name),\
								'\x0317,16\x02['+gamer.frags+']\x02\x0F')
		return allgamers

	def q3gamedata2irc(self,q):
		if not isinstance(q, str):
			if len(q.gamers) > 8:
				return 'MAP:%s|' % ('\x02'+q.vars['mapname']+'\x02')
			elif len(q.gamers) > 4:
				return '%s MAP:%s (%s/%s)|' % ('\x0F'+self.q3color2irc(q.vars['sv_hostname']),\
					'\x02'+q.vars['mapname']+'\x02', len(q.gamers),q.vars['sv_maxclients'])
			elif len(q.gamers) <= 4:
				return '%s@%s MAP:%s (%s/%s)|' % \
					('\x0F'+self.q3color2irc(q.vars['sv_hostname']), q.get_address(),\
					'\x02'+q.vars['mapname']+'\x02', len(q.gamers),q.vars['sv_maxclients'])
		else:
			return q

	def q3_sv_status(self,q):
		if not isinstance(q, str):
			return self.q3gamedata2irc(q)+self.q3players2irc(q)
		else:
			return q

	def check_q3_cmd(self,user, options,ls=False):
		if not ls:
			if options.count('dir'):
				options=''
		parts = options.split(" ")
		""" using an optional internal 'addbot' from irc, addbot bot_nickanme [level][team] """
		if parts[0] == 'addbot':
			qbotlevel = 50
			qbotteam=DEFAULT_GAME_BOT_TEAM
			qbotnick = ''
			if len(parts) >= 2:
				qbotnick = parts[1].encode('ascii')
				if len(parts) >= 3:
					qbotlevel = parts[2].encode('ascii')
					print qbotlevel
					try:
						qbotlevel=int(qbotlevel)
					except:
						qbotlevel = 66
						pass
					if len(parts) >= 4:
						qbotteam=parts[3].upper()
				options="addbot "+DEFAULT_GAME_BOT+" "+str(qbotlevel)+" "+qbotteam+" 0 0 "+qbotnick
				print options
		return options, self.q3server.getpassw(user)

	def check_server_link(self,options):
		ded = '(?:ded.*://)?(?P<host>[^:/ ]+).?(?P<port>[0-9]*).*'
		match = re.search(ded, options)
		if match:
			match.group('host')
			match.group('port')
			if match.group('host') and match.group('port'):
				link=match.group('host')+':'+match.group('port')
				return link
			else:
				return False

	def poll_init(self,q3server,user,channel,polltime):
		if polltime=='off':
			polltime = 0
		try:
			t_polltime=int(polltime)
		except:
			t_polltime=POLLTIME_SERVER_DEFAULT
			pass
		if t_polltime > 999:
			t_polltime = 999
		if INFORM_ABOUT_JOINED_GAMERS or INFORM_ABOUT_LEFT_GAMERS or INFORM_ABOUT_MAPCHANGES:
			if not self.nTimer.running:
				self.bot.logger.info('Starting poll timer')
				self.nHook=0
				self.nTimer.start(POLLTIME_TIMER)
			if self.q3server.pollsv(channel,user,t_polltime):
				addmsg=""
				addmsg = "Gamers join" if INFORM_ABOUT_JOINED_GAMERS else addmsg
				addmsg = addmsg+"|Gamers left" if INFORM_ABOUT_LEFT_GAMERS else addmsg
				addmsg = addmsg+"|Mapchanges" if INFORM_ABOUT_MAPCHANGES else addmsg
				self.bot.sendmsg(channel, user.getNick()+':Polling every '+str(t_polltime)+\
						' seconds for '+addmsg+' on '+q3server)
			else:
				self.bot.sendmsg(channel, user.getNick()+":Polling stopped for "+q3server)
		else:
			self.bot.sendmsg(channel, user.getNick()+":Not configured for polling "+q3server)

	def poll_update(self,act_ts):
		channellist,polldict=self.q3server.getchannels()
		for channel in channellist:
			ch_ts=self.q3server.get_poll_ts(channel)
			if ch_ts < act_ts:
				t_polltime=self.q3server.polldict[channel]['polltime']
				self.q3server.set_poll_ts(channel,act_ts+t_polltime)
				rpw=self.q3server.getpassw(polldict[channel]['user'])
				svlink=self.q3server.getsv(channel)
				q=IOQuake(svlink, rpw)
				gamers=self.q3server.pollupdate(q ,channel, False)
				svhostname = self.q3color2irc(self.q3server.polldict[channel]['hostname'])
				if gamers:
					ngamers=''
					a_gamers=''
					d_gamers=''
					if gamers[0]=='error':
						self.q3server.pollstop(channel)
						self.bot.sendmsg(channel, svhostname+':'+svlink+':'+gamers[1])
					else:
						amsg=''
						for ngamer in gamers:
							a_d=ngamer[0]
							ngamer=ngamer[1:]
							if a_d == '+' and INFORM_ABOUT_JOINED_GAMERS:
								a_gamers=a_gamers+self.q3color2irc(ngamer)+' '
							elif a_d == '-' and INFORM_ABOUT_LEFT_GAMERS:
								d_gamers=d_gamers+self.q3color2irc(ngamer)+' '
						if len(a_gamers) > 0:
							amsg="Gamers joined game: "+a_gamers
						if len(d_gamers) > 0:
							amsg=amsg+'Gamers left game:'+d_gamers
						self.bot.sendmsg(channel,svhostname+' '+amsg)
				if INFORM_ABOUT_MAPCHANGES:
					try:
						qmap = q.get_sv_var('mapname')
						if self.q3server.polldict[channel]['actmap'] != qmap:
							self.q3server.polldict[channel]['actmap'] = qmap
							qmap = qmap.rsplit('^', 1)[0]
							self.bot.sendmsg(channel,svhostname+' Map changed to: \x034'+qmap)
					except:
						self.bot.logger.debug(str(sys.exc_info()[1]))
						pass

	def nTimerhook(self):
		act_ts=int(time.time())
		self.poll_update(act_ts)
		if len(self.q3server.polldict) == 0:
			self.nHook+=1
		if self.nHook > 2:
			self.bot.logger.info('Stopping poll timer')
			try:
				self.nTimer.stop()
			except:
				pass
			self.nHook=0

	def multi_command(self,command):
		command=command.lower();
		self.kcs=["oa","openarena","ioquake","ioquake3","quake","quake3",\
				"q3","et","etw","wolfenstein","pad","padman","wop"]
		if command in self.kcs:
			return command
		return False

	@callback
	def connectionLost(self,reason):
		self.q3server.save(self.datadir,self.bot.network)
	@callback
	def connectionMade(self):
		self.q3server.load(self.datadir,self.bot.network)
	@callback
	def reload(self):
		self.q3server.load(self.datadir,self.bot.network)

	@callback
	def query(self, user, channel, msg):
		if channel != user.getNick():
			cmd=msg.split()
			if cmd:
				if self.multi_command(cmd[0]): #in known cmd for game
					if len(cmd)==3:
						if cmd[1].lower()[0:9]=='rconpassw':
							try:
								newrconpass=cmd[2]
							except:
								pass
								newrconpass=''
						if newrconpass:
							self.q3server.addpassw(user,newrconpass)
							self.bot.notice(user.getNick(),"rconpassword set")
					elif len(cmd)==2:
						if cmd[1].lower()=='pollstop':
							self.bot.notice(user.getNick(),"Ok polling stopped")
							self.q3server.pollstopall()
						if cmd[1].lower()=='show':
							print self.q3server
	def check_auth(self, user, channel):
		if FORCE_AUTH:
			if not self.bot.auth(user):
				self.bot.sendmsg(channel, "Please authenticate!")
				return False
		return True
	
	def getMaplist(self, user, channel, force=False):
		if len(self.q3server.maplist) == 0 and not force:
			self.q3server.maplist =  []
			maplist=self.q3_send_rcon("dir ./../baseoa pk3", user, channel, True).split('\n')
			for gmap in maplist:
				if not gmap in self.q3server.maplist:
					self.q3server.maplist.append(gmap.split('.')[0])
			maplist=self.q3_send_rcon("dir ./../cpma pk3", user, channel, True).split('\n')
			for gmap in maplist:
				if not gmap in self.q3server.maplist:
					self.q3server.maplist.append(gmap.split('.')[0])
			maplist=self.q3_send_rcon("dir maps bsp", user, channel, True).split('\n')
			for gmap in maplist:
				if not gmap in self.q3server.maplist:
					self.q3server.maplist.append(gmap.split('.')[0])
			self.q3server.maplist.sort()

	def resolveMap(self, user, channel, search):
		rt = ''
		qty = 0
		for gmap in self.q3server.maplist:
			if gmap[0:len(search)] == search:
				qty += 1
				rt=gmap+' '+rt
		return qty, rt

	def requestOneChar(self,channel,nick):
		self.bot.sendmsg(channel, nick+": Give one or more character(s) to search for, please.")

	@callback
	def command(self, user, channel, command, options):
		if channel != self.bot.nickname:
			#initial value check
			if self.multi_command(command):
				q3server=self.q3server.getsv(channel)
				if options.find(':') != -1:
					given_sv_link=self.check_server_link(options)
					if given_sv_link:
						q3server=given_sv_link
						if self.check_auth(user, channel):
							self.q3server.addsv(channel, given_sv_link)
							self.bot.sendmsg(channel, user.getNick()+": Gameserver set to:"+given_sv_link) 
						else:
							return False
				if q3server=='':
					self.bot.sendmsg(channel, 'Which server? !'+command+' <ded://host:port>  (should work with any id3/4-engine)')
				#server status and gamer list without rconpassw
				if self.multi_command(command) and options == '' and q3server!='':
					rmsg=self.q3_sv_status(self.q3_update(user,channel)).encode('utf-8')
					self.bot.sendmsg(channel, rmsg)
				#rcon functionality for user with given rconpassword only
				if self.multi_command(command) and options != '' and q3server !='':
					q3_cmd, rconpassword=self.check_q3_cmd(user, options)
					if rconpassword != '':
						loptions=options.split()
						if loptions[0] == 'poll':
							if len(loptions)>1:
								polltime=loptions[1]
							else:
								polltime=POLLTIME_SERVER_DEFAULT
							self.poll_init(q3server,user,channel,polltime)
						elif loptions[0] == 'pollstop':
							self.bot.sendmsg(channel, user.getNick()+"Ok polling stopped")
							self.q3server.pollstopall()
						elif loptions[0] == 'command':
							"""handle information about server rcon commands and vars"""
							if len(loptions) < 1:
								self.requestOneChar(channel, user.getNick())
							else:
								rt = self.handle_console_commands(loptions[1])
								if len(rt) == 1:
									bmsg=("\x02"+rt[0] + "\x0F " +(" ".join(self.consoleCommands[rt[0]]))).strip()
									self.bot.sendmsg(channel,bmsg)
								else:
									bmsg=("|".join(rt))
									if len(bmsg) > 512:
										bmsg=bmsg[0:512]+' ...'
									self.bot.sendmsg(channel,bmsg)
						elif loptions[0][0:3] == 'map':
							""" internal map and maplist handling"""
							param=loptions[1] if len(loptions) >= 2 else ''
							nparam=loptions[2] if len(loptions) >= 3 else ''
							force=True if nparam == 'update' else False
							self.getMaplist(user, channel, force)
							if len(param) > 0:
								qty, maps=self.resolveMap(user, channel, loptions[1])
							else:
								self.requestOneChar(channel, user.getNick())
								return False
							qty, maps=self.resolveMap(user, channel, loptions[1])
							if qty == 1:
								self.bot.sendmsg(channel, self.q3_send_rcon("map "+maps, user, channel, False))
							elif qty > 1:
								self.bot.sendmsg(channel, maps)
						elif loptions[0] == 'reset':
							if self.check_auth(user, channel):
								self.q3server.pollstop(channel)
								feedback = self.q3server.reset(user, channel)
							else:
								return False
						else:
							if options != "":
								feedback = self.q3_send_rcon(q3_cmd,user,channel)
								if feedback:
									self.bot.sendmsg(channel, feedback.encode('ascii'))
					else:
						self.bot.sendmsg(channel ,user.getNick()+\
								':Please send in the rconpassword via /msg '+\
								self.bot.nickname+' '+\
								command.encode('ascii')+' rconpassword <the_password>)'.encode('ascii') )