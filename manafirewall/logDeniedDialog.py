# vim: set fileencoding=utf-8 :
'''
logDeniedDialog — small dialog to change the firewalld log-denied setting

License: GPLv2+

Author:  Angelo Naselli <anaselli@linux.it>

@package manafirewall
'''

from firewall.config import LOG_DENIED_VALUES

import manatools.ui.basedialog as basedialog
import manatools.aui.yui as MUI

import logging
logger = logging.getLogger('manafirewall.logdenieddialog')


class LogDeniedDialog(basedialog.BaseDialog):
  '''
  A small popup dialog that lets the user choose a log-denied value
  from the set defined by firewalld (all, unicast, broadcast, multicast, off).

  Usage::
      dlg = LogDeniedDialog(current_value)
      new_value = dlg.run()   # returns None if cancelled, str otherwise
  '''

  def __init__(self, current_value="off"):
    basedialog.BaseDialog.__init__(
        self, _("Log Denied"), "manafirewall",
        basedialog.DialogType.POPUP, 40, 6)
    self._current_value = current_value if current_value in LOG_DENIED_VALUES else "off"
    self._selected_value = None
    self._cancelled = False

  def UIlayout(self, layout):
    '''
    Layout: one combobox, Cancel / OK buttons.
    '''
    align = self.factory.createLeft(layout)
    hbox  = self.factory.createHBox(align)

    self.valueCombobox = self.factory.createComboBox(hbox, _("Log Denied"))
    itemColl = []
    for v in LOG_DENIED_VALUES:
      item = MUI.YItem(v, False)
      if v == self._current_value:
        item.setSelected(True)
      itemColl.append(item)
    self.valueCombobox.addItems(itemColl)
    self.valueCombobox.setNotify(True)
    self.eventManager.addWidgetEvent(self.valueCombobox, self._onValueChanged)

    # OK enabled only when the selection actually differs from the current value
    align = self.factory.createRight(layout)
    bottomLine = self.factory.createHBox(align)
    self.cancelButton = self.factory.createPushButton(bottomLine, _("&Cancel"))
    self.eventManager.addWidgetEvent(self.cancelButton, self.onCancelButtonEvent)

    self.okButton = self.factory.createPushButton(bottomLine, _("&Ok"))
    self.okButton.setEnabled(False)   # disabled until user picks a different value
    self.eventManager.addWidgetEvent(self.okButton, self.onOkEvent)

    self.eventManager.addCancelEvent(self.onCancelEvent)

  # ------------------------------------------------------------------
  def _onValueChanged(self):
    selected = self.valueCombobox.selectedItem()
    if selected:
      self.okButton.setEnabled(selected.label() != self._current_value)

  def onCancelButtonEvent(self):
    self._cancelled = True
    self.ExitLoop()

  def onCancelEvent(self):
    self._cancelled = True

  def onOkEvent(self):
    selected = self.valueCombobox.selectedItem()
    if selected:
      self._selected_value = selected.label()
    self.ExitLoop()

  # ------------------------------------------------------------------
  def run(self):
    '''
    Run the dialog and return the chosen value string, or None if cancelled.
    '''
    basedialog.BaseDialog.run(self)
    if not self._cancelled and self._selected_value is not None:
      return self._selected_value
    return None
