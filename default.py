#############################################################################
# xMLS	 : MLS.com Highlight Viewer
# Version    : 1.001
#
# Notes	 : Make sure you have your xbox's date / time correctly set prior
#	   to running this script.  This script uses datetime.date.today().
#	   See version history at the bottom of file.
#
# Based on the xgetGamesFromMonth getGamesFromMonth Highlight Viewer
#
# Author     : Patrick Joyce (patrick.t.joyce@gmail.com)
# Blog       : http://pragmati.st
#############################################################################

from string import *
from os import getcwd
from traceback import print_exc
import sys, traceback, os.path, re, datetime, threading

ScriptPath = re.sub('^(.*?)[\\\\;]*$','\\1\\\\',os.getcwd()) #works in both emu and xbox
sys.path.insert(0, ScriptPath+'utils')

import xbmc, xbmcgui
import xMLSParser as mlsparser

try: Emulating = xbmcgui.Emulating
except: Emulating = False

Utils = os.path.join(replace(getcwd(), ';', ''),  'utils')
Version = 1.001

#############################################################################
# remote constants
#############################################################################

ACTION_MOVE_LEFT	   =  1
ACTION_MOVE_RIGHT	   =  2
ACTION_MOVE_UP	       =  3
ACTION_MOVE_DOWN	   =  4
ACTION_PAGE_UP	       =  5
ACTION_PAGE_DOWN	   =  6
ACTION_SELECT_ITEM     =  7
ACTION_HIGHLIGHT_ITEM	   =  8
ACTION_PARENT_DIR	   =  9
ACTION_PREVIOUS_MENU	   = 10
ACTION_SHOW_INFO	   = 11
ACTION_PAUSE	       = 12
ACTION_STOP	       = 13
ACTION_NEXT_ITEM	   = 14
ACTION_PREV_ITEM	   = 15

#############################################################################
# autoscaling constants
#############################################################################

HDTV_1080i = 0		#(1920x1080, 16:9, pixels are 1:1)
HDTV_720p = 1		#(1280x720, 16:9, pixels are 1:1)
HDTV_480p_4x3 = 2	    #(720x480, 4:3, pixels are 4320:4739)
HDTV_480p_16x9 = 3	#(720x480, 16:9, pixels are 5760:4739)
NTSC_4x3 = 4		#(720x480, 4:3, pixels are 4320:4739)
NTSC_16x9 = 5		#(720x480, 16:9, pixels are 5760:4739)
PAL_4x3 = 6		#(720x576, 4:3, pixels are 128:117)
PAL_16x9 = 7		#(720x576, 16:9, pixels are 512:351)
PAL60_4x3 = 8		#(720x480, 4:3, pixels are 4320:4739)
PAL60_16x9 = 9		#(720x480, 16:9, pixels are 5760:4739)

#############################################################################

# TODO: Start with the current date
theDate = datetime.date.today()

class mlsEntry:
    def __init__(self, name, url, isGame):
	self.name = name
	self.url = url
	self.isGame = isGame

#############################################################################

class VersionTools:
    def __init__(self):
	global Version
	self.curVer = Version
	self.latestVer = Version
    def getVersionString(self):
	return "%.03f" % self.curVer
    def getLatestVersionString(self):
	return "%.03f" % self.latestVer

#############################################################################

class MainWindow(xbmcgui.Window):
    def __init__(self):
	global theDate
	if Emulating: xbmcgui.Window.__init__(self)
	
	# Rely on the 720p coordinate system, making the xbox responsible for repositioning
	# the UI for other resolutions.	 Makes the UI much easier to implement and easier to
	# update.
	self.setCoordinateResolution(HDTV_720p)
	
	self.nextbtn = xbmcgui.ControlButton(80, 240, 240, 48, "Next", textXOffset=25)
	self.backbtn = xbmcgui.ControlButton(80, 312, 240, 48, "Back", textXOffset=25)
	self.refreshbtn = xbmcgui.ControlButton(80, 384, 240, 48, "Refresh", textXOffset=25)
	self.exitbtn = xbmcgui.ControlButton(80, 456, 240, 48, "Exit", textXOffset=25)
	
	self.headlbl = xbmcgui.ControlLabel(400, 75, 700, 48, "Foo")
	self.list = xbmcgui.ControlList(400, 120, 700, 450, imageWidth=25, imageHeight=25)
	self.versionlbl = xbmcgui.ControlLabel(400, 600, 700, 40, "Version")
	self.mlsimage = xbmcgui.ControlImage(115, 50, 170, 170, os.path.join(Utils, "mls_logo.jpg"), "0xFFFFFF00")
	
	self.addControl(self.nextbtn)
	self.addControl(self.backbtn)
	self.addControl(self.refreshbtn)
	self.addControl(self.exitbtn)
	self.addControl(self.headlbl)
	self.addControl(self.list)
	self.addControl(self.versionlbl)
	self.addControl(self.mlsimage)
	
	self.nextbtn.controlDown(self.backbtn)
	self.nextbtn.controlLeft(self.list)
	self.nextbtn.controlRight(self.list)
	self.nextbtn.controlUp(self.exitbtn)
	self.backbtn.setNavigation(self.nextbtn, self.refreshbtn, self.list, self.list)
	self.refreshbtn.setNavigation(self.backbtn, self.exitbtn, self.list, self.list)
	self.exitbtn.setNavigation(self.refreshbtn, self.nextbtn, self.list, self.list)
	self.list.controlLeft(self.nextbtn)
	self.setFocus(self.nextbtn)
	
	self.theGames = []
	self.updateVersionLabel()
	self.fillList(theDate)
    
    def onAction(self, action):
	if action == ACTION_PREVIOUS_MENU:
	    self.close()
    
    def onControl(self, control):
	if control == self.nextbtn:
	    self.incDate()
	if control == self.backbtn:
	    self.decDate()
	if control == self.refreshbtn:
	    self.refreshDate()
	if control == self.exitbtn:
	    self.close()
	if control == self.list:
	    item = self.list.getSelectedPosition()
	    aGame = self.theGames[item]
	    if aGame.links is not None and len(aGame.links) > 0:
		xbmc.Player().play(aGame.links[0].url)
    
    def fillList(self, date, useCache=True):
	self.headlbl.setLabel("Games for " + mlsparser.getStringedDate(date))
	self.list.reset()
	progress = xbmcgui.DialogProgress()
	progress.create("MLS Highlights", "Fetching game list...")
##	  progress = None
	try:
	    self.theGames = mlsparser.getGamesFromMonth(date, progress, useCache)
	except:
	    progress.close()
	    xbmcgui.Dialog().ok("MLS Highlights", "Error fetching data for " + mlsparser.getStringedDate(date))
	    return
	progress.close()
	for aGame in self.theGames:
	    # Show the reel icon if the game has highlights available.
	    reelFilename = os.path.join(Utils, "reel.jpg")
	    if aGame.links is None or len(aGame.links) <= 0:
		reelFilename = ""
	    
	    # The following trick is needed to accomodate the French accent in Montreal.
	    self.list.addItem(xbmcgui.ListItem(aGame.getDisplayString(), iconImage=reelFilename))
	self.setFocus(self.list)
    
    def refreshDate(self):
	self.fillList(theDate, False)
    
    
    def incDate(self):
	global theDate
	theDate = theDate + datetime.timedelta(31)
	theDate = theDate.replace(day=1)
	self.fillList(theDate)

    def decDate(self):
	global theDate
	theDate = theDate - datetime.timedelta(31)
	theDate = theDate.replace(day=1)
	self.fillList(theDate)

    def updateVersionLabel(self):
	ver = VersionTools()
	self.versionlbl.setLabel("Version: %s" % ver.getVersionString())

#############################################################################

win = MainWindow()
win.doModal()
del win

#############################################################################
# Version history
#
# 1.000	    = Initial version as posted on XBMCScripts.
# 1.001	    = Added reel icon to clarify whether a game has highlights
#	      available.
#############################################################################


