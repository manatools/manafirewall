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
            self, _("IP Set Settings"), "", basedialog.DialogType.POPUP, 420, 280)
        self._info = (ipsetInfo or {}).copy()
        self._types = ipset_types if ipset_types else _DEFAULT_IPSET_TYPES
        self._cancelled = False
        self._result = None

    # ------------------------------------------------------------------
    def UIlayout(self, layout):
        is_edit   = bool(self._info)
        builtin   = self._info.get('builtin', False)
        default_f = self._info.get('default', True)
        options   = self._info.get('options', {})

        # ── Name ──────────────────────────────────────────────────────
        align = self.factory.createLeft(layout)
        self._nameField = self.factory.createInputField(align, _("Name"))
        if 'name' in self._info:
            self._nameField.setValue(self._info['name'])
        # builtin sets cannot be renamed
        name_editable = not (is_edit and builtin and not default_f)
        self._nameField.setEnabled(name_editable)
        self.eventManager.addWidgetEvent(self._nameField, self._onNameChanged, True)

        # ── Type ──────────────────────────────────────────────────────
        align = self.factory.createLeft(layout)
        hbox  = self.factory.createHBox(align)
        self.factory.createLabel(hbox, _("Type"))
        self._typeCombo = self.factory.createComboBox(hbox, "", False)
        itemColl = []
        cur_type = self._info.get('type', 'hash:ip')
        for t in self._types:
            it = MUI.YItem(t, t == cur_type)
            itemColl.append(it)
        if cur_type not in self._types:
            # unknown type from existing config — add it
            it = MUI.YItem(cur_type, True)
            itemColl.insert(0, it)
        self._typeCombo.addItems(itemColl)
        # type cannot be changed for existing sets
        self._typeCombo.setEnabled(not is_edit)

        # ── Version ───────────────────────────────────────────────────
        align = self.factory.createLeft(layout)
        self._versionField = self.factory.createInputField(align, _("Version"))
        self._versionField.setValue(self._info.get('version', ''))

        # ── Short ─────────────────────────────────────────────────────
        align = self.factory.createLeft(layout)
        self._shortField = self.factory.createInputField(align, _("Short"))
        self._shortField.setValue(self._info.get('short', ''))

        # ── Description ───────────────────────────────────────────────
        align = self.factory.createLeft(layout)
        self._descField = self.factory.createMultiLineEdit(align, _("Description"))
        self._descField.setDefaultVisibleLines(3)
        self._descField.setValue(self._info.get('description', ''))

        # ── Options ───────────────────────────────────────────────────
        align = self.factory.createLeft(layout)
        hbox  = self.factory.createHBox(align)

        # Family
        self.factory.createLabel(hbox, _("Family"))
        self._familyCombo = self.factory.createComboBox(hbox, "", False)
        fam_items = []
        cur_fam   = options.get('family', 'inet')
        for f in _FAMILY_CHOICES:
            fi = MUI.YItem(f, f == cur_fam)
            fam_items.append(fi)
        self._familyCombo.addItems(fam_items)

        # Timeout
        self.factory.createLabel(hbox, _("Timeout"))
        self._timeoutField = self.factory.createInputField(hbox, "")
        self._timeoutField.setValue(options.get('timeout', ''))
        self._timeoutField.setStretchable(MUI.YUIDimension.YD_HORIZ, False)

        # Hashsize
        self.factory.createLabel(hbox, _("Hash size"))
        self._hashsizeField = self.factory.createInputField(hbox, "")
        self._hashsizeField.setValue(options.get('hashsize', ''))
        self._hashsizeField.setStretchable(MUI.YUIDimension.YD_HORIZ, False)

        # Maxelem
        self.factory.createLabel(hbox, _("Max elem"))
        self._maxelemField = self.factory.createInputField(hbox, "")
        self._maxelemField.setValue(options.get('maxelem', ''))
        self._maxelemField.setStretchable(MUI.YUIDimension.YD_HORIZ, False)

        # ── Buttons ───────────────────────────────────────────────────
        align = self.factory.createRight(layout)
        bottomLine = self.factory.createHBox(align)

        cancelButton = self.factory.createPushButton(bottomLine, _("&Cancel"))
        self.eventManager.addWidgetEvent(cancelButton, self._onCancelButton)

        self._okButton = self.factory.createPushButton(bottomLine, _("&Ok"))
        self.eventManager.addWidgetEvent(self._okButton, self._onOkButton)

        self.eventManager.addCancelEvent(self._onCancelEvent)

        # Ok requires a non-empty name
        has_name = bool(self._info.get('name', ''))
        self._okButton.setEnabled(has_name)

    # ------------------------------------------------------------------
    def _onNameChanged(self):
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
