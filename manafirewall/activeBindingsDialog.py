# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:

'''
activeBindingsDialog — popup showing current active zone bindings
(network-manager connections, interfaces, sources) grouped by zone.

License: GPLv2+
Author:  Angelo Naselli <anaselli@linux.it>
@package manafirewall
'''

import gettext
import logging

import manatools.ui.basedialog as basedialog
import manatools.aui.yui as MUI

try:
    from firewall.core.fw_nm import (
        nm_is_imported,
        nm_get_connections,
        nm_get_zone_of_connection,
    )
except ImportError:
    def nm_is_imported():
        return False
    def nm_get_connections(*a, **kw):
        pass
    def nm_get_zone_of_connection(*a, **kw):
        return ''

_ = gettext.gettext
logger = logging.getLogger('manafirewall.activebindingsdialog')


class ActiveBindingsDialog(basedialog.BaseDialog):
    '''Read-only popup listing the active zone bindings at runtime.

    Grouping:
      Zone name
        └─ [NM] connection name (interface1, interface2, …)
        └─ interface  (bare / not NM-managed)
        └─ source
    '''

    def __init__(self, fw):
        basedialog.BaseDialog.__init__(
            self, _("Active Bindings"), "", basedialog.DialogType.POPUP, 500, 400)
        self._fw = fw

    def UIlayout(self, layout):
        vbox = self.factory.createVBox(layout)

        heading = self.factory.createHeading(vbox, _("Active zone bindings (runtime)"))
        heading.setAutoWrap()
        self.factory.createVSpacing(vbox, 0.3)

        self._tree = self.factory.createTree(vbox, "")
        self._tree.setStretchable(MUI.YUIDimension.YD_VERT, True)
        self._tree.setStretchable(MUI.YUIDimension.YD_HORIZ, True)

        self._fillTree()

        align = self.factory.createRight(layout)
        closeBtn = self.factory.createPushButton(align, _("&Close"))
        self.eventManager.addWidgetEvent(closeBtn, self._onClose)
        self.eventManager.addCancelEvent(self._onClose)
        self.dialog.setDefaultButton(closeBtn)

    def _fillTree(self):
        '''Populate the tree with the same grouping as the original active-bindings
        left panel: top-level nodes are Connections / Interfaces / Sources, each
        child shows the zone it belongs to (mirroring update_active_bindings()).'''
        active_zones = {}
        default_zone = ''
        try:
            active_zones = self._fw.getActiveZones()
            default_zone = self._fw.getDefaultZone()
        except Exception as exc:
            logger.warning("Could not retrieve active zones: %s", exc)

        # --- collect NM connections data -----------------------------------------
        _connections      = {}   # iface_path -> conn_id
        _connections_name = {}   # conn_id    -> display_name
        nm_connections_data = {} # conn_id    -> [zone, [ifaces], display_name]

        if nm_is_imported():
            try:
                nm_get_connections(_connections, _connections_name)
            except Exception:
                pass
            for zone_name, data in active_zones.items():
                for iface in data.get('interfaces', []):
                    if iface in _connections:
                        conn_id = _connections[iface]
                        if conn_id not in nm_connections_data:
                            try:
                                nm_zone = nm_get_zone_of_connection(conn_id)
                            except Exception:
                                nm_zone = ''
                            nm_connections_data[conn_id] = [
                                nm_zone if nm_zone else zone_name,
                                [],
                                _connections_name.get(conn_id, conn_id),
                            ]
                        nm_connections_data[conn_id][1].append(iface)

        nm_ifaces = {iface for _, ifaces_l, _ in nm_connections_data.values()
                     for iface in ifaces_l}

        # --- bare interfaces and sources -----------------------------------------
        bare_interfaces = {}  # iface  -> zone
        sources         = {}  # source -> zone
        for zone_name, data in active_zones.items():
            for iface in data.get('interfaces', []):
                if iface not in nm_ifaces:
                    bare_interfaces[iface] = zone_name
            for source in data.get('sources', []):
                sources[source] = zone_name

        # --- build tree: Connections / Interfaces / Sources -----------------------
        itemColl = []

        conn_parent = MUI.YTreeItem(label=_("Connections"), is_open=True)
        for conn_id in sorted(nm_connections_data):
            z, ifaces, name = nm_connections_data[conn_id]
            zone_str = z if z else default_zone
            label = '{} ({})\n{}: {}'.format(
                name, ', '.join(sorted(ifaces)), _('Zone'), zone_str)
            MUI.YTreeItem(parent=conn_parent, label=label)
        itemColl.append(conn_parent)

        iface_parent = MUI.YTreeItem(label=_("Interfaces"), is_open=True)
        for iface in sorted(bare_interfaces):
            label = '{}\n{}: {}'.format(iface, _('Zone'), bare_interfaces[iface])
            MUI.YTreeItem(parent=iface_parent, label=label)
        itemColl.append(iface_parent)

        src_parent = MUI.YTreeItem(label=_("Sources"), is_open=True)
        for source in sorted(sources):
            label = '{}\n{}: {}'.format(source, _('Zone'), sources[source])
            MUI.YTreeItem(parent=src_parent, label=label)
        itemColl.append(src_parent)

        self._tree.addItems(itemColl)

    def _onClose(self):
        self.ExitLoop()

    def run(self):
        basedialog.BaseDialog.run(self)
