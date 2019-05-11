# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:

'''
port dialog is a dialog to manage ports

License: LGPLv2+

Author:  Angelo Naselli <anaselli@linux.it>

@package manafirewall
'''
from firewall import functions

import manatools.ui.basedialog as basedialog
import manatools.ui.common as ui

import yui



class PortDialog(basedialog.BaseDialog):
  def __init__(self, portInfo={}):
    '''
    PortDialog is a dialog to manage port changes (add/edit/remove).
    portInfo dictionary contains following keys
    port_range        => port range
    protocol          => protocol type
    '''
    basedialog.BaseDialog.__init__(self, _("Port and Protocol"), "", basedialog.DialogType.POPUP, 40, 7)
    self._portInfo = portInfo.copy()
    self._cancelled = False
    
  def UIlayout(self, layout):
    '''
    layout implementation called in base class to setup UI
    '''
    align = self.factory.createLeft(layout)
    hbox = self.factory.createHBox(align)
    self.port_range   = self.factory.createInputField(hbox, _("Port / Port Range"))
    self.port_range.setInputMaxLength(32)

    protocols = [ 'tcp', 'udp', 'sctp', 'dccp' ]

    self.protocolCombobox = self.factory.createComboBox(hbox,_("Protocol"))
    itemColl = yui.YItemCollection()
    show_item = 'tcp'
    if 'protocol' in self._portInfo.keys():
      if self._portInfo['protocol']:
        show_item = self._portInfo['protocol']
    for p in protocols:
      item = yui.YItem(p, False)
      if show_item == p :
          item.setSelected(True)
      itemColl.push_back(item)
      item.this.own(False)

    self.protocolCombobox.addItems(itemColl)
    if 'port_range' in self._portInfo.keys():
      self.port_range.setValue(self._portInfo['port_range'])

    #### buttons on the last line
    align = self.factory.createRight(layout)
    bottomLine = self.factory.createHBox(align)

    cancelButton = self.factory.createPushButton(bottomLine, _("&Cancel"))
    self.eventManager.addWidgetEvent(cancelButton, self.onCancelButtonEvent)

    okButton = self.factory.createPushButton(bottomLine, _("&Ok"))
    self.eventManager.addWidgetEvent(okButton, self.onOkEvent)
    
    # Let's test a cancel event
    self.eventManager.addCancelEvent(self.onCancelEvent)

      
  def run(self):
    '''
    overrides basdialog run to return information (portInfo)
    See constructor for dictioary key meanings
    '''
    basedialog.BaseDialog.run(self)
    if not self._cancelled:
      return self._portInfo
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
    Confirm changes (name is mandatory) and prepare portInfo to return.
    See constructor for key meanings
    '''
    port_range = self.port_range.value()
    ports = functions.getPortRange(port_range)
    if not ports or not (isinstance(ports, list) or \
                         isinstance(ports, tuple)):
      ui.warningMsgBox({'title': _("Wrong port range"), 'text': _("Use port number or range (10000 or 12000-12002)")})
      return

    self._portInfo['port_range'] = port_range
    sel = self.protocolCombobox.selectedItem()
    self._portInfo['protocol'] = sel.label()

    # BaseDialog needs to force to exit the handle event loop
    self.ExitLoop()


  
  
