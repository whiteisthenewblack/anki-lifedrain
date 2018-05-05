"""
Anki Add-on: Life Drain
Add a bar that is reduced as time passes. Completing reviews recovers it.

**
Some of the code used here was originally done by Glutanimate, from the
Addon Progress Bar. So I copied the copyright from that Addon and appended my name.
**

Copyright:  (c) Unknown author (nest0r/Ja-Dark?) 2017
            (c) SebastienGllmt 2017 <https://github.com/SebastienGllmt/>
            (c) Glutanimate 2017 <https://glutanimate.com/>
            (c) Yutsuten 2018 <https://github.com/Yutsuten>
License: GNU AGPLv3 or later <https://www.gnu.org/licenses/agpl.html>
"""

from anki.hooks import addHook, wrap
from aqt.qt import *
from aqt import mw
from aqt.progress import ProgressManager
from aqt.utils import showInfo
from aqt.reviewer import Reviewer


config = {
    'maxValue': 150,
    'recoverValue': 22,
    'position': 'bottom',
    'progressBarStyle': {
        'height': 17,
        'textColor': '#dddddd',
        'backgroundColor': '#222222',
        'foregroundColor': '#666666',
        'borderRadius': 0,
        'customStyle': 'default'
    }
}

class AnkiProgressBar(object):
    _qProgressBar = None
    _maxValue = 1
    _currentValue = 1

    def __init__(self, config):
        self._qProgressBar = QProgressBar()
        self.setMaxValue(config['maxValue'])
        self.resetBar()
        self.setTextVisible(False)
        self.setStyle(config['progressBarStyle'])
        self._dockAt(config['position'])

    def show(self):
        self._qProgressBar.show()

    def hide(self):
        self._qProgressBar.hide()

    def resetBar(self):
        self._currentValue = self._maxValue
        self._validateUpdateCurrentValue()

    def setMaxValue(self, maxValue):
        self._maxValue = maxValue
        if (self._maxValue <= 0):
            self._maxValue = 1
        self._qProgressBar.setRange(0, self._maxValue)

    def setCurrentValue(self, currentValue):
        self._currentValue = currentValue
        self._validateUpdateCurrentValue()

    def incCurrentValue(self, increment):
        self._currentValue += increment
        self._validateUpdateCurrentValue()

    def getCurrentValue(self):
        return self._currentValue

    def setTextVisible(self, flag):
        self._qProgressBar.setTextVisible(flag)

    def setStyle(self, options):
        if (options['customStyle'] != 'default'):
            palette = QPalette()
            palette.setColor(QPalette.Base, QColor(options['backgroundColor']))
            palette.setColor(QPalette.Highlight, QColor(options['foregroundColor']))
            palette.setColor(QPalette.Button, QColor(options['backgroundColor']))
            palette.setColor(QPalette.WindowText, QColor(options['textColor']))
            palette.setColor(QPalette.Window, QColor(options['backgroundColor']))

            self._qProgressBar.setStyle(QStyleFactory.create(options['customStyle']))
            self._qProgressBar.setPalette(palette)
            self._qProgressBar.setStyleSheet(
                '''
                QProgressBar {
                    max-height: %spx;
                }
                '''
                % (
                    options['height'],
                )
            )
        else:
            self._qProgressBar.setStyleSheet(
                '''
                QProgressBar {
                    text-align:center;
                    color: %s;
                    background-color: %s;
                    border-radius: %dpx;
                    max-height: %spx;
                }
                QProgressBar::chunk {
                    background-color: %s;
                    margin: 0px;
                    border-radius: %dpx;
                }
                '''
                % (
                    options['textColor'],
                    options['backgroundColor'],
                    options['borderRadius'],
                    options['height'],
                    options['foregroundColor'],
                    options['borderRadius']
                )
            )

    def _validateUpdateCurrentValue(self):
        if (self._currentValue > self._maxValue):
            self._currentValue = self._maxValue
        elif (self._currentValue < 0):
            self._currentValue = 0
        self._qProgressBar.setValue(self._currentValue)

    def _dockAt(self, place):
        '''
        - Valid place values: top, bottom
        Default to bottom
        '''
        if (place not in ['top', 'bottom']):
            place = 'bottom'

        if (place == 'top'):
            dockArea = Qt.TopDockWidgetArea
        elif (place == 'bottom'):
            dockArea = Qt.BottomDockWidgetArea

        dock = QDockWidget()
        tWidget = QWidget()
        dock.setWidget(self._qProgressBar)
        dock.setTitleBarWidget(tWidget)

        existing_widgets = [widget for widget in mw.findChildren(QDockWidget) if mw.dockWidgetArea(widget) == dockArea]
        if (len(existing_widgets) == 0):
            mw.addDockWidget(dockArea, dock)
        else:
            mw.setDockNestingEnabled(True)
            mw.splitDockWidget(existing_widgets[0], dock, Qt.Vertical)
        mw.web.setFocus()


class DeckProgressBarManager(object):
    '''
    Allow using the same instance of AnkiProgressBar with different configuration and
    currentValue for each deck.
    '''
    _ankiProgressBar = None
    _barInfo = {}
    _currentDeck = None

    def __init__(self, ankiProgressBar):
        self._ankiProgressBar = ankiProgressBar

    def addDeck(self, deckId):
        self._barInfo[str(deckId)] = {
            'currentValue': self._ankiProgressBar.getCurrentValue()
        }

    def setDeck(self, deckId):
        if self._currentDeck:
            self._barInfo[self._currentDeck]['currentValue'] = self._ankiProgressBar.getCurrentValue()
        if deckId:
            self._currentDeck = str(deckId)
            self._ankiProgressBar.setCurrentValue(self._barInfo[self._currentDeck]['currentValue'])
        else:
            self._currentDeck = None

    def getBar(self):
        return self._ankiProgressBar


# Remove separator strip
separatorStripCss = '''
    QMainWindow::separator {
        width: 0px;
        height: 0px;
    }
'''
try:
    import Night_Mode
    Night_Mode.nm_css_menu += separatorStripCss
    if (not Night_Mode.nm_state_on):
        mw.setStyleSheet(separatorStripCss)
except ImportError:
    mw.setStyleSheet(separatorStripCss)


deckBarManager = None
timer = None
status = {
    'reviewed': False,
    'screen': None
}

def timerTrigger():
    global deckBarManager
    deckBarManager.getBar().incCurrentValue(-1)

def profileLoaded():
    global deckBarManager, config
    progressBar = AnkiProgressBar(config)
    deckBarManager = DeckProgressBarManager(progressBar)
    for deckId in mw.col.decks.allIds():
        deckBarManager.addDeck(deckId)
    progressBar.hide()

def afterStateChange(state, oldState):
    global deckBarManager, config, timer, status

    if not timer:
        timer = ProgressManager(mw).timer(1000, timerTrigger, True)
    timer.stop()

    if (status['reviewed'] and state in ['overview', 'review']):
        deckBarManager.getBar().incCurrentValue(config['recoverValue'])
    status['reviewed'] = False
    status['screen'] = state

    if state in ['overview', 'review']:
        deckBarManager.setDeck(mw.col.decks.current()['id'])
        deckBarManager.getBar().show()
    elif deckBarManager:
        deckBarManager.getBar().hide()
        deckBarManager.setDeck(None)

    if state == 'review':
        timer.start()

def showQuestion():
    global deckBarManager, config, status
    activateTimer()
    if (status['reviewed']):
        deckBarManager.getBar().incCurrentValue(config['recoverValue'])

def showAnswer():
    global status
    activateTimer()
    status['reviewed'] = True

def reset():
    global deckBarManager, config, status
    status['reviewed'] = False
    if (status['screen'] == 'review'):
        activateTimer()
        deckBarManager.getBar().incCurrentValue(-1 * config['recoverValue'])

def activateTimer():
    global timer
    if not timer.isActive():
        timer.start()

def keyHandler(self, evt, _old):
    '''
    Add the P shortcut for pausing/unpausing the drain.
    '''
    global timer
    key = unicode(evt.text())
    if key == 'p' and timer:
        if (timer.isActive()):
            timer.stop()
        else:
            timer.start()
    else:
        return _old(self, evt)

Reviewer._keyHandler = wrap(Reviewer._keyHandler, keyHandler, "around")


addHook('profileLoaded', profileLoaded)
addHook('afterStateChange', afterStateChange)
addHook('showQuestion', showQuestion)
addHook('showAnswer', showAnswer)
addHook('reset', reset)

