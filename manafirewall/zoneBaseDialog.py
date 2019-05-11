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
    '''
    ZoneBaseDialog dialog to manage add or edit zone.
    zoneBaseInfo dictionary contains following keys most significant only for edit mode
    name              => zone name
    version           => zone version
    short             => zone short description
    description       => zone long description
    target            => zone target (default, ACCEPT, DROP, %%REJECT%%)
    max_zone_name_len => max length allowed for zone name
    default           => default zone (True/False)
    builtin           => builtin zone (True/False)
    '''
    basedialog.BaseDialog.__init__(self, _("Zone Settings"), "", basedialog.DialogType.POPUP, 40, 15)
    self._zoneBaseInfo = zoneBaseInfo.copy()
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
    if 'max_zone_name_len' in self._zoneBaseInfo.keys():
      self.name.setInputMaxLength(self._zoneBaseInfo['max_zone_name_len'])
    if 'name' in self._zoneBaseInfo.keys():
      self.name.setValue(self._zoneBaseInfo['name'])
    if 'version' in self._zoneBaseInfo.keys():
      self.version.setValue(self._zoneBaseInfo['version'])
    if 'short' in self._zoneBaseInfo.keys():
      self.short.setValue(self._zoneBaseInfo['short'])
    if 'description' in self._zoneBaseInfo.keys():
      self.description.setValue(self._zoneBaseInfo['description'])

    hbox = self.factory.createHBox(layout)
    align = self.factory.createLeft(hbox)
    self.defaultTarget = self.factory.createCheckBox( align, _("Default Target"), False)
    self.eventManager.addWidgetEvent(self.defaultTarget, self.onDefaultTargetEvent)

    self.targets = {
            'ACCEPT' : {'title' : _("Accept")},
            'DROP'   : {'title' : _("Drop")},
            'REJECT' : {'title' : _("Reject")},
        }
    ordered_targets = [ 'ACCEPT', 'DROP', 'REJECT' ]

    defaultTgt = "default"
    if 'target' in self._zoneBaseInfo.keys():
      defaultTgt = self._zoneBaseInfo['target'] if self._zoneBaseInfo['target'] != "%%REJECT%%" else "REJECT"

    self.currentTargetCombobox = self.factory.createComboBox(hbox,"")
    itemColl = yui.YItemCollection()
    for v in ordered_targets:
      item = yui.YItem(self.targets[v]['title'], False)
      show_item = 'ACCEPT' if defaultTgt == "default" else defaultTgt
      if show_item == v :
          item.setSelected(True)
      # adding item to targets to find the item selected
      self.targets[v]['item'] = item
      itemColl.push_back(item)
      item.this.own(False)
    self.currentTargetCombobox.addItems(itemColl)
    self.defaultTarget.setValue(defaultTgt == "default")
    self.currentTargetCombobox.setEnabled(defaultTgt != "default")
    self.defaultTarget.setNotify(True)

    #### buttons on the last line
    align = self.factory.createRight(layout)
    bottomLine = self.factory.createHBox(align)

    cancelButton = self.factory.createPushButton(bottomLine, _("&Cancel"))
    self.eventManager.addWidgetEvent(cancelButton, self.onCancelButtonEvent)

    okButton = self.factory.createPushButton(bottomLine, _("&Ok"))
    self.eventManager.addWidgetEvent(okButton, self.onOkEvent)
    
    # Let's test a cancel event
    self.eventManager.addCancelEvent(self.onCancelEvent)

    if 'builtin' in self._zoneBaseInfo.keys() and 'default' in self._zoneBaseInfo.keys():
      # Let's disable name changes for builtin zones
      enabled = not self._zoneBaseInfo['builtin'] and self._zoneBaseInfo['default']
      self.name.setEnabled(enabled)
      
  def run(self):
    '''
    overrides basdialog run to return information (zoneBaseInfo)
    See constructor for dictioary key meanings
    '''
    basedialog.BaseDialog.run(self)
    if not self._cancelled:
      return self._zoneBaseInfo
    return None

  def onDefaultTargetEvent(self):
    '''
    change default target
    '''
    self.currentTargetCombobox.setEnabled( not self.defaultTarget.value() )

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
    Confirm changes (name is mandatory) and prepare zoneBaseInfo to return.
    See constructor for key meanings
    '''
    name = self.name.value()
    if name:
      self._zoneBaseInfo['name'] = name
      self._zoneBaseInfo['version'] = self.version.value()
      self._zoneBaseInfo['short'] = self.short.value()
      self._zoneBaseInfo['description'] = self.description.value()
      if self.defaultTarget.value():
        self._zoneBaseInfo['target'] = 'default'
      else:
        item = self.currentTargetCombobox.selectedItem()
        for tgt in self.targets.keys():
          if self.targets[tgt]['item'] == item:
            self._zoneBaseInfo['target'] = tgt if tgt != "REJECT" else "%%REJECT%%"

      # BaseDialog needs to force to exit the handle event loop
      self.ExitLoop()
    else:
      ui.warningMsgBox({'title': _("Missing value"), 'text': _("Name is mandatory")})


  
  
