# -*- coding: utf-8 -*-
# This file is an optional part of OtfBot.
# GPL2'ed
"""
The NIP-game plugin isn't really suitable to be run within more than one channel on one network at the same time.
For now it's "multi-network" since every configured network will have its own data(files).
Starting a game is possible within any _configured_ channel 
in bot config.
TODO multi language (I'll create an intial translation table by the time the game has become more famous)
#Floodprotection and completing/suggestion bot-commands are obsolete within the game, 
since they are now ported to the bot itself
New: Quizmaster will get one point for sending in a NIP-Question/answer, and -1 point if he did not
"""
###################################################################################################
#Have fun!
NIPRELEASE="1.0.9"
DEFAULT_GAME_CHANNELS="#nip" 
#NIP_RULES_LINK="Wer suchet der findet."
NIP_RULES_LINK="https://otfchat.otfbot.org/games/nobody-is-perfect (TODO cp2wp)"
NIP_SOURCE_LINK="https://github.com/raeTen/otfbot-misc/blob/master/nip.py"
HELPUSER="MitNipper -> #CCHAR#join #CCHAR#part (mitspielen/aussteigen) #CCHAR#score #CCHAR#rules #CCHAR#players"
HELPADMIN="Admin -> #CCHAR#restartgame #CCHAR#add/remove MitNipper #CCHAR#gamespeed #CCHAR#autoremove #CCHAR#autorestart #CCHAR#kill "
HELPBUG="Genervte #BOLD#irssi#BOLD#-Anwender moegen ein \"/set mirc_blink_fix on\" machen."
DEFAULT_COLOR_DECORATOR="™ "
""" set NIP_SPOIL to True only if your configuration uses real irc hostnames as network (name)configuration"""
NIP_SPOIL=False
#other internal config values
DEFAULT_NIP_MIN_PLAYER=5
DEFAULT_NIP_MAX_PLAYER=24
DEFAULT_MAX_NICK_LEN=13
AUTOREMOVE_PLAYER_AFTER_ROUNDS_OF_INACTIVITY=2 # !autoremove
NIP_TIMEOUT_BASE=60 #seconds,

""" defines game phases do not edit """
NO_GAME=0
WAITING_FOR_PLAYERS=1
WAITING_FOR_QUESTION=2
WAITING_FOR_QUIZMASTER_ANSWER=3
WAITING_FOR_ANSWERS=4
QUIZ=5
GAME_WAITING=6

from otfbot.lib import chatMod
from otfbot.lib import functions
from otfbot.lib.pluginSupport.decorators import callback
import twisted.internet.task as timehook # ugh
import shutil, time, random, string, os
import math, pickle, atexit
import operator
import sys
import gc

#FIXME ! #remove the del for twisted debugging and finally if fixed
from twisted.internet.defer import DebugInfo
del DebugInfo.__del__  
#from twisted.internet.defer import setDebugging
#setDebugging(True)
# dropping errors is a monkey solution, but the 
#"unhandled error in deferred" +  "NoneType" object has no attribute "errback"...
#Everything with twisted.internet.task.LoopingCall works fine, until LoopingCall.stop() is called _and_ not started 'immediately' again.
#Just stumbled about how to save objects from being destroyed by garbagecollection
# http://stackoverflow.com/questions/107705/disable-output-buffering
#    gc.garbage.append(sys.stdout)
#this should fix nTimer.stop()  "unhandled error in deferred"
#well, but it does not
#will have a deeper look a twisted - game still works fine at all...

class Plugin(chatMod.chatMod):
	
	def __init__(self, bot):
		self.bot=bot
		
	def start(self):
		atexit.register(self.nipexithook)
		self.fav=self.favorits()
		self.NIPbuffer=self.NIPqb()
		self.NIPnetwork=self.NIPNET()
		self.default_nip()
		self.nip_init()
		self.init_vars()
		self.NIP_network_pid(False,False,"cleanup")

	class favorits():
		def __init__(self):
			self.favdict = {} # any player with at least "3" points gets his own favlist
			self.temp=[]
		def findex(self, oldlist, favoritee):
			for i in range(len(oldlist)):
				if oldlist[i][0]==favoritee:
					return i
			return -1
		def add(self, player, favoritee):
			if player==favoritee:
				return False
			if self.favdict.has_key(player):
				favoritees=self.favdict.get(player,"[]")
				findex=self.findex(favoritees, favoritee)
				if findex > -1:
					favoritees[findex][1]+=1
					self.favdict[player]=favoritees
				else:
					self.favdict[player]=[[favoritee,1],]
					favoritees.append([favoritee, 1])
					self.favdict[player]=favoritees
			else: #first add 
				self.favdict[player]=[[favoritee,1],]
				
		def getlist(self, player):
			if self.favdict.has_key(player):
				return sorted(self.favdict.get(player,"[]"),key=operator.itemgetter(1),reverse=True)
			else:
				return False
		def save(self, favfile):
				try:
					sfile=open(favfile, "w")
					pickle.dump(self.favdict,sfile)
					sfile.close()
				except IOError:
					print "Error writing to file "+favfile+"(check permission)"
				finally:
					sfile.close()
					pass
		
		def load(self, favfile):
				try:
					lfile=open(favfile, "r")
					self.favdict=pickle.load(lfile)
					lfile.close()
				except IOError:
					print "Cannot read "+favfile+"(will be created)"
				finally:
					pass
		def clear(self, acthof): #will remove any "favoritee" in fav.dict if not found in "HoF"
				foo=""
				isin=[]
				isdel=[]
				li=0
				for players in acthof:
				  isin.append(players[0]) #all players in hof
				
				for playername,favlist in self.favdict.iteritems():
					li=0
					for fav, val in favlist:
					    if fav not in isin:
					      del self.favdict[playername][li]
					      if fav not in isdel:
						isdel.append(fav)
					    li+=1
				for deletedplayers in isdel:
					try:
					  del self.favdict[deletedplayers]
					except:
					  pass
				return isdel
		
	class NIPqb():
		def __init__(self):
			self.question = {}
			self.answer = {}
			self.tip = {}
		def get(self, nick):
			rv=[(self.question.get(nick,"")), (self.answer.get(nick,"")),(self.tip.get(nick,""))]
			return rv
		def put(self, nick, cmd, options):
			options.replace("#","")
			if cmd=="q":
				self.question[nick]=options
			elif cmd=="a":
				self.answer[nick]=options
			elif cmd=="t":
				self.tip[nick]=options
		def clean(self, nick):
			self.question[nick]=""
			self.answer[nick]=""
			self.tip[nick]=""
		def save(self, nipbufferfile):
			try:
				sfile=open(nipbufferfile+".dat", "w")
				for player in self.question:
					player=str(player)
					if self.question.has_key(player) and self.answer.has_key(player):
						tip=""
						if self.tip.has_key(player):
							tip=self.tip[player]
						sfile.write(player+"#"+str(self.question[player])+"#"+str(self.answer[player])+"#"+tip+"\n")
				sfile.close()
			except:
				self.bot.logger.info("while saving NIPbuffer")
			finally:
				sfile.close()
		def load(self, nipbufferfile):
			try:
				lfile=open(nipbufferfile+".dat", "r")
				qbdata=lfile.read()
				lfile.close()
				for line in qbdata.split("\n"):
					if len(line)>1:
						ls=line.split("#")
						self.question[ls[0]]=ls[1]
						self.answer[ls[0]]=ls[2]
						self.tip[ls[0]]=ls[3]
			except:
				pass
			      
	class NIPNET():
		def __init__(self):
			self.runninggames=[]
			
		def getpids(self):
			pidfiles=[]
			for pidfile in os.listdir(datadir):
			    if pidfile.endswith('.nip'):
				pidfiles.append(datadir+"/"+pidfile)
			return pidfiles
		
		def cleanup(self):
			for pid in self.getpids():
				try:
					os.unlink(pid)
				except:
					pass
		def writepid(self, NIPnetwork, NIPchannel):
			try:
				pidfile=open(datadir+'/'+NIPnetwork+'.nip', 'w')
				pidfile.write(NIPnetwork+"="+NIPchannel)
				pidfile.close()
			except:
				pass
			return True
		def deletepid(self, NIPnetwork, NIPchannel):
			try:
				os.unlink(datadir+'/'+NIPnetwork+'.nip')
			except:
				pass
		def running(self):
			self.runninggames=[]
			for pid in self.getpids():
				try:
					pidfile=open(pid ,"r")
					gamedata=pidfile.read()
					pidfile.close()
				except:
					self.bot.logger.debug(str(sys.exc_info()[1]))
					pass
				pair=gamedata.split("=",1)
				if not pair in self.runninggames:
					self.runninggames.append(pair)

	def NIP_network_pid(self, NIPnetwork=None, NIPchannel=None, command=None):
		if command=='cleanup':
			self.NIPnetwork.cleanup()
			return True
		self.NIPnetwork.running()
		if command=='end_of_game':
			self.NIPnetwork.deletepid(NIPnetwork,NIPchannel)
		if command=='startgame':
			self.NIPnetwork.writepid(NIPnetwork,NIPchannel)
			othergames=[]
		if command == 'spoil':
			othergames=[]
			for network in self.NIPnetwork.runninggames:
				othergames.append('irc://'+network[0]+"/"+network[1])
			return othergames
		for network in self.NIPnetwork.runninggames:
			if network[0]!=NIPnetwork:
				othergames.append('irc://'+network[0]+"/"+network[1])
				return othergames
		    
	def check_path(self,chkpath):
		if (not os.path.isdir(os.path.dirname(chkpath))):
			try:
				os.makedirs(os.path.dirname(chkpath))
			except:
				self.bot.logger.info("Error, creating "+chkpath)

	@callback
	def joined(self, channel):
		if not self.bot.network in self.NKN:
			self.bot.logger.debug("NIP initial datafile loading for "+self.bot.network)
			self.NKN.append(self.bot.network)
			self.nipdatadir=datadir+'/'+self.bot.network+'/' 
			self.check_path(self.nipdatadir)
			self.niparchivdir=datadir+'/'+self.bot.network+'/NIPArchiv/'
			self.check_path(self.niparchivdir)
		self. datafiles_loading()
		if channel in self.channels:
			self.nipmsg("PRE_H"+self.NAMEOFGAME+"-engine ["+NIPRELEASE+"] initialised", channel)

	def nipexithook(self):
		self.NIPbuffer.save(self.nipdatadir+"NIPbuffer")
		self.nip_hof_update(self.nipdatadir+self.hofdatafile)
		self.save_score(True)
		self.fav.save(self.nipdatadir+self.favfile)
		pass
	
	def datafiles_loading(self):
		#TODO per network 
		self.load_score()
		self.hof=self.nip_hof(self.nipdatadir+self.hofdatafile,"read")
		self.NIPbuffer.load(self.nipdatadir+"NIPbuffer")
		self.fav.load(self.nipdatadir+self.favfile)
		
	def nip_init(self): 
		self.DATA_UPDATE_NEEDED=False
		self.POLLTIME=2    		#timer poll in seconds
		self.NAMEOFGAME="\x1F\x0314.-\x037~\x034\x02\x035Nob\x034od\x037y \x02\x0314is \x037Pe\x034rfe\x035ct\x034\x037~\x0314-.\x0F".decode(self.NIPencoding)
		self.HALLOFFAME="\x1F\x0314.-\x037~\x034=_\x02\x035H\x034al\x037l \x02\x0314of\x02 \x037F\x034a\x035me_\x034=\x037~\x0314-.".decode(self.NIPencoding)
		self.SCORETABLE="\x1F\x0314.-\x037~\x034=\x02\x035Sc\x034or\x037in\x02\x0314g T\x037a\x034b\x035le\x034=\x037~\x0314-.".decode(self.NIPencoding)
		self.GAMECHANNEL=""
		self.allscore={}
		self.nT_init() 			#(used for different timeouts and automatic gameflow)
		self.GL_TS=0       		#timestamp for timeouts, needs to be initialised - <=0 is the hook for an action
		self.gamespeed=1 		#default gamespeed=1 normal 2= faster timeouts/2
		self.minplayersold=0 		#toogle cmd "testing"
		self.autoremove=1 		#"!autoremove" toggles 0|1, if set to 1 - players will be removed from list when they do not send in question/answer 
		self.splitpoints=1 		#!splitpoints" toggles between 0|1, used to show splittet points. if true returns details in scoring 
		self.autorestart=0  		#!autorestart 1=gameadmin does not need to !restartgame, the bot does itself
		self.hookaction="None" 		#which function to call on timerhook
		self.hof_show_max_player=8  	#max player from HoF to send in channel #
		self.hof_max_player=999 	#max players in hof-file
		self.nickvoted_end=[]
		self.votedEnd=0
		self.newplayers=[] 		#used as buffer for joining during game round 
		self.hof=[] #
		self.NKN=[]
		self.othergames=[]
		self.bot.logger.info("NIP Plugin release "+NIPRELEASE+" initialised")
		####
		
	def default_nip(self):
		#Getting and settings some defaults and (bot-)configurable values
		#bot.config.get() is a bit intransparent should be fixed
		#.config.get() should write a the simple yaml in plugin dir
		self.NIPencoding='utf-8'
		self.cchar="!"
		self.pchar=""
		
		#### internal file names
		self.hofdatafile="niphof.txt"
		self.favfile=str("fav.data")
		self.nipbufferfile=str("NIPbuffer")
		self.actscoretable=str("NIPactScoreTable")
		####
		self.channels=self.bot.config.get("nipchannels", DEFAULT_GAME_CHANNELS, "main",self.bot.network).split() #NIP internal multichannel support
		self.nip_spoil=self.bot.config.getBool("nip_spoiling", NIP_SPOIL, "main",self.bot.network)
		self.minplayers=DEFAULT_NIP_MIN_PLAYER
		self.maxplayers=DEFAULT_NIP_MAX_PLAYER
		self.maxnicklen=DEFAULT_MAX_NICK_LEN
		self.nickWarnMax=AUTOREMOVE_PLAYER_AFTER_ROUNDS_OF_INACTIVITY
		
		self.init_timeouts(NIP_TIMEOUT_BASE)
		self.TGAMEADMIN="#BOLD#Spiel-Admin#BOLD#"
		self.TGAMEMASTER="#BOLD#QUIZ-Meister#BOLD#"
		self.TNIPQUESTION="#BOLD##DBLUE#NIP-Frage#NORM#"
		self.TNIPWARNINGS="Verteilung von#BOLD# #DRED#Trantüten-Lametta#NORM# an".decode(self.NIPencoding)
		self.NIPRULES=NIP_RULES_LINK
		self.NIPSOURCE=NIP_SOURCE_LINK
		self.mirc_stuff_init()

	def init_autocmd(self):
		""" 
		obsolete inhere, a modified bot reads its source and evaluates a given self.kcs within plugins internally
		Well that'll also work without having that definition here,
		This also represents an overview of applied commands with the game plugin, so keeping it
		"""
		self.kcs=["clearfav","pchar","evol","vote","halloffame","hof","nip_hof","nip_place","place","splitpoints",\
		           "abortgame","reset","nip_startgame","startgame","restartgame", "kill",\
		           "nip_scores", "nip_ranking","scores", "gamespeed", "autoremove", "stats","nip_favorits","nip_groupies",\
		           "favorits","groupies","continue", "players","nip_rules","rules",\
		           "nip_source","nip_status","status","nip_help","help","join","part",\
		           "autorestart",\
		           "testing","nip_version","nip_credits","version","credits","nip_channels"]

	def init_timeouts(self, timeOutBase):
		#!gamespeed will toggle between halve and default values
		TimeBase=60
		if type(timeOutBase)==int:
			if timeOutBase>30 and timeOutBase<420:
				TimeBase=timeOutBase
			else:
				self.bot.logger.info("TimeOutBase Config must not be smaller than 30 or greater than 420")
				TimeBase=60
		else:
			self.bot.logger.info("TimeOutBase Config has to be an integer")
			TimeBase=60
		self.timeouts={}#used in nTimerset
		self.timeouts['ANSWER_TIME']=2*TimeBase
		self.timeouts['QUIZ_TIME']=TimeBase-10   	#60 time waiting for quiz answers, nTimerset will add foo seconds for each player
		self.timeouts['QUIZ_TIME_ADD']=9 		#add seconds to QUIZ_TIME for each player
		self.timeouts['TIMEOUT']=2*TimeBase 		#300 idle time until game stops to "game_waiting", "waiting_for_gamemaster" NIP-Question
		self.timeouts['STARTPHASE']=TimeBase*8 		#large initial timeout - catching players ;) 
		self.timeouts['GAMEADMINNOTIFY']=TimeBase 	#sends a "highlight" to a sleeping "gameadmin"
		self.timeouts['GAMEADMINKICK']=TimeBase 	#kick lazy gameadmin from game, not from irc 

	def mirc_stuff_init(self):
		self.NIPPREFIX="\x0F\x0316,14NIP\x033\x0F" #eyecatcher for game output 
		#some (m)IRCstuff...  ".encoding" just to be sure
		self.colors={}
		self.colors["#BOLD#"]="\x02".encode(self.NIPencoding) #toogle like irc sequence
		self.colors["#NORM#"]="\x0F".encode(self.NIPencoding) #resetallMIRColorslike
		self.colors["#UNDERLINE#"]="\x1F".encode(self.NIPencoding) # tooglelike 
		self.colors["#DBLUE#"]="\x032".encode(self.NIPencoding)
		self.colors["#DGREEN#"]="\x033".encode(self.NIPencoding)
		self.colors["#LGREEN#"]="\x039".encode(self.NIPencoding)
		self.colors["#LRED#"]="\x034".encode(self.NIPencoding)
		self.colors["#DRED#"]="\x035".encode(self.NIPencoding)
		self.colors["#LCYAN#"]="\x0311".encode(self.NIPencoding)
		self.colors["#DCYAN#"]="\x0310".encode(self.NIPencoding)
		self.colors["#LBLUE#"]="\x0312".encode(self.NIPencoding)
		self.colors["#LGREY#"]="\x0315".encode(self.NIPencoding)
		self.colors["#DGREY#"]="\x0314".encode(self.NIPencoding)
		self.colors["#WHITE#"]="\x0316".encode(self.NIPencoding)
		self.colors["#LMAGENTA#"]="\x0313".encode(self.NIPencoding)
		self.colors["#DMAGENTA#"]="\x036".encode(self.NIPencoding)
		self.colors["#DYELLOW#"]="\x037".encode(self.NIPencoding)
		self.colors["#LYELLOW#"]="\x038".encode(self.NIPencoding)
		if self.pchar: #color decorator characters
		  pchar=self.pchar[0:4]
		else:
		  pchar=DEFAULT_COLOR_DECORATOR.decode(self.NIPencoding)
		self.pres={}
		self.pres["PRE_N"]="\x031"+pchar+"\x0F".encode(self.NIPencoding)		#Black after Standard Prefix as default
		self.pres["PRE_Q"]="\x034"+pchar+"\x0F".encode(self.NIPencoding)		#Red - Send me the Question /The question is/was
		self.pres["PRE_A"]="\x033"+pchar+"\x0F".encode(self.NIPencoding)		#Dark Green right Answer
		self.pres["PRE_C"]="\x039"+pchar+"\x0F".encode(self.NIPencoding)		#Light Green for possible answers are
		self.pres["PRE_S"]="\x037"+pchar+"\x0F".encode(self.NIPencoding)		#dark yellow for scoring
		self.pres["PRE_H"]="\x0311"+pchar+"\x0F".encode(self.NIPencoding)		#cyan for help messages
		self.pres["PRE_X"]="\x036"+pchar+"\x0F".encode(self.NIPencoding)		#magenta for messages to gameadmin
		self.pres["PRE_G"]="\x035"+pchar+"\x0F".encode(self.NIPencoding)		#dark red for game status things....
		self.pres["PRE_P"]="\x0312"+pchar+"\x0F".encode(self.NIPencoding)		#Light blue for Punishments
		self.pres["PRE_Z"]="\x035"+pchar+"\x0F".encode(self.NIPencoding)		#Dark Red also for Hall of fame
		self.pres["PRE_Y"]="\x038"+pchar+"\x0F".encode(self.NIPencoding)		#Hall of fame top line
		self.pres["PRE_V"]="\x0310"+pchar+"\x0F".encode(self.NIPencoding)		#dark cyan for VOTES
		self.pres["PRE_D"]="\x0314"+pchar+"\x0F".encode(self.NIPencoding)		#dark Grey for misc
		
 
	def init_vars(self):
		self.phase=NO_GAME
		self.players=[]
		self.gameadmin="" 	
		self.gamemaster="" 	#different for each round.
		self.gamemasterold="" 	#used to catch lazy user, who wants to cheat by removing and adding himself as gamemaster!
		
		self.question=""
		self.answers={}
		self.answernick={} 	#usernames(!) for the numbers
		self.score={}			#live score
		self.scores={} 		#live splitted scores
		self.guessed=[] 	#nicks, which already have guessed 
		self.additional_info=None
		self.abortcnt=0
		self.resetcnt=0 	#used to punish a gamemaster who resets game to WAITING_FOR_QUESTION
		self.starttime=time.strftime("%Y/%m/%d %H:%M:%S") #used for scoring table data on disc when game ends
		self.roundofgame=1 	#counter, used in game as info, maybe good for new statistic
		self.eoq_cnt=0 		#see end_of_quiz ~used for debugging #obsolete when everything works
		self.votedEnd=0 	#important to reset here...
		self.userWarnCnt={} 	#used for autoremoving player


	def init_vars_for_restart(self):
		self.abortcnt=0 	
		self.question=""
		self.answers={}
		self.answernick={} 	#usernames(!) for the numbers
		self.score={}
		self.scores={}
		self.guessed=[] 	#nicks, which already have guessed
		self.additional_info=None
		self.roundofgame+=1
		self.nickvoted_end=[]
		self.new_gamemaster()

	def new_gamemaster(self):
		""" each player will (has to be) the gamemaster in chaotic order, cheatprotection incl.  """
		if len(self.gamemasterold) > 0: 			#we have a cheat candidate
			if str(self.gamemasterold) in self.players: 	# and the cheater is back in next round, so 
				self.nipmsg("PRE_P"+self.gamemasterold\
				     +" Du versuchstzu #BOLD#mogeln#BOLD#? 2 NiPs Abzug und gleich nochmal der "+self.TGAMEMASTER) 
				self.add_allscore(str(self.gamemasterold),-2)
				self.gamemaster=self.gamemasterold
				if self.gamemaster in self.players: 	# todo set_gamemaster()
					self.players.remove(self.gamemaster)
			else:
				self.gamemasterold="" 			#did not rejoin the game, so he did not try to cheat
		if len(self.gamemasterold) == 0:
			#changing gamemaster if no cheater
			if len(self.gamemaster) > 0 and not self.gamemaster in self.players:
				self.bot.logger.debug("Pushing gamemaster back to players -"+str(self.gamemaster))
				self.players.append(self.gamemaster) 	#puts him back to the end	
			self.gamemaster=self.players[0] 		#sets the next
			self.players=self.players[1:]
			self.gamemasterold=""
			self.resetcnt=0
			self.bot.logger.debug("Setting new Gamemaster to: "+self.gamemaster)
		self.gamemasterold=="" #to be sure
		

	def nipmsg(self, cmsg, ochannel=None):
		if ochannel==None and not self.GAMECHANNEL:
			self.bot.logger.debug("No nipmsg (no gamechannel)- "+cmsg)
		else:
			if ochannel==None:
				cchannel=self.GAMECHANNEL
			else:
				cchannel=ochannel
			for color in self.colors.keys():
				if cmsg.count(color):
					val=self.colors.get(color, "")
					cmsg = cmsg.replace(color,val)
			for pre in self.pres.keys():
				if cmsg.count(pre):
					val=self.pres.get(pre, "")
					cmsg = cmsg.replace(pre, val)
			if cmsg.count("#CCHAR#"):
				cmsg = cmsg.replace("#CCHAR#",str(self.cchar))
			self.bot.sendmsg(cchannel, str(self.NIPPREFIX)+cmsg, self.NIPencoding)
	####
	def nT_init(self):
		self.nTimer = timehook.LoopingCall(self.nTimerhook)
		gc.garbage.append(self.nTimer)
		
	def stop_timer(self):
		try:
			if self.nTimer.running:
				try:
					self.nTimer.stop()
				except:
					self.bot.logger.debug("Error on stopping timer"+str(sys.exc_info()[1]))
					pass
		except:
			self.bot.logger.debug("nTimer"+str(sys.exc_info()[1]))
			pass
		self.GL_TS=0 #
		
	def nTimerset(self, REQ_TIME, REQ_ACTION):
		self.stop_timer()
		#dynamically longer timeouts for some conditions (ircd thwarts game when playing with more players )
		if type(REQ_TIME)==str:
			REQ_TIME=int(self.timeouts.get(REQ_TIME, 60))
		addtime=2
		if self.phase==QUIZ: # maybe we don't need that with less than 5 players ... 
			addtime=self.player_qty()*int(self.timeouts.get('QUIZ_TIME_ADD',5))
			self.bot.logger.debug("Expanding Timeout"+str(addtime))
		self.hookaction=REQ_ACTION
		self.GL_TS=(REQ_TIME+addtime)/self.gamespeed
		self.warn_ts=self.GL_TS / 3 	#used for "warning" "sleeping" players
		self.playerwarned=0 #bool to avoid multiple warnings
		
		self.nTimer.start(self.POLLTIME)
		#print str(nTimer.__class__.__name__)
		self.bot.logger.debug("Starting Timer: polltime=" +str(self.POLLTIME)+" REQ_ACTION:"+\
		               str(self.hookaction)+" REQTIME:"+str(self.GL_TS)+" warn_ts:"+str(self.warn_ts))


	def nTimerhook(self):
		""" art happens by happy accidents, do you now about the NE555? well this is LOCnr 556 :)"""
		self.GL_TS-=self.POLLTIME
		if self.GL_TS <= 0:
			self.stop_timer()    
			if self.hookaction=="end_of_quiz":
				self.bot.logger.debug("hookaction->"+str(self.hookaction)+" Phase:"+str(self.phase))
				self.hookaction="None"
				self.end_of_quiz()
		 
			elif self.hookaction=="end_of_answertime":
				self.bot.logger.debug("hookaction->"+str(self.hookaction)+" Phase:"+str(self.phase))
				self.hookaction="None"
				self.end_of_answertime()

			elif self.hookaction=="notify_gameadmin":
				self.bot.logger.debug("hookaction->"+str(self.hookaction)+" Phase:"+str(self.phase))
				self.hookaction="None"
				self.notify_gameadmin()
		
			elif self.hookaction=="kick_gameadmin":
				self.bot.logger.debug("hookaction->"+str(self.hookaction)+" Phase:"+str(self.phase))
				self.hookaction="None"
				self.kick_gameadmin()
				if self.phase==WAITING_FOR_PLAYERS:
					self.end_of_game()

		if (self.phase==QUIZ or self.phase==WAITING_FOR_ANSWERS or self.phase==WAITING_FOR_QUESTION) and not self.playerwarned:
			if self.GL_TS <= self.warn_ts:
				self.warn_players()
				self.playerwarned=1

	def notify_gameadmin(self):
		if self.gameadmin!="":
			if not self.autorestart:
			    self.nTimerset('GAMEADMINKICK', "kick_gameadmin")
			    taction="restartgame"
			    if self.phase==WAITING_FOR_PLAYERS:
				taction="startgame"
			else:
			    self.restart_the_game(self.gameadmin)
			    return 1
			self.nipmsg("PRE_X"+self.TGAMEADMIN+" "+str(self.gameadmin)+" #CCHAR#"+taction)
		else:
			if not self.phase==WAITING_FOR_PLAYERS and not self.phase==NO_GAME:
				self.show_players()
				self.nipmsg("PRE_XWeiter geht's mit #BOLD##CCHAR#restartgame #BOLD##DGREY#(#CCHAR#vote end #CCHAR#autorestart#DGREY#")
				self.phase=GAME_WAITING

	def kick_gameadmin(self, refby=None):
		self.bot.logger.debug("kick_gameadmin refby "+str(refby))
		if self.gameadmin!="":
			gameadmin=self.gameadmin
			self.nipmsg("PRE_X"+self.TGAMEADMIN+" #UNDERLINE#"+gameadmin+"#UNDERLINE# hat wohl keine Lust mehr. !restartgame !vote end")
			self.gameadmin=""
		else:
			self.show_players()
			self.nipmsg("PRE_XWeiter geht's mit #BOLD##CCHAR#restartgame ")
			
		if not self.phase==WAITING_FOR_PLAYERS and not self.phase==NO_GAME: #
			self.phase=GAME_WAITING #set only when not in "startphase", so the "running" game can pause for longer period of time (years if u like)
		else:
			self.nipmsg("PRE_XWeiter geht's mit #BOLD##CCHAR#startgame ")


	def add_player(self, addnick):
		if self.phase==NO_GAME:
			return 0
		if len(addnick) > self.maxnicklen:
			self.nipmsg("PRE_X"+addnick+": Dein Nickname ist zu lang fuer das Spiel, maximal "+str(self.maxnicklen)+" Zeichen.")
		else:
			addnick=addnick[:self.maxnicklen] #
			if addnick in self.players:
				return 0
			else:
				if self.check_maxplayer():
					if addnick!=self.gamemaster:
						if not self.phase==WAITING_FOR_PLAYERS: #do not add while waiting for "ich" in startphase
							self.nipmsg("PRE_X"+addnick+" spielt jetzt mit.")
						self.bot.logger.debug("add_player: Appending player:"+addnick)
						#open a query to user initially
						self.bot.sendmsg(addnick ,"Hier kannst du NIP Frage und Antwort erstellen wenn du an der Reihe bist."\
						                 "Oder benutze hier !help um den NIP-Buffer zu nutzen", self.NIPencoding)
						self.players.append(addnick)
					return 1


	def del_player(self, delnick, refby=None): #refby=call other subroutines or not
		self.bot.logger.debug("del_player refby:"+str(refby))
		#cheatprotection
		if delnick==str(self.gamemaster) and self.gamemasterold=="":
			self.gamemasterold=delnick
			self.bot.logger.debug("set Gamemasterold="+self.gamemasterold)

		#del_player rest
		if not self.votedEnd:
			#once voted a game_end, do NOT remove players (missing self.end_of_game() for some conditions) 
			c=False
			if delnick in self.players:
				self.players.remove(delnick)
				c=True
			if self.gameadmin==delnick:
				self.gameadmin=""
			if self.gamemaster==delnick:
				c=True
				self.gamemaster=""
				if not refby=="end_of_quiz":
					if not self.answers.has_key(delnick): 	#avoids eog while gamemaster had sent in question AND answer
						self.end_of_quiz()

			if c: 	#changed
				if delnick: #
					if refby=="autoremoving":
						self.nipmsg("PRE_X"+delnick+" mangels Lebenszeichen automatisch aus dem Spiel entfernt.")
					else:
						self.nipmsg("PRE_X"+delnick+" spielt nicht mehr mit.")
					
				if delnick in self.nickvoted_end:
					self.nickvoted_end.remove(delnick)
				if delnick in self.newplayers:
					self.newplayers.remove(delnick)
					if not delnick in self.players:
						self.nipmsg("PRE_X"+delnick+" hat wohl doch keine Lust.")
		else:
			if not self.phase==NO_GAME and not self.phase==GAME_WAITING:
				self.nipmsg("PRE_V"+delnick+": Nach der Runde ist ohnehin Spielende.")


	def show_players(self, channel=None):
		pnr=len(self.players)
		pnr=0
		splayers=""
		for tplayer in self.players:
			if tplayer==self.gameadmin:
				tplayer="#UNDERLINE##BOLD#"+tplayer+"#BOLD##UNDERLINE#"
			if tplayer!=self.gamemaster:
				splayers=splayers+" "+tplayer
			pnr+=1
		if self.gamemaster:
			splayers=splayers+" #BOLD#"+self.gamemaster+"#BOLD#"
			pnr+=1
		self.nipmsg("PRE_G"+str(pnr)+" Nippies:"+splayers, channel)
	
	
	def warn_players(self):
		wplayers=""
		if self.phase==QUIZ:
			for player in self.players:
				if not player in self.guessed:
					wplayers=wplayers+" "+player
		if self.phase==WAITING_FOR_ANSWERS:
			for player in self.players:
				if not player in self.answers.keys():
					wplayers=wplayers+" "+player
		if self.phase==WAITING_FOR_QUESTION:  # or self.phase==WAITING_FOR_QUIZMASTER_ANSWER:
			wplayers=str(self.gamemaster)
		if len(wplayers) > 1:
			self.nipmsg("PRE_H"+self.TNIPWARNINGS+" "+wplayers+"#DGREY#  Noch ~"+str(self.GL_TS)+" Sek.")
	

	def new_gameadmin(self, gnick):
		self.bot.logger.debug("new_gameadmin <"+gnick+"> phase:"+str(self.phase))
		if self.phase==GAME_WAITING: #not for no_game
			self.nTimerset('GAMEADMINNOTIFY',"notify_gameadmin")
		if len(gnick) <= self.maxnicklen: 
			self.gameadmin=gnick
			if not gnick in self.players: #"if" should be obsolete due to add_player()
				self.add_player(gnick)
			self.nipmsg("PRE_XDer neue "+self.TGAMEADMIN+" ist #BOLD#"+gnick)
		else:
			self.nipmsg("PRE_X"+gnick+": Dein Nick ist leider zu lang!")
	
	def player_qty(self):
		plc=len(self.players)
		if self.gamemaster:
			plc+=1
		return plc
	
	def check_maxplayer(self):
		if self.player_qty() >= self.maxplayers:
			self.nipmsg("PRE_XDie Bude ist voll.  Maximal "+str(self.maxplayers)+\
			            " können mitspielen.".decode(self.NIPencoding))
			self.bot.logger.debug("MaxPlayer "+str(self.maxplayers))
			return 0
		else:
			return 1
	#hoockaction
	def end_of_answertime(self):
		self.phase=QUIZ
		self.nTimerset('QUIZ_TIME', "end_of_quiz") #needs to be here 
		count=1
		qw="Die Frage war: "
		if self.gamemaster:
			qw=self.gamemaster+" fragte: "
		self.nipmsg("PRE_Q"+qw+"#BOLD#"+self.question)

		self.nipmsg("PRE_G#UNDERLINE#Mögliche #BOLD#Antworten#BOLD# sind:"\
		            "#UNDERLINE#  (#DRED#Aufforderung abwarten!#DRED#)".decode(self.NIPencoding))

		nicks=self.answers.keys()
		random.shuffle(nicks)
		for nick in nicks:
			self.nipmsg("PRE_C#BOLD#"+str(count)+"#BOLD#. "+self.answers[nick])
			self.answernick[count]=nick
			count+=1
		self.nipmsg("PRE_G#DGREY##UNDERLINE#_-=Und nun nur die Zahl als Antwort"\
		            "=-_#UNDERLINE#  #LGREY#~"+str(self.GL_TS)+" Sek. Zeit!")

	#### functions below belong to end_of_quiz
	def add_allscore(self, player, qty=None):
		self.bot.logger.debug("add_allscore:"+player+" "+str(qty))
		#just send in negative values for qty if you want to "punish" a player
		# if qty is 0 self.score[nick] will be used to calc gameround points
		if  qty!=None:
			if str(player) in self.allscore.keys():
				self.allscore[player]+=qty
			else:
				self.allscore[player]=qty
		else: #round "allscore" calculation
			if str(player) in self.answernick.values(): #we are evil at that point - no point for none given answer
				if player in self.allscore.keys():
					self.allscore[player]+=self.score[player]
				else:
					self.allscore[player]=self.score[player]
		if not self.DATA_UPDATE_NEEDED:
				self.DATA_UPDATE_NEEDED=True
				self.bot.logger.debug("Setting data update is needed")

	def answer_from_who(self):
		"""show who gave which answer, return right answer at first"""
		snum=0
		firsttext="PRE_C"+""
		text=""
		"""build the output array here for 'from who'"""
		for num in self.answernick:
			if self.answernick[num]==self.gamemaster or self.answernick[num]==self.gamemasterold:
				snum=num #stored for later use 
				firsttext+="("+self.answernick[num]+" #NORM#**#BOLD#"+str(num)+"#BOLD#**)#NORM# "
			else:
				text+="#DGREY#("+self.answernick[num]+" #NORM#"+str(num)+"#DGREY#)"
		fromwho=firsttext+text
		return fromwho,snum
	
	def quiz_scoring(self):
		if len(self.score):
			for player in self.score:
				pword="NiPs"
				pscore=self.score[player]
				pscores="" #show splitted if more than one point
				if pscore >= 9:
					""" three in a row bonus """
					pscore+=2 
					self.bot.logger.debug("Three in a row for "+player)
					self.score[player]+=2
					self.scores[player]+="#LRED# +2* Bonus#DGREY#"
				if pscore==1:
					pword="#LMAGENTA#*#NORM#chen"
				else:
					if self.splitpoints: #show only if wanted scoreS(splitted) not score ;)
						pscores="#DGREY#("+self.scores[player]+")#NORM#" #maybe good to use in add_allscore with eval() - later
				
				if str(player) in self.answernick.values(): #no points for no given nip answer but guessing an answer
					self.nipmsg("PRE_S"+player+" bekommt #BOLD#"+str(pscore)+"#BOLD##NORM# "+pword+" "+pscores)
				else:
					self.nipmsg("PRE_P"+player+" #UNDERLINE#bekäme#UNDERLINE##BOLD# ".decode(self.NIPencoding)\
					             +str(pscore)+"#BOLD##NORM# "+pword+"#DGREY# (Keine mögl. Antwort geliefert,"\
					             "keine Pünktchen!)".decode(self.NIPencoding))
			for nick in self.score:
				self.add_allscore(nick)


	def check_for_answer(self):
		for player in self.players:
			if not player in self.answernick.values():
				if self.userWarnCnt.has_key(player):
					self.userWarnCnt[player]+=1
				else:
					self.userWarnCnt[player]=1
			else:
				if self.userWarnCnt.has_key(player):
					self.userWarnCnt[player]=0

	
	def autoremoving(self, justplayer=None):
		if not justplayer:
			atext="" #
			if self.gamemaster==self.gameadmin:
				if self.autoremove and not self.votedEnd:
					self.kick_gameadmin("end_of_quiz")
			else:
				if self.autoremove and not self.votedEnd:
					self.del_player(self.gamemaster, "end_of_quiz")
		else:
			for player in self.players:
				if player in self.userWarnCnt.keys():
					if int(self.userWarnCnt.get(player,0))>=self.nickWarnMax:
						self.del_player(player,"autoremoving")


	def correct_answer(self, snum):
		gm=self.gamemaster
		if gm=="":
			gm=self.gamemasterold
		correct="PRE_ARichtige Antwort war: #BOLD#"+str(snum)+"#BOLD# (#DGREY#"+self.answers[gm]
		if self.additional_info:
			correct=correct+"#NORM# Tip:#DGREY#"+self.additional_info+"#NORM#)"
		else:
			correct=correct+"#NORM#)"
		""" question and answer were complete so rewarded with 1 point"""
		self.add_allscore(gm ,1)
		self.nipmsg(("PRE_X"+self.TGAMEMASTER+" "+gm+" bekommt 1 #LMAGENTA#*#NORM#chen fuer die vollstaendige "+self.TNIPQUESTION).encode(self.NIPencoding))
		return correct
	
	def no_nip_question(self):
		gmaster=""
		if self.gamemasterold!="":
			gmaster=self.gamemasterold #maybe he has left the game
		if self.gamemaster!="":
			gmaster=self.gamemaster
		if not self.answers.has_key(gmaster):
			self.add_allscore(gmaster ,-1)
			pword="#LMAGENTA#*#NORM#chen"
			return "PRE_X"+self.TGAMEMASTER+" "+gmaster+" hatte keine "+self.TNIPQUESTION+" (-1"+pword+" !)"
		
	def add_new_players(self):
		if len(self.newplayers) > 0:
			for newplayer in self.newplayers:
				if not newplayer in self.players:
					self.add_player(newplayer)
					self.bot.logger.debug("Adding player from newplayers buffer"+newplayer)
			self.newplayers=[]
		
	#### a hookaction	
	def end_of_quiz(self):
		""" end of quiz n round """
		self.bot.logger.debug("end_of_quiz:"+str(self.roundofgame)+"-"+str(self.eoq_cnt))
		
		if not self.votedEnd: #votedEnd also means gameadmin did !abortgame
		   self.phase=GAME_WAITING
		#show who gave which answer
		if self.eoq_cnt==self.roundofgame: #avoids double scoring, at least for debugging
			self.bot.logger.debug("EndOfQuiz called more than once!")
		else:
			fromwho, snum=self.answer_from_who() #builds the string for output and gives no. of right answer
			self.quiz_scoring() #throws score results and does calculalations
		
		self.nipmsg("PRE_X#UNDERLINE#_-=#BOLD#Ende der Runde#BOLD#=-_#UNDERLINE# #DGREY#"+str(self.roundofgame))
		if snum > 0: # 0= at least no given answer
			self.nipmsg(self.correct_answer(snum))
			self.nipmsg(fromwho)
			self.gamemasterold="" #reset cheatprotection Nipquestion was given
		else: 
			if self.eoq_cnt==self.roundofgame:
				self.bot.logger.debug("EndOfQuiz called more than once!")
			else:
				self.autoremoving() #
				self.nipmsg(self.no_nip_question())
		if self.votedEnd:
			self.end_of_game()
		#last but not least co
		else:
			if self.autoremove:
				self.check_for_answer()
				self.autoremoving(True)
			self.add_new_players()
			if self.eoq_cnt < self.roundofgame:
				self.eoq_cnt=self.roundofgame #
			self.eoq_cnt=self.roundofgame
			self.nTimerset('GAMEADMINNOTIFY', "notify_gameadmin")

	def end_of_game(self):
		self.stop_timer()
		self.nipmsg("PRE_X#BOLD#Spiel beendet.#BOLD# (#DRED##CCHAR#scores#NORM#"\
		             " zeigt den Endstand. #DRED##CCHAR#hof#NORM# die neue Hall of Fame)")
		self.phase=NO_GAME
		self.gameadmin=""
		self.gamemaster=""
		self.nip_hof_update(self.nipdatadir+self.hofdatafile)
		self.save_score()
		self.fav.save(self.nipdatadir+self.favfile)
		self.players=[]
		self.nickvoted_end=[]
		self.NIP_network_pid(self.bot.network,self.GAMECHANNEL,'end_of_game')
		self.GAMECHANNEL=""
		self.bot.logger.info("Gamechannel disangeged")


	def vote_for_end(self, vuser, adminVote=None):
		self.bot.logger.debug("AdminVote:"+str(adminVote))
		#how many players are needed to end game without gameadmin,  let's try ~30%
		if self.player_qty() >= self.minplayers or adminVote:
			vote_min_player=int(round(self.player_qty() * 0.4)+0.49) #
			if not vuser in self.nickvoted_end and (vuser in self.players or vuser==self.gamemaster): #
				self.nickvoted_end.append(vuser)
			veq=str(len(self.nickvoted_end))
			if vote_min_player < 2:
				vote_min_player=2
			if self.minplayers==1:
				vote_min_player=1
			self.bot.logger.debug("Vote End:"+str(veq)+"/"+str(vote_min_player))
			if int(veq) >= vote_min_player:
				if self.phase==WAITING_FOR_PLAYERS or self.phase==GAME_WAITING:
					if not adminVote:
						self.nipmsg("PRE_VAbstimmung: #BOLD#Spielende!")
					self.end_of_game()
				else:
					if not adminVote:
						self.nipmsg("PRE_VAbstimmung:#BOLD#Spielende#BOLD# am Ende der Runde!")
					else:
						self.nipmsg("PRE_V#BOLD#Spielende#BOLD# am Ende der Runde!")
					self.votedEnd=1 #dacapo al fine
			else:
				self.nipmsg("PRE_VAbstimmung Spielende:"+veq+" von erforderlichen "+str(vote_min_player)+" Mitnippern - \"!vote end\"")
		else:
			self.bot.logger.debug("No vote...")
	
	def check_nip_buffer(self, nick): 
		uservals=self.NIPbuffer.get(nick)
		if uservals[0]!="" and uservals[1]!="":
			self.question=uservals[0]
			self.answers[nick]=uservals[1]
			self.additional_info=uservals[2]
			self.NIPbuffer.clean(nick)
			self.nipmsg("PRE_Q"+self.TNIPQUESTION+" von "+nick+": #BOLD#"+self.question)
			self.nipmsg("PRE_ASchickt mir eure #BOLD#\"falschen\"#BOLD# Antworten! ~"\
			             +str(self.GL_TS)+" Sek. Zeit! #DGREY#  (/msg "+self.bot.nickname+" eure Antwort)")
			self.phase=WAITING_FOR_ANSWERS
			self.nTimerset('ANSWER_TIME', "end_of_answertime")
			return True
		else:
			return False
	
	def nip_buffer(self, nick, channel, command, options):
		bmsg=""
		cmd=command[0]
		if cmd=="h":
			bmsg="!q[uestion] Deine Frage - !a[nswer] deine richtige Antwort !t[ip] optionaler Tip 'vorab' abliefern,"\
			      "!n[ip] zeigt dir was der bot 'gespeichert' hat.".decode(self.NIPencoding)
			bmsg=bmsg+"Überschreiben ist jederzeit moeglich. Der Bot benutzt dann automatisch "\
			          "deine Frage und Antwort (sofern Beides gespeichert ist) - ".decode(self.NIPencoding)
			bmsg=bmsg+"wenn du als \"Quizmaster\" an der Reihe bist."\
			      .decode(self.NIPencoding)
		elif cmd=="q" or cmd=="a" or cmd=="t" or cmd=="n":
			if len(command) == 1:
				if options:
					self.NIPbuffer.put(nick, cmd, options)
				rv=self.NIPbuffer.get(nick)
				bmsg="Frage: "+rv[0]+" Antwort: "+rv[1]+" Tip: "+rv[2]
		if bmsg:
			self.bot.sendmsg(nick, "NIPbuffer: "+bmsg,self.NIPencoding)

	def restart_the_game(self, nick):
		if self.gameadmin=="" and self.phase==GAME_WAITING:
		    self.new_gameadmin(nick)
		if self.gameadmin==nick and self.phase<2: #test
		    self.stop_timer() #remains pausing the actual game without "timer" functionallity
		if self.phase==GAME_WAITING and nick==self.gameadmin:
		    if self.player_qty() >= self.minplayers:
			tmpplayers=string.join(self.players," ") # trunc this? or predone?
			if self.gamemaster:
			  tmpplayers=self.gamemaster+" "+tmpplayers
			self.init_vars_for_restart()
			self.nipmsg("PRE_GRunde (#BOLD#"+str(self.roundofgame)+"#BOLD#) mit: "+tmpplayers)
			self.phase=WAITING_FOR_QUESTION
			self.nTimerset('TIMEOUT', "end_of_quiz")
			if not self.check_nip_buffer(self.gamemaster):
			  self.nipmsg("PRE_Q"+str(self.gamemaster)+": Schick' mir die "+self.TNIPQUESTION+"."+"  ~"+\
			              str(self.GL_TS)+" Sek. Zeit!#DGREY# (/msg "+self.bot.nickname+\
			              " \"die NIP-Frage\")") #guess gamemaster might work in all cases instead of nick here ;)
			  self.bot.sendmsg(self.gamemaster,"Du kannst im "+self.GAMECHANNEL+" !reset machen,\
			                   falls du dich vertippt hast. Und nun deine NIP-Frage:",self.NIPencoding)
		    else:
			self.nipmsg("PRE_GZu wenig Spieler. Mindestens "+str(self.minplayers)+\
			            " müssen mitspielen! #BOLD##CCHAR#join".decode(self.NIPencoding))
	
	def eastereggs(self, user, command, options):
			if self.bot.auth(user):
				if command=="pchar":
					self.pchar=options[0:4]
					self.mirc_stuff_init()
					self.bot.sendmsg(user,"Color decorator set to: "+options[0:4],self.NIPencoding)
				elif command=="evol":
					self.pchar="❤ ".decode(self.NIPencoding)
					self.mirc_stuff_init()

	def query_command(self, user, channel, command, options):
			if len(command) == 0:
				return False
			self.eastereggs(user,command,options)
			if user!=self.gamemaster: 
				self.nip_buffer(user, channel, command, options)	#check for nipbuf cmd 
			else:
				self.bot.sendmsg(user,"Du bist gerade Quizmaster, warte mit den "\
				                 "NIPBuffer-Funktionen bis zur nächsten Runde!",self.NIPencoding)

	def NIP_spoil(self, channel,command):
			if not self.nip_spoil:
				return False
			othergames=self.NIP_network_pid(self.bot.network, channel, command)
			if othergames:
				og=''
				for othergame in othergames:
					og=str(othergame)+' '+og
				self.nipmsg("PRE_HBereits laufende Spiele-> #DRED#"+str(og),channel)
			else:
				self.nipmsg("PRE_HKein laufendes Spiel im Netzwerk.",channel)
    
	def NIP_global_cmd(self, channel, command, options):
			""" returns the command to be processed elsewhere """
			if self.GAMECHANNEL == channel:
				#game running in this channel
				return command.replace('nip_','')

			if len(self.GAMECHANNEL) > 0:
				#game running in other channel
				if command == "nip_startgame":
					return "status"
				if command[0:4] == "nip_":
					return command.replace('nip_','')
			else:
				"""game not running"""
				if channel in self.channels:
					""" but in configured channel """
					return command.replace('nip_','')
				else:
					""" not in configured channel = global command only """
					if command == "nip_startgame":
						return "channels"
					if command == "nip_status":
						return "status"
					if command == "nip_spoil":
						return "spoil"
					if command[0:4] == "nip_":
						return command.replace('nip_','')
			return ""

	def nice_channels(self):
		rt=''
		for ch in self.channels:
			rt=str(ch)+' '+rt
		if rt=='':
			rt='n/a'
		return rt

	@callback
	def command(self, user, channel, command, options):
			if channel == self.bot.nickname:
				self.query_command(user, channel, command, options)
				#TODO return False?
			command = self.NIP_global_cmd(channel, command, options)
			nick=user.getNick()
			if 2 == 1:
				print "placeholding condition"
			else:
				if channel!=self.bot.nickname:					#no query
					if command == "spoil":
						self.NIP_spoil(channel,command)
						
					elif command == "channels":
						self.nipmsg('PRE_XGame is restricted to:'+self.nice_channels(), channel)
						
					elif command == "kill":
						if self.gameadmin==nick and self.phase!=WAITING_FOR_PLAYERS: 
							self.nipmsg("PRE_XOoops!"+self.TGAMEADMIN+" "+self.gameadmin+" hat wohl keine Lust mehr...")
							self.del_player(nick)
							self.gameadmin=""
						else: 
							if self.gameadmin==nick:
								self.nipmsg("PRE_X"+self.TGAMEADMIN+" "+self.gameadmin\
								            +" das geht erst nach #CCHAR#startgame oder #CCHAR#abortgame")
					
					elif command == "niphelp":
						self.nipmsg("PRE_H"+HELPBUG,channel)
						if not self.phase==NO_GAME:
							if options[:3].strip()=="all":
 								self.nipmsg("PRE_H"+HELPUSER, channel)
								self.nipmsg("PRE_H"+HELPADMIN, channel)
							else:
								if self.gameadmin==nick:
									self.nipmsg("PRE_H"+self.TGAMEADMIN+" "+HELPADMIN)
								else:
									self.nipmsg("PRE_H"+HELPUSER)
						else:
							self.nipmsg("PRE_H#CCHAR#startgame. Waehrend des Spiels #CCHAR#niphelp <all> oder #CCHAR#rules", channel)
					
					elif command=='clearfav': #internal use only
						if self.bot.auth(user):
							deletedplayers=""
							cleandfrom=self.fav.clear(self.hof)
							for delplayer in cleandfrom:
							      deletedplayers=deletedplayers+' '+delplayer
							if deletedplayers:      
							  self.nipmsg("PRE_H Favorits not found in HoF deleted: "+deletedplayers,channel)
							else:
							  self.nipmsg("PRE_H NOP",channel)
							self.fav.save(self.nipdatadir+self.favfile)
						else:
							self.nipmsg("PRE_H Not authenticated",channel)
						
					elif command=="vote":
						if not self.phase==NO_GAME:
							if string.lower(options[:3].strip())=="end" or string.lower(options[:5].strip())=="abort":
								self.vote_for_end(nick)
				
					elif command=="autoremove":
						if nick==self.gameadmin:
							if self.autoremove==0:
								self.autoremove=1
								self.nipmsg("PRE_X#BOLD#Autoremove#BOLD# ist nun #BOLD#aktiv#BOLD#,"\
								             "NIP-Fragesteller ohne Aktion werden automatisch aus dem Spiel entfernt")
							else:
								self.autoremove=0
								self.nipmsg("PRE_X#BOLD#Autoremove#BOLD# ist nun #BOLD#inaktiv#BOLD#.")
						else:
							addword="inaktiv"
							if self.autoremove==1:
								addword="aktiv"
							if not self.phase==NO_GAME:
								self.nipmsg("PRE_X#BOLD#Autoremove#BOLD# ist #BOLD#"+addword+\
								            "#BOLD#. Wechsel nur durch den "+self.TGAMEADMIN+" moeglich!")

					elif command=="autorestart":
						if nick==self.gameadmin:
							if self.autorestart==0:
								self.autorestart=1
								self.nipmsg("PRE_X#BOLD#Autorestart#BOLD# ist nun #BOLD#aktiv#BOLD#,"\
								             "Ich \"restarte\" automatisch neue Runden")
							else:
								self.autorestart=0
								self.nipmsg("PRE_X#BOLD#Autorestart#BOLD# ist nun #BOLD#inaktiv#BOLD#.")
						else:
							addword="inaktiv"
							if self.autorestart==1:
								addword="aktiv"
							if not self.phase==NO_GAME:
								self.nipmsg("PRE_X#BOLD#Autorestart#BOLD# ist #BOLD#"+addword+"#BOLD#."\
								             "Wechsel nur durch den "+self.TGAMEADMIN+" moeglich!")

					elif command=="splitpoints":
						if nick==self.gameadmin:
							if self.splitpoints==0:
								self.splitpoints=1
								self.nipmsg("PRE_X#BOLD#Splitpoints#BOLD# ist nun #BOLD#aktiv#BOLD#,"\
								             "ich zeige die genaue Punkteverteilung (NiPs)")
							else:
								self.splitpoints=0
								self.nipmsg("PRE_X#BOLD#Splitpoints#BOLD# ist nun #BOLD#inaktiv#BOLD#,"\
								             "ich zeige nur die Gesamtpunktzahl (NiPs)")
						else:
							addword="inaktiv"
							if self.splitpoints==1:
								addword="aktiv"
							if not self.phase==NO_GAME:
								self.nipmsg("PRE_X#BOLD#Splitpoints#BOLD# ist #BOLD#"+addword+"#BOLD#."\
								            "Wechsel nur durch den "+self.TGAMEADMIN+" moeglich!")

					elif command=="gamespeed":
						if nick==self.gameadmin:
							if self.gamespeed==1:
								self.gamespeed=2
								self.nipmsg("PRE_XSpielgeschwindigkeit ist nun #BOLD#schnell.")
							else:
								self.gamespeed=1
								self.nipmsg("PRE_XSpielegeschwindigkeit ist nun #BOLD#normal.")
						else:
							actspeed="normal"
							if self.gamespeed==2:
								actspeed="schnell"
							if not self.phase==NO_GAME:
								self.nipmsg("PRE_XSpielgeschwindigkeit ist #BOLD#"+actspeed+"#BOLD#.\
								             Wechsel nur durch den "+self.TGAMEADMIN+" moeglich!")

					elif command=="testing":
						if nick==self.gameadmin:
							if self.minplayersold == 0:
								self.minplayersold=self.minplayers
								self.maxplayersold=self.maxplayers
								self.minplayers=1
								self.maxplayers=24
								self.nipmsg("PRE_XMinimum Spieler=#BOLD#"+str(self.minplayers)\
								            +"#BOLD# Maximum Spieler=#BOLD#"+str(self.maxplayers))
							else:
								self.minplayers=self.minplayersold
								self.maxplayers=self.maxplayersold
								self.minplayersold=0
								self.maxplayersold=0
								self.nipmsg("PRE_XMinimum Spieler=#BOLD#"+str(self.minplayers)\
								            +"#BOLD# Maximum Spieler=#BOLD#"+str(self.maxplayers))
						else:
							self.nipmsg("PRE_XYou have found a secret :)")

					elif command=="join":
						self.bot.logger.debug("Adding player in phase "+str(self.phase))
						if self.phase==NO_GAME or self.phase==GAME_WAITING:
							if self.gameadmin: 				#we have one
								if nick==self.gameadmin: 		#himself
									if len(options) > 1:
										player=options.strip()
										self.add_player(player)
									else:
										self.add_player(nick) 	#add himself
								else:
									self.add_player(nick) 		#a player 
							else:
								self.add_player(nick) 			#again, maybe we have no admin
						else:
							if self.phase==WAITING_FOR_PLAYERS:
								self.nipmsg("PRE_X"+nick+": Einfach #BOLD##UNDERLINE#ich#UNDERLINE##BOLD# tippern!")
							else: #only nicks join thereself
								if not nick in self.players and not nick in self.newplayers and self.gameadmin!=nick:
									self.nipmsg("PRE_X"+nick+" spielt ab der nächsten Runde mit".decode(self.NIPencoding))
									self.newplayers.append(nick)
								elif nick==self.gameadmin:
									self.nipmsg("PRE_X"+nick+": "+self.TGAMEADMIN+" kann nur zwischen den Runden einsteigen")

					elif command=="part":
						if self.phase!=7: 					#obsolete
							if self.gameadmin: 				#we may have one ;)
								if nick==self.gameadmin: 		#himself
									if len(options) > 1: 
										player=options[:24].strip() 	#truncated and the trailing spaces eliminated 
										self.del_player(player) 	#admin removes player
									else:
										self.del_player(nick) 		#just remove himself 
								else:
									if len(options) == 0: #
										self.del_player(nick) 		# a player
									else:
										self.nipmsg("PRE_X"+nick+": Das darf nur der "+self.TGAMEADMIN+" "+str(self.gameadmin))
							else:
								self.del_player(nick) 			# again even if there is no admin
						
					elif command=="players":
						self.show_players(channel)

					elif command=="restartgame" or command == "continue":
						self.restart_the_game(nick)

					elif command=="startgame":
						if self.phase==NO_GAME:
							
							if len(nick) < self.maxnicklen:
								self.NIP_spoil(channel,command)
								self.GAMECHANNEL=channel
								
								self.bot.logger.info("Setting Gamechannel to "+channel+" - "+self.GAMECHANNEL)
								self.init_vars()
								self.allscore={}
								self.save_score(True)
								self.phase=WAITING_FOR_PLAYERS
								self.gameadmin=nick
								
								self.nipmsg("PRE_X"+nick+": Du bist nun der "+self.TGAMEADMIN+\
								            "- Richtig los geht's mit erneutem #DRED##BOLD##CCHAR#startgame.")
								self.nipmsg("PRE_XDen Willen bei "+self.NAMEOFGAME+" mitzumischen, mit einem "+\
								             "#BOLD##UNDERLINE#ich#UNDERLINE##BOLD# bekräftigen!".decode(self.NIPencoding))
								self.nTimerset('STARTPHASE',"kick_gameadmin") #in this phase we'll do end_of_game after given timeout
							else:
								self.nipmsg("PRE_X"+nick+": Dein nickname ist zu lang. Maximal "+str(self.maxnicklen)+" Zeichen.")
					
						elif self.phase==WAITING_FOR_PLAYERS and nick==self.gameadmin:
							if self.player_qty() >= self.minplayers:
								self.phase=WAITING_FOR_QUESTION
								random.shuffle(self.players)
								self.gamemaster=random.choice(self.players)
								if self.gamemaster in self.players:
									self.players.remove(self.gamemaster) # (because he knows the answer)
								self.bot.logger.debug("Random choice setting gamemaster:"+self.gamemaster)
								self.nTimerset('TIMEOUT', "end_of_quiz")
								if not self.check_nip_buffer(self.gamemaster):
									self.nipmsg("PRE_Q"+self.gamemaster+": Schick' mir die "+self.TNIPQUESTION+". ~"\
									            +str(self.GL_TS)+" Sek. Zeit! #DGREY# (/msg "+self.bot.nickname+" \"NIP-Frage\")")
									self.bot.sendmsg(self.gamemaster, "Du kannst im "+self.GAMECHANNEL+" !reset machen,"\
									                 "falls du dich vertippt hast. Und nun die NIP-Frage:", self.NIPencoding)
						
							else:
								self.nipmsg("PRE_X"+self.gameadmin+": Zuwenig Nippies! Mindestens "+str(self.minplayers)+\
								            " müssen mitspielen. #BOLD##UNDERLINE#ich#UNDERLINE##BOLD# ich ich!".decode(self.NIPencoding))
			
						elif self.gameadmin=="":
							self.new_gameadmin(nick)

					elif command=="abortgame": 		#vote end only
						if self.gameadmin=="" and self.phase!=NO_GAME:
							self.new_gameadmin(nick)
						self.nipmsg("PRE_XDemokratie felst: #BOLD##CCHAR#vote end")
						
					elif command=="reset":
						if self.phase==WAITING_FOR_QUIZMASTER_ANSWER or self.phase==WAITING_FOR_ANSWERS:
							if self.gameadmin==nick or self.gamemaster==nick:
								self.resetcnt+=1 	#TODO blocking more than x resets....
								ppoints=self.resetcnt * 2
								if self.resetcnt>1:
									self.nipmsg("PRE_H"+nick+": Auf ein Neues! #BOLD#Punktabzug: -"+str(ppoints))
									self.bot.sendmsg(self.gamemaster,"Deine NIP-Frage:")
									self.add_allscore(nick,int(ppoints*-1))
									self.reset_game()
								else:
									ppoints=1
									self.nipmsg("PRE_H"+nick+": Auf ein neues! #BOLD#Naechstemal Punktabzug!")
									self.bot.sendmsg(self.gamemaster,"Deine NIP-Frage:")
									self.reset_game()
							else:
								self.nipmsg("PRE_H NOP")
						else:
							self.nipmsg("PRE_H NOP")

					elif command=="scores":
						pointlen=0
						if len(self.allscore):
							pointlen=len(str(max(self.allscore.values())))
						SCOREHEAD=self.SCORETABLE+self.create_tab(pointlen-3+self.maxnicklen-12)+"_#UNDERLINE##DGREY#"+" Runde:"+str(self.roundofgame)
						self.nipmsg("PRE_S"+SCOREHEAD, channel)
						if len(self.allscore):	
							points=self.allscore.values()
							points.sort()
							points.reverse()
							players=self.allscore.keys()
							for point in points:
								for player in players:
									if self.allscore[player]==point:
										pword="#DRED#NiPs"
										if point==1:
											pword="#DBLUE#NiP"
										splayer=player+self.create_tab(self.maxnicklen)
										spoints=str(point)+self.create_tab(pointlen-len(str(point)))
										self.nipmsg("PRE_S"+splayer[:self.maxnicklen]+"  "+spoints+ " "+pword, channel)
										players.remove(player)
										break;

					elif command=="rules" or command == "howto":
						self.nipmsg("PRE_H"+self.NIPRULES, channel)

					elif command=="source":
						self.nipmsg("PRE_H"+self.NIPSOURCE, channel)
					
					elif command=="version":
						self.nipmsg("PRE_H"+self.NAMEOFGAME+"["+NIPRELEASE+"]",channel)
						
					elif command=="credits":
					    self.nipmsg("PRE_Z Credits to: #BOLD#Wete allo cato stetie p_kater neTear #BOLD#;-)#DGREY#(release:"+NIPRELEASE+")",channel)
					    
					elif command=="status":
						
						if self.GAMECHANNEL != channel and self.GAMECHANNEL != "":
							self.nipmsg("PRE_GEs wird im Netz gespielt! #BOLD#/join "+self.GAMECHANNEL, channel)
							return False
						if self.GAMECHANNEL == '' and not channel in self.channels:
							self.nipmsg('PRE_XGameplay is restricted to:'+self.nice_channels(), channel)
							return False
						if self.GAMECHANNEL == channel or self.GAMECHANNEL == "":
							result=self.game_status(channel)
							self.nipmsg("PRE_G"+result, channel)

					elif command == "place":
						self.show_user_in_halloffame(channel,nick,options)

					elif command == "halloffame" or command == "hof" or command == "ranking":
						if not self.hof:
							self.bot.logger.debug("HoF empty, file permissions? Maybe it is just new.")
							self.nipmsg("PRE_Z Nobody ever played the game, there is no Hall of Fame yet",channel)
						else:
							loption=options.split(" ")[0]
							try:
								loption=int(loption)
							except:
								loption=1
							if type (loption)==int:
								loption-=1
								self.show_halloffame(channel,nick,int(loption))
					
					elif command == "favorits" or command == "groupies":
						if len(self.fav.favdict)>0:
								loption=options.split(" ")[0]
								if loption:
									nick=loption
								favOut=nick+"#BOLD# <-#BOLD#"
								favlist=self.fav.getlist(nick)
								if favlist:
									for player,val in favlist:
										favOut+="#DGREY#("+player+":#NORM#"+str(val*3)+"#DGREY#)" #
									self.nipmsg("PRE_Z"+favOut,channel)
								else:
									self.nipmsg("PRE_ZNOP",channel)

	def show_halloffame(self, channel, nick, pagekey=None):
		pointlen=len(str(self.hof[0][1])) 			# for building the length in formatted output
		expand=""
		if pointlen>=3:
			expand=self.create_tab(pointlen-3) 		#three is (min) default
		expand=expand+self.create_tab(self.maxnicklen-(self.maxnicklen+1))
		expand=string.replace(expand," ","_")
		
		self.nipmsg("PRE_Y"+self.HALLOFFAME+expand, channel)
		if len(self.hof):
			first=self.hof_show_max_player*pagekey+1
			pcnt=0
			for i in range(self.hof_show_max_player):
				iplace=i+first-1
				if iplace >= len(self.hof):
					break
				place=str(iplace+1)+".     " 		#we do not have placement on zeros....
				nick=self.hof[iplace][0]+self.create_tab(self.maxnicklen)
				allpoints=str(self.hof[iplace][1])+"         " 
				self.nipmsg("PRE_Z"+place[:3]+" "+nick[:self.maxnicklen]+"  "+str(allpoints), channel)


	def show_user_in_halloffame(self, channel, nick, options):
		player=options[:self.maxnicklen].strip()
		try:
			player=int(player)
		except:
			pass
		if not player:
			player=nick
		if not type(player)==int:
			isin=self.isinhof(player,"nocases")			#just a bool
			if not isin:
				self.nipmsg("PRE_Z#BOLD#"+player+"#BOLD# noch nicht in der"+self.HALLOFFAME+\
				            "#NORM#gefunden! #BOLD#Skandalös!#BOLD#".decode(self.NIPencoding), channel)
			else:
				place=isin[0]+".    "
				player=isin[1]+self.create_tab(self.maxnicklen) 	#easier way to create whitespaces (and own tabs)?
				allpoints=isin[2]
				self.nipmsg("PRE_Z"+place[:3]+player[:self.maxnicklen]+" "+str(allpoints), channel)
		else: #we got just an integer, how plain!
			hplace=int(player)
			place=str(hplace)+".            " 			#could be depending on len(max_hof_players)...
			try:
			    player=self.hof[hplace-1][0]+self.create_tab(self.maxnicklen)
			    allpoints=self.hof[hplace-1][1]
			    self.nipmsg("PRE_Z"+place[:3]+player[:self.maxnicklen]+" "+str(allpoints), channel)
			except:
			    pass


	def create_tab(self, qty):
		if qty<1:
			return ""
		ws=[]
		for i in range(qty):
			ws.append(' ')
		return ''.join(ws)

	def reset_game(self):
		self.bot.logger.debug("Reset game in phase="+str(self.phase))
		self.resetcnt+=1
		self.question=""
		self.answers={}
		self.answernick={}
		self.additional_info=None
		self.guessed=[]
		self.nTimerset('TIMEOUT', "end_of_quiz")
		self.phase=WAITING_FOR_QUESTION
		self.bot.logger.debug("Game resetted")
		
	@callback
	def userRenamed(self, oldname, newname):
		return False
		if oldname in self.players:
		    self.players = [player.replace(oldname, newname) for player in self.players]
		    self.nipmsg("PRE_P"+oldname+" renamed to "+newname)
		if oldname in self.newplayers:
		    self.newplayers = [player.replace(oldname, newname) for player in self.newplayers]
		    self.nipmsg("PRE_P"+oldname+" renamed to "+newname)
		if self.gamemaster==oldname:
		    self.gamemaster=newname
		if self.gameadmin==oldname:
		    self.gameadmin=newname
		    
		
	@callback
	def userKicked(self, kickee, channel, kicker, message):
		player=kickee
		playerkicker=kicker
		#remove gamemaster and or gameadmin from game if kicked, 
		if self.GAMECHANNEL==channel:
			if self.gameadmin==player:
				self.kick_gameadmin()
		if self.gamemaster==player:
			self.del_player(player)
			if self.phase==WAITING_FOR_QUESTION or self.phase==WAITING_FOR_QUIZMASTER_ANSWER:
				self.nipmsg("PRE_P"+kicker+":Den "+self.TGAMEMASTER\
				            +" gerade #BOLD#jetzt#BOLD# zu kicken ist boese, 3 NiPs Abzug!")
				self.add_allscore(str(playerkicker),-3)
			self.phase=GAME_WAITING
			
	@callback
	def userJoined(self, user, channel):
		if self.GAMECHANNEL==channel:
			nick=user.getNick()
			statusinfo=self.game_status(channel, nick)
			self.bot.notice(nick, "Hi,"+nick+"! "+statusinfo.encode('utf-8'))

	def game_status(self, channel=None, player=None):
		"""assemble status strings for different situations"""
		ustat=""
		uadd=""
		stat=""
		nt=""
		ujoin=""
		status=self.phase
		if player in self.players:
			uadd=" Du bist noch dabei."
		if self.gamemaster==player:
			uadd=" Du bist "+self.TGAMEMASTER
		if self.gameadmin==player:
			uadd=" Du bist "+self.TGAMEADMIN
		if self.gameadmin==player and self.gameadmin==player:
			uadd=" Du bist "+self.TGAMEADMIN+" und "+self.TGAMEMASTER
		if self.GL_TS >= 1:
			nt="#DGREY# Noch ~"+str(self.GL_TS)+" Sek."
		else:
			nt="#BOLD##DRED#~#LRED#~#DYELLOW#~#BOLD#" #no timeouts running
		if len(uadd)==0:
			ujoin="Zum Mitspielen #CCHAR#join."
		if status==NO_GAME:
				#if channel in self.channels:
				stat="Es läuft kein Spiel. #CCHAR#startgame wird das instantan ändern".decode(self.NIPencoding)
				ustat=stat
		elif status==WAITING_FOR_PLAYERS:
			stat="NIP läuft. Wer mitmischen will, möge das mit #BOLD##UNDERLINE#ich#UNDERLINE##BOLD# bekräftigen!"\
			     .decode(self.NIPencoding)
			ustat=stat+uadd
			stat=stat+nt
		elif status==WAITING_FOR_QUESTION or status==WAITING_FOR_QUIZMASTER_ANSWER:
			gm=""
			if self.gamemaster:
				gm="#BOLD#"+self.gamemaster+"#BOLD#"
			stat="NIP-Spiel läuft. Wir üben uns in Geduld mit dem "\
			      .decode(self.NIPencoding)+self.TGAMEMASTER+" "+gm
			ustat=stat+ujoin+uadd
			stat=stat+nt
		elif status==WAITING_FOR_ANSWERS:
			stat="NIP-Spiel läuft. Die \"falschen\" Antworten sind wohl in Arbeit.".decode(self.NIPencoding)
			ustat=stat+ujoin+uadd
			stat=stat+nt
		elif status==QUIZ:
			stat="NIP-Spiel läuft. #DGREY#eins zwei oder drei ... die #BOLD#"\
			      "Wahrheit#BOLD# ist dabei#NORM#.  ".decode(self.NIPencoding)
			ustat=stat+ujoin+uadd
			stat=stat+nt
		elif status==GAME_WAITING:
			astat=""
			if self.gameadmin=="":
				astat=" #BOLD##CCHAR#restartgame #CCHAR#vote end#BOLD#"
			stat="#DGREY#I#LGREY#c#BOLD#h#NORM# atme tief durch und meditiere etwas"\
			      "- #BOLD#o#BOLD#m#LGREY#m#DGREY#mm."+astat
			ustat=stat
			stat=stat+nt
		rv=""
		if player:
			if ustat.count("#CCHAR#"):
				ustat=ustat.replace("#CCHAR#","!")
			for color in self.colors:
				if ustat.count(color):
					val=self.colors.get(color,"")
					ustat=ustat.replace(color, val)
			rv=ustat
		else:
			rv=stat
	
		return rv
		
	@callback
	def query(self, user, channel, msg):
		msg=msg.replace("%","") #FIXME
		nick=user.getNick()
		if self.phase==WAITING_FOR_QUESTION and nick==self.gamemaster:
			self.question=msg
			self.bot.sendmsg(nick, "Und jetzt die richtige Antwort")
			self.phase=WAITING_FOR_QUIZMASTER_ANSWER
			self.nTimerset(self.GL_TS+24, "end_of_quiz") #player is alive - give him again a little bit more time
			
		elif self.phase==WAITING_FOR_QUIZMASTER_ANSWER and nick==self.gamemaster:
			self.answers[nick]=msg
			self.nTimerset('ANSWER_TIME', "end_of_answertime")
			
			self.nipmsg("PRE_Q"+self.TNIPQUESTION+" ist: #BOLD#"+self.question)
			self.nipmsg("PRE_ASchickt mir eure #BOLD#\"falschen\"#BOLD# Antworten! ~"\
			            +str(self.GL_TS)+" Sek. Zeit! #DGREY#  (/msg "+self.bot.nickname+" Antwort)")
			self.phase=WAITING_FOR_ANSWERS
			#remove gamemaster from game, because he knows the answer
			if self.gamemaster in self.players: #sometimes he is not in before 
			      self.players.remove(self.gamemaster)
				
			self.bot.sendmsg(self.gamemaster, "Zusatzinformation zur Frage einfach hinterherschicken oder weglassen")


		elif (self.phase==WAITING_FOR_ANSWERS or self.phase==QUIZ) and nick==self.gamemaster and not self.additional_info:
			self.additional_info=msg

		elif self.phase==WAITING_FOR_ANSWERS and not nick in self.answers and nick in self.players:
			if msg[0]!="!": # NIP understands some commands in query 
				self.answers[nick]=msg
				if len(self.answers) == len(self.players)+1: #+gamemaster
					self.end_of_answertime()
					
	@callback
	def msg(self, user, channel, msg):
		msg=msg.replace("%","")
		nick=user.getNick()
		if 'foo' == "bar": 
			print "obsolete"
		else:
			if self.GAMECHANNEL==channel:
				
				if self.phase==WAITING_FOR_PLAYERS and nick!=self.bot.nickname: #add player with "ich" in first 42characters while startphase
					if len(string.lower(msg).split("ich")[:42]) > 1: # parses *ich* just do that on WAITING_FOR_PLAYERS (startphase)
						if len(string.lower(msg).split("nicht")[:24]) > 1: #yag
							if not nick in self.players:
								self.nipmsg("PRE_H Och schade "+nick)
							else:
								self.nipmsg("PRE_H"+nick+": Wer nicht will hat schon ;-)")
								self.players.remove(nick)
						else:
							if not (nick in self.players or nick==self.gamemaster):
								if self.check_maxplayer():
									self.add_player(nick)
									text=""
									for item in self.players:
										text=text+item+", "
									text=text[:-2]+"."
								self.show_players(channel)
				elif self.phase==QUIZ and nick in self.players and not nick in self.guessed and nick!=self.gamemaster and nick!=self.gamemasterold:
					try:
						gmaster=self.gamemaster
						if gmaster=="":
							gmaster=self.gamemasterold
						if(self.answernick[int(msg)]==gmaster):
							if nick in self.score:
								self.score[nick]+=1
								if self.splitpoints:
									self.scores[nick]=self.scores[nick]+(" +1*") #
							else:
								self.score[nick]=1
								if self.splitpoints:
									self.scores[nick]="+1*"

						elif (self.answernick[int(msg)]==nick):
							#to select the own answer gives 0 points
							pass
						else:
							if(self.answernick[int(msg)] in self.score):
								self.score[self.answernick[int(msg)]]+=3
								#Favorits
								player=self.answernick[int(msg)] #put that in .add #he? I don't understand my own comment ;-)
								self.fav.add(player, nick)
								
								if self.splitpoints:
									self.scores[self.answernick[int(msg)]]=self.scores[self.answernick[int(msg)]]+" 3<-"+nick #
							else:
								self.score[self.answernick[int(msg)]]=3
								#Favorits
								player=self.answernick[int(msg)]
								self.fav.add(player, nick)
								
								if self.splitpoints:
									self.scores[self.answernick[int(msg)]]=" 3<-"+nick
						self.guessed.append(nick)
					except: #trying to catch all
						self.bot.logger.debug("Error in msg"+str(sys.exc_info()[1]))
						pass
					if len(self.guessed) == len(self.players):
						self.end_of_quiz()

	def nip_hof(self,hofdataf,action):
		if action=="read":
			try:
				cnt=0
				hofFile=open(hofdataf, "r")
				hofData=hofFile.read()
				hofFile.close()
				thof={}
				hof=[]
				for line in hofData.split("\n"):
					if len(line) > 1:
						pair=line.split("=",1)
						try:
							thof[pair[0]]=int(pair[1])
							hof.append("")
							cnt+=1
						except:
							self.bot.logger.debug("Error in "+hofdataf)
				pairs = sorted((key,value) for (value,key) in thof.iteritems())
				hcnt=len(pairs)-1 
				for value, key in pairs:
					hof[hcnt]=key,value
					hcnt-=1
				#HoF filled and sorted
				return hof
	
			except IOError:
				self.bot.logger.debug("Could not open HoF Data "+hofdataf)
				try:
					self.bot.logger.debug("Creating "+hofdataf)
					hofFile = open(hofdataf, "w")
					hofFile.close()
					self.bot.logger.debug("File created "+hofdataf)
				except IOError:
					self.bot.logger.info("Could not create "+hofdataf+str(IOError))
	
		self.bot.logger.debug("HoF Data ready to use")
		if action=="write":
			self.bot.logger.debug("Writing HOF to file "+hofdataf)
			ts=time.strftime('%Y%m%d_%H%M%S')
			hofarchivfile=self.niparchivdir+self.hofdatafile+"."+ts
			self.bot.logger.info("Creating HoF Archiv "+hofarchivfile)
			try:
				shutil.copyfile(hofdataf, hofarchivfile)
			except:
				self.bot.logger.info("Couldn't create "+hofarchivfile+" "+str(IOError))	
			try:
				hofFile=open(hofdataf, "w")
				cnt=0
				for key, val in self.hof:
					hofFile.write(str(key)+"="+str(val)+"\n")
					cnt+=1
					if cnt > self.hof_max_player:
						break
						hofFile.close()
				hofFile.close()
			except IOerror:
				self.bot.logger.debug("Could not open or write to "+hofdataf)

	####
	
	def nip_hof_update(self, hofdataf):
		if len(self.allscore):
			points=self.allscore.values()
			players=self.allscore.keys()
			for player in players:
				point=self.allscore[player]
				updateplayer=self.isinhof(str(player))
				if updateplayer:
					newscore=updateplayer[2]+point
					self.hof[int(updateplayer[0])-1]=player,newscore
				else:
					newscore=self.allscore[player]
					self.hof.append("dim") #d
					self.hof[len(self.hof)-1]=player,newscore
		#hmm let's write and "reload" HoF here, so we just call nip_hof_update when game ends with "aborted" and/or atexit
		if self.DATA_UPDATE_NEEDED:
			self.nip_hof(hofdataf,"write")
			self.hof=self.nip_hof(hofdataf,"read")
			self.bot.logger.debug("HoF updated")
		else:
			self.bot.logger.debug("HoF no updated needed")
	
	def isinhof(self, player, nocases=None):
		placecnt=0
		if self.hof==None:
			return False
		for hplayer, val in self.hof:
			placecnt+=1
			
			if nocases==None:
				if player==hplayer:
					return str(placecnt),hplayer, val
			else:
				if player.lower()==hplayer.lower():
					return str(placecnt),hplayer, val
		return False
	

	def save_score(self,force=None):
		#saving game scoring table for another external "HoF statistic" 4later use
		if len(self.allscore.values()) > 0: #no need to save empty scoretable
			self.bot.logger.debug("Saving score table")
			ts=time.strftime('%Y%m%d_%H%M%S')
			scorefile=self.niparchivdir+'NIPScore.'+ts
			try:
				sf=open(scorefile, "w")
				sf.write("GameStartTime="+str(self.starttime)+"\nGameStopTime="\
				         +str(time.strftime('%Y/%m/%d %H:%M:%S'))+"\nNo. of Rounds="+str(self.roundofgame)+"\n")
				for key, value in self.allscore.items():
					sf.write(str(key)+"="+str(value)+"\n")
				sf.close()
			except IOError:
				self.bot.logger.info("IOError on "+scorefile)
			finally:
				sf.close()
		else:
			self.bot.logger.debug("Did not store empty scoretable")
		if self.DATA_UPDATE_NEEDED or force:
				scorefile=self.nipdatadir+"NIPactScoreTable"
				self.bot.logger.debug("Saving "+scorefile+" update_need:"+str(self.DATA_UPDATE_NEEDED)+" Force:"+str(force))
				try:
					sf=open(scorefile, "w")
					pickle.dump(self.allscore, sf)
					sf.close()
				except IOError:
					self.bot.logger.info("IOError on "+scorefile)
				finally:
					sf.close()
		else:
			self.bot.logger.debug("No need to update ActScoreTable")


	def load_score(self):
		scorefile=self.nipdatadir+"NIPactScoreTable"
		try:
			sf=open(scorefile, "r")
			self.allscore=pickle.load(sf)
			sf.close()
		except IOError:
			self.bot.logger.info("IOError on "+scorefile)
			