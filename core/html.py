#!/usr/bin/python
# This file is part of Altair web vulnerability scanner.
#
# Copyright(c) 2010-2011 Simone Margaritelli
# evilsocket@gmail.com
# http://www.evilsocket.net
# http://www.backbox.org
#
# This file may be licensed under the terms of of the
# GNU General Public License Version 2 (the ``GPL'').
#
# Software distributed under the License is distributed
# on an ``AS IS'' basis, WITHOUT WARRANTY OF ANY KIND, either
# express or implied. See the GPL for the specific language
# governing rights and limitations.
#
# You should have received a copy of the GPL along with this
# program. If not, go to http://www.gnu.org/licenses/gpl.html
# or write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
from HTMLParser import HTMLParser, HTMLParseError
from http import Url, GetRequest, PostRequest
from edispatcher import EventDispatcher
from urllib2 import HTTPError
from urllib import *
import os
import re
import time

class Parser(HTMLParser):
	def __init__( self, root, config, edispatcher ):
		HTMLParser.__init__(self)
		self.scheme   = root.scheme
		self.domain	  = root.netloc
		self.root	  = root
		self.config   = config
		self.requests = []
		self.parsed	  = []
		self.form	  = None
		self.ed		  = edispatcher
		
	def parse( self, request ):
		self.ed.parsing( request.url )
		
		# check for a valid extension
		if self.config.AllowedExtensions != None:
			( root, ext ) = os.path.splitext( request.url.path )
			if ext[1:] not in self.config.AllowedExtensions and ext != '':
				self.ed.warning( "Skipping page with unallowed extension '%s' ." % request.url.path )
				self.parsed.append( request )
				return
		# check directory depth
		if self.config.MaxDirectoryDepth != None:
			if len(request.url.path.split('/')) + 1 > self.config.MaxDirectoryDepth:
				self.ed.warning( "Max directory depth exceeded '%s' ." % request.url.path )
				self.parsed.append( request )
				return
		# if enabled, delay the crawl process
		if self.config.CrawlDelayEnabled != None and self.config.CrawlDelayEnabled == True:
			self.ed.warning( "Delaying crawling process of %d ms ..." % self.config.CrawlDelay )
			time.sleep( self.config.CrawlDelay / 1000.0 )
		
		try:
			# set user-agent if specified
			if self.config.UserAgent != None:
				request.setHeader( 'User-Agent', self.config.UserAgent )
			# set proxy if specified
			if self.config.ProxyEnabled != None and self.config.ProxyEnabled == True:
				self.ed.status( "Setting request proxy to %s:%d ." % ( self.config.ProxyServer, self.config.ProxyPort ) )
				request.setProxy( self.config.ProxyServer, self.config.ProxyPort )
			
			self.feed( request.fetch() )
			self.close()
		except:
			pass
		finally:
			self.parsed.append( request )
		
		for req in self.requests:
			if req not in self.parsed:
				self.parse( req )
				
	def __get_attr( self, name, attrs, default = '' ):
		for a in attrs:
			aname = a[0].lower()
			if aname == name:
				return a[1]
		return default
	
	def handle_starttag( self, tag, attrs ):
		tag = tag.lower()
		if tag == 'a':
			href = self.__get_attr( 'href', attrs )
			url  = Url( href, default_netloc = self.domain )
			if url.netloc == self.domain and url.scheme == self.scheme:
				req = GetRequest( url )
				if req not in self.requests:
					self.requests.append( req )
		if tag == 'img':
			src = self.__get_attr( 'src', attrs )
			for ext in self.config.AllowedExtensions:
				if re.match( ".+\.%s.*" % ext, src ):
					url = Url( src, default_netloc = self.domain )
					if url.netloc == self.domain and url.scheme == self.scheme:
						req = GetRequest( url )
						if req not in self.requests:
							self.requests.append( req )
							break
		elif tag == 'form':
			self.form 		    = {}
			self.form['data']   = {}
			self.form['action'] = self.__get_attr( 'action', attrs, self.root.path )
			self.form['method'] = self.__get_attr( 'method', attrs, 'get' ).lower()
		elif self.form != None:
			if tag == 'input':
				name  = self.__get_attr( 'name',  attrs )
				value = self.__get_attr( 'value', attrs )
				self.form['data'][name] = value
			elif tag == 'select':
				self.form['data'][self.__get_attr( 'name',  attrs )] = ''
				
	def handle_endtag( self, tag ):
		tag = tag.lower()
		if tag == 'form' and self.form != None:
			# {'action': 'search.php?test=query', 'data': {'searchFor': '', 'goButton': 'go'}, 'method': 'post'}
			if self.form['method'] == 'get':
				link = self.form['action'] + "?" + urlencode( self.form['data'] )
				url  = Url( link, default_netloc = self.domain )
				if url.netloc == self.domain and url.scheme == self.scheme:
					req = GetRequest( url )
					if req not in self.requests:
						self.requests.append( req )
			elif self.form['method'] == 'post':
				link = self.form['action']
				url  = Url( link, default_netloc = self.domain )
				if url.netloc == self.domain and url.scheme == self.scheme:
					req = PostRequest(url)
					for name, value in self.form['data'].items():
						req.addField( name, value )
					if req not in self.requests:
						self.requests.append( req )
				
			self.form = None