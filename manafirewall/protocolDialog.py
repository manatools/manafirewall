# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:

'''
protocol dialog is a dialog to manage protocol

License: GPLv2+

Author:  Angelo Naselli <anaselli@linux.it>

@package manafirewall
'''
from firewall import functions

import manatools.ui.basedialog as basedialog
import manatools.ui.common as ui

import yui



class ProtocolDialog(basedialog.BaseDialog):
  def __init__(self, info={}):
    '''
    ProtocolDialog is a dialog to manage protocols changes (add/edit/remove).
    info dictionary contains following keys
    protocol          => protocol type
    '''
    basedialog.BaseDialog.__init__(self, _("Protocol"), "", basedialog.DialogType.POPUP, 40, 7)
    self._info = info.copy()
    self._cancelled = False
    
  def UIlayout(self, layout):
    '''
    layout implementation called in base class to setup UI
    '''
    align = self.factory.createLeft(layout)

    protocols = [ 'ah', 'esp', 'dccp', 'ddp', 'icmp', 'ipv6-icmp', 'igmp', 'mux', 'sctp', 'tcp','udp' ]

    self.protocolCombobox = self.factory.createComboBox(align,_("Protocol"))
    itemColl = yui.YItemCollection()
    show_item = ""
    selected = False
    if 'protocol' in self._info.keys():
      if self._info['protocol']:
        show_item = self._info['protocol']
    for p in protocols:
      item = yui.YItem(p, False)
      if show_item == p :
          item.setSelected(True)
          selected = True
      itemColl.push_back(item)
      item.this.own(False)
    self.protocolCombobox.addItems(itemColl)

    align = self.factory.createLeft(layout)
    hbox = self.factory.createHBox(align)
    self.enable_other   = self.factory.createCheckBox(hbox, _("Other Protocol"), False)

    self.eventManager.addWidgetEvent(self.enable_other, self.onEnableOther)

    self.other_protocol = self.factory.createInputField(hbox, "")
    self.other_protocol.setInputMaxLength(50)
    self.other_protocol.setEnabled(False)

    if show_item and not selected:
      self.other_protocol.setValue(show_item)
      self.other_protocol.setEnabled(True)
      self.enable_other.setValue(yui.YCheckBox_on)
      self.protocolCombobox.setEnabled(False)


    self.enable_other.setNotify(True)

    #### buttons on the last line
    align = self.factory.createRight(layout)
    bottomLine = self.factory.createHBox(align)

    cancelButton = self.factory.createPushButton(bottomLine, _("&Cancel"))
    self.eventManager.addWidgetEvent(cancelButton, self.onCancelButtonEvent)

    okButton = self.factory.createPushButton(bottomLine, _("&Ok"))
    self.eventManager.addWidgetEvent(okButton, self.onOkEvent)
    
    # Let's test a cancel event
    self.eventManager.addCancelEvent(self.onCancelEvent)

  def onEnableOther(self):
    '''
    check box enable other protocols has been checked/uncheked
    '''
    checked = self.enable_other.isChecked()
    self.other_protocol.setEnabled(checked)
    self.protocolCombobox.setEnabled(not checked)

      
  def run(self):
    '''
    overrides basdialog run to return information (info)
    See constructor for dictioary key meanings
    '''
    basedialog.BaseDialog.run(self)
    if not self._cancelled:
      return self._info
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
    Confirm changes (name is mandatory) and prepare info to return.
    See constructor for key meanings
    '''
    checked = self.enable_other.isChecked()
    sel = self.protocolCombobox.selectedItem()
    protocol = sel.label()
    if checked:
      protocol = self.other_protocol.value()
      if not protocol:
        ui.warningMsgBox({'title': _("Protocol is mandatory"), 'text': _("Please insert a valid protocol (see /etc/protocols)")})
        return
      if not functions.checkProtocol(protocol):
        ui.warningMsgBox({'title': _("Wrong protocol entry"), 'text': _("Please insert a valid protocol (see /etc/protocols)")})
        return

    self._info['protocol'] = protocol

    # BaseDialog needs to force to exit the handle event loop
    self.ExitLoop()


  
  
