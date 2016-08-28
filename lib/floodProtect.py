# -*- coding: utf-8 -*-
# This file is an optional part of OtfBot.
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
# (c) 2016 neTear
""" 
nt_fp a optional service library to be optional included within service.ircClient
TODO: ircClientPlugin to control the config via irc
version 0.0.3
    a) kcs = dict of "known command set" - kcs_= sortet list of "known command set"
    self.bot.kcs and self.bot.kcs_ 
    e.g. command_list=self.bot.kcs[command] will give you the list holding
    ['seconds to protect','specific flags how to protect','[optional channel whitelist]','command belongs to pluginname']
    
    b)
    (nt_fp)This will do bot-command flood-protection on "PRIVMSG" and a bit more than that.
    The existing 'main.linePerSeconds' isn't affected by this kind of protection, but it backs it a bit.
    You'll need to edit the main configuration fp_* to use it after an inital start.
    At least set fp_floodprotection: true, otherwise the bot reacts
    and works like the floodprotection.py is not in place.
    Once the bot has been started with fp_floodprotection:true any other fp_* are set
    to true by default (except for 'fp_whitelist_drops_command' which is false by default), 
    You might edit the configuration a second time for these things.
    It's also up to you to have bot-command-suggestions at all. fp_* should be self-explaining enough.
    Don't forget to stop the bot right before you edit the configuration!
    Default protection time is around  "once per second" on channel+user basis.
    The default Floodprotection-time could be adjusted optionally for each command (in data/floodprotection.config)
    And it'll do a kind of completion by suggesting "unknown" or abbrevitated commands,
    ~the thing from the NIP game for any bot-command right now ;-)
    c)
    Optional given #channel names (as whitelist) relate to 'suggestions' only by default.
    You might let the bot treat this whitelist as a bot-command processing-whitelist as well,
    Another option will be treating the whitelist as a blacklist (TODO), or better having a blacklist
    supplemntally, 'cause both might be reasonable at the same time.
    By setting 'fp_whitelist_drops_command: true', a possibly given whitelist for any specific bot-command
    will be dropped in any channel which isn't whitelisted.
    So for now there's a whitelist only.
    
    The plugins 'known-commands' are adjustable in a very accurate manner
    This protection is involved even for !commands which are not part of the
    "internal kcs ~ known command set", so simply any simple !* will be at least flood-protected
    with 'fp_default_protect_time' while 'fp_protect_any' is set to true.
    d)
    The bot thrawts its io already.So, WHY?
    Because I'm using several plugins with heavy output, and a few
    people cannot behave on IRC. So even the bot slackens down its output
    in many cases it's just ratioal to drop down heavy use of the 
    same bot-command right _before_ they are being processed e.g. !figlet !tvtip and similar.
    So this will economising LOC within each plugin with similar functionalities or the need of them.
    And it helps out the user to discover your bot-commands as well.
    e)
    There's also a 'user_black_list' (a space seperated string! within config! -> 'fp_user_ignore'), 
    which drops bot-command-processing at all for the case of any given string-part (lowercase) is part 
    of the invoking nick!user@host. So bot-commands could be ignored from serveral
    users at all, e.g. other bots.
    f)
    To use this library, you simply need to put it into $bot/lib/
    and the $bot/services/ircClient.py with its few modifications (6 LoC) accordingly.
    New commands from "new" plugins or changes will be added to the configuration only, "lost" commands
    will stay in kcs (from config) until you delete them from floodprotection.config. You also may delete
    the complete floodprotection.config, but then you'll loose your own modifications too,
    but a new "default" configuration will be created during startup.
"""
#TODO controlling the config -> ircClientPlugin
import re, os, time, sys, string, yaml
fp_default_protect_time=2
""" in seconds"""
fp_default_flags='cu'
"""
context for protection c=channel u=user. n=network, empty = no protection at all 
so reasonable are: none,c,u,cu or just n. both configurable for eaach command
"""
fp_known_command_dicts={'data/ircClient.commands/commands.txt':['#heise-otf','#on-topic','#pigeonhole','#otfbot']}
"""
dedicated to the command plugin, any config (dict) file with the same style will work including a channel
whitelist for commands as suggestions only. protection will work even if nothing will be processed
Each known command is configurable in data/floodprotection.config
"""
fp_user_info=False #TODO feedback on network protected commands only?
""" puts info to user once, presently there is no respond on protected commands"""

""" index of the list within the kcs-dict """
FP_PT=0
FP_FLAG=1
FP_CH_WL=2
FP_PLUGIN=3
class floodProtect:
    class gFp():
        def __init__(self):
            """ dynamic dict holding {flag-keywords;[timestamp]}"""
            self.gfp = {}
        def garbage_collect(self):
            print "TODO"
            """timestamp older than 60 minutes e.g."""
            """ could be used for bot-command stats as well by appending a counter e.g. to kcs_"""
        def getProtectFlags(self, p_command, kcs, channel ,nick, network):
            try:
                pflags = kcs[p_command][1]
            except:
                pflags = p_command
                pass
            pflags=pflags.replace('c',channel+'-')
            pflags=pflags.replace('u',nick+'-')
            pflags=pflags.replace('n',network+'-')
            pflags=pflags+p_command
            return pflags
        def getProtectValues(self, p_command, kcs):
            try:
                ptime = int(kcs[p_command][0])
            except:
                ptime = fp_default_protect_time
                pass
            return ptime
        """ main method, check if it is protected ?else protect it"""
        def protect(self, p_command, kcs,channel,nick,network):
            act_ts = int(time.time())
            pflags = self.getProtectFlags(p_command, kcs, channel, nick, network)
            if not pflags in self.gfp:
                """ not protected so we protect it """
                self.gfp[pflags] = act_ts+self.getProtectValues(p_command, kcs)
                return False
            else:
                """ protected, check for released """
                if self.gfp[pflags] < act_ts:
                    self.gfp[pflags] = act_ts+self.getProtectValues(p_command, kcs)
                    return False
                else:
                    """ protected - increase protection time """
                    if self.fp_increase_time:
                        self.gfp[pflags] = act_ts+self.getProtectValues(p_command, kcs)
                    return True

    def __init__(self):
        """ kcs->known command set, if empty, floodprotection is disabled at all within ircClient.service """
        self.kcs = {} 
        if self.config.getBool('floodprotection', False, 'main', self.network):
            self.logger.info("Bot-command floodprotection enabled")
            self.fp_auto_command = self.config.getBool('fp_autocommand', True, 'main', self.network)
            if self.fp_auto_command:
                self.logger.info("Bot-command auto_command enabled")
                
            self.fp_auto_command_suggest = self.config.getBool('fp_suggestion', True, 'main', self.network)
            """TODO true or list as #channel whitelist """
            if self.fp_auto_command_suggest:
                self.logger.info("Bot-command auto_command_suggestions enabled")
            self.fp_protect_any = self.config.getBool('fp_protect_any', True, 'main', self.network)
            self.gFp.fp_increase_time = self.config.getBool('fp_increase_time', True, 'main', self.network)
            self.fp_log_info = self.config.getBool('fp_log_info', True, 'main', self.network)
            self.fp_user_ignore = self.config.get('fp_user_ignore', '', 'main', self.network).split()
                
            """ Trying to use the config file initially """
            if not floodProtect.fp_config(self, False):
                self.logger.info("No bot-command configuration for floodprotection yet.")
            self.logger.debug("Parsing commands from plugins in "+str(self.pluginSupportPath) )
            """ kcs  = generated and fixed dict of any commands holding the protection time """
            floodProtect.get_kcs(self)
            """ adding commands from several files, dedicated to the commands plugin """
            floodProtect.get_from_file(self)
                
            """ kcs_ a generated and fixed *sorted* list of all known commands used for bot-command completion"""
            if self.kcs:
                self.kcs_ = floodProtect.init_kcs_(self)
                self.gfp_ = floodProtect.gFp()
                self.logger.info("Bot-command floodprotection initialised")
                floodProtect.fp_config(self, True)
                self.logger.info(str(len(self.kcs))+" known commands overall")
    
    def fp_config(self, save):
        """ file should be human read/writeable, since yaml and co are inconvenient within mixed encoding environment"""
        fpf='data/floodprotection.config'
        if not save:
            """ load """
            try:
                cf=open(fpf, "r")
                configdata=cf.read()
                cf.close()
            except:
                return False
            for l in configdata.split("\n"):
                if len(l) > 1 and l[0]!='#':
                    pair=l.split("=",1)
                    try:
                        key=pair[0].split('@',1)[0]
                        pluginname = pair[0].split('@')[1]
                        vals=pair[1].split(',')
                        self.kcs[key]=[vals[FP_PT],str(vals[FP_FLAG]),list(vals[FP_CH_WL].split()),pluginname]
                    except:
                        pass
            if len(self.kcs)>0:
                return True
            else:
                return False
        else: 
            """ save """
            with open(fpf, 'w') as f:
                f.write("# <command@plugin>=<protect time in seconds>,<cun>,[<space separated list of whitelisted channels for suggesting commands>]\n")
                f.write("# leave this format in good order, context flags are c|u|n\n")
                f.write("# c[channel] u[ser] n[network] \n")
                f.write("# so reliable flags are: 'c' OR 'u' OR 'cu' OR 'n'\n")
                f.write("# set time to 0 for no protection and the flag to 'n' \n")
                f.write("# while no whitelisted channel(s) are given, command will be suggested in any channel.\n")
                f.write("# IMPORTANT:if no (whitelist) channels are given, leave the trailing ',' in place.\n")
                for key in self.kcs:
                    whitelisted=''
                    pluginname=self.kcs[key][FP_PLUGIN]
                    try:
                        wcs=self.kcs[key][FP_CH_WL]
                        for wc in wcs:
                            whitelisted=whitelisted+wc+' '
                    except:
                        pass
                    f.write(key+'@'+pluginname+'='+str(self.kcs[key][FP_PT])+','+str(self.kcs[key][FP_FLAG])+','+whitelisted+'\n')
    
    def init_kcs_(self):
        kcs_= []
        for bcmd in self.kcs:
            kcs_.append(str(bcmd))
        kcs_.sort()
        return kcs_

    def check(self, command, prefix, params):
        """ returns params and TRUE when (bot)-!command is actively shielded against channel|user|network """
        if str(command)=='PRIVMSG':
            if params[1][0] != "!":
                #TODO where is the main.char
                return params, False
            """ it might be a known bot-command """
            for v in self.fp_user_ignore:
                if v in str(prefix).lower():
                    self.logger.info("Bot-command access denied for ("+v+")"+str(prefix))
                    return True, params
            f_command=''
            suggestions=[]
            try:
                f_channel = params[0]
                f_command = params[1].split()[0][1:]
                p_command = f_command
                f_user = str(prefix).split('!')[0]

            except:
                self.logger.debug('Error on parsing'+str(params)+' '+str(sys.exc_info()[1]))
                return params, False
                pass
            if len(f_command) > 0 and self.fp_auto_command:
                try:
                    full_command = floodProtect.auto_command(self, f_command, f_user, f_channel)
                    """buffering suggestions, so they are being protected too"""
                    if isinstance(full_command, list):
                        """ we got suggestions """
                        if self.fp_auto_command_suggest:
                            try:
                                suggestions=list(full_command)
                            except:
                                pass
                        full_command = ''
                    if len(full_command) >= len(f_command):
                        p_command = full_command
                        """ command has been resolved, rebuilding params """
                    elif ( ( len(full_command) < len(f_command) ) and ( len(full_command) > 2) ):
                        p_command = full_command
                        """ command has been cropped, rebuilding params too """
                    if len(p_command) > 2:
                        try:
                            tcmb = params[1].split()
                            tcmb[0] = tcmb[0].replace(f_command, full_command)
                            params = [f_channel,' '.join(tcmb)]
                        except:
                            pass
                except:
                    self.logger.debug('Error in auto_command()'+str(params)+' '+str(sys.exc_info()[1]))
            try:
                """ main protection call """
                if self.gfp_.protect(p_command, self.kcs, f_channel, f_user, self.network):
                    if self.fp_log_info:
                        self.logger.info("Floodprotected "+str(p_command)+" in "+str(f_channel)+" by "+str(f_user) )
                    return params, True
                else:
                    try:
                        if len(suggestions)> 0:
                            suggest=''
                            for s in suggestions:
                                suggest=suggest+'|'+s
                            self.sendme(f_channel, '.oO('+suggest+')')
                    except:
                        print str(sys.exc_info()[1])
                        pass
                    return params, False
            except:
                self.logger.debug(str(sys.exc_info()[1]))
                pass
                
        """nothing to protect"""
        return params,False 
###################################################################################################
    def auto_command(self, cmd, uuser, cchannel, suggesting=True):
        """ 
        tries to extract  a given bot-command to a known command (not case-sensitive)
        and tries to crop a bot-command until it hits a known one
        """
        if cmd=="":
            return cmd
        i=0
        n=0
        it=""
        if cmd in self.kcs_:
            it=cmd
            return it
        else:
            while ( n < len(self.kcs_)):
                kc=self.kcs_[n]    
                n+=1
                if kc[:len(cmd)]==string.lower(cmd):
                    hit=kc
                    i+=1
                    if i >= 2: #not unique
                        it = floodProtect.suggest_command(self, cmd, cchannel, False)
                        break
            if i == 1:
                return str(hit)
            else:
                #too long?
                if i == 0:
                    it = floodProtect.suggest_command(self, cmd, cchannel, True)
                    self.logger.debug("command cropped to "+str(it))
                    return str(it)
            return it
        return it

    def suggest_command(self, cmd, cchannel, cropping):
        try:
            suggest=[]
            if not cropping:
                for suggests in self.kcs_:
                    if cmd==suggests[:len(cmd)]:
                        whitelisted=self.kcs[suggests][2]
                        if len(whitelisted) > 0:
                            if cchannel in whitelisted:
                                suggest.append(suggests)
                        else:
                            suggest.append(suggests)
            else:
                chk=cmd
                while len(chk)>2:
                    chk=chk[:-1]
                    if chk in self.kcs_:
                        suggest=str(chk)
                        break
        except:
            self.logger.debug('Error in suggest_command()'+str(params)+' '+str(sys.exc_info()[1]))
            return ""
            pass
        finally:
            return suggest
        return suggest
    """ 
    functions below belong to source file parsing for building the kcs
    Once built and saved results to floodprotection.config - only "new" commands from source will be appended
    """
    def get_from_file(self, enc="utf-8", cfilter='_'):
        """ in fact this is dedicated to the commands plugin for now, but any .txt with same style will work"""
        k=0
        for propertiesFile in fp_known_command_dicts:
            pluginname=os.path.basename(propertiesFile).split('.')[0]
            try:
                fp_channel_whitelist = fp_known_command_dicts[propertiesFile]
            except:
                fp_channel_whitelist=['#commands']
            self.logger.debug("Getting commands from known dict file in "+str(propertiesFile) )
            if os.path.exists(propertiesFile):
                propFile = open(propertiesFile, "r")
                try:
                    content = unicode(propFile.read(), enc, errors='replace')
                except:
                    self.logger.debug('Error on reading:'+str(propertiesFile)+' '+str(sys.exc_info()[1]))
                    pass
                propFile.close()
                for line in content.split("\n"):
                    if len(line) > 1 and line[0] != "#":
                        pair = line.split("=", 1)
                        if len(pair) == 2:
                            try:
                                bcmd=str(pair[0])
                            except:
                                print str(sys.exc_info()[1])
                                pass
                            if cfilter:
                                bcmd=bcmd.strip(cfilter)
                            if not bcmd in self.kcs:
                                k+=1
                                try:
                                    self.kcs[pair[0]]=[fp_default_protect_time,\
                                                       fp_default_flags,\
                                                       fp_channel_whitelist,\
                                                       pluginname]
                                except:
                                    print str(sys.exc_info()[1])
        self.logger.info("Took "+str(k)+" commands from known dict files")


    def get_kcs(self):
        """ 
        Getting all plugin bot-!commands from source, 
        including values from an optional given "kcs" dict
        Used for (general and specified) bot-command - floodprotection
        Could be done with ast, but there are irregularties within 2to3 "phase"...
        !commands *should* be unique over all plugins, so we treat them as unique
        """
        k=0
        rt_kcs=self.kcs # {command:protection_time}
        pattern = re.compile('\W')
        sps=['if command ==','if command==','self.kcs=','self.kcs =','allowed_commands=']
        fp_channel_whitelist=list([])
        lb='' # line buffer to unbreak line breaks 
        try:
            for pyf in os.listdir(self.pluginSupportPath):
                if pyf.endswith(".py"):
                    pluginname=pyf.split('.')[0]
                    for l in open(self.pluginSupportPath+'/'+pyf).readlines():
                        l=l.strip()
                        if l:
                            if l[-1]=="\\":
                                lb=lb+l[:-1]
                            else:
                                if lb != '':
                                    lb=lb+l.strip()
                                    l=lb
                                    lb=''
                        if lb == '':
                            for sp in sps:
                                if re.search(sp, l):
                                    multiple=l.split(' or ')
                                    if len(multiple) == 0:
                                        multiple=[l]
                                    for m in multiple:
                                        lst_squote = re.findall(r"'(.*?)(?<!\\)'", m)
                                        for ckey in lst_squote:
                                            if not ckey in rt_kcs and ckey!='':
                                                k+=1
                                                rt_kcs[ckey]=[fp_default_protect_time,\
                                                            fp_default_flags,\
                                                            fp_channel_whitelist,\
                                                            pluginname]
                                        lst_dquote = re.findall(r'"(.*?)(?<!\\)"', m)
                                        for ckey in lst_dquote:
                                            if not ckey in rt_kcs and ckey!='':
                                                k+=1
                                                rt_kcs[ckey]=[fp_default_protect_time,\
                                                            fp_default_flags,\
                                                            fp_channel_whitelist,\
                                                            pluginname]
                                        if sp[0:8]=='self.kcs':
                                            chk_kcs=l.split('=')
                                            if len(chk_kcs)>=2:
                                                if chk_kcs[1].startswith('[') and chk_kcs[1].endswith(']'):
                                                    s = re.sub(pattern, ' ', chk_kcs[1])
                                                    try:
                                                        tmp=s.split()
                                                    except:
                                                        pass
                                                    if tmp:
                                                        for t in tmp:
                                                            ckey=str(t)
                                                            if not ckey in rt_kcs:
                                                                k+=1
                                                                rt_kcs[ckey]=[fp_default_protect_time,\
                                                                            fp_default_flags,\
                                                                            fp_channel_whitelist,\
                                                                            pluginname]
        except:
            self.logger.debug("Error while parsing source code for bot commands "+str(sys.exc_info()[1]))
            return False
            pass
        self.logger.info("Took "+str(k)+" commands from plugin sources")
