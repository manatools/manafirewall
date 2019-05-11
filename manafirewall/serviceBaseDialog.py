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



class ServiceBaseDialog(basedialog.BaseDialog):
  def __init__(self, serviceBaseInfo={}):
    '''
    ServiceBaseDialog dialog to manage add or edit zone.
    serviceBaseInfo dictionary contains following keys most significant only for edit mode
    name              => zone name
    version           => zone version
    short             => zone short description
    description       => zone long description
    default           => default zone (True/False)
    builtin           => builtin zone (True/False)
    '''
    basedialog.BaseDialog.__init__(self, _("Service Settings"), "", basedialog.DialogType.POPUP, 40, 15)
    self._serviceBaseInfo = serviceBaseInfo.copy()
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
    self.description.setDefaultVisibleLines(5)
    if 'name' in self._serviceBaseInfo.keys():
      self.name.setValue(self._serviceBaseInfo['name'])
    if 'version' in self._serviceBaseInfo.keys():
      self.version.setValue(self._serviceBaseInfo['version'])
    if 'short' in self._serviceBaseInfo.keys():
      self.short.setValue(self._serviceBaseInfo['short'])
    if 'description' in self._serviceBaseInfo.keys():
      self.description.setValue(self._serviceBaseInfo['description'])


    #### buttons on the last line
    align = self.factory.createRight(layout)
    bottomLine = self.factory.createHBox(align)

    cancelButton = self.factory.createPushButton(bottomLine, _("&Cancel"))
    self.eventManager.addWidgetEvent(cancelButton, self.onCancelButtonEvent)

    okButton = self.factory.createPushButton(bottomLine, _("&Ok"))
    self.eventManager.addWidgetEvent(okButton, self.onOkEvent)
    
    # Let's test a cancel event
    self.eventManager.addCancelEvent(self.onCancelEvent)

    if 'builtin' in self._serviceBaseInfo.keys() and 'default' in self._serviceBaseInfo.keys():
      # Let's disable name changes for builtin zones
      enabled = not self._serviceBaseInfo['builtin'] and self._serviceBaseInfo['default']
      self.name.setEnabled(enabled)
      
  def run(self):
    '''
    overrides basdialog run to return information (serviceBaseInfo)
    See constructor for dictioary key meanings
    '''
    basedialog.BaseDialog.run(self)
    if not self._cancelled:
      return self._serviceBaseInfo
    return None

  def onCancelButtonEvent(self) :
    '''
    Cancelled, discards changes
    '''
    self._cancelled = True
    # BaseDialog needs to force to exit the handle event loop
    self.ExitLoop()

  def onCancelEvent(self) :
    '''
    Cancelled, discards changes
    '''
    self._cancelled = True

  def onOkEvent(self) :
    '''
    Confirm changes (name is mandatory) and prepare serviceBaseInfo to return.
    See constructor for key meanings
    '''
    name = self.name.value()
    if name:
      self._serviceBaseInfo['name'] = name
      self._serviceBaseInfo['version'] = self.version.value()
      self._serviceBaseInfo['short'] = self.short.value()
      self._serviceBaseInfo['description'] = self.description.value()

      # BaseDialog needs to force to exit the handle event loop
      self.ExitLoop()
    else:
      ui.warningMsgBox({'title': _("Missing value"), 'text': _("Name is mandatory")})


  
  
