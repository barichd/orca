# Orca
#
# Copyright 2005-2008 Sun Microsystems Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., Franklin Street, Fifth Floor,
# Boston MA  02110-1301 USA.

"""Provides the default implementation for bookmarks in Orca."""

import pickle
import os

from . import messages
from . import orca_state
from . import settings_manager

_settingsManager = settings_manager.getManager()

class Bookmarks:
    """Represents a default bookmark handler."""
    def __init__(self, script):
        self._script = script
        self._bookmarks = {} 
        self._saveObservers = []
        self._loadObservers = []
        self._loadBookmarks() 
        self._currentbookmarkindex = None

    def addSaveObserver(self, observer):
        self._saveObservers.append(observer)

    def addLoadObserver(self, observer):
        self._loadObservers.append(observer)

    def goToBookmark(self, inputEvent, index=None):
        """ Go to the bookmark indexed by inputEvent.hw_code """
        # establish the _bookmarks index
        index = index or inputEvent.hw_code

        try:
            context = self._script.getFlatReviewContext()
            context_info = self._bookmarks[index]
            context.setCurrent(context_info['line'], context_info['zone'], \
                                context_info['word'], context_info['char'])
            self._bookmarks[index] = context_info
        except KeyError:
            self._script.systemBeep()
            return

        self._script.flatReviewContext = context
        self._script.reviewCurrentItem(inputEvent)

        # update the currentbookmark
        self._currentbookmarkindex = index

    def addBookmark(self, inputEvent):
        """ Add an in-page accessible object bookmark for this key. """
        context = self._script.getFlatReviewContext()
        self._bookmarks[inputEvent.hw_code] = self._contextToBookmark(context)
        self._script.presentMessage(messages.BOOKMARK_ENTERED)

    def bookmarkCurrentWhereAmI(self, inputEvent):
        """ Report "Where am I" information for this bookmark relative to the 
        current pointer location."""
        try:
            context = self._bookmarkToContext( \
                          self._bookmarks[inputEvent.hw_code])
        except KeyError:
            self._script.systemBeep()
            return   

        obj = context.getCurrentAccessible()    
        cur_obj = orca_state.locusOfFocus

        # Are they the same object?
        if self._script.utilities.isSameObject(cur_obj, obj):
            self._script.presentMessage(messages.BOOKMARK_IS_CURRENT_OBJECT)
            return
        # Are their parents the same?
        elif self._script.utilities.isSameObject(cur_obj.parent, obj.parent):
            self._script.presentMessage(messages.BOOKMARK_PARENT_IS_SAME)
            return

        # Do they share a common ancestor?
        # bookmark's ancestors
        bookmark_ancestors = []
        p = obj.parent
        while p:
            bookmark_ancestors.append(p)
            p = p.parent
        # look at current object's ancestors to compare to bookmark's ancestors
        p = cur_obj.parent
        while p:
            if bookmark_ancestors.count(p) > 0:
                msg = messages.BOOKMARK_SHARED_ANCESTOR % p.getLocalizedRoleName()
                self._script.presentMessage(msg)
                return
            p = p.parent

        self._script.presentMessage(messages.BOOKMARK_COMPARISON_UNKNOWN)

    def saveBookmarks(self, inputEvent):
        """ Save the bookmarks for this script. """        
        try:
            self.saveBookmarksToDisk(self._bookmarks)
            self._script.presentMessage(messages.BOOKMARKS_SAVED)
        except IOError:
            self._script.presentMessage(messages.BOOKMARKS_SAVED_FAILURE)

        # Notify the observers
        for o in self._saveObservers:
            o()

    def goToNextBookmark(self, inputEvent):
        """ Go to the next bookmark location.  If no bookmark has yet to be
        selected, the first bookmark will be used.  """

        # get the hardware keys that have registered bookmarks
        hwkeys = sorted(self._bookmarks.keys())

        # no bookmarks have been entered
        if len(hwkeys) == 0:
            self._script.systemBeep()
            return
        # only 1 bookmark or we are just starting out
        elif len(hwkeys) == 1 or self._currentbookmarkindex is None:
            self.goToBookmark(None, index=hwkeys[0])
            return

        # find current bookmark hw_code in our sorted list.  
        # Go to next one if possible
        try:
            index = hwkeys.index(self._currentbookmarkindex)
            self.goToBookmark(None, index=hwkeys[index+1])
        except (ValueError, KeyError, IndexError):
            self.goToBookmark(None, index=hwkeys[0])

    def goToPrevBookmark(self, inputEvent):
        # get the hardware keys that have registered bookmarks
        hwkeys = sorted(self._bookmarks.keys())

        # no bookmarks have been entered
        if len(hwkeys) == 0:
            self._script.systemBeep()
            return
        # only 1 bookmark or we are just starting out
        elif len(hwkeys) == 1 or self._currentbookmarkindex is None:
            self.goToBookmark(None, index=hwkeys[0])
            return

        # find current bookmark hw_code in our sorted list.  
        # Go to previous one if possible
        try:
            index = hwkeys.index(self._currentbookmarkindex)
            self.goToBookmark(None, index=hwkeys[index-1])
        except (ValueError, KeyError, IndexError):
            self.goToBookmark(None, index=hwkeys[0])

    def _loadBookmarks(self):
        """ Load this scripts saved bookmarks."""
        self._bookmarks = self.readBookmarksFromDisk() or {}

        # notify the observers
        for o in self._loadObservers:
            o()

    def readBookmarksFromDisk(self, filename=None):
        """ Read saved bookmarks from disk.  Currently an unpickled object
        that represents a bookmark """
        filename = filename or self._script.name.split(' ')[0]
        orcaDir = _settingsManager.getPrefsDir()
        if not orcaDir:
            return

        orcaBookmarksDir = os.path.join(orcaDir, "bookmarks")
        try:
            inputFile = open( os.path.join( orcaBookmarksDir, \
                        '%s.pkl' %filename), "r")
            bookmarks = pickle.load(inputFile.buffer)
            inputFile.close()
            return bookmarks
        except (IOError, EOFError, OSError):
            return None

    def saveBookmarksToDisk(self, bookmarksObj, filename=None):
        """ Write bookmarks to disk.  bookmarksObj must be a pickleable 
        object. """
        filename = filename or self._script.name.split(' ')[0]
        orcaDir = _settingsManager.getPrefsDir()
        orcaBookmarksDir = os.path.join(orcaDir, "bookmarks")
        # create directory if it does not exist.  correct place??
        try:
            os.stat(orcaBookmarksDir)
        except OSError:
            os.mkdir(orcaBookmarksDir)
        output = open( os.path.join( orcaBookmarksDir, \
                    '%s.pkl' %filename), "w", os.O_CREAT)
        pickle.dump(bookmarksObj, output.buffer)
        output.close()

    def _contextToBookmark(self, context):
        """Converts a flat_review.Context object into a bookmark."""
        context_info = {}
        context_info['zone'] = context.zoneIndex
        context_info['char'] = context.charIndex
        context_info['word'] = context.wordIndex
        context_info['line'] = context.lineIndex
        return context_info

    def _bookmarkToContext(self, bookmark):
        """Converts a bookmark into a flat_review.Context object."""
        context = self._script.getFlatReviewContext()
        context.setCurrent(bookmark['line'], bookmark['zone'], \
                           bookmark['word'], bookmark['char'])
        return context
