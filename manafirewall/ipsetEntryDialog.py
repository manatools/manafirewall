# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:
'''
ipsetEntryDialog — popup to add or edit a single IP set entry.

License: GPLv2+
Author:  Angelo Naselli <anaselli@linux.it>
@package manafirewall
'''

import gettext
import logging

import manatools.ui.basedialog as basedialog
import manatools.aui.yui as MUI

try:
    from firewall.core.io.ipset import IPSet
except ImportError:
    IPSet = None

_ = gettext.gettext
logger = logging.getLogger('manafirewall.ipsetentrydialog')


class IPSetEntryDialog(basedialog.BaseDialog):
    '''Popup dialog to add or edit one IP set entry.

    Parameters:
        ipset_type    – string like "hash:ip" or "hash:net"
        ipset_options – dict of options (e.g. {"family": "inet"})
        old_entry     – current value when editing; empty string when adding
    '''

    def __init__(self, ipset_type, ipset_options, old_entry=''):
        title = _("Edit Entry") if old_entry else _("Add Entry")
        basedialog.BaseDialog.__init__(
            self, title, '', basedialog.DialogType.POPUP, 420, 160)
        self._ipset_type    = ipset_type or ''
        self._ipset_options = ipset_options or {}
        self._old_entry     = old_entry or ''
        self._result        = None

    def UIlayout(self, layout):
        vbox = self.factory.createVBox(layout)

        # Type info row
        hbox_type = self.factory.createHBox(vbox)
        self.factory.createLabel(hbox_type, _("Type:"))
        self.factory.createLabel(hbox_type, '  ' + self._ipset_type)
        self.factory.createHStretch(hbox_type)

        self.factory.createVSpacing(vbox, 0.3)

        # Entry input row
        hbox_entry = self.factory.createHBox(vbox)
        self.factory.createLabel(hbox_entry, _("Entry:"))
        self._entryInput = self.factory.createInputField(hbox_entry, '')
        self._entryInput.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
        if self._old_entry:
            self._entryInput.setValue(self._old_entry)
        self._entryInput.setNotify(True)
        self.eventManager.addWidgetEvent(
            self._entryInput, self._onEntryChanged, True)

        self.factory.createVSpacing(vbox, 0.5)

        # Buttons
        align = self.factory.createRight(layout)
        hbox_btns = self.factory.createHBox(align)
        self._cancelButton = self.factory.createIconButton(hbox_btns, 'dialog-cancel', _("&Cancel"))
        self._okButton     = self.factory.createIconButton(hbox_btns, 'dialog-ok',     _("&Ok"))
        # Ok starts disabled — user must type a valid entry (or re-type when editing)
        self._okButton.setEnabled(False)
        self.dialog.setDefaultButton(self._okButton)

        self.eventManager.addWidgetEvent(self._okButton,     self._onOk)
        self.eventManager.addWidgetEvent(self._cancelButton, self._onCancel)
        self.eventManager.addCancelEvent(self._onCancel)

    def _validate(self, entry):
        '''Return True if *entry* is valid for this IP set type.'''
        if not entry:
            return False
        if IPSet is None:
            return bool(entry.strip())  # fallback: non-empty
        try:
            IPSet.check_entry(entry, self._ipset_options, self._ipset_type)
            return True
        except Exception:
            return False

    def _onEntryChanged(self, *args):
        entry = self._entryInput.value()
        self._okButton.setEnabled(self._validate(entry))

    def _onOk(self):
        self._result = self._entryInput.value()
        self.ExitLoop()

    def _onCancel(self):
        self._result = None
        self.ExitLoop()

    def run(self):
        '''Run the dialog. Returns the entry string on Ok, None on Cancel.'''
        basedialog.BaseDialog.run(self)
        return self._result
