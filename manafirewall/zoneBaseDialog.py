# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:

'''
ui dialog demo

License: LGPLv2+

Author:  Angelo Naselli <anaselli@linux.it>

@package manafirewall
'''

import manatools.ui.basedialog as basedialog
import manatools.ui.common as ui

import yui



class ZoneBaseDialog(basedialog.BaseDialog):
  def __init__(self, zoneBaseInfo={}):
    basedialog.BaseDialog.__init__(self, _("Zone Settings"), "", basedialog.DialogType.POPUP, 40, 15)
    self._zoneBaseInfo = zoneBaseInfo
    self._cancelled = False
    
  def UIlayout(self, layout):
    '''
    layout implementation called in base class to setup UI
    '''
    align = self.factory.createLeft(layout)
    self.name        = self.factory.createInputField(align, _("Name"))
    align = self.factory.createLeft(layout)
    self.version     = self.factory.createInputField(align, _("Version"))
    align = self.factory.createLeft(layout)
    self.short       = self.factory.createInputField(align, _("Short"))
    align = self.factory.createLeft(layout)
    self.description = self.factory.createMultiLineEdit(align, _("Description"))

    if 'name' in self._zoneBaseInfo.keys():
      self.name.setValue(self._zoneBaseInfo['name'])
    if 'version' in self._zoneBaseInfo.keys():
      self.version.setValue(self._zoneBaseInfo['version'])
    if 'short' in self._zoneBaseInfo.keys():
      self.short.setValue(self._zoneBaseInfo['short'])
    if 'description' in self._zoneBaseInfo.keys():
      self.description.setValue(self._zoneBaseInfo['description'])
    if 'builtin' in self._zoneBaseInfo.keys() and 'default' in self._zoneBaseInfo.keys():
      self.name.setEnabled(not self._zoneBaseInfo['builtin'] and self._zoneBaseInfo['default'])

    #### buttons on the last line
    align = self.factory.createRight(layout)
    bottomLine = self.factory.createHBox(align)

    cancelButton = self.factory.createPushButton(bottomLine, "&Cancel")
    self.eventManager.addWidgetEvent(cancelButton, self.onCancelButtonEvent)

    okButton = self.factory.createPushButton(bottomLine, "&Ok")
    self.eventManager.addWidgetEvent(okButton, self.onOkEvent)
    
    # Let's test a cancel event
    self.eventManager.addCancelEvent(self.onCancelEvent)
      
  def run(self):
    basedialog.BaseDialog.run(self)
    if not self._cancelled:
      return self._zoneBaseInfo
    return None

  def onCancelButtonEvent(self) :
    print ("Got a cancel button")
    self._cancelled = True
    # BaseDialog needs to force to exit the handle event loop
    self.ExitLoop()

  def onCancelEvent(self) :
    print ("Got a cancel event")
    self._cancelled = True

  def onOkEvent(self) :
    print ("Ok button pressed")
    name = self.name.label()
    if name:
      # BaseDialog needs to force to exit the handle event loop
      self.ExitLoop()
    else:
      ui.warningMsgBox({'title': _("Missing value"), 'text': _("Name is mandatory")})


  
  
