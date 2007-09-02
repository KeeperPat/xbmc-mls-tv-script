# -*- coding: utf-8 -*-
#############################################################################
# xMLSParser : Parser for MLS.com pages
#
# Notes  : Relies on the nifty BeautifulSoup HTML parser.
#              (http://www.crummy.com/software/BeautifulSoup/)
#
#          This file can be used/run indenpendently of the xMLS xbmc extension.
#          In fact it's useful to do so to sanity test the parser.  I have a
#          rudimentary unit test in there but it should really be more tho-
#          rough.
#
# Author : episcopus (episcopus@comcast.net)
#############################################################################

import re, os, sys

ScriptPath = re.sub('^(.*?)[\\\\;]*$','\\1\\\\',os.getcwd()) #works in both emu and xbox
sys.path.insert(0, ScriptPath+'utils')

import BeautifulSoup as bs
import datetime
import urllib, urllib2
import socket

# timeout in seconds
socket = socket.setdefaulttimeout(10)

SCORESPAGEURL = "http://ww2.mlsnet.com/mls/schedule/index.jsp"

HEADERS = {"Accept": "image/gif, image/x-xbitmap, image/jpeg, image/pjpeg, application/x-shockwave-flash, application/vnd.ms-excel, application/vnd.ms-powerpoint, application/msword, */*",
            "Accept-Language": "en-us",
            "UA-CPU": "x86",
            "User-Agent": "Mozilla/4.0 (compatible; MSIE 7.0b; Windows NT 5.1; .NET CLR 1.1.4322; InfoPath.2)",
            "Pragma": "no-cache",
            "Referer": SCORESPAGEURL }

#############################################################################

class dayOfWeek:
	def __init__(self, name, url):
		self.name = name
		self.url = url
	def __str__(self):
		return "[dayOfWeek] Name: " + self.name + ", Url: " + self.url + "\n"

#############################################################################

class mediaLink:
	def __init__(self, name, url):
		self.name = name
		self.url = url
	def __str__(self):
		return "[mediaLink] Name: " + self.name + ", Url: " + self.url

#############################################################################

class game:
	def __init__(self, team1, team2, status, links):
		self.team1 = team1
		self.team2 = team2
		self.links = links
		self.status = status
	def __eq__(self, other):
            simple = self.team1 == other.team1 and self.score1 == other.score1 and self.team2 == other.team2 and self.score2 == other.score2 and self.status == other.status and len(self.links) == len(other.links)
            
            for i in range(len(self.links)):
                simple = simple and self.links[i].name == other.links[i].name
                simple = simple and self.links[i].url == other.links[i].url
            return simple
	def __str__(self):
		result = "[game] " + self.team1 + " " + str(self.score1) + ", " + self.team2 + " " + str(self.score2) + " (" + self.status + ")\n"
		index = 1
		if self.links is not None and len(self.links) > 0:
                    for link in self.links:
                        result = result + "\t" + str(index) + ") " + str(link) + "\n"
                        index = index + 1
		elif self.links is None or len(self.links) <= 0:
                    result += "\tNo media found!\n"
		return result
	def appendMediaLink(self, name, url):
		ml = mediaLink(name, url)
		self.links.append(ml)
	def getDisplayString(self):
		result = self.team1 + " at " + self.team2 + " (" + self.status + ")"
		return result
	def getCodeString(self):
            hello = "game(\"" + self.team1 + "\",\"" + self.score1 + "\",\"" + self.team2 + "\",\"" + self.score2 + "\",\"" + self.status + "\",%s)"
            links = "["
            if self.links is not None and len(self.links) > 0:
                index = 0
                for link in self.links:
                    links += "mediaLink(\"" + link.name + "\",\"" + link.url[len(HIGHLIGHTBASEURL2):] + "\")"
                    index += 1
                    if index < len(self.links):
                        links += ","
            links += "]"
            hello = hello % links
            return hello

def gamesFromStream(theStream, progress):
    games = []
    
    if theStream is None or len(theStream) <= 0:
        return games
    
    soup = bs.BeautifulSoup(theStream)
    
    # Get the table with all the games
    contentTableCell = soup.find("td", {"id":"content"})
    gamesTable = contentTableCell.contents[5]
    
    # Discard the header Row
    gamesRows = gamesTable('tr')
    gamesRows = gamesRows[1:len(gamesRows)]
    
    currentDate = ''
    
    for row in gamesRows:
      cells = row('td')
      if len(cells) == 1:
        # it is a date row
        currentDate = cells[0].strong.string.replace('\n\t\t\t', '')
        print currentDate
      else:
        # it is a game row
        team1 = cells[0].find(text=True)
        team2 = cells[1].find(text=True)
        score = cells[2](text=True).pop().strip()
        if score is None or len(score) <= 0:
          score = "Couldn't get Score"
        
        links = []
        
        highlightsMatch = re.search(r"w:'(mms://.+\.wmv)", cells[3].a['href'])
        if highlightsMatch is not None and len(highlightsMatch.groups()) == 1:
          links.append(mediaLink("Highlights", str(highlightsMatch.group(1))))
        
        if len(links) == 1:
           highlightsURL = highlightsMatch.group(1)
        else:
           highlightsURL = 'No Highlights Available'
        
        print team1 + ' vs ' + team2 + ' (' + score + ')'
        
        games.append(game(team1, team2, score, links))
    
    return games

#############################################################################

def getStringedDate(date):
    if date is None:
        return ""
    return date.strftime("%B %Y")

# Currently this cache doesn't have a size limit and will only be explictly
# refreshed through passing False for the useCache params.
streamCache = {}

def getStreamForMonth(date, progress, useCache):
    if date is None:
        return ""
    
    theStream = ""
    dateStr = getStringedDate(date)
    if progress is not None:
        progress.update(0, "Fetching data for " + dateStr)
    miss = False
    try:
        theStream = streamCache[dateStr]
        print "Cache hit for " + dateStr
    except:
        miss = True
    
    if not useCache:
        miss = True
    
    if miss == True or len(theStream) <= 0:
        # Format url for request
        datePart = date.strftime("?year=%Y&month=%m")
        requestUrl = SCORESPAGEURL + datePart
        
        print "Requesting url: " + requestUrl
        
        myRequest = urllib2.Request(requestUrl, None, HEADERS)
        theReturnedFile = urllib2.urlopen(myRequest)
        theStream = theReturnedFile.read()
        
        if len(theStream) > 0:
            streamCache[dateStr] = theStream
    
    return theStream

#############################################################################

def getGamesFromMonth(date, progress=None, useCache=True):
    if date is None:
        return []
    
    theStream = getStreamForMonth(date, progress, useCache)
    games = gamesFromStream(theStream, progress)
    
    print str(len(games)) + " games found."
    return games

#############################################################################

class mockProgress:
    def update(self, num, string):
        print str(num) + "%: " + string

#############################################################################

def unitTest():
    expected1 = []
    
    result1 = getGamesFromMonth(datetime.date(2007, 8, 01))
    
    assert len(expected1) == len(result1)
    for i in range(len(expected1)):
        try:
            assert expected1[i] == result1[i]
        except:
            print "Unit test: failed comparing game #" + str(i) + ":\n\tExpected: " + str(expected1[i]) + "\n\tResult: " + str(result1[i])
            raise
    
    print "Unit test: passed comparing games from 05/2006."

#############################################################################

if __name__ == '__main__':
    unitTest()
