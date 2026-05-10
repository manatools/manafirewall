# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:
'''
ipsetBaseDialog — popup to add or edit an IP set (permanent mode).

Fields: name, type, version, short, description, family, timeout,
hashsize, maxelem.

License: GPLv2+
Author:  Angelo Naselli <anaselli@linux.it>
@package manafirewall
'''

import gettext
import logging

import manatools.ui.basedialog as basedialog
import manatools.ui.common as ui
import manatools.aui.yui as MUI

_ = gettext.gettext
logger = logging.getLogger('manafirewall.ipsetbasedialog')

# Default list used when the caller cannot query the firewall daemon.
_DEFAULT_IPSET_TYPES = [
    'hash:ip', 'hash:ip,mark', 'hash:ip,port', 'hash:ip,port,ip',
    'hash:ip,port,net', 'hash:mac', 'hash:net', 'hash:net,iface',
    'hash:net,net', 'hash:net,port', 'hash:net,port,net',
    'list:set',
]

_FAMILY_CHOICES = ['inet', 'inet6']


class IPSetBaseDialog(basedialog.BaseDialog):
    '''Popup dialog to create or edit an IP set.

    Parameters:
        ipsetInfo  – dict with existing values (edit mode) or empty (add mode).
                     Keys: name, type, version, short, description, options
                           (sub-keys: family, timeout, hashsize, maxelem),
                           default, builtin.
        ipset_types – optional list of type strings; falls back to a built-in
                      default list when not provided.
    '''

    def __init__(self, ipsetInfo=None, ipset_types=None):
        basedialog.BaseDialog.__init__(
            self, _("IP Set Settings"), "", basedialog.DialogType.POPUP, 380, 180)
        self._info = (ipsetInfo or {}).copy()
        self._types = ipset_types if ipset_types else _DEFAULT_IPSET_TYPES
        self._cancelled = False
        self._result = None

    # ------------------------------------------------------------------
    def _row(self, parent, label_text):
        '''Helper: create a horizontal row with a right-aligned label on the
        left and return the HBox so the caller can add the widget on the right.
        '''
        hbox = self.factory.createHBox(parent)
        lbl  = self.factory.createLabel(hbox, label_text)
        lbl.setStretchable(MUI.YUIDimension.YD_HORIZ, False)
        return hbox

    # ------------------------------------------------------------------
    def UIlayout(self, layout):
        is_edit   = bool(self._info)
        builtin   = self._info.get('builtin', False)
        default_f = self._info.get('default', True)
        options   = self._info.get('options', {})

        # ── Name  [label | field] — mandatory ─────────────────────────
        hbox = self._row(layout, _("Name:"))
        self._nameField = self.factory.createInputField(hbox, "")
        if 'name' in self._info:
            self._nameField.setValue(self._info['name'])
        name_editable = not (is_edit and builtin and not default_f)
        self._nameField.setEnabled(name_editable)
        self.eventManager.addWidgetEvent(self._nameField, self._onNameChanged, True)

        # ── Type  [label | combo] — mandatory ─────────────────────────
        hbox = self._row(layout, _("Type:"))
        self._typeCombo = self.factory.createComboBox(hbox, "", False)
        self._typeCombo.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
        itemColl = []
        cur_type = self._info.get('type', 'hash:ip')
        for t in self._types:
            itemColl.append(MUI.YItem(t, t == cur_type))
        if cur_type not in self._types:
            itemColl.insert(0, MUI.YItem(cur_type, True))
        self._typeCombo.addItems(itemColl)
        self._typeCombo.setEnabled(not is_edit)

        # ── Family  [label | combo] — mandatory ───────────────────────
        hbox = self._row(layout, _("Family:"))
        self._familyCombo = self.factory.createComboBox(hbox, "", False)
        self._familyCombo.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
        cur_fam = options.get('family', 'inet')
        fam_items = [MUI.YItem(f, f == cur_fam) for f in _FAMILY_CHOICES]
        self._familyCombo.addItems(fam_items)

        # ── Version  [label | field] ───────────────────────────────────
        hbox = self._row(layout, _("Version:"))
        self._versionField = self.factory.createInputField(hbox, "")
        self._versionField.setValue(self._info.get('version', ''))

        # ── Short  [label | field] ─────────────────────────────────────
        hbox = self._row(layout, _("Short:"))
        self._shortField = self.factory.createInputField(hbox, "")
        self._shortField.setValue(self._info.get('short', ''))

        # ── Description  [label | multiline] ──────────────────────────
        hbox = self._row(layout, _("Description:"))
        self._descField = self.factory.createMultiLineEdit(hbox, "")
        self._descField.setDefaultVisibleLines(2)
        self._descField.setValue(self._info.get('description', ''))

        # ── Timeout  [label | field + tooltip] ────────────────────────
        hbox = self._row(layout, _("Timeout:"))
        self._timeoutField = self.factory.createInputField(hbox, "")
        self._timeoutField.setValue(options.get('timeout', ''))
        self._timeoutField.setInputMaxLength(10)
        self._timeoutField.setHelpText(_("Timeout value in seconds"))

        # ── Hash size  [label | field + tooltip] ──────────────────────
        hbox = self._row(layout, _("Hash size:"))
        self._hashsizeField = self.factory.createInputField(hbox, "")
        self._hashsizeField.setValue(options.get('hashsize', ''))
        self._hashsizeField.setInputMaxLength(10)
        self._hashsizeField.setHelpText(_("Initial hash size, default 1024"))

        # ── Max elements  [label | field + tooltip] ────────────────────
        hbox = self._row(layout, _("Max elements:"))
        self._maxelemField = self.factory.createInputField(hbox, "")
        self._maxelemField.setValue(options.get('maxelem', ''))
        self._maxelemField.setInputMaxLength(10)
        self._maxelemField.setHelpText(_("Max number of elements, default 65536"))

        # ── Buttons ────────────────────────────────────────────────────
        align = self.factory.createRight(layout)
        bottomLine = self.factory.createHBox(align)
        cancelButton = self.factory.createIconButton(bottomLine, 'dialog-cancel', _("&Cancel"))
        self.eventManager.addWidgetEvent(cancelButton, self._onCancelButton)
        self._okButton = self.factory.createIconButton(bottomLine, 'dialog-ok', _("&Ok"))
        self.eventManager.addWidgetEvent(self._okButton, self._onOkButton)
        self.eventManager.addCancelEvent(self._onCancelEvent)

        self._okButton.setEnabled(bool(self._info.get('name', '')))

    # ------------------------------------------------------------------
    def _onNameChanged(self, obj=None):
        name = self._nameField.value().strip()
        self._okButton.setEnabled(bool(name))

    # ------------------------------------------------------------------
    def _onCancelButton(self):
        self._cancelled = True
        self.ExitLoop()

    def _onCancelEvent(self):
        self._cancelled = True

    # ------------------------------------------------------------------
    def _onOkButton(self):
        name = self._nameField.value().strip()
        if not name:
            ui.warningMsgBox({'title': _("Missing value"),
                              'text':  _("Name is mandatory")})
            return

        options = {}
        fam = self._familyCombo.value()
        if fam and fam != 'inet':
            options['family'] = fam
        timeout = self._timeoutField.value().strip()
        if timeout:
            options['timeout'] = timeout
        hashsize = self._hashsizeField.value().strip()
        if hashsize:
            options['hashsize'] = hashsize
        maxelem = self._maxelemField.value().strip()
        if maxelem:
            options['maxelem'] = maxelem

        self._result = {
            'name':        name,
            'type':        self._typeCombo.value(),
            'version':     self._versionField.value().strip(),
            'short':       self._shortField.value().strip(),
            'description': self._descField.value().strip(),
            'options':     options,
        }
        self.ExitLoop()

    # ------------------------------------------------------------------
    def run(self):
        '''Show dialog; return info dict on Ok or None on Cancel.'''
        basedialog.BaseDialog.run(self)
        if self._cancelled or self._result is None:
            return None
        return self._result
