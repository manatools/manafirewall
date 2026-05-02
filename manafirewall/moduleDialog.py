# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:

'''
moduleDialog — dialog to select a conntrack helper for a firewalld service.

License: GPLv2+
Author:  Angelo Naselli <anaselli@linux.it>
@package manafirewall
'''

import gettext
import logging

import manatools.ui.basedialog as basedialog
import manatools.aui.yui as MUI

_ = gettext.gettext
logger = logging.getLogger('manafirewall.moduledialog')


class HelperDialog(basedialog.BaseDialog):
    '''Popup to pick a conntrack helper from the list of known firewalld helpers.

    Parameters
    ----------
    fw : FirewallClient
        Live firewall client — used to query available helper names.
    existing : list[str]
        Helper names already assigned to the service (shown as dimmed / selectable
        only if not already present).
    '''

    def __init__(self, fw, existing=None):
        basedialog.BaseDialog.__init__(
            self, _("Add Helper"), "", basedialog.DialogType.POPUP, 360, 280)
        self._fw = fw
        self._existing = set(existing or [])
        self._selected = None

    def UIlayout(self, layout):
        vbox = self.factory.createVBox(layout)

        heading = self.factory.createHeading(vbox, _("Available helpers"))
        heading.setAutoWrap()
        self.factory.createVSpacing(vbox, 0.3)

        # Build the list of helpers that are not already assigned
        try:
            all_helpers = sorted(self._fw.config().getHelperNames())
        except Exception as exc:
            logger.warning("Could not retrieve helper names: %s", exc)
            all_helpers = []

        tbl_header = MUI.YTableHeader()
        tbl_header.addColumn(_('Helper'))
        self._helperTable = self.factory.createTable(vbox, tbl_header, False)
        self._helperTable.setStretchable(MUI.YUIDimension.YD_VERT, True)
        self._helperTable.setNotify(True)

        items = []
        for name in all_helpers:
            if name not in self._existing:
                it = MUI.YTableItem()
                it.addCell(name)
                items.append(it)
        self._helperTable.addItems(items)

        self.eventManager.addWidgetEvent(self._helperTable, self._onSelection, True)

        align = self.factory.createRight(vbox)
        hbox = self.factory.createHBox(align)
        self.okButton     = self.factory.createPushButton(hbox, _("&Ok"))
        self.cancelButton = self.factory.createPushButton(hbox, _("&Cancel"))
        self.okButton.setEnabled(False)
        self.eventManager.addWidgetEvent(self.okButton,     self._onOk)
        self.eventManager.addWidgetEvent(self.cancelButton, self._onCancel)
        self.eventManager.addCancelEvent(self._onCancel)

    def _onSelection(self, obj):
        item = self._helperTable.selectedItem()
        self.okButton.setEnabled(item is not None)

    def _onOk(self):
        item = self._helperTable.selectedItem()
        if item is not None:
            self._selected = item.cell(0).label()
        self.ExitLoop()

    def _onCancel(self):
        self._selected = None
        self.ExitLoop()

    def run(self):
        '''Run the dialog. Returns the selected helper name, or None on Cancel.'''
        basedialog.BaseDialog.run(self)
        return self._selected
