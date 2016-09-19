# -*- coding: utf-8 -*-
# This file is an optional part of OtfBot.
# GPL'ed Version 2 + non-commercial use only
####################################################################################################################
"""
The NIP-game plugin isn't really suitable to be run within more than one channel concurrently
For now it's "multi-network" since every configured network will have its own data(files).
Starting a game is possible within any _configured_ channel meet the bot configuration.
#Floodprotection and completing/suggestion bot-commands are obsolete within the game, 
since they are now ported to the bot, you'll need my mod for that functionallity.
nTimer issues FIXED,Language support added, de en for now, 
TODO:flag skipped nipme questions as incapable of being used for NIP (e.g. by vote), and releasing NIP.db after rework
internal config"""
NIPRELEASE="1.1.4#DGREY#[ml]#NORM#"
DEFAULT_GAME_CHANNELS = "#nip" 
NIP_RULES_LINK = "https://github.com/raeTen/otfbot-misc/wiki/NIP"
NIP_SOURCE_LINK = "https://github.com/raeTen/otfbot-misc/blob/master/nip.py"
NIP_WIKI_LANGUAGES = "https://github.com/raeTen/otfbot-misc/wiki/"
WIKI_KNOWN_LANGUAGES = ['de','en','ru','fr']
DEFAULT_COLOR_DECORATOR="♦ "
""" set NIP_SPOIL to True only if your configuration uses real irc hostnames as network (name)configuration| meet bot configuration"""
NIP_SPOIL=False
#other internal config values
DEFAULT_NIP_MIN_PLAYER=5
DEFAULT_NIP_MAX_PLAYER=24
DEFAULT_MAX_NICK_LEN=13
AUTOREMOVE_PLAYER_AFTER_ROUNDS_OF_INACTIVITY=2 # !autoremove
NIP_TIMEOUT_BASE=60 #seconds,
"""internal game phases don't edit"""
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
import shutil, time, random, string, os, re
import math, pickle, atexit,datetime,operator,sys
import sqlite3 as sqlite
try:
    from otfbot.lib import wiki_body_parser
except:
    NIP_WIKI_LANGUAGES = ""
    pass

class Plugin(chatMod.chatMod):
    def __init__(self, bot):
        self.bot=bot
    def start(self):
        atexit.register(self.nipexithook)
        self.languages=self.init_languages()
        self.fav=self.favorits()
        self.NIPbuffer=self.NIPqb()
        self.NIPnetwork=self.NIPNET()
        self.default_nip()
        self.nip_init()
        self.init_vars()
        self.NIP_network_pid(False,False,"cleanup")
        if os.path.isfile(datadir+'/NIP.db'):
            self.bot.logger.info("NIP.db found, ready to use")
            self.NIPdb=datadir+'/NIP.db'
        else:
            self.NIPdb=False;
            self.bot.logger.info("NIP.db not found")

    class favorits():
        def __init__(self):
            self.favdict = {}   
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
        def clear(self, acthof): #will remove any "favoritee" not found in "HoF"
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
                self.bot.logger.info("error while saving NIPbuffer")
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
######################## functions below
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
            self.nipmsg_("PRE_H"+self.NAMEOFGAME+"-engine ["+NIPRELEASE+"] initialised", channel)

    def nipexithook(self):
        self.NIPbuffer.save(self.nipdatadir+"NIPbuffer")
        self.nip_hof_update(self.nipdatadir+self.hofdatafile)
        self.save_score(True)
        self.fav.save(self.nipdatadir+self.favfile)
        pass

    def datafiles_loading(self):
        self.load_score()
        self.hof=self.nip_hof(self.nipdatadir+self.hofdatafile,"read")
        self.NIPbuffer.load(self.nipdatadir+"NIPbuffer")
        self.fav.load(self.nipdatadir+self.favfile)

    def nip_init(self): 
        self.DATA_UPDATE_NEEDED=False
        self.POLLTIME=2            #timer poll in seconds
        self.NAMEOFGAME="\x1F\x0314.-\x037~\x034\x02\x035No\x034He\x037ad \x02\x0314is \x037Pe\x034rfe\x035ct\x034\x037~\x0314-.\x0F".decode(self.NIPencoding)
        self.HALLOFFAME="\x1F\x0314.-\x037~\x034=_\x02\x035H\x034al\x037l \x02\x0314of\x02 \x037F\x034a\x035me_\x034=\x037~\x0314-.".decode(self.NIPencoding)
        self.SCORETABLE="\x1F\x0314.-\x037~\x034=\x02\x035Sc\x034or\x037in\x02\x0314g T\x037a\x034b\x035le\x034=\x037~\x0314-.".decode(self.NIPencoding)
        self.GAMECHANNEL=""
        self.nicknames={}        #expandable nick database f/m
        self.allscore={}        #dict holding th socring
        self.nTimer=self.nT_init() #(used for different timeouts and automatic gameflow)
        self.GL_TS=0            #timestamp for timeouts
        self.gamespeed=False         #default gamespeed=1 normal 2= faster timeouts/2
        self.testing=False        #test mode
        self.autoremove=True     #"!autoremove" toggles 0|1, if set to 1 - players will be removed from list when they do not send in question/answer 
        self.splitpoints=True         #!splitpoints" toggles between 0|1, used to show splittet points. if true returns details in scoring 
        self.hookaction="None"    #which function to call on timerhook
        self.hof_show_max_player=8  #max player from HoF to send in channel #
        self.hof_max_player=999 
        self.nickvoted_end=[]
        self.nickvoted_skip=[]
        self.votedEnd=False
        self.newplayers=[]        #buffer joins  
        self.hof=[]
        self.NKN=[]
        self.othergames=[]
        self.warned_players=""    #dynamic str to be replaced in nipmsg
        self.nipvalue=1            #value for sending in NIP-Question [0-5] to be set by gameadmin if disered in "startphase"
        self.wikilink = NIP_WIKI_LANGUAGES
        self.bot.logger.info("NIP Plugin release "+NIPRELEASE+" initialised")

    def default_nip(self):
        self.NIPencoding='utf-8'
        self.cchar="!"
        self.pchar=""
        self.hofdatafile="niphof.txt"
        self.favfile=str("fav.data")
        self.nipbufferfile=str("NIPbuffer")
        self.actscoretable=str("NIPactScoreTable")
        self.channels=self.bot.config.get("nipchannels", DEFAULT_GAME_CHANNELS, "main",self.bot.network).split() #NIP internal multichannel support
        self.nip_spoil=self.bot.config.getBool("nip_spoiling", NIP_SPOIL, "main",self.bot.network)
        self.joinkey=self.bot.config.get("nip_join_key", "ich", "main",self.bot.network).decode(self.NIPencoding)
        self.default_language=self.bot.config.get("nip_lang", "de", "main",self.bot.network).decode(self.NIPencoding)
        self.minplayers=DEFAULT_NIP_MIN_PLAYER
        self.maxplayers=DEFAULT_NIP_MAX_PLAYER
        self.maxnicklen=DEFAULT_MAX_NICK_LEN
        self.nickWarnMax=AUTOREMOVE_PLAYER_AFTER_ROUNDS_OF_INACTIVITY
        self.init_timeouts(NIP_TIMEOUT_BASE)
        self.NIPRULES=NIP_RULES_LINK
        self.NIPSOURCE=NIP_SOURCE_LINK
        self.mirc_stuff_init()
        self.kcs=["clearfav","pchar","evol","vote","halloffame","hof","nip_hof","nip_place","place","splitpoints",\
                   "abortgame","reset","nip_startgame","startgame","restartgame", "kill",\
                   "nip_scores", "nip_ranking","scores", "gamespeed", "autoremove","nip_favorits","nip_groupies",\
                   "favorits","groupies","continue", "players","nip_rules","rules","nip_source","nip_status",\
                   "status","nip_help","help","joingame","partgame",\
                   "autorestart","testing","nip_version","nip_credits","version","credits","nip_channels",\
                   "nohead","nipme","skip_question","laplimit","timelimit","nipvalue"]
        self.language=self.import_language(self.default_language) #dict containing actual messages belonging to given language

    def init_timeouts(self, timeOutBase):
        """!gamespeed will toggle between halve and default values"""
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
        self.timeouts['QUIZ_TIME']=TimeBase-10       #60 time waiting for quiz answers, nTimerset will add foo seconds for each player
        self.timeouts['QUIZ_TIME_ADD']=9         #add seconds to QUIZ_TIME for each player
        self.timeouts['TIMEOUT']=2*TimeBase         #300 idle time until game stops to "game_waiting", "waiting_for_gamemaster" NIP-Question
        self.timeouts['STARTPHASE']=TimeBase*8         #large initial timeout - catching players ;) 
        self.timeouts['GAMEADMINNOTIFY']=TimeBase     #sends a "highlight" to a sleeping "gameadmin"
        self.timeouts['GAMEADMINKICK']=TimeBase     #kick lazy gameadmin from game, not from irc 

    def mirc_stuff_init(self):
        """defining mirc colors and colored labels"""
        self.NIPPREFIX="\x0F\x0316,14NIP\x033\x0F" #eyecatcher for game output 
        self.colors={}
        self.colors["#BOLD#"]="\x02".encode(self.NIPencoding) #toogle like irc sequence
        self.colors["#NORM#"]="\x0F".encode(self.NIPencoding) #resetallMIRColorslike
        self.colors["#UNDERLINE#"]="\x1F".encode(self.NIPencoding) # tooglelike 
        mcolor=['#BLACK#','#DBLUE#','#DGREEN#','#LRED#','#DRED#','#DMAGENTA#',\
                '#DYELLOW#','#LYELLOW#','#LGREEN#','#DCYAN#','#LCYAN#','#LBLUE#',\
                '#LMAGENTA#','#DGREY#','#LGREY#','#WHITE#']
        n=0
        for m in mcolor:
            n+=1
            self.colors[m] = ("\x03"+str(n)).encode(self.NIPencoding)
        if self.pchar: #colored decorator character
          pchar=self.pchar[0:4]
        else:
          pchar=DEFAULT_COLOR_DECORATOR.decode(self.NIPencoding)
        self.pres={}
        """N=Black default || Q=Red requesting Question/answer||  A=dgreen correct answer || C=lgreen given answers
                S=dyellow scoring || H=cyan helping msg || X=magenta msg for admin || G=dred game status || P=lblue punishments
                Z=dred Hall of fame || Y=hall of fame top || V=dcyan Votes || D=dgrey misc    """
        pres={'N':1,'Q':4,'A':3,'C':9,'S':7,'H':11,'X':6,'G':5,'P':12,'Z':5,'Y':8,'V':10,'D':14}
        for pre in pres:
            self.pres["PRE_"+pre]="\x03"+str(pres[pre])+pchar+"\x0F".encode(self.NIPencoding)

    def init_vars(self):
        self.phase=NO_GAME
        self.players=[]        #dynamic list for active nicks in game
        self.gameadmin=""
        self.gamemaster=""     #different for each round.
        self.gamemasterold=""     #used to catch lazy user, who wants to cheat by removing and adding himself as gamemaster!
        self.question=""
        self.answers={}
        self.answernick={}     #usernames(!) for the numbers
        self.score={}
        self.scores={}         #live splitted scores
        self.guessed=[]     #nicks, which already have guessed 
        self.dynamic_val=""    #output buffer for nipmsg()
        self.hint=None
        self.abortcnt=0
        self.resetcnt=0     #used to punish a gamemaster who resets game to WAITING_FOR_QUESTION
        self.starttime=time.strftime("%Y/%m/%d %H:%M:%S") #used for scoring table data on disc when game ends
        self.roundofgame=0     #counter, used in game as info, maybe good for new statistic
        self.eoq_cnt=0         #see end_of_quiz ~used for debugging #obsolete when everything works
        self.votedEnd=False     #important to reset here...
        self.userWarnCnt={}     #used for autoremoving player
        self.nohead=False        #toggled on|off by Gamemaster (!nohead), for true !nipme will fill in a random question
        self.nipmeused=False    #flag showing if gamemaster used DB for question/answer
        self.gametime=0            #overall game time in seconds, used for status and timelimit
        self.timelimit=False    #minutes - could be set bei gameadmin, game ends after reaching this timelimit if set, last lap will be completed
        self.laplimit=False     #could be set by gameadmin, game ends after reaching number of laps, last lap will be completed
        self.autorestart=False      #!autorestart 1=gameadmin does not need to !restartgame, the bot does itself
        self.minplayers=DEFAULT_NIP_MIN_PLAYER
        self.testing=False

    def init_vars_for_restart(self):
        self.abortcnt=0     
        self.question=""
        self.answers={}
        self.answernick={}     #usernames(!) for the numbers
        self.score={}
        self.scores={}
        self.guessed=[]     #nicks, which already have guessed
        self.hint=None
        self.roundofgame+=1
        self.nickvoted_end=[]
        self.nickvoted_skip=[]
        self.new_gamemaster()
        self.nipmeused=False

    def new_gamemaster(self):
        """ each player will (has to be) the gamemaster in chaotic order, cheatprotection incl.  """
        if len(self.gamemasterold) > 0:             #we have a cheat candidate
            if str(self.gamemasterold) in self.players:     # and the cheater is back in next round, so 
                self.nipmsg("PRE_P, "+self.gm('msg_cheat'))
                self.add_allscore(str(self.gamemasterold),-2)
                self.gamemaster=self.gamemasterold
                if self.gamemaster in self.players:
                    self.players.remove(self.gamemaster)
            else:
                self.gamemasterold=""             #did not rejoin the game, so he did not try to cheat
        if len(self.gamemasterold) == 0: #change gamemaster if no cheater
            if len(self.gamemaster) > 0 and not self.gamemaster in self.players:
                self.bot.logger.debug("Pushing gamemaster back to players -"+str(self.gamemaster))
                self.players.append(self.gamemaster)     #puts him back to the end    
            self.gamemaster=self.players[0]         #sets the next
            self.players=self.players[1:]
            self.gamemasterold=""
            self.resetcnt=0
            self.bot.logger.debug("Setting new Gamemaster to: "+self.gamemaster)
        self.gamemasterold = ""

    def replace_nipmsg(self, cmsg, gnick):
        rw={"#QUESTION#":self.question,"#RESTTIME#":str(self.GL_TS),"#CCHAR#":str(self.cchar),"#GAMEADMIN#":self.gm('label_gameadmin'),\
            "#GAMEMASTER#":self.gm('label_gamemaster'),"#MAXNICKLEN#":str(self.maxnicklen),"#NIPWARNINGS#":self.gm('label_warning'),\
            "#NIPQUESTION#":self.gm('label_nipquestion'),"#POINT#":self.gm('label_point'),"#POINTS#":self.gm('label_points'),"#LAZY#":self.gm('label_lazy'),\
            "#HELPBUG#":self.gm('msg_help_bug'),"#HELPADMIN#":self.gm('msg_help_admin'),"#HELPUSER#":self.gm('msg_help_user'),"#MINPLAYERS#":str(self.minplayers),"#NIPCHANNELS#":self.nice_channels(),\
            "#JOINKEY#":self.joinkey,'#GAMEMASTEROLD#':self.gamemasterold,"#BOTNICK#":self.bot.nickname,"#GAMECHANNEL#":self.GAMECHANNEL,\
            "#NAMEOFGAME#":self.NAMEOFGAME,"#ROUNDOFGAME#":str(self.roundofgame),"#N_LAP#":self.gm('label_lap'),"#PLAYERS#":self.gm('label_players'),\
            "#PLAYER#":self.gm('label_player'),"#HALLOFFAME#":self.HALLOFFAME,"#ALLPLAYERNAMES#":self.show_players(self.GAMECHANNEL, True),\
            "#WARNPLAYERS#":self.warned_players,"#DYNVAL#":self.dynamic_val,"#MISSINGANSWERS#":self.get_missing_qty(),"#OTHERGAMES#":self.othergames,\
            "#NIPANSWER#":self.gm('label_nipanswer'),"#NIPHINT#":self.gm('label_niphint'),"#NIPVALUE#":str(self.nipvalue)}
        if cmsg.count("#N_GAMEADMIN#"):
            cmsg=cmsg.replace("#N_GAMEADMIN#",self.gameadmin)
        if cmsg.count("#N_GAMEMASTER#"):
            cmsg=cmsg.replace("#N_GAMEMASTER#",(self.gamemaster if len(self.gamemaster)>0 else self.gamemasterold) )
        for kw in rw:
            if cmsg.count(kw):
                if rw[kw].count('|'):
                    mf = rw[kw].split('|')
                    rw[kw]=mf[1] #default f
                    if gnick != "":
                        if gnick.lower() in self.nicknames:
                            rw[kw] = mf[0] if self.nicknames[gnick.lower()]=="m" else mf[1]
                    if  gnick == "":
                        for nick in self.nicknames:
                            check=cmsg.lower().split(nick)
                            if len(check)>=2: #hit on nick in nicknames dict
                                rw[kw] = mf[0] if self.nicknames[nick]=='m' else mf[1]
                                break
                cmsg=cmsg.replace(kw,rw[kw].strip())
        return cmsg

    def replace_pre_color(self, cmsg, gnick=None):
        gnick = "".encode(self.NIPencoding) if gnick == None else gnick.encode(self.NIPencoding)
        for pre in self.pres.keys():
            if cmsg.count(pre):
                val=self.pres.get(pre, "")
                cmsg = cmsg.replace(pre, val+("" if gnick=="" else gnick))
        cmsg = self.replace_nipmsg(cmsg, gnick)
        for color in self.colors.keys():
            if cmsg.count(color):
                val=self.colors.get(color, "")
                cmsg = cmsg.replace(color,val)
        return cmsg

    def replace_niprun(self, cmsg):
        if cmsg.count("#NIPRUN#"):
            add=''
            if self.gametime:
                add='('+str(self.sec2str(self.gametime))+')'
            cmsg = cmsg.replace("#NIPRUN#",self.gm('status_run')+add)
        return cmsg

    def sendmsg_(self, target, cmsg, encoding=None):
        self.bot.sendmsg(target, self.replace_pre_color(cmsg, target), encoding)

    def nipmsg_(self, cmsg, ochannel=None, gnick=None):
        """msg without need of translations / replacements"""
        self.nipmsg(cmsg, ochannel, gnick)

    def nipmsg(self, cmsg, ochannel=None, gnick=None):
        if ochannel==None and not self.GAMECHANNEL:
            self.bot.logger.debug("Dropped nipmsg (no gamechannel)- "+cmsg)
        else:
            cchannel=self.GAMECHANNEL if ochannel==None else ochannel
            cmsg=self.replace_pre_color(cmsg, gnick)
            cmsg=self.replace_niprun(cmsg)
            self.bot.sendmsg(cchannel, str(self.NIPPREFIX)+cmsg, self.NIPencoding)

    def nT_init(self):
        return timehook.LoopingCall(self.nTimerhook)

    def start_timer(self):
        try:
            self.nTimer.start(self.POLLTIME)
        except:
            pass

    def stop_timer(self):
        run=False
        try:
            if self.nTimer.running:
                run=True
        except:
            self.bot.logger.debug("nTimer"+str(sys.exc_info()[1]))
            pass
        try:
            if run:
                self.nTimer.stop()
                self.bot.logger.debug("Timer stopped")
        except:
            pass

    def NOP(self, channel):
        self.nipmsg_("PRE_ZNOP",channel)

    def nTimerhook(self):
        """ this hook is compatible with NE555 because art always happens by happy accidents :-)       """
        self.check_limits()
        self.GL_TS -= self.POLLTIME
        self.gametime += self.POLLTIME
        
        if self.GL_TS <= 0:
            if self.hookaction=="end_of_quiz":
                self.bot.logger.debug("hookaction->"+str(self.hookaction)+" Phase:"+str(self.phase))
                self.hookaction="None"
                if self.phase:
                    """ Avoids a runtime condition votedend/normal end"""
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
                self.playerwarned=True

    def toggle_timer(self):
        """ testing purposes only """
        if self.nTimer.running:
            self.stop_timer()
        else:
            self.start_timer()

    def nTimerset(self, REQ_TIME, REQ_ACTION):
        """dynamically longer timeouts for some conditions (ircd thwarts game when playing with more players )"""
        if type(REQ_TIME)==str:
            REQ_TIME=int(self.timeouts.get(REQ_TIME, 60))
        addtime=2
        if self.phase==QUIZ:
            addtime=self.player_qty()*int(self.timeouts.get('QUIZ_TIME_ADD',5))
            self.bot.logger.debug("Expanding Timeout "+str(addtime))
        self.hookaction=REQ_ACTION
        divider = 2 if self.gamespeed else 1
        self.GL_TS=(REQ_TIME+addtime)/divider
        self.warn_ts=self.GL_TS / 3     #used for "warning" "sleeping" players
        self.playerwarned=False #bool to avoid multiple warnings
        self.start_timer()
        self.bot.logger.debug("Starting Timer: polltime=" +str(self.POLLTIME)+" REQ_ACTION:"+\
            str(self.hookaction)+" REQTIME:"+str(self.GL_TS)+" warn_ts:"+str(self.warn_ts))

    def check_limits(self):
        if self.timelimit:
            if self.gametime/60 >= self.timelimit:
                if not self.votedEnd:
                    self.votedEnd = True
                    self.nipmsg("PRE_V"+self.gm('msg_timelimit_hit'))
                    if self.phase != GAME_WAITING:
                        self.nipmsg("PRE_V"+self.gm('msg_end_after_lap'))
                    if self.phase == GAME_WAITING:
                        self.bot.logger.debug("endofgame due to timelimit reached within pause")
                        self.end_of_game()
        if self.laplimit:
            if self.roundofgame >= self.laplimit:
                if not self.votedEnd:
                    self.votedEnd = True
                    self.nipmsg("PRE_V"+self.gm('msg_laplimit_hit'))
                    if self.phase != GAME_WAITING:
                        self.nipmsg("PRE_V"+self.gm('msg_end_after_lap'))
                    if self.phase == GAME_WAITING:
                        self.bot.logger.debug("endofgame due to laplimit reached within pause")
                        self.end_of_game()

    def notify_gameadmin(self):
        if self.gameadmin!="":
            if not self.autorestart:
                self.nTimerset('GAMEADMINKICK', "kick_gameadmin")
                append= "#CCHAR#restartgame (or #CCHAR#autorestart)" if self.phase == WAITING_FOR_PLAYERS else "#CCHAR#startgame!"
                self.nipmsg("PRE_X,"+self.gm('msg_admin_remind')+append, None, self.gameadmin)
            else:
                self.restart_the_game(self.gameadmin, self.GAMECHANNEL)
                return True
        else:
            if not self.phase==WAITING_FOR_PLAYERS and not self.phase==NO_GAME:
                self.show_players()
                self.nipmsg("PRE_X"+self.gm('msg_continue'))
                self.phase=GAME_WAITING

    def kick_gameadmin(self, refby=None):
        self.bot.logger.debug("kick_gameadmin refby "+str(refby))
        if self.gameadmin!="":
            gameadmin=self.gameadmin
            self.nipmsg("PRE_X"+self.gm('msg_admin_lost'))
            self.gameadmin=""
        else:
            self.show_players()
            self.nipmsg("PRE_X"+self.gm('msg_continue_restart'))

        if not self.phase==WAITING_FOR_PLAYERS and not self.phase==NO_GAME: 
            self.phase=GAME_WAITING
        else:
            self.nipmsg("PRE_X"+self.gm('msg_continue_start'))

    def handle_nicknames(self, nick, mf=None):
        nick=nick.lower()
        if mf == "s":
            if nick in self.nicknames:
                self.sendmsg_(nick, self.nicknames[nick], self.NIPencoding)
                return False
        if not nick in self.nicknames:
            if nick[-1]=='a' or nick[-1]=='o':
                self.nicknames[nick]='f'
            else:
                self.nicknames[nick]='m'
        if mf:
            self.nicknames[nick]=str(mf)
        if len(self.nicknames) > 0:
            nickfile=self.nipdatadir+"nickNames"
            try:
                sf=open(nickfile, "w")
                pickle.dump(self.nicknames, sf)
                sf.close()
            except IOError:
                self.bot.logger.info("IOError on "+nickfile)
            finally:
                sf.close()

    def nick2long(self, nick, channel):
        self.nipmsg("PRE_X,"+self.gm('msg_nick_length'), channel, nick)

    def add_player(self, addnick, init=True):
        if self.phase==NO_GAME:
            return False
        if len(addnick) > self.maxnicklen:
            self.nick2long(addnick, self.GAMECHANNEL)
        else:
            addnick=addnick[:self.maxnicklen]
            self.handle_nicknames(addnick.lower())
            if addnick in self.players:
                return False
            else:
                if self.check_maxplayer():
                    if addnick!=self.gamemaster:
                        if not self.phase==WAITING_FOR_PLAYERS: #do not add while waiting for "self.joinkey" in startphase
                            self.nipmsg("PRE_X,"+self.gm('msg_nick_added'), None, addnick)
                        self.bot.logger.debug("add_player: Appending player:"+addnick)
                        """open a query to user initially"""
                        if init:
                            self.sendmsg_(addnick ,self.gm('query_init'), self.NIPencoding)
                        self.players.append(addnick)
                    return True

    def del_player(self, delnick, refby=None): #refby=call other subroutines or not
        self.bot.logger.debug("del_player refby:"+str(refby))
        #cheatprotection
        if delnick==str(self.gamemaster) and self.gamemasterold=="":
            self.gamemasterold=delnick
            self.bot.logger.debug("set Gamemasterold="+self.gamemasterold)
        if not self.votedEnd:
            #once voted a game_end, do NOT remove players
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
                    if not self.answers.has_key(delnick):     #avoids eog while gamemaster had sent in question AND answer
                        self.end_of_quiz()

            if c:     #changed
                if delnick:
                    if refby=="autoremoving":
                        self.nipmsg("PRE_X "+self.gm('msg_autoremoved'), None, delnick)
                    else:
                        self.nipmsg("PRE_X "+self.gm('msg_parted_1'), None, delnick)
                if delnick in self.newplayers:
                    self.newplayers.remove(delnick)
                    if not delnick in self.players:
                        self.nipmsg("PRE_X"+self.gm('msg_parted_2'),None, delnick)
        else:
            if not self.phase==NO_GAME and not self.phase==GAME_WAITING:
                self.nipmsg("PRE_V,"+self.gm('msg_voted_end_misc'),None, delnick)

    def getfm(self, nick):
        return "_" + self.nicknames[nick.lower()]\
                if nick.lower() in self.nicknames else "_u"

    def show_players(self, channel=None, returnonly=None):
        pnr=len(self.players)
        pnr=0
        splayers=""
        for tplayer in self.players:
            if tplayer == self.gameadmin:
                tplayer = "#UNDERLINE##BOLD#"+tplayer + "#BOLD##UNDERLINE#"
            if tplayer != self.gamemaster:
                splayers = splayers+ " " + tplayer
            pnr+=1
        if self.gamemaster:
            splayers=splayers+" #NORM##LRED#" + self.gamemaster +"#NORM#"
            pnr+=1
        if returnonly==None:
            pn=" #PLAYER#:" if pnr==1 else " #PLAYERS#:"
            self.nipmsg_("PRE_G"+str(pnr)+pn+splayers, channel)
        else:
            return splayers

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
        if self.phase==WAITING_FOR_QUESTION:
            wplayers=str(self.gamemaster)
        if len(wplayers) > 1:
            self.warned_players=wplayers
            self.nipmsg("PRE_H#NIPWARNINGS# #WARNPLAYERS# #DGREY#")

    def new_gameadmin(self, gnick):
        self.bot.logger.debug("new_gameadmin <"+gnick+"> phase:"+str(self.phase))
        if self.phase==GAME_WAITING: #not for no_game
            self.nTimerset('GAMEADMINNOTIFY',"notify_gameadmin")
        if len(gnick) <= self.maxnicklen: 
            self.gameadmin=gnick
            self.add_player(gnick)
            self.nipmsg("PRE_X,"+self.gm('status_is_gameadmin'), None, gnick)
        else:
            self.nick2long(gnick, self.GAMECHANNEL)
    
    def player_qty(self):
        plc=len(self.players)
        if self.gamemaster:
            plc+=1
        return plc
    
    def check_maxplayer(self):
        if self.player_qty() >= self.maxplayers:
            self.nipmsg("PRE_X"+self.gm('msg_max_players'))
            self.bot.logger.debug("MaxPlayer "+str(self.maxplayers))
            return False
        else:
            return True
    #hoockaction
    def end_of_answertime(self):
        self.phase=QUIZ
        self.nTimerset('QUIZ_TIME', "end_of_quiz") #needs to be here 
        count=1
        self.nipmsg("PRE_Q"+self.gm('msg_main_question'))
        self.nipmsg("PRE_G"+self.gm('msg_main_answer_top'))

        nicks=self.answers.keys()
        random.shuffle(nicks)
        for nick in nicks:
            self.nipmsg_("PRE_C#BOLD#"+str(count)+"#BOLD#. "+self.answers[nick])
            self.answernick[count]=nick
            count+=1
        self.nipmsg("PRE_G"+self.gm('msg_main_answer_bottom'))

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
        """ output score valuation """
        if len(self.score):
            for player in self.score:
                pword="#LRED##POINTS#"
                pscore=self.score[player]
                pscores="" #show splitted if more than one point
                if pscore >= 9:
                    """ three in a row bonus """
                    pscore+=2 
                    self.score[player]+=2
                    self.scores[player]+="#DRED# +2 #POINTS# "+self.gm('label_threeinrow_bonus')+"#NORM##DGREY#"
                pword = "#LMAGENTA##POINT#" if pscore == 1 else "#LMAGENTA##POINTS#"
                if self.splitpoints: #show details of scoring
                    pscores="#DGREY#("+self.scores[player]+")#NORM#" 
                if str(player) in self.answernick.values(): #no points for no given nip answer but guessing the 'correct' answer
                    self.nipmsg_("PRE_S #BOLD#"+str(pscore)+"#BOLD##NORM# "+pword+" "+pscores, None, player)
                else:
                    self.dynamic_val=str(pscore)
                    msg_name = "msg_nopoint" if pscore == 1 else "msg_nopoints"
                    self.nipmsg("PRE_P "+self.gm(msg_name),None, player)
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
        if self.votedEnd:
            return False
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

    def get_gmaster(self):
        return self.gamemaster if len(self.gamemaster)>0 else self.gamemasterold 
        
    def correct_answer(self, snum):
        gmaster=self.get_gmaster()
        correct = "PRE_A"+self.gm('msg_main_answer_presenting')+"#NORM#"+str(snum)+" ["+self.answers[gmaster]+"]"
        if self.hint:
            correct=correct+"#NORM# (#DGREY#"+self.hint+"#NORM#)"
        else:
            correct=correct+"#NORM#"
        """ question and answer were complete so rewarded with self.nipvalue point"""
        self.add_allscore(gmaster ,self.nipvalue)
        msg_id="msg_nipme_point_back" if self.nipmeused else "msg_nipquestion_point"
        self.nipmsg("PRE_X"+self.gm(msg_id) )
        return correct
    
    def no_nip_question(self):
        gmaster = self.get_gmaster()
        if not self.answers.has_key(gmaster):
            self.add_allscore(gmaster ,-1)
            self.nipmsg("PRE_X "+self.gm('msg_nipquestion_point_deduct'), None, gmaster)

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
        
        if not self.votedEnd: #votedEnd also means gameadmin did !abortgame or time/lap limit reached
           self.phase=GAME_WAITING
        #show who gave which answer
        if self.eoq_cnt==self.roundofgame: #avoids double scoring, at least for debugging
            self.bot.logger.debug("EndOfQuiz called more than once!")
        else:
            fromwho, snum=self.answer_from_who() #builds the string for output and gives no. of right answer
            self.quiz_scoring() #throws score results and does calculalations
        
        self.nipmsg("PRE_X"+self.gm('msg_end_lap'))
        if snum > 0: # 0= at least no given answer
            self.nipmsg_(self.correct_answer(snum))
            self.nipmsg_(fromwho)
            self.gamemasterold="" #reset cheatprotection Nipquestion was given
        else: 
            if self.eoq_cnt==self.roundofgame:
                self.bot.logger.debug("EndOfQuiz called more than once!")
            else:
                self.autoremoving() #
                self.no_nip_question()
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
        self.nipmsg("PRE_X"+self.gm('msg_game_finished'))
        self.phase=NO_GAME
        self.gameadmin=""
        self.gamemaster=""
        self.nip_hof_update(self.nipdatadir+self.hofdatafile)
        self.save_score()
        self.fav.save(self.nipdatadir+self.favfile)
        self.players=[]
        self.nickvoted_end=[]
        self.nickvoted_skip=[]
        self.NIP_network_pid(self.bot.network,self.GAMECHANNEL,'end_of_game')
        self.GAMECHANNEL=""
        self.bot.logger.info("Gamechannel disangeged")

    def get_vote_ratio(self):
        """ returns how many players should have voted for end or skip question from Database. 
        votes need a bit more than 30% of players to be a voted for        """
        return int(round((self.player_qty()+1) * 0.4)+0.49)

    def nip_vote(self, vuser, votelist, option):
        """ vote for game "end" or "skip"ping_any nipquestion """
        vote_min_player = self.get_vote_ratio()
        if not vuser in votelist and (vuser in self.players or vuser==self.gamemaster):
            votelist.append(vuser)
        votes = len(votelist)
        if int(votes) >= vote_min_player:
            return True
        else:
            """ needs more player to vote """
            self.nipmsg("PRE_Vvoted "+option+" "+str(votes)+" / "+str(vote_min_player)+" #PLAYERS#")
            return False

    def request_answers(self):
        self.nipmsg("PRE_A"+self.gm('msg_get_answers'))

    def start_waiting_for_answers(self, nick, channel):
        self.phase=WAITING_FOR_ANSWERS
        self.nTimerset('ANSWER_TIME', "end_of_answertime")
        self.nipmsg("PRE_Q"+self.gm('msg_main_question'),channel)
        self.request_answers()

    def check_nip_buffer(self, nick, channel): 
        uservals=self.NIPbuffer.get(nick)
        if uservals[0]!="" and uservals[1]!="":
            self.question=uservals[0]
            self.answers[nick]=uservals[1]
            self.hint=uservals[2]
            self.NIPbuffer.clean(nick)
            self.start_waiting_for_answers(nick, channel)
            return True
        else:
            return False
    
    def nip_buffer(self, user, channel, command, options):
        bmsg=""
        nick=user.getNick()
        cmd=command[0]
        if cmd=="h":
            bmsg=self.gm('msg_help_nipbuffer_main')+"\n"+\
                        self.gm('msg_help_nipbuffer_detail')
        elif cmd=="q" or cmd=="a" or cmd=="t" or cmd=="n":
            if len(command) == 1:
                if options:
                    self.NIPbuffer.put(nick, cmd, options)
                rv=self.NIPbuffer.get(nick)
                bmsg=self.gm('label_nipquestion')+":"+rv[0]+"\n"+\
                    self.gm('label_nipanswer')+":"+rv[1]+"\n"+\
                    self.gm('label_niphint')+":"+rv[2]+"\n"+\
                    self.gm('msg_help_nipbuffer_detail_2')
        if bmsg:
            self.sendmsg_(nick, bmsg,self.NIPencoding)

    def restart_the_game(self, nick, channel):
        if self.votedEnd:
            return False
        if self.gameadmin == "" and self.phase==GAME_WAITING:
            self.new_gameadmin(nick)
            """remains pausing the actual game without "timer" functionallity"""
        if self.phase == GAME_WAITING and nick == self.gameadmin:
            if self.player_qty() >= self.minplayers:
                tmpplayers=string.join(self.players," ")
                if self.gamemaster:
                    tmpplayers=self.gamemaster+" "+tmpplayers
                self.init_vars_for_restart()
                self.nipmsg("PRE_G"+self.gm('msg_lap_init'))
                self.phase=WAITING_FOR_QUESTION
                self.nTimerset('TIMEOUT', "end_of_quiz")
                if not self.check_nip_buffer(self.gamemaster, channel):
                    self.nipmsg("PRE_Q,"+self.gm('msg_get_question'),None, self.get_gmaster())
                    self.sendmsg_(self.gamemaster, self.gm('query_get_question'), self.NIPencoding)
            else:
                self.nipmsg("PRE_G"+self.gm('msg_few_players_2'))
    
    def is_it_eastern_again(self, user, command, options):
            if self.bot.auth(user):
                if command=="pchar":
                    self.pchar=options[0:4].decode(self.NIPencoding)
                    self.mirc_stuff_init()
                    self.bot.sendmsg(user,"Color decorator set to: "+options[0:4],self.NIPencoding)
                elif command=="evol":
                    self.pchar="❤ ".decode(self.NIPencoding)
                    self.mirc_stuff_init()

    def query_command(self, user, channel, cmd, options):
        if len(cmd) > 1:
            self.is_it_eastern_again(user, cmd, options)
        if len(cmd) == 1:
            nick=user.getNick()
            if nick!=self.gamemaster: 
                """ handle NIPbuffer !q !a !t !h + !f(emale) !m(ale)"""
                self.nip_buffer(user, channel, cmd, options)
            if cmd=="f" or cmd=="m" or cmd=="s":
                self.handle_nicknames(nick, cmd)
            return True
        return False

    def NIP_spoil(self, channel,command):
        if not self.nip_spoil:
            return False
        othergames=self.NIP_network_pid(self.bot.network, channel, command)
        if othergames:
            og=''
            for othergame in othergames:
                og=str(othergame)+' '+og
            self.othergames=og
            self.nipmsg("PRE_H"+self.gm('msg_spoil'),channel)
        else:
            self.nipmsg("PRE_H"+self.gm('msg_nospoil'),channel)
    
    def NIP_global_cmd(self, channel, command, options):
        """ returns the command to be processed elsewhere """
        if self.GAMECHANNEL == channel:
            """game running in this channel"""
            return command.replace('nip_','')
        if len(self.GAMECHANNEL) > 0:
            """game running in other channel"""
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

    def sec2str(self,runtime):
        return datetime.timedelta(seconds = runtime).__str__()

    def output_limits(self, channel):
        laps=str(self.laplimit) if self.laplimit else "none"
        WTL=self.gm('label_timelimit')
        WLL=self.gm('label_laplimit')
        WET=self.gm('label_time_elapsed')
        WRN=self.gm('label_lap')
        self.nipmsg_("PRE_X#BOLD#"+WTL+"#BOLD#:"+\
                    self.sec2str(self.timelimit*60)+\
                    " #BOLD#"+WLL+"#BOLD#:"+\
                    laps+\
                    " #BOLD#"+WRN+"#BOLD#:"+str(self.roundofgame)+\
                    " #BOLD#"+WET+"#BOLD#:"+str(self.sec2str(self.gametime)), channel )
    
    def output_gflags(self, channel):
        self.nipmsg_("PRE_X#BOLD#Minimum Players#BOLD# = "+\
                    str(self.minplayers)+\
                    " #BOLD#Maximum Players#BOLD# = "+\
                    str(self.maxplayers) ,channel)

    def output_oflags(self,channel):
        flags={'autorestart':0,'autoremove':0,'splitpoints':0,'gamespeed':['fast','normal'],'nohead':0,'testing':0,'votedEnd':['yes','no']}
        bmsg=""
        for flag in flags:
            words=['enabled','disabled'] if not flags[flag] else flags[flag]
            try:
                m = getattr(self, str(flag))
                bmsg='#NORM##BOLD#'+flag+'#BOLD#:'+('#LGREEN#'+words[0] if m else '#LRED#'+words[1])+' '+bmsg
            except:
                self.bot.logger.debug(str(sys.exc_info()[1]))
                pass
        try:
            bmsg='#NORM##BOLD#Timer#BOLD#:'+('#LGREEN#running' if self.nTimer.running else '#LRED#stopped')+' '+bmsg
        except:
            self.bot.logger.debug(str(sys.exc_info()[1]))
        self.nipmsg_("PRE_XPhase"+str(self.phase)+"("+str(self.GL_TS)+")"+bmsg,channel)

    def handle_nipvalue(self,nick,channel,cmd,options):
        loptions=options.split()
        if len(loptions) == 0:
            self.nipmsg("PRE_X"+self.gm('msg_init_nipvalue'), channel)
        else:
            if self.phase == WAITING_FOR_PLAYERS:
                if self.gameadmin == nick:
                    try:
                        newval=int(loptions[0])
                    except:
                        newval = 1
                    newval=newval if newval <6 else 1
                    newval=newval if newval >=0 else 1
                    self.nipvalue = newval
                    self.nipmsg_("PRE_XNipvalue="+str(self.nipvalue), channel)
                else:
                    self.NOP(channel)


    def handle_limits(self, nick, channel, cmd, options):
        if self.phase == NO_GAME:
            return False
        if nick == self.gameadmin:
            intval=False
            try:
                intval = int(options)
            except:
                pass
            if intval:
                if intval >= 2 and intval < 1000000:
                    if cmd == 'timelimit':
                        self.timelimit=intval
                    elif cmd == 'laplimit':
                        self.laplimit=intval
                    self.output_limits(channel)
            else:
                self.output_limits(channel)
        else:
            self.output_limits(channel)

    def game_flags(self,nick, gflag, cmd, words=None, flag_comment=None):
        if nick == self.gameadmin:
            gflag = not gflag
        if words:
            add = words[0] if gflag else words[1]
        else:
            add="is enabled" if gflag else "is disabled"
        self.nipmsg_("PRE_X#BOLD#"+cmd+"#BOLD# "+add)
        return gflag

    def check_stall(self):
        """ this should be obsolete """
        if self.GL_TS <= 0 and self.votedEnd and self.phase == GAME_WAITING:
            self.end_of_game()

    def throw_nip_channels(self, channel):
        self.nipmsg("PRE_XNIP-Channels: #DYELLOW##NIPCHANNELS#", channel)
    
    @callback
    def reload(self):
        self.language=self.import_language(self.default_language)
        
    @callback
    def command(self, user, channel, command, options):
            if channel == self.bot.nickname:
                self.query_command(user, channel, command, options)
                return False
            command = self.NIP_global_cmd(channel, command, options)
            nick=user.getNick()
            if channel!=self.bot.nickname:
                """ not query """
                if nick==self.gamemaster:
                    self.check_stall()
                if command == "spoil":
                    self.NIP_spoil(channel, command)
                elif command == "channels":
                    self. throw_nip_channels(channel)
                elif command == "kill":
                    if self.gameadmin==nick and self.phase!=WAITING_FOR_PLAYERS: 
                        self.nipmsg("PRE_X "+self.gm('msg_admin_lost2'), None, self.gameadmin)
                        self.del_player(nick)
                        self.gameadmin=""
                    else: 
                        if self.gameadmin == nick:
                            self.nipmsg("PRE_X"+self.gm('msg_admin_misc_fail'), channel)
                elif command == "niplanguage":
                    from_wiki = False
                    if options=="":
                        self.nipmsg("PRE_H"+self.default_language, channel)
                    else:
                        if options.count('wiki') == 1:
                            options = ( options.replace('wiki','')).strip()
                            from_wiki = True
                        if self.bot.auth(user):
                            if options in self.languages or options in WIKI_KNOWN_LANGUAGES:
                                self.default_language = options
                                self.language = self.import_language(self.default_language, from_wiki)
                                if len(self.language) > 0:
                                    append = "" if not from_wiki else  " from " + self.wikilink+'nip_messages.'+self.default_language 
                                    self.nipmsg("PRE_HLanguage set to " + self.default_language+append ,channel )
                                else:
                                    self.nipmsg("PRE_HLanguage File not found. Try, 'de' or 'en' ", channel)
                            else:
                                self.nipmsg("PRE_HLanguage File not found ", channel)
                        else:
                            self.nipmsg_("PRE_HNot authenticated", channel)
                elif command == "niphelp":
                    self.nipmsg_("PRE_H#HELPBUG#",channel)
                    if not self.phase==NO_GAME:
                        if options[:3].strip()=="all":
                            self.nipmsg_("PRE_H#HELPUSER#", channel)
                            self.nipmsg_("PRE_H#HELPADMIN#", channel)
                        else:
                            if self.gameadmin==nick:
                                self.nipmsg_("PRE_H#GAMEADMIN# "+HELPADMIN)
                            else:
                                self.nipmsg_("PRE_H#HELPUSER#")
                    else:
                        self.nipmsg("PRE_H"+self.gm('msg_help_1'), channel)
                
                elif command=='clearfav': #internal use only
                    if self.bot.auth(user):
                        deletedplayers=""
                        cleandfrom=self.fav.clear(self.hof)
                        for delplayer in cleandfrom:
                            deletedplayers=deletedplayers+' '+delplayer
                        if deletedplayers:      
                            self.nipmsg_("PRE_HFavorits not found in HoF deleted: "+deletedplayers,channel)
                        else:
                            self.NOP(channel)
                        self.fav.save(self.nipdatadir+self.favfile)
                    else:
                        self.nipmsg_("PRE_HNot authenticated",channel)
                    
                elif command=='niptimer':
                    if self.bot.auth(user):
                        self.toggle_timer()
                    else:
                        self.nipmsg_("PRE_HNot authenticated",channel)
                elif command=="vote":
                    if not self.phase==NO_GAME:
                        votefor=["end","skip"]
                        for what2vote in votefor:
                            if options.count(what2vote) > 0:
                                if what2vote == "end":
                                    if self.nip_vote(nick, self.nickvoted_end, what2vote):
                                        if self.phase==WAITING_FOR_PLAYERS or self.phase==GAME_WAITING:
                                            self.nipmsg("PRE_V"+self.gm('msg_end_now'))
                                            self.end_of_game()
                                        else:
                                            self.nipmsg("PRE_V"+self.gm('msg_end_after_lap'))
                                            self.votedEnd = True #dacapo al fine
                                elif what2vote == "skip":
                                    if self.phase==WAITING_FOR_ANSWERS or self.phase:
                                        if self.nip_vote(nick, self.nickvoted_skip, what2vote):
                                            self.nickvoted_skip=[]
                                            if self.reset_game(True):
                                                self.nipmsg("PRE_Q,"+self.gm('msg_get_question'),None, self.get_gmaster())
                elif command == "autoremove":
                    self.autoremove = self.game_flags(nick,self.autoremove,command)
                elif command == "autorestart":
                    self.autorestart = self.game_flags(nick, self.autorestart, command)
                elif command == "laplimit" or command=="timelimit":
                    self.handle_limits(nick, channel, command, options)
                elif command == "nipvalue":
                    self.handle_nipvalue(nick,channel,command,options)
                elif command=="splitpoints":
                    self.splitpoints = self.game_flags(nick, self.splitpoints, command)
                elif command=="nohead":
                    if self.NIPdb:
                        self.nohead = self.game_flags(nick, self.nohead, command)
                    else:
                        self.nipmsg_("PRE_X#BOLD#Nohead#BOLD# has no database.")
                    return False
                elif command == "gamespeed":
                    if channel in self.channels:
                        self.gamespeed = self.game_flags(nick, self.gamespeed, command,['fast','normal'])
                elif command == "testing":
                    self.testing = self.game_flags(nick, self.testing, command,['mode enabled','mode disabled'])
                    self.minplayers = 2 if self.testing else DEFAULT_NIP_MIN_PLAYER 
                elif command == "nipoptions":
                    if channel in self.channels:
                        self.output_limits(channel)
                        self.output_gflags(channel)
                        self.output_oflags(channel)
                elif command == 'nipme':
                    """ fills a question/answer from database """
                    if self.nohead and nick == self.gamemaster:
                        self.nipme(nick, channel)
                elif command == 'skip_question':
                    """ 
                    for the case an inappropriate question was given by nohead's database .
                    Quizmaster himself could do it by doing !reset in advance
                    """
                    if self.nohead and nick == self.gameadmin and self.nipmeused and self.phase==WAITING_FOR_ANSWERS:
                        if len(self.gamemaster):
                            self.reset_game(True)
                            if self.nipmeused:
                                self.nipme(self.gamemaster, channel)
                    else:
                        self.NOP(channel)
                elif command == "joingame":
                    self.bot.logger.debug("Adding player in phase "+str(self.phase))
                    if self.phase==NO_GAME or self.phase==GAME_WAITING:
                        if self.gameadmin:
                            if nick==self.gameadmin:         #himself
                                if len(options) > 1:
                                    player=options.strip().encode('ascii')
                                    self.add_player(player)
                                else:
                                    self.add_player(nick)     #add himself
                            else:
                                self.add_player(nick)         #a player 
                        else:
                            self.add_player(nick)             #again, maybe we have no admin
                    else:
                        if self.phase == WAITING_FOR_PLAYERS:
                            if nick == self.gameadmin and options:
                                for option in options.split():
                                    option=option.encode('ascii')
                                    for u in self.bot.user_list:
                                        if u.split('!')[0] == option:
                                            if not option.count(' '):
                                                if self.add_player(option.encode('ascii'), False):
                                                    self.nipmsg_("PRE_X "+self.gm('msg_nick_added_forced'), None, option)
                                                break
                            else:
                                self.nipmsg("PRE_X,"+self.gm('msg_init_join'), None, nick)
                        else: #only nicks join thereself
                            if not nick in self.players and not nick in self.newplayers and self.gameadmin!=nick:
                                self.nipmsg("PRE_X "+self.gm('msg_nick_added_next'), None, nick)
                                self.newplayers.append(nick)
                            elif nick==self.gameadmin:
                                self.nipmsg("PRE_X,"+self.gm('msg_admin_misc'), None, nick)
                elif command=="partgame":
                    if self.phase!=7:                     #obsolete
                        if self.gameadmin:                 #we may have one ;)
                            if nick==self.gameadmin:         #himself
                                if len(options) > 1: 
                                    player=options[:24].strip()     #truncated and the trailing spaces eliminated 
                                    self.del_player(player)     #admin removes player
                                else:
                                    self.del_player(nick)         #just remove himself 
                            else:
                                if len(options) == 0: #
                                    self.del_player(nick)         # a player
                                else:
                                    self.nipmsg("PRE_X,"+self.gm('msg_admin_needed'), None, nick)
                        else:
                            self.del_player(nick)             # again even if there is no admin
                    
                elif command=="players":
                    self.show_players(channel)
                elif command=="restartgame" or command == "continue":
                    self.restart_the_game(nick, channel)
                elif command=="startgame":
                    if self.phase==NO_GAME:
                        if len(nick) < self.maxnicklen:
                            self.handle_nicknames(nick)
                            self.NIP_spoil(channel,command)
                            self.GAMECHANNEL=channel
                            
                            self.bot.logger.info("Setting Gamechannel to "+channel+" - "+self.GAMECHANNEL)
                            self.init_vars()
                            self.allscore={}
                            self.save_score(True)
                            self.phase=WAITING_FOR_PLAYERS
                            self.gameadmin=nick
                            self.nipmsg("PRE_X,"+self.gm('msg_admin_game_init'),None, nick)
                            self.nipmsg("PRE_X"+self.gm('msg_init_nipvalue'), channel)
                            self.nipmsg("PRE_X"+self.gm('msg_init_request'))
                            self.nTimerset('STARTPHASE',"kick_gameadmin") #in this phase we'll do end_of_game after given timeout
                        else:
                            self.nick2long(nick,channel)
                    
                    elif self.phase==WAITING_FOR_PLAYERS and nick==self.gameadmin:
                        if self.player_qty() >= self.minplayers:
                            self.roundofgame+=1
                            self.phase=WAITING_FOR_QUESTION
                            random.shuffle(self.players)
                            self.gamemaster=random.choice(self.players)
                            if self.gamemaster in self.players:
                                self.players.remove(self.gamemaster) # (because he knows the answer)
                            self.bot.logger.debug("Random choice setting gamemaster:"+self.gamemaster)
                            self.nTimerset('TIMEOUT', "end_of_quiz")
                            if not self.check_nip_buffer(self.gamemaster, channel):
                                self.nipmsg("PRE_Q,"+self.gm('msg_get_question'),None, self.get_gmaster())
                                self.sendmsg_(self.gamemaster, self.gm('query_get_question'), self.NIPencoding)
                        else:
                            self.nipmsg("PRE_X"+self.gm('msg_few_players_1'))
        
                    elif self.gameadmin=="":
                        self.new_gameadmin(nick)
                elif command=="abortgame":         #vote end only
                    if self.gameadmin=="" and self.phase!=NO_GAME:
                        self.new_gameadmin(nick)
                    self.nipmsg("PRE_X"+self.gm('msg_voted_end_misc_2'))
                    
                elif command=="reset":
                    if self.phase==WAITING_FOR_QUIZMASTER_ANSWER or self.phase==WAITING_FOR_ANSWERS:
                        if self.gameadmin == nick or self.gamemaster == nick:
                            self.resetcnt+=1
                            ppoints=self.resetcnt * 2
                            if self.resetcnt>1:
                                self.nipmsg("PRE_H,"+self.gm('msg_reset_warned'),None, nick)
                                self.sendmsg_(self.gamemaster,"#NIPQUESTION#:")
                                self.add_allscore(nick,int(ppoints*-1))
                                self.reset_game()
                            else:
                                ppoints=1
                                self.nipmsg("PRE_H,"+self.gm('msg_reset_warn'), None, nick)
                                self.sendmsg_(self.gamemaster,"#NIPQUESTION#:")
                                self.reset_game()
                        else:
                            self.NOP(channel)
                    else:
                        self.NOP(channel)
                elif command=="scores":
                    pointlen=0
                    if len(self.allscore):
                        pointlen=len(str(max(self.allscore.values())))
                    SCOREHEAD=self.SCORETABLE+self.create_tab(pointlen-3+self.maxnicklen-12)+"_#UNDERLINE##DGREY#"+" #N_LAP#:#ROUNDOFGAME#"
                    self.nipmsg_("PRE_S"+SCOREHEAD, channel)
                    if len(self.allscore):    
                        points=self.allscore.values()
                        points.sort()
                        points.reverse()
                        players=self.allscore.keys()
                        for point in points:
                            for player in players:
                                if self.allscore[player]==point:
                                    pword="#DRED##POINTS#"
                                    if point==1:
                                        pword="#DBLUE##POINT#"
                                    splayer=player+self.create_tab(self.maxnicklen)
                                    spoints=str(point)+self.create_tab(pointlen-len(str(point)))
                                    self.nipmsg_("PRE_S"+splayer[:self.maxnicklen]+"  "+spoints+ " "+pword, channel)
                                    players.remove(player)
                                    break;
                elif command=="rules" or command == "howto":
                    self.nipmsg_("PRE_H"+self.NIPRULES, channel)
                elif command=="source":
                    self.nipmsg_("PRE_H"+self.NIPSOURCE, channel)
                
                elif command=="version":
                    self.nipmsg_("PRE_H"+self.NAMEOFGAME+"["+NIPRELEASE+"]",channel)
                    
                elif command=="credits":
                    self.nipmsg_("PRE_Z Credits to: #BOLD#Wete allo cato stetie p_kater neTear #BOLD#;-)#DGREY#(release:"+NIPRELEASE+")",channel)
                    
                elif command=="status":
                    
                    if self.GAMECHANNEL != channel and self.GAMECHANNEL != "":
                        self.nipmsg_("PRE_GEs wird im Netz gespielt! #BOLD#/join #GAMECHANNEL#", channel)
                        return False
                    if self.GAMECHANNEL == '' and not channel in self.channels:
                        self.throw_nip_channels(channel)
                        return False
                    if self.GAMECHANNEL == channel or self.GAMECHANNEL == "":
                        result=self.game_status(channel)
                        self.nipmsg_("PRE_G"+result, channel)
                elif command == "place":
                    self.show_user_in_halloffame(channel,nick,options)
                elif command == "halloffame" or command == "hof" or command == "ranking":
                    if not self.hof:
                        self.bot.logger.debug("HoF empty, file permissions? Maybe it is just new.")
                        self.nipmsg_("PRE_Z Nohead ever played the game, there is no Hall of Fame yet",channel)
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
                                self.nipmsg_("PRE_Z"+favOut,channel)
                            else:
                                self.NOP(channel)

    def show_halloffame(self, channel, nick, pagekey=None):
        pointlen=len(str(self.hof[0][1]))             # for building the length in formatted output
        expand=""
        if pointlen>=3:
            expand=self.create_tab(pointlen-3)         #three is (min) default
        expand=expand+self.create_tab(self.maxnicklen-(self.maxnicklen+1))
        expand=string.replace(expand," ","_")
        
        self.nipmsg_("PRE_Y"+self.HALLOFFAME+expand, channel)
        if len(self.hof):
            first=self.hof_show_max_player*pagekey+1
            pcnt=0
            for i in range(self.hof_show_max_player):
                iplace=i+first-1
                if iplace >= len(self.hof):
                    break
                place=str(iplace+1)+".     "
                nick=self.hof[iplace][0]+self.create_tab(self.maxnicklen)
                allpoints=str(self.hof[iplace][1])+"         " 
                self.nipmsg_("PRE_Z"+place[:3]+" "+nick[:self.maxnicklen]+"  "+str(allpoints), channel)

    def show_user_in_halloffame(self, channel, nick, options):
        player=options[:self.maxnicklen].strip()
        try:
            player=int(player)
        except:
            pass
        if not player:
            player=nick
        if not type(player)==int:
            isin=self.isinhof(player,"nocases")
            if not isin:
                self.nipmsg("PRE_Z "+self.gm('msg_hof_not_found'), channel, player)
            else:
                place=isin[0]+".    "
                player=isin[1]+self.create_tab(self.maxnicklen)     #easier way to create whitespaces (and own tabs)?
                allpoints=isin[2]
                self.nipmsg_("PRE_Z"+place[:3]+player[:self.maxnicklen]+" "+str(allpoints), channel)
        else:
            hplace=int(player)
            place=str(hplace)+".            "
            try:
                player=self.hof[hplace-1][0]+self.create_tab(self.maxnicklen)
                allpoints=self.hof[hplace-1][1]
                self.nipmsg_("PRE_Z"+place[:3]+player[:self.maxnicklen]+" "+str(allpoints), channel)
            except:
                pass

    def create_tab(self, qty):
        if qty<1:
            return ""
        ws=[]
        for i in range(qty):
            ws.append(' ')
        return ''.join(ws)

    def reset_game(self, skip=False):
        """ sets game to WAITING_FOR_QUESTION, used for !reset or skipping question by admin or voted"""
        self.bot.logger.debug("Reset game in phase="+str(self.phase)+" skip="+str(skip))
        if not skip:
            self.resetcnt+=1
        self.question=""
        self.answers={}
        self.answernick={}
        self.hint=None
        self.guessed=[]
        self.nTimerset('TIMEOUT', "end_of_quiz")
        self.phase=WAITING_FOR_QUESTION
        return True

    @callback
    def userKicked(self, kickee, channel, kicker, message):
        player = kickee
        playerkicker = kicker
        #remove gamemaster and or gameadmin from game if kicked, 
        if self.GAMECHANNEL == channel:
            if self.gameadmin == player:
                self.kick_gameadmin()
        if self.phase == WAITING_FOR_QUESTION or self.phase == WAITING_FOR_QUIZMASTER_ANSWER:
            self.nipmsg("PRE_P, "+self.gm('msg_kicked_gamemaster'), None, kicker)
            self.add_allscore(str(playerkicker),-3)
            self.phase=GAME_WAITING
        if self.gamemaster == player:
            self.del_player(player)
            
    @callback
    def userJoined(self, user, channel):
        if self.GAMECHANNEL==channel:
            nick=user.getNick()
            statusinfo=self.replace_pre_color(self.game_status(channel, nick))
            statusinfo=self.replace_niprun(statusinfo)
            self.bot.notice(nick, "Hi,"+nick+"! "+statusinfo.encode(self.NIPencoding))

    def get_missing_qty(self):
        return str( len(self.players) - (len(self.answers)-1))

    def game_status(self, channel=None, player=None):
        """assemble status strings for different situations"""
        ustat=""
        uadd=""
        stat=""
        nt=""
        ujoin=""
        status=self.phase
        if player in self.players:
            uadd = " "+self.gm('status_isin')
        if self.gamemaster==player:
            uadd = " "+self.gm('status_is_gamemaster')
        if self.gameadmin==player:
            uadd = " "+self.gm('status_is_gameadmin')
        if self.gameadmin==player and self.gameadmin==player:
            uadd = " "+self.gm('status_is_both')
        if self.GL_TS >= 1:
            nt = self.gm('status_resttime')
        else:
            nt = self.gm('status_stalled')
        if len(uadd)==0:
            ujoin = self.gm('status_join_info')
        if status==NO_GAME:
                stat = self.gm('status_no_game')
                ustat=stat
        elif status==WAITING_FOR_PLAYERS:
            stat = self.gm('status_wait_for_players')
            ustat=stat+uadd
            stat=stat+nt
        elif status==WAITING_FOR_QUESTION or status==WAITING_FOR_QUIZMASTER_ANSWER:
            stat = self.gm('status_wait_for_question')
            ustat=stat+ujoin+uadd
            stat=stat+nt
        elif status==WAITING_FOR_ANSWERS:
            stat = self.gm('status_wait_answers')
            ustat=stat+ujoin+uadd
            stat=stat+nt
        elif status==QUIZ:
            stat = self.gm('status_quiz')
            ustat=stat+ujoin+uadd
            stat=stat+nt
        elif status==GAME_WAITING:
            astat=""
            if self.gameadmin=="":
                astat="#BOLD##CCHAR#restartgame"
            stat = self.gm('status_game_waiting')+astat
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
            self.sendmsg_(nick, self.gm('query_get_answer'))
            self.phase=WAITING_FOR_QUIZMASTER_ANSWER
            self.nTimerset(self.GL_TS+24, "end_of_quiz") #player is alive - a bit more time
            
        elif self.phase==WAITING_FOR_QUIZMASTER_ANSWER and nick==self.gamemaster:
            self.answers[nick]=msg
            self.nTimerset('ANSWER_TIME', "end_of_answertime")
            
            self.nipmsg("PRE_Q#NIPQUESTION#: #BOLD#"+self.question)
            self.request_answers()
            self.phase=WAITING_FOR_ANSWERS
            if self.gamemaster in self.players: #sometimes he is not in before 
                  self.players.remove(self.gamemaster)
            self.sendmsg_(self.gamemaster, self.gm('query_get_infotip'))
        elif (self.phase==WAITING_FOR_ANSWERS or self.phase==QUIZ) and nick==self.gamemaster and not self.hint:
            self.hint=msg
        elif self.phase==WAITING_FOR_ANSWERS and not nick in self.answers and nick in self.players:
            if msg[0]!="!": # some commands in query 
                self.answers[nick] = msg
                self.sendmsg_(nick, self.gm('query_ack'))
                if len(self.answers) == len(self.players)+1: #+gamemaster
                    self.end_of_answertime()
                    
    @callback
    def msg(self, user, channel, msg):
        msg=msg.replace("%","")
        nick=user.getNick()
        if self.GAMECHANNEL==channel:
            if self.phase==WAITING_FOR_PLAYERS and nick!=self.bot.nickname: #add by "joinkey" within startphase
                if len(string.lower(msg).split(self.joinkey)[:42]) > 1:
                    """in startphase collecting players by looking for configured joinkey"""
                    if len(string.lower(msg).split("nicht")[:24]) > 1:
                        if not nick in self.players:
                            self.nipmsg("PRE_H,"+self.gm('msg_parted_3'), None, nick)
                        else:
                            self.nipmsg("PRE_H,"+self.gm('msg_parted_4'), None, nick)
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
                    gmaster = self.get_gmaster()
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
                        #to select the own answer gives 0 points, well -1?
                        pass
                    else:
                        if(self.answernick[int(msg)] in self.score):
                            self.score[self.answernick[int(msg)]]+=3
                            #Favorits
                            player=self.answernick[int(msg)]
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
        """saving game scoring table for another external "HoF statistic" 4later use"""

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
        if not len(self.allscore):
            scorefile=self.nipdatadir+"NIPactScoreTable"
            try:
                sf=open(scorefile, "r")
                self.allscore=pickle.load(sf)
                sf.close()
            except IOError:
                self.bot.logger.info("IOError on "+scorefile)
        if not len(self.nicknames):
            nickfile=self.nipdatadir+"nickNames"
            try:
                sf=open(nickfile, "r")
                self.nicknames=pickle.load(sf)
                sf.close()
            except:
                pass
    """ 
        optional database for nip-questions and     answers
        used for !nipme
        TODO:insert new questions posed by players with good sanitation
    """
    def db_connect(self):
        con = sqlite.connect(self.NIPdb)
        cur = con.cursor()
        return con,cur
     
    def nipQuery(self, query):
        try:
            con,cur = self.db_connect()
            cur.execute(query)
            con.commit()
            return con, cur.fetchall()
        except:
            print ('error:'+str(sys.exc_info()[1]))
            con.close()
            pass

    def nipme(self, nick, channel):
        if self.phase==WAITING_FOR_QUESTION:
            try:
                con, rndIDs = self.nipQuery("select ROWID from NIP where L='"+self.default_language+"' and cnt=0")
                if rndIDs:
                    con.close()
                    newid=(random.choice(rndIDs))[0]
                    con, qtuple=self.nipQuery("select Q,A from NIP where ROWID="+str(newid))
                self.question=qtuple[0][0].strip()
                self.answers[nick]=qtuple[0][1].strip()
                self.hint="NoHead has no answers"
                if not self.nipmeused:
                    self.nipmsg("PRE_P "+self.gm('msg_nipme_lazy'), None, nick)
                    self.add_allscore(nick, -(self.nipvalue))
                con.close()
                self.start_waiting_for_answers(nick,channel)
                self.nipmeused=True
            except:
                self.nipmsg("PRE_D:"+self.gm('msg_nipme_error'), None, nick)
            finally:
                con.close()
        else:
            if self.phase == WAITING_FOR_ANSWERS:
                self.nipmsg("PRE_H"+self.gm('msg_nipme_hint'))

    def init_languages(self):
        """ looks for available language files nip_messages.<country like de ger eng fr etc>"""
        rt={}
        try:
            for langfile in os.listdir(datadir):
                if langfile.startswith("nip_messages."):
                    l=langfile.split('.')
                    if len(l)==2:
                        self.bot.logger.debug("Adding language:"+str(l[1]))
                        rt[l[1]] = langfile
        except:
            pass
        if len(rt) > 0:
            self.bot.logger.debug("Found "+str(len(rt))+" languages in "+datadir)
        else:
            self.bot.logger.debug("Cannot run game due to missing language messages file within "+datadir)
        return rt

    def parse_language(self, data, langfile):
        rt = {}
        lc = 0
        if not isinstance(data, list):
            data = data.split('\n')
        for l in data:
            lc+=1
            l=l.strip()
            if len(l)>1 and l[0]!='#' and l[0]!='[':
                tmp=l.split('=',1)
                try:
                    if len(tmp[1]) > 1:
                        rt[tmp[0]] = tmp[1].decode(self.NIPencoding)
                    else:
                        self.bot.logger.debug("Syntax Error in "+langfile+" line:"+str(lc))
                        print tmp[0]
                except:
                    self.bot.logger.debug("Syntax Error in "+langfile+" line:"+str(lc))
                    print tmp[0]
        return rt

    def wiki_import_language(self, language ,rt):
        if self.wikilink:
            lf = self.wikilink+'nip_messages.'+language
            data = wiki_body_parser.wiki_body(lf)
            rt = self.parse_language(data, lf)
            return rt
        else:
            self.nipmsg_("PRE_HNot configuered for using wiki language files.")

    def import_language(self, language, from_wiki=None):
        """ language local file using, """
        rt = {}
        if language in self.languages:
            if not from_wiki:
                lf = datadir+'/'+self.languages[language]
                if os.path.isfile(lf):
                    data = open(lf).readlines()
                    rt = self.parse_language(data, lf)
            else:
                rt = self.wiki_import_language(language, rt)
        if 'join_key' in rt:
            self.joinkey = rt['join_key']
        return rt

    def gm(self,strid):
        """ get translated messages from language dict"""
        rt=""
        try:
            rt=self.language[strid]
        except:
            pass
        if len(rt) == 0:
            self.bot.logger.debug("Missing languages entry for msg "+strid)
            return "Missing language entry for "+strid
        return rt