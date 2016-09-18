#!/usr/bin/python
# -*- coding: utf-8 -*- 
# This file is an optional part of the OtfBot.
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
getting  values from wikis textile bodies - with proxy support - helper lib.
The mod requests looks decadently expensive and we do some sanitising and
limiting, but this is still ugly. So please use this if you know what you are doing
and improve it - or restrict editing of the wiki to trusted mates
String sanitising should be fine, but we should check "content-length" before
processing values at all.
"""
import requests
from lxml import html
import sys, re

#########################################
#PROXYIP_PORT = 'ip:port'
########################################
PROXY_PROTOCOLS = ['http','https','ftp']
WIKI_DIV_IDENTIFIER = 'wiki-body'
MAX_BYTES=100000


def wiki_sanitise_data(data):
    return re.sub(r'([^\s\w\,\=]|_)+', 'x', data)

def wiki_body_size(rcontent):
    """ 
    rcontent.headers['content-length'] - no content-length from git wiki
    so to limit the response we need to work with timeout and iterate chunks.
    For now we check the length of the complete response size before 
    Thats's ugly...
    """
    if rcontent.status_code == 200:
        return True if len(rcontent.text) <= MAX_BYTES else False
    return False

def wiki_get_content(url, wproxies):
    try:
        r = requests.get(url, proxies = wproxies )
    except:
        print(str(sys.exc_info()[1]))
        return False
        pass
    return r if wiki_body_size(r) else False

def wiki_get_elements(rcontent, rid):
    
    if rcontent:
        try:
            tree = html.fromstring(rcontent.content)
            elements = tree.get_element_by_id(rid)
            return elements
        except:
            print (str(sys.exc_info()[1]))
            return False

def wiki_parse_elements(elements):
    if elements is not None:
        try:
            chk = elements.text_content().strip().split('\n')
            ndata=''
            for c in chk:
                ndata=ndata+wiki_sanitise_data(c)+'\n'
            return ndata
        except:
            print (str(sys.exc_info()[1]))
            return False

def wiki_body(url):
    wproxies = {}
    if PROXYIP_PORT:
        for p in PROXY_PROTOCOLS:
            wproxies[p] = p+'://'+str(PROXYIP_PORT) 
    return wiki_parse_elements(\
        wiki_get_elements(\
        wiki_get_content(url, wproxies) , WIKI_DIV_IDENTIFIER)\
        )
