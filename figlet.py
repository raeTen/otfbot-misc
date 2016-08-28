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
####
# v 0.9.7 (c) 2016 neTear
"""
irc figlet plugin. First you'll need the pyFiglet library.
On deb based systems "apt-get install python-pyFiglet" should work fine, 
otherwise read about it at
https://pypi.python.org/pypi/pyfiglet
The plugin does _not_ use systems figlet font-path but plugindir/fonts.
So you'll need to copy any tlf|flf into there. Find them most probable at /usr/share/figlet
pyFiglet would work with a zip file containing the fonts, this plugin does NOT,
so you really need a copy of each font you like

Since not all fonts are compatible, only those which are really working
will be "known" to the plugin and accepted by parameter (option).
The plugin initially checks if they are working.
If you have installed another font to ./fonts just delete the figlet.yaml
and restart the bot OR reload the plugin.

usage !Figlet [known-fontname] <text>  where ['known' fontname] could be placed anywhere

querycommands for authenticated users:
figlet showfonts:shows the fonts respecting the given maxheight (lines of output)
figlet maxheight: shows actual maximal height, set it with given as integer parameter
figlet maxwidth: shows actual maximal width, set it with given as integer parameter, just crops the output
figlet show: shows configuration
figlet test <fontname>: well...
figlet font fontname: sets the default font which is used for no recognised fontname

there's no saved configuration yet, after restarting/reloading we begin with given internal values
figlet.yaml just holds working fonts and their output render sizes
"""
 
from otfbot.lib import chatMod
from otfbot.lib.pluginSupport.decorators import callback
from pyfiglet import Figlet 
import yaml, os, time, sys

MAX_HEIGHT=5
MAX_WIDTH=120
DEFAULT_FONT='pagga'
class Plugin(chatMod.chatMod):
    """ uses PYfiglet library to create figlet/toilet like output """

    def __init__(self, bot):
        self.bot = bot
        self.datapath=datadir+'/'
        self.fontpath=self.datapath+'fonts/'
        self.conffile=self.datapath+'figlet.yaml'

    @callback
    def start(self):
        if not os.path.isdir(os.path.dirname(self.datapath)):
            try:
                os.makedirs(os.path.dirname(self.fontpath))
            except:
                self.bot.logger.debug("Error, creating "+self.fontpath)
                pass
        self.figletconfig={} 
        """{str(fontname):[outputlines, width orig, width_output])}"""
        try:
            stream = file(self.conffile, 'r')
            self.figletconfig=yaml.load(stream)
        except:
            pass
        if len(self.figletconfig) == 0:
            self.bot.logger.info("Figlet has no font configuration, trying to create it, this may last a few seconds")
            if self.fonts2config():
                self.bot.logger.info("Font configuration successfully created")
            else:
                self.bot.logger.info("No working flf or tlf fonts found in "+self.datapath+'fonts/')
        else:
            self.bot.logger.info("Figlet has got "+str(len(self.figletconfig))+" known working fonts")
        self.max_height=MAX_HEIGHT
        self.max_width=MAX_WIDTH
        self.fontname=DEFAULT_FONT
        self.getActiveFonts()
    
    @callback
    def reload(self):
        """ 
        creating config may last a few seconds, so we better use bot-control, 
        suggesting: reload(user=none)
        """
        try:
            os.remove(self.conffile)
        except:
            self.bot.logger.debug("Problem occured with font configuration"+str(sys.exc_info()[1]))
            pass
        self.start()
####################################################################################
    def fonts2config(self):
        """ 
        if we haven't a font-configuration right now, we'll render any font from 
        our own font location initially and save height and width along with
        its name to our own internal font facility
        """
        fontnames=[]
        fnames = os.listdir(self.datapath+'fonts/')
        fnames.sort()
        outputlines=0
        width_orig=0
        width_output=0
        for fname in fnames:
            if not fname in self.figletconfig:
                fontname=fname.split('.')[0]
                try:
                    width_orig=len(fontname)
                    f = Figlet(font=fontname)
                    m_figlet = (f.renderText(str(fontname) )).split('\n')
                    outputlines=len(m_figlet)-1
                except:
                    self.bot.logger.debug(fontname+" seems not to be compatible with pyFiglet") 
                    outputlines=0
                    pass
                for aline in m_figlet:
                        width_output=len(aline)
                        break
                width_ratio=width_output/width_orig
                self.figletconfig[fontname]=[outputlines,width_ratio,width_orig,width_output]
        with open(self.conffile, 'w') as yaml_file:
            yaml_file.write( yaml.dump(self.figletconfig, default_flow_style=False))
        if len(self.figletconfig)>0:
            return True
        return False
###################################################################################
    def getActiveFonts(self,rt=None):
        self.activeFonts=[]
        bmsg=''
        for fontname in self.figletconfig:
            if self.figletconfig[fontname][0] < self.max_height and self.figletconfig[fontname][0] >0:
                self.activeFonts.append(fontname)
        self.activeFonts.sort()
        if rt:
            for f in self.activeFonts:
                bmsg=bmsg+f+'|\x02'
            return bmsg
        return ""

    def getFont(self,options):
        for w in options.split():
            if w in self.activeFonts:
                return w
        return self.fontname

    def render(self, renderTo, renderText,fontname=None):
        if not fontname:
            f = Figlet(font=self.fontname)
        else:
            f = Figlet(font=fontname)
        m_figlet = (f.renderText(renderText)).split('\n')
        maxcnt=0
        for l in m_figlet:
            if l:
                maxcnt+=1
                if maxcnt <= self.max_height:
                    self.bot.sendmsg(renderTo,l[0:self.max_width])
        if maxcnt>self.max_height:
            return "Figlet output has been truncated"
        return ""

    @callback
    def command(self, user, channel, command, options):
        if command == "figlet" or command == "paint":
            feedback=""
            if self.max_height>20 or self.max_height<1:
                self.max_height=MAX_HEIGHT
            if self.max_width>200 or self.max_width<1:
                self.max_width=MAX_WIDTH
            if len(options)<1:
                self.render(channel, "I love ascii art!")
            else:
                f_options=options.split()
                self.fontname=self.getFont(options)
                if self.fontname in f_options:
                    options=options.replace(self.fontname,'')
                feedback=self.render(channel, str(options.encode('iso-8859-1')))
                if len(feedback)>0:
                    self.bot.notice(user.getNick(),feedback)
###################################################################
    def handle_query(self, user,nick, channel, msg):
        qcmd=''
        figlet_msg=msg.split()
        qcmd=figlet_msg[0]
        feedback=''
        tv=0
        newfont=''
        if qcmd=='maxheight':
            try:
                tv=int(figlet_msg[1])
                self.max_height=tv
                self.getActiveFonts(False)
                feedback=str(tv)
            except:
                self.max_height=5
                feedback=str(self.max_height)
                pass
        elif qcmd=='maxwidth':
            try:
                tv=int(figlet_msg[1])
                self.max_width=tv
                self.getActiveFonts(False)
                feedback=str(tv)
            except:
                self.max_width=MAX_WIDTH
                feedback=str(self.max_width)
                pass
        elif qcmd=='showfonts':
            self.bot.sendmsg(nick, self.getActiveFonts(True))
        elif qcmd=='font':
            try:
                newfont=figlet_msg[1]
            except:
                newfont=""
                pass
            if len(newfont)>0:
                if newfont in self.activeFonts:
                    self.fontname=newfont
                    feedback="Font:"+self.fontname
            else:
                feedback="Font:"+self.fontname

        elif qcmd=='show':
            feedback="maxheight:"+str(self.max_height)+" maxwidth:"+str(self.max_width)+" font:"+self.fontname
        elif qcmd=='test':
            fontname=self.getFont(msg)
            self.render(nick,fontname,fontname)
        if feedback != '':
            self.bot.sendmsg(nick, feedback)
    
    @callback
    def query(self, user, channel, msg):
        if self.bot.auth(user):
            if msg[0:6]=='figlet':
                msg=msg.replace("%","") #FIXME
                msg=msg[6:]
                self.handle_query(user,user.getNick(),channel,msg)
        
