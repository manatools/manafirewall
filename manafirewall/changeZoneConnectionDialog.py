# vim: set fileencoding=utf-8 :
'''
changeZoneConnectionDialog — popup dialog to change the firewall zone of a
NetworkManager connection.

License: GPLv2+

Author:  Angelo Naselli <anaselli@linux.it>

@package manafirewall
'''
import manatools.aui.yui as MUI
import manatools.ui.basedialog as basedialog
import logging

logger = logging.getLogger('manafirewall.changeZoneConnectionDialog')


class ChangeZoneConnectionDialog(basedialog.BaseDialog):
  '''
  Popup dialog that lets the user pick a firewall zone for a NetworkManager
  connection.  Returns the chosen zone string ('' means "Default Zone") when
  the user presses OK, or None when they cancel.
  '''

  def __init__(self, fw, conn_id, conn_name, current_zone):
    '''
    fw           — firewall client (to call getZones())
    conn_id      — NetworkManager connection UUID / id
    conn_name    — human-readable connection name shown in the title
    current_zone — zone currently assigned to the connection ('' = default)
    '''
    title = _("Select zone for connection '{}'").format(conn_name)
    basedialog.BaseDialog.__init__(self, title, "manafirewall", basedialog.DialogType.POPUP, 360, 120)
    self._fw           = fw
    self._conn_id      = conn_id
    self._conn_name    = conn_name
    self._current_zone = current_zone
    self._cancelled    = True
    self._selected_zone = None

  def UIlayout(self, layout):
    # Description label
    label = self.factory.createLabel(layout, _("Select zone for connection '{}'").format(self._conn_name))

    # Zone combobox: "Default Zone" first, then all zones sorted
    self.zoneCombo = self.factory.createComboBox(layout, "")
    itemColl = []
    default_item = MUI.YItem(_("Default Zone"), self._current_zone == "")
    itemColl.append(default_item)
    try:
      zones = sorted(self._fw.getZones())
    except Exception:
      zones = []
    for z in zones:
      itemColl.append(MUI.YItem(z, z == self._current_zone))
    self.zoneCombo.addItems(itemColl)
    self.zoneCombo.setNotify(True)
    self.eventManager.addWidgetEvent(self.zoneCombo, self._onComboChanged)

    # Buttons
    align = self.factory.createRight(layout)
    hbox  = self.factory.createHBox(align)
    closeButton = self.factory.createPushButton(hbox, _("&Close"))
    self.eventManager.addWidgetEvent(closeButton, self._onCancelButtonEvent)
    self.okButton = self.factory.createPushButton(hbox, _("&Ok"))
    self.okButton.setEnabled(False)
    self.eventManager.addWidgetEvent(self.okButton, self._onOkEvent)

    self.eventManager.addCancelEvent(self._onCancelEvent)

  # ── helpers ────────────────────────────────────────────────────────────────

  def _currentSelection(self):
    '''Return the zone string for the currently highlighted combo item.'''
    item = self.zoneCombo.selectedItem()
    if item is None:
      return None
    text = item.label()
    return "" if text == _("Default Zone") else text

  # ── event handlers ─────────────────────────────────────────────────────────

  def _onComboChanged(self):
    sel = self._currentSelection()
    self.okButton.setEnabled(sel is not None and sel != self._current_zone)

  def _onCancelButtonEvent(self):
    self._cancelled = True
    self.ExitLoop()

  def _onCancelEvent(self):
    self._cancelled = True
    self.ExitLoop()

  def _onOkEvent(self):
    self._selected_zone = self._currentSelection()
    self._cancelled = False
    self.ExitLoop()

  # ── public API ─────────────────────────────────────────────────────────────

  def run(self):
    '''Run the dialog and return the chosen zone string, or None if cancelled.'''
    basedialog.BaseDialog.run(self)
    return None if self._cancelled else self._selected_zone
