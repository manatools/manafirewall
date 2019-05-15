# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:

'''
port forwarding dialog is a dialog to manage port forwarding configuration

License: LGPLv2+

Author:  Angelo Naselli <anaselli@linux.it>

@package manafirewall
'''
from firewall import functions

import manatools.ui.basedialog as basedialog
import manatools.ui.common as ui

import yui

class PortForwardingDialog(basedialog.BaseDialog):
  def __init__(self, portForwardingInfo={}):
    '''
    PortForwardingDialog is a dialog to manage port forwarding changes (add/edit/remove).
    portForwardingInfo dictionary contains following keys
    port        => port
    protocol    => protocol type
    to_port     => forwarding to which port
    to_address  => forwarding to which to_address
    '''
    basedialog.BaseDialog.__init__(self, _("Port Forwarding"), "", basedialog.DialogType.POPUP, 40, 7)
    self._portForwardingInfo = portForwardingInfo.copy()
    self._cancelled = False
    
  def UIlayout(self, layout):
    '''
    layout implementation called in base class to setup UI
    '''
    label = self.factory.createLabel(layout, _("Source"))
    align = self.factory.createLeft(layout)
    hbox = self.factory.createHBox(align)
    self.port   = self.factory.createInputField(hbox, _("Port / Port Range"))
    self.port.setInputMaxLength(32)

    protocols = [ 'tcp', 'udp', 'sctp', 'dccp' ]

    self.protocolCombobox = self.factory.createComboBox(hbox,_("Protocol"))
    itemColl = yui.YItemCollection()
    show_item = 'tcp'
    if 'protocol' in self._portForwardingInfo.keys():
      if self._portForwardingInfo['protocol']:
        show_item = self._portForwardingInfo['protocol']
    for p in protocols:
      item = yui.YItem(p, False)
      if show_item == p :
          item.setSelected(True)
      itemColl.push_back(item)
      item.this.own(False)
    self.protocolCombobox.addItems(itemColl)
    label = self.factory.createLabel(layout, _("Destination"))
    align = self.factory.createLeft(layout)
    self.to_address   = self.factory.createInputField(align, _("IP address"))
    self.to_address.setInputMaxLength(60)
    align = self.factory.createLeft(layout)
    self.to_port   = self.factory.createInputField(align, _("Port / Port Range"))
    self.to_port.setInputMaxLength(32)

    if 'port' in self._portForwardingInfo.keys():
      if self._portForwardingInfo['port']:
        self.port.setValue(self._portForwardingInfo['port'])

    if 'to_port' in self._portForwardingInfo.keys():
      if self._portForwardingInfo['to_port']:
        self.to_port.setValue(self._portForwardingInfo['to_port'])

    if 'to_address' in self._portForwardingInfo.keys():
      if self._portForwardingInfo['to_address']:
        self.to_address.setValue(self._portForwardingInfo['to_address'])

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
      return self._portForwardingInfo
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
    port = self.port.value()
    ports = functions.getPortRange(port)
    if not ports or not (isinstance(ports, list) or \
                         isinstance(ports, tuple)):
      ui.warningMsgBox({'title': _("Source port is mandatory"), 'text': _("Use port number or range (10000 or 12000-12002)")})
      return

    to_address = self.to_address.value()
    if to_address:
      if not functions.checkIP(to_address) and not functions.checkIP6(to_address):
        ui.warningMsgBox({'title': _("Wrong IP address"), 'text': _("The given IP address is not valid.")})
        return
    to_port = self.to_port.value()
    if to_port:
      ports = functions.getPortRange(to_port)
      if not ports or not (isinstance(ports, list) or \
                          isinstance(ports, tuple)):
        ui.warningMsgBox({'title': _("Wrong to_port range"), 'text': _("Use port number or range (10000 or 12000-12002)")})
        return

    if port and to_address and not to_port or \
       port and to_port and not to_address or \
       port and to_address and to_port:
      if (port and to_port and not to_address) and (port == to_port):
        ui.warningMsgBox({'title': _("Wrong port given"),
                          'text': _("<b>local forwarding</b><br>port and to_port must be different"),
                          'richtext': True})
        return
      sel = self.protocolCombobox.selectedItem()
      self._portForwardingInfo['port'] = port
      self._portForwardingInfo['protocol']   = sel.label()
      self._portForwardingInfo['to_port']    = to_port
      self._portForwardingInfo['to_address'] = to_address
    else:
      ui.warningMsgBox({'title': _("Missing data"), 'text': _("Valid configuration are:<br>\
        <b>local forwarding</b> fill port and to_port, note that those ports must be different<br> \
        <b>forward to address</b> fill port and to_address<br> \
        <b>forward to a remote port</b> fill port, to_address and to_port"), 'richtext': True})
      return

    # BaseDialog needs to force to exit the handle event loop
    self.ExitLoop()


  
  
