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
getting  values from github-wikis textile(!) bodies - with proxy support - helper lib.
The module requests looks decadently expensive - We do some sanitising and
limiting, but this is still ugly. So please use this if you know what you are doing
and improve it - or restrict editing the used wiki pages to trusted mates
The string sanitising should be fine, but we should check "content-length" before
processing values at all. 
"""

import requests
from lxml import html
import sys, re


PROXY_PROTOCOLS = ['http','https','ftp']
WIKI_DIV_IDENTIFIER = 'wiki-body'
MAX_BYTES=100000

def wiki_sanitise_data(data, enc=None):
    """ building yard: let me know what to eliminate as well to be safer """
    if enc == None:
        enc = True
    while data.count('__'):
        data = data.replace('__','')
    while data.count('__'):
        data = data.replace('__','_')
    return \
        re.sub(ur'[{&%$;*§;>`}]', '', data)\
        if enc else \
        re.sub(r'[{&%$;*§;>`}]', '', data)

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
        r = requests.get(url, proxies = wproxies, allow_redirects = False )
        r.encoding = 'utf-8'
    except:
        print(str(sys.exc_info()[1]))
        return False
        pass
    return r if wiki_body_size(r) else False

def wiki_get_elements(rcontent, rid):
    if rcontent and rcontent.status_code == 200:
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
                if c!='':
                    if c[0]!='#' and c[0]!='<':
                        ndata=ndata+ (wiki_sanitise_data(c)+'\n').encode('utf-8')
            return ndata
        except:
            print (str(sys.exc_info()[1]))
            return False
    return False

def wiki_body(url, proxy_ip_port=None):
    wproxies = {}
    if proxy_ip_port:
        for p in PROXY_PROTOCOLS:
            wproxies[p] = p+'://'+str(proxy_ip_port) 
    return wiki_parse_elements(\
        wiki_get_elements(\
        wiki_get_content(url, wproxies) , WIKI_DIV_IDENTIFIER)\
        )
