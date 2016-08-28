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
#
# (c) 2012 by Alexander Schier
# neTear thought (2014) true checkboxes as option will increase the entropy

"""
marks randomly checkboxes [ ] (or not) - and or - one radiobox ( ) from a list of checkboxes&|radioboxes
Any number ahead in checkbox-list will be treaten as a maximum qty of checkboxes to be checked randomly,
but there's no "minimum" value at the moment, so possibly like 'bitwise' it could be "0" as nothing is being checked

NEW: makes decisions either by given bot-command parameters "decide choice1 choice2 choiceN
optional by configurable keywords:lists in plugin-dir/decision.txt
If you'll let your user edit the decision.txt, do a sanitation before
just put a decision.txt into the plugindir. Format key=choice1 choice2 choiceN ...
called by "decide key | decide cb key" the latter 'cb' if you want checkboxes instead of radioboxes
Invoked by filtered msg not command, so this could be called an easteregg 
"""
from otfbot.lib import chatMod
from otfbot.lib.pluginSupport.decorators import callback
import random, re, os
BOLD="\x02"
COLOR="\x035"
RESET="\x0F"
"""
authenticated bot-users can toggle any #channel to or from channelblack-list 
The plugin won't respond on channels which are in this blacklist
The list will be saved to the main configuration as well.
"""
class Plugin(chatMod.chatMod):
    """ checkbox radiobox plugin """
    def __init__(self, bot):
        self.bot = bot
        self.channel_blacklist=[]
        try:
            self.tib=tib
        except:
            self.tib=[]
    
    @callback
    def start(self):
        self.default_decision=''
        self.channel_blacklist = self.bot.config.get("checkbox_channel_blacklist", '', "main",self.bot.network).split()
        self.decide_config=datadir+'/decision.txt'
        self.decide={}
        if (not os.path.isdir(os.path.dirname(datadir+'/'))):
            try:
                os.makedirs(os.path.dirname(datadir+'/'))
            except:
                pass
        if not os.path.isfile(self.decide_config):
             with open(self.decide_config, 'w') as f:
                f.write('default=yes no never\n')
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
                    if pair[0][0]!='#':
                        if pair[0] == 'default':
                            self.default_decision = pair[1]
                        self.decide[pair[0]]=pair[1].split(',')
        except:
            pass

    @callback
    def msg(self, user, channel, msg):
        if channel in self.channel_blacklist:
            return False
        if user.getNick().lower().replace("_","") in self.tib:
            return False
        decide_msg=msg.split()
        if decide_msg[0] == 'decide':
            w = '( )'
            d_key = ''
            nmsg = ''
            try:
                if decide_msg[1] == 'cb':
                    w='[ ]'
                if decide_msg[1] in self.decide:
                    d_key = decide_msg[1]
                if decide_msg[2] in self.decide:
                    d_key = decide_msg[2]
            except:
                pass
            if d_key == '':
                for decision in decide_msg:
                    if decision!='decide' and decision!='cb':
                        nmsg=nmsg+decision+w+' '
            else:
                for decision in self.decide[d_key]:
                    if decision!='decide' and decision!='cb' and decision!=d_key:
                        nmsg=nmsg+decision+w+' '
            if nmsg == '' and self.default_decision != '':
                for d in self.default_decision.split():
                    nmsg=nmsg+d+w+' '
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
            if self.bot.auth(user):
                blacklist=self.channel_blacklist
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
                self.bot.sendmsg(user.getNick(),'Ingoring checkbox in '+str(blacklist)+' give channelname to toggle')
                newblacklist=''
                for c in blacklist:
                    newblacklist=newblacklist+' '+c
                    if len(newblacklist)>0:
                        self.bot.config.set("checkbox_channel_blacklist", newblacklist, "main",self.bot.network)
            