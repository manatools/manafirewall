#  dialog.py
# -*- coding: utf-8 -*-

'''
Python manafirewall.dialog contains main manafirewall window

License: GPLv2+

Author:  Angelo Naselli <anaselli@linux.it>

@package manafirewall
'''

import logging
import logging.handlers
import os.path

import manatools.ui.common as common
import manatools.ui.basedialog as basedialog
import manatools.services as mnservices
import manatools.ui.helpdialog as helpdialog
import manatools.config as configuration
import manatools.aui.yui as MUI

from dbus.exceptions import DBusException

from firewall import config
from firewall import client
from firewall import functions
from firewall.core.base import DEFAULT_ZONE_TARGET, REJECT_TYPES, \
                               SOURCE_IPSET_TYPES
from firewall.core.ipset import IPSET_MAXNAMELEN
from firewall.core.helper import HELPER_MAXNAMELEN
from firewall.core.io.zone import Zone
from firewall.core.io.service import Service
from firewall.core.io.icmptype import IcmpType
from firewall.core.io.ipset import IPSet
from firewall.core.io.helper import Helper
from firewall.core import rich
from firewall.core.fw_nm import nm_is_imported, nm_get_dbus_interface, \
                                nm_get_connections, nm_get_zone_of_connection, \
                                nm_set_zone_of_connection
from firewall import errors
from firewall.errors import FirewallError
import gettext
import time
import threading
#we need a glib.MainLoop in TUI :(
from gi.repository import GLib
from inspect import ismethod

from manafirewall.version import __version__ as VERSION
from manafirewall.version import __project_name__ as PROJECT

from queue import SimpleQueue, Empty

import manafirewall.zoneBaseDialog as zoneBaseDialog
import manafirewall.serviceBaseDialog as serviceBaseDialog
import manafirewall.changeZoneConnectionDialog as changeZoneConnectionDialog
import manafirewall.portDialog as portDialog
import manafirewall.forwardDialog as forwardDialog
import manafirewall.protocolDialog as protocolDialog
import manafirewall.optionDialog as optionDialog
import manafirewall.helpinfo as helpinfo
import manafirewall.moduleDialog as moduleDialog
import manafirewall.activeBindingsDialog as activeBindingsDialog

logger = logging.getLogger('manafirewall.dialog')
_ = gettext.gettext

def TimeFunction(func):
    """
    This decorator prints execution time
    """
    def newFunc(*args, **kwargs):
        t_start = time.monotonic()
        rc = func(*args, **kwargs)
        t_end = time.monotonic()
        name = func.__name__
        t_diff = t_end - t_start
        if t_diff >= 0.001:
          logger.debug("%s took %.3f sec", name, t_diff)
        return rc

    newFunc.__name__ = func.__name__
    newFunc.__doc__ = func.__doc__
    newFunc.__dict__.update(func.__dict__)
    return newFunc


class ManaWallDialog(basedialog.BaseDialog):
  '''
  manafirewall main dialog
  '''
  def __init__(self):
    #gettext.install('manafirewall', localedir='/usr/share/locale', names=('ngettext',))
    # set icon (if missing into python-manatools)
    self.__name = "manafirewall"
    self.log_enabled = False
    self.log_directory = None
    self.level_debug = False

    MUI.YUI.app().setApplicationIcon("manafirewall")
    # Wayland/Plasma: tell the compositor which .desktop file represents this
    # window so the task manager shows the correct icon and application name.
    MUI.YUI.app().desktop_file_name = "org.mageia.manafirewall"

    basedialog.BaseDialog.__init__(self, _("Manatools - firewalld configurator"), "manafirewall", basedialog.DialogType.MAIN, 640, 480)
    self._application_name = _("{} - ManaTools firewalld configurator").format(PROJECT)

    # Publish application metadata to the backend so AboutDialog can read
    # it without the deprecated info-dict parameter.
    try:
      _app = MUI.YUI.app()
      _app.application_name = self._application_name
      _app.version = VERSION
      _app.license = 'GPLv2+'
      _app.authors = 'Angelo Naselli &lt;anaselli@linux.it&gt;'
      _app.description = _("{} is a graphical configuration tool for firewalld.").format(PROJECT)
      _app.credits = _("Credits 2019-2026 Angelo Naselli")
      _app.logo = 'manafirewall'
      _app.information = ""
    except Exception:
      pass

    # most used text
    self.connected_label = _("Connection to firewalld established.")
    self.trying_to_connect_label = \
        _("Trying to connect to firewalld, waiting...")
    self.failed_to_connect_label = \
        _("Failed to connect to firewalld. Please make sure that the "
          "service has been started correctly and try again.")
    self.changes_applied_label = _("Changes applied.")
    self.used_by_label = _("Used by network connection '%s'")
    self.default_zone_used_by_label = _("Default zone used by network "
                                        "connection '%s'")
    self.enabled = _("enabled")
    self.disabled = _("disabled")
    self.connection_lost = False
    self.log_denied = ""
    self.automatic_helpers = ""
    self.active_zones = { }
    self.runtime_view = True
    self.buttons = None
    self.replacePointWidgetsAndCallbacks = []
    self.leftReplacePointWidgetsAndCallbacks = []
    self._reloading = False
    self._reload_pending_zones = []
    self._reload_pending_services = []
    # UX state tracking
    self._currentCategory = 'zones'    # 'zones', 'services', 'ipsets'
    self._currentItem     = None       # selected zone/service/ipset name
    self._currentRightTab = 'summary'  # selected right tab key
    self._nm_connections_data = {}     # NM connection data cache
    self.activeBindingsTree = None     # current left tree/list widget
    self._leftList = None              # current left list widget (services/ipsets)

    self.config = configuration.AppConfig(self.__name)

    # settings from configuration file first
    self._configFileRead()

    if self.log_enabled:
      if self.log_directory:
        log_filename = os.path.join(self.log_directory, "manafirewall.log")
        if self.level_debug:
          self._logger_setup(log_filename, loglvl=logging.DEBUG)
        else:
          self._logger_setup(log_filename)
        print("Logging into %s, debug mode is %s"%(self.log_directory, ("enabled" if self.level_debug else "disabled")))
        logger.info("%s started"%(self.__name))
    else:
      print("Logging disabled")

    self.fwEventQueue = SimpleQueue()

    if MUI.YUI.app().isTextMode():
      self.glib_loop = GLib.MainLoop()
      self.glib_thread = threading.Thread(target=self.glib_mainloop, args=(self.glib_loop,))
      self.glib_thread.start()


  def _logger_setup(self,
                    file_name='manafirewall.log',
                    logroot='manafirewall',
                    logfmt='%(asctime)s [%(name)s]{%(filename)s:%(lineno)d}(%(levelname)s) %(message)s',
                    loglvl=logging.INFO):
    """Setup Python logging."""
    maxbytes = 10*1024*1024
    fmt = logging.Formatter(logfmt)
    handler = logging.handlers.RotatingFileHandler(
              file_name, maxBytes=maxbytes, backupCount=5)
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    logger.setLevel(loglvl)
    logger.propagate = False


  def _configFileRead(self) :
    '''
    reads the configuration file and sets application data
    '''

    # System settings
    if self.config.systemSettings :
      pass

    # User preferences overriding
    user_settings = {}
    if self.config.userPreferences:
      if 'settings' in self.config.userPreferences.keys() :
        if self.config.userPreferences['settings'] is None:
            self.config.userPreferences['settings'] = {}
        user_settings = self.config.userPreferences['settings']

        #### Logging
        if 'log' in user_settings.keys():
          log = user_settings['log']
          if 'enabled' in log.keys() :
            self.log_enabled = log['enabled']
          if self.log_enabled:
            if 'directory' in log.keys() :
                self.log_directory = log['directory']
            if 'level_debug' in log.keys() :
                self.level_debug = log['level_debug']

    # metadata settings is needed adding it to update old configuration files
    if not 'settings' in self.config.userPreferences.keys() :
      self.config.userPreferences['settings'] = {}


  def glib_mainloop(self, loop):
    '''
    thread function for glib main loop
    '''
    loop.run()

  def UIlayout(self, layout):
    '''
    layout implementation called in base class to setup UI
    '''

    # TEST self.eventManager.addTimeOutEvent(self.onTimeOutEvent)

    sendObjOnEvent=True
    menu_line = self.factory.createHBox(layout)
    ### BEGIN Menus #########################
    if (hasattr(self.factory, 'createMenuBar') and ismethod(getattr(self.factory, 'createMenuBar'))):
      self.menubar = self.factory.createMenuBar(menu_line)

      # building File menu
      mItem = self.menubar.addMenu(_("&File"))
      self.fileMenu = {
          'menu_name' : mItem,
          'quit'      : self.menubar.addItem(mItem, _("&Quit"), "application-exit"),
      }
      self.eventManager.addMenuEvent(self.fileMenu['quit'], self.onQuitEvent, sendObjOnEvent)

      # building Options menu
      mItem = self.menubar.addMenu(_("&Options"))
      self.optionsMenu = {
          'menu_name'  : mItem,
          'runtime_to_permanent': self.menubar.addItem(mItem, _("Runtime To Permanent"), 'document-save'),
          'reload' : self.menubar.addItem(mItem, _("&Reload Firewalld"), 'view-refresh'),
          'sep0'     : mItem.addSeparator(),
          'active_bindings': self.menubar.addItem(mItem, _("Active &Bindings…"), 'network-wired'),
          'sep1'     : mItem.addSeparator(),
          'settings' : self.menubar.addItem(mItem, _("&Settings"), 'preferences-system'),
      }
      self.eventManager.addMenuEvent(self.optionsMenu['runtime_to_permanent'], self.onRuntimeToPermanent)
      self.eventManager.addMenuEvent(self.optionsMenu['reload'], self.onReloadFirewalld)
      self.eventManager.addMenuEvent(self.optionsMenu['active_bindings'], self.onActiveBindings)
      self.eventManager.addMenuEvent(self.optionsMenu['settings'], self.onOptionSettings)

      # building Help menu
      mItem = self.menubar.addMenu(_("&Help"))
      self.helpMenu = {
          'menu_name': mItem,
          'help'     : self.menubar.addItem(mItem, _("&Manual"), 'help-contents'),
          'sep0'     : mItem.addSeparator(),
          'about'    : self.menubar.addItem(mItem, _("&About"), 'manafirewall'),
      }
      self.eventManager.addMenuEvent(self.helpMenu['help'], self.onHelp)
      self.eventManager.addMenuEvent(self.helpMenu['about'], self.onAbout)

      #self.menubar.resolveShortcutConflicts()
      self.menubar.rebuildMenus()
    else:
     raise Exception("Error: no menu support for this UI backend")
    ### END Menus #########################


    # ─────────────────────────────────────────────────────────────────────────
    # Mode bar: Runtime / Permanent  +  Reload / Runtime→Permanent buttons
    # ─────────────────────────────────────────────────────────────────────────
    modeBarAlign = self.factory.createLeft(layout)
    hbox_mode = self.factory.createHBox(modeBarAlign)

    self._runtimeRadio   = None
    self._permanentRadio = None
    if (hasattr(self.factory, 'createRadioButtonGroup') and
        callable(getattr(self.factory, 'createRadioButtonGroup'))):
      rbGroup = self.factory.createRadioButtonGroup(hbox_mode)
      self._runtimeRadio   = self.factory.createRadioButton(rbGroup, _("&Runtime"),   True)
      self._permanentRadio = self.factory.createRadioButton(rbGroup, _("&Permanent"), False)
      self._runtimeRadio.setNotify(True)
      self._permanentRadio.setNotify(True)
      self.eventManager.addWidgetEvent(self._runtimeRadio,   self.onModeChanged)
      self.eventManager.addWidgetEvent(self._permanentRadio, self.onModeChanged)
    else:
      # Fallback: ComboBox for backends that lack radio-button group support
      self.views = {
          'runtime'   : {'title': _("Runtime"),   'item': None},
          'permanent' : {'title': _("Permanent"), 'item': None},
      }
      self.currentViewCombobox = self.factory.createComboBox(hbox_mode, _("Configuration"))
      itemColl = []
      for k in ['runtime', 'permanent']:
        it = MUI.YItem(self.views[k]['title'], k == 'runtime')
        self.views[k]['item'] = it
        itemColl.append(it)
      self.currentViewCombobox.addItems(itemColl)
      self.currentViewCombobox.setNotify(True)
      self.eventManager.addWidgetEvent(self.currentViewCombobox, self.onModeChanged)

    self.factory.createHSpacing(hbox_mode, 1)
    self._reloadButton = self.factory.createIconButton(hbox_mode, 'view-refresh',  _("Re&load"))
    self._rtpButton    = self.factory.createIconButton(hbox_mode, 'document-save', _("Runtime→&Permanent"))
    self.eventManager.addWidgetEvent(self._reloadButton, self.onReloadFirewalld)
    self.eventManager.addWidgetEvent(self._rtpButton,    self.onRuntimeToPermanent)

    # ─────────────────────────────────────────────────────────────────────────
    # Main area: left (categories) + right (detail/configuration)
    # Use YPaned (QSplitter) so the user can drag the divider at runtime.
    # ─────────────────────────────────────────────────────────────────────────
    mainArea = self.factory.createPaned(layout, MUI.YUIDimension.YD_HORIZ)
    mainArea.setStretchable(MUI.YUIDimension.YD_VERT, True)

    # ── Left pane (30%) ──────────────────────────────────────────────────────
    col1 = self.factory.createVBox(mainArea)
    col1.setWeight(MUI.YUIDimension.YD_HORIZ, 30)

    # Left DumbTab: Zones | Services | IP Sets
    self.leftTab = self.factory.createDumbTab(col1)
    self._zonesTabItem    = MUI.YItem(_("Zones"),    True)
    self._servicesTabItem = MUI.YItem(_("Services"), False)
    self._ipsetsTabItem   = MUI.YItem(_("IP Sets"),  False)
    for ti in [self._zonesTabItem, self._servicesTabItem, self._ipsetsTabItem]:
      self.leftTab.addItem(ti)
    self.leftTab.setNotify(True)
    self.eventManager.addWidgetEvent(self.leftTab, self.onLeftTabChanged)

    # Left content replace point (lives inside DumbTab).
    # IMPORTANT: must have an initial child + showChild() called here so that the
    # Qt parent-context is valid before _fillLeft*() is first invoked; otherwise
    # subsequent factory.createXxx(leftReplacePoint) calls open a new top-level
    # popup instead of inserting into the existing layout.
    self.leftReplacePoint = self.factory.createReplacePoint(self.leftTab)
    self.leftReplacePoint.setStretchable(MUI.YUIDimension.YD_VERT, True)
    self.leftReplacePoint.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
    self.factory.createVStretch(self.leftReplacePoint)   # initial placeholder child
    self.leftReplacePoint.showChild()

    # Left action buttons (below DumbTab)
    btnAlign = self.factory.createLeft(col1)
    hbox_btns = self.factory.createHBox(btnAlign)
    self._leftAddButton          = self.factory.createIconButton(hbox_btns, 'list-add',    _("&Add"))
    self._leftEditButton         = self.factory.createPushButton(hbox_btns, _("&Edit"))
    self._leftRemoveButton       = self.factory.createIconButton(hbox_btns, 'list-remove', _("&Remove"))
    self._leftLoadDefaultsButton = self.factory.createPushButton(hbox_btns, _("Load &Defaults"))
    self.eventManager.addWidgetEvent(self._leftAddButton,          self.onLeftAddButton)
    self.eventManager.addWidgetEvent(self._leftEditButton,         self.onLeftEditButton)
    self.eventManager.addWidgetEvent(self._leftRemoveButton,       self.onLeftRemoveButton)
    self.eventManager.addWidgetEvent(self._leftLoadDefaultsButton, self.onLeftLoadDefaultsButton)

    # Change Zone button (enabled only when an NM connection child is selected)
    self.changeBindingsButton = self.factory.createPushButton(col1, _("Change &Zone"))
    self.changeBindingsButton.setEnabled(False)
    self.eventManager.addWidgetEvent(self.changeBindingsButton, self.onChangeBinding, sendObjOnEvent)
    self._connectionsTreeItem = None   # kept for onChangeBinding compat
    self._interfacesTreeItem  = None
    self._sourcesTreeItem     = None

    # ── Right pane (70%) ─────────────────────────────────────────────────────
    col2 = self.factory.createVBox(mainArea)
    col2.setWeight(MUI.YUIDimension.YD_HORIZ, 70)

    # Right DumbTab: tabs rebuilt per category — start empty, _rebuildRightTabs() fills it.
    self.rightTab = self.factory.createDumbTab(col2)
    # Pre-create all possible tab items (only the relevant ones are added at runtime)
    self._summaryTabItem   = MUI.YItem(_("Summary"),      False)
    self._svcTabItem       = MUI.YItem(_("Services"),     False)
    self._portsTabItem     = MUI.YItem(_("Ports"),        False)
    self._protosTabItem    = MUI.YItem(_("Protocols"),    False)
    self._srcPortsTabItem  = MUI.YItem(_("Source Ports"), False)
    self._masqTabItem      = MUI.YItem(_("Masquerade"),   False)
    self._fwdTabItem       = MUI.YItem(_("Forwarding"),   False)
    self._icmpTabItem      = MUI.YItem(_("ICMP Filter"),  False)
    self._modulesTabItem   = MUI.YItem(_("Modules"),      False)
    self._destTabItem      = MUI.YItem(_("Destinations"), False)
    self._entriesTabItem   = MUI.YItem(_("Entries"),      False)
    self._ifacesTabItem    = MUI.YItem(_("Interfaces"),   False)
    self._sourcesTabItem   = MUI.YItem(_("Sources"),      False)
    self._richRulesTabItem = MUI.YItem(_("Rich Rules"),   False)
    self.rightTab.setNotify(True)
    self.eventManager.addWidgetEvent(self.rightTab, self.onRightTabChanged)

    # Right pane replace point (lives inside rightTab).
    # Same constraint as leftReplacePoint: needs an initial child + showChild() so
    # that the Qt parent-context is valid before _refreshRightPane() first runs.
    self.replacePoint = self.factory.createReplacePoint(self.rightTab)
    self.replacePoint.setStretchable(MUI.YUIDimension.YD_VERT, True)
    self.replacePoint.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
    self.factory.createVStretch(self.replacePoint)       # initial placeholder child
    self.replacePoint.showChild()

    # ─────────────────────────────────────────────────────────────────────────
    # Status bar
    # ─────────────────────────────────────────────────────────────────────────
    align = self.factory.createLeft(layout)
    statusLine = self.factory.createHBox(align)
    self.statusLabel = self.factory.createLabel(statusLine, self.failed_to_connect_label)
    align = self.factory.createLeft(layout)
    statusLine = self.factory.createHBox(align)
    self.defaultZoneLabel      = self.factory.createLabel(statusLine, _("Default Zone: {}").format("--------"))
    self.logDeniedLabel        = self.factory.createLabel(statusLine, _("  Log Denied: {}").format("--------"))
    self.panicLabel            = self.factory.createLabel(statusLine, _("  Panic Mode: {}").format("--------"))
    self.automaticHelpersLabel = self.factory.createLabel(statusLine, _("  Automatic Helpers: {}").format("--------"))

    # ─────────────────────────────────────────────────────────────────────────
    # Bottom button bar
    # ─────────────────────────────────────────────────────────────────────────
    align = self.factory.createRight(layout)
    bottomLine = self.factory.createHBox(align)
    aboutButton = self.factory.createPushButton(bottomLine, _("&About"))
    self.eventManager.addWidgetEvent(aboutButton, self.onAbout)
    quitButton = self.factory.createPushButton(bottomLine, _("&Quit"))
    self.eventManager.addWidgetEvent(quitButton, self.onQuitEvent, sendObjOnEvent)

    # Let's test a cancel event
    self.eventManager.addCancelEvent(self.onCancelEvent)
    # Let's check external events every 100 msec
    self.timeout = 100
    #self.eventManager.addTimeOutEvent(self.onTimeOutEvent)
    # End Dialof layout

    self.dialog.setEnabled(False)
    self.initFWClient()

  def _serviceSettings(self):
    '''
    returns current service settings
    '''
    selected_service = self._currentItem
    if not selected_service:
      return None
    if self.runtime_view:
      try:
        return self.fw.getServiceSettings(selected_service)
      except Exception:
        return None
    else:
      try:
        service = self.fw.config().getServiceByName(selected_service)
        return service.getSettings()
      except Exception:
        return None

  def _zoneSettings(self):
    '''
    returns current zone settings
    '''
    selected_zone = self._currentItem
    if not selected_zone:
      return None
    if self.runtime_view:
      try:
        return self.fw.getZoneSettings(selected_zone)
      except Exception:
        return None
    else:
      try:
        zone = self.fw.config().getZoneByName(selected_zone)
        return zone.getSettings()
      except Exception:
        return None

  def _AddEditRemoveButtons(self, container):
    '''
    adds Add, Edit and Remove buttons on the left of the given container
    returns a widget dictionary which keys are 'add', 'edit' and 'remove'
    '''
    buttons = None
    if container.widgetClass() in ("YHBox", "YVBox"):
      buttons = { 'add' : None, 'edit': None, 'remove': None }
      align = self.factory.createLeft(container)
      hbox = self.factory.createHBox(align)
      buttons['add']    = self.factory.createIconButton(hbox, 'list-add', _("&Add"))
      #self.factory.createPushButton(hbox, _("A&dd"))
      buttons['edit']   = self.factory.createPushButton(hbox, _("&Edit"))
      buttons['remove'] = self.factory.createIconButton(hbox, 'list-remove', _("&Remove"))
      #self.factory.createPushButton(hbox, _("&Remove"))
      

    return buttons

  def _createsingleStrItem(self, values):
    '''
    create a YTableItem with string values
    '''
    item = MUI.YTableItem()
    for v in values:
      item.addCell(str(v))    
    return item

  def _createSingleCBItem(self, checked, strValue):
    '''
    create a YTableItem with checkbox state and string value
    '''
    item = MUI.YTableItem()
    item.addCell(bool(checked))
    item.addCell(str(strValue))
    return item

  def _replacePointICMP(self):
    if len(self.replacePointWidgetsAndCallbacks) > 0:
      logger.error("Error there are still widget events for ReplacePoint")
      return
    if self.replacePoint.hasChildren():
      logger.error("Error there are still widgets into ReplacePoint")
      return
    hbox = self.factory.createHBox(self.replacePoint)
    table_header = MUI.YTableHeader()
    table_header.addColumn("", True)
    table_header.addColumn(_('ICMP Filter'), False)
    self.icmpFilterList = self.factory.createTable(hbox, table_header)
    self.icmpFilterInversionCheck = self.factory.createCheckBox(hbox, _("Selected are accepted"), False)
    self.icmpFilterInversionCheck.setNotify(True)
    self._fillRPICMPFilter()
    self.eventManager.addWidgetEvent(self.icmpFilterList, self.onRPICMPFilterChecked)
    self.replacePointWidgetsAndCallbacks.append({'widget': self.icmpFilterList, 'action': self.onRPICMPFilterChecked})
    self.eventManager.addWidgetEvent(self.icmpFilterInversionCheck, self.OnICMPFilterInversionChecked)
    self.replacePointWidgetsAndCallbacks.append({'widget': self.icmpFilterInversionCheck, 'action': self.OnICMPFilterInversionChecked})

  def _fillRPICMPFilter(self):
    '''
    fill current ICMP into replace point
    '''
    settings = self._zoneSettings()
    if settings:
      configured_icmp = settings.getIcmpBlocks()
      icmp_block_inversion = settings.getIcmpBlockInversion()

      icmp_types = None
      if self.runtime_view:
        icmp_types = self.fw.listIcmpTypes()
      else:
        icmp_types = self.fw.config().getIcmpTypeNames()

      current_icmp = ""
      current = self.icmpFilterList.selectedItem()
      current_icmp = current.cell(0).label() if current else ""
      v = []
      for icmp in icmp_types:
        item = self._createSingleCBItem(icmp in configured_icmp, icmp)
        item.setSelected(icmp == current_icmp)
        v.append(item)

      # cleanup old changed items since we are removing all of them      
      self.icmpFilterList.deleteAllItems()
      self.icmpFilterList.addItems(v)

      self.icmpFilterInversionCheck.setNotify(False)
      self.icmpFilterInversionCheck.setValue(MUI.YCheckBoxState.YCheckBox_on if icmp_block_inversion else MUI.YCheckBoxState.YCheckBox_off)
      self.icmpFilterInversionCheck.setNotify(True)


  def _replacePointMasquerade(self):
    if len(self.replacePointWidgetsAndCallbacks) > 0:
      logger.error("Error there are still widget events for ReplacePoint")
      return
    if self.replacePoint.hasChildren():
      logger.error("Error there are still widgets into ReplacePoint")
      return
    vbox = self.factory.createVBox(self.replacePoint)
    align = self.factory.createLeft(vbox)
    self.masquerade = self.factory.createCheckBox(align, _("Masquerade zone"), False)
    self.masquerade.setNotify(True)
    self.eventManager.addWidgetEvent(self.masquerade, self.onZoneMasquerade)
    self.replacePointWidgetsAndCallbacks.append({'widget': self.masquerade, 'action': self.onZoneMasquerade})
    self._fillRPMasquerade()

  def _fillRPMasquerade(self):
    '''
    sets masquerade value
    '''
    settings = self._zoneSettings()
    masquerade = settings.getMasquerade()
    self.masquerade.setNotify(False)
    self.masquerade.setValue(MUI.YCheckBoxState.YCheckBox_on if masquerade else MUI.YCheckBoxState.YCheckBox_off)
    self.masquerade.setNotify(True)

  def _replacePointProtocols(self, context):
    if len(self.replacePointWidgetsAndCallbacks) > 0:
      logger.error("Error there are still widget events for ReplacePoint")
      return
    if self.replacePoint.hasChildren():
      logger.error("Error there are still widgets into ReplacePoint")
      return
    vbox = self.factory.createVBox(self.replacePoint)
    port_header = MUI.YTableHeader()
    port_header.addColumn(_('Protocol'))
    self.protocolList = self.factory.createTable(vbox, port_header, False)
    self.buttons = self._AddEditRemoveButtons(vbox)
    for op in self.buttons.keys():
      self.eventManager.addWidgetEvent(self.buttons[op], self.onPortButtonsPressed, True)
      self.replacePointWidgetsAndCallbacks.append({'widget': self.buttons[op], 'action': self.onPortButtonsPressed})
    self._fillRPProtocols(context)

  def _fillRPProtocols(self, context):
    '''
    fill current protocols into replace point
    '''
    protocols = None
    if context == 'zone_protocols':
      settings = self._zoneSettings()
      if settings:
        protocols = settings.getProtocols()
    elif context == 'service_protocols':
      settings = self._serviceSettings()
      if settings:
        protocols = settings.getProtocols()

    current_protocol = protocols[0] if protocols else ""
    current = self.protocolList.selectedItem()
    if current:
      current_protocol = current.label()

    v = []
    for protocol in protocols:
      item = MUI.YTableItem()
      item.setSelected(protocol == current_protocol)
      item.addCell(protocol)
      v.append(item)

    self.protocolList.deleteAllItems()
    self.protocolList.addItems(v)

  def _replacePointPort(self, context):
    if len(self.replacePointWidgetsAndCallbacks) > 0:
      logger.error("Error there are still widget events for ReplacePoint")
      return
    if self.replacePoint.hasChildren():
      logger.error("Error there are still widgets into ReplacePoint")
      return
    vbox = self.factory.createVBox(self.replacePoint)
    port_header = MUI.YTableHeader()
    port_header.addColumn(_('Port'))
    port_header.addColumn(_('Protocol'))
    self.portList = self.factory.createTable(vbox, port_header, False)
    self.buttons = self._AddEditRemoveButtons(vbox)
    for op in self.buttons.keys():
      self.eventManager.addWidgetEvent(self.buttons[op], self.onPortButtonsPressed, True)
      self.replacePointWidgetsAndCallbacks.append({'widget': self.buttons[op], 'action': self.onPortButtonsPressed})
    self._fillRPPort(context)

  def _fillRPPort(self, context):
    '''
    fill current ports into replace point
    '''
    ports = []
    if context == 'zone_ports':
      settings = self._zoneSettings()
      if settings:
        ports = settings.getPorts()
    elif context == 'zone_sourceports':
      settings = self._zoneSettings()
      if settings:
        ports = settings.getSourcePorts()
    elif context == 'service_ports':
      settings = self._serviceSettings()
      if settings:
        ports = settings.getPorts()
    elif context == 'service_sourceports':
      settings = self._serviceSettings()
      if settings:
        ports = settings.getSourcePorts()

    current_port = ports[0] if ports else ""
    current = self.portList.selectedItem()
    #### TODO try to select the same

    v = []
    for port in ports:
      item = self._createsingleStrItem(port)
      #item.setSelected(service == current_service)
      v.append(item)

    self.portList.deleteAllItems()
    self.portList.addItems(v)

  def _replacePointServices(self):
    if len(self.replacePointWidgetsAndCallbacks) > 0:
      logger.error("Error there are still widget events for ReplacePoint")
      return
    if self.replacePoint.hasChildren():
      logger.error("Error there are still widgets into ReplacePoint")
      return
    vbox = self.factory.createVBox(self.replacePoint)
    services_header = MUI.YTableHeader()
    services_header.addColumn("", True)
    services_header.addColumn(_('Service'), False)
    self.serviceList = self.factory.createTable(vbox, services_header)
    self._fillRPServices()
    self.eventManager.addWidgetEvent(self.serviceList, self.onRPServiceChecked)
    self.replacePointWidgetsAndCallbacks.append({'widget': self.serviceList, 'action': self.onRPServiceChecked})

  def _fillRPServices(self):
    '''
    fill current services into replace point
    '''
    settings = self._zoneSettings()
    if settings:
      configured_services = settings.getServices()

      services = None
      if self.runtime_view:
        services = self.fw.listServices()
      else:
        services = self.fw.config().getServiceNames()

      current_service = ""
      current = self.serviceList.selectedItem()
      current_service = current.cell(0).label() if current else ""
      v = []
      for service in services:
        item = self._createSingleCBItem(service in configured_services, service)
        item.setSelected(service == current_service)
        v.append(item)

      # cleanup old changed items since we are removing all of them      
      self.serviceList.deleteAllItems()
      self.serviceList.addItems(v)

  def _replacePointForwardPorts(self):
    if len(self.replacePointWidgetsAndCallbacks) > 0:
      logger.error("Error there are still widget events for ReplacePoint")
      return
    if self.replacePoint.hasChildren():
      logger.error("Error there are still widgets into ReplacePoint")
      return
    vbox = self.factory.createVBox(self.replacePoint)
    port_header = MUI.YTableHeader()
    port_header.addColumn(_('Port'))
    port_header.addColumn(_('Protocol'))
    port_header.addColumn(_("To Port"))
    port_header.addColumn(_("To Address"))
    self.portForwardList = self.factory.createTable(vbox, port_header, False)
    self.buttons = self._AddEditRemoveButtons(vbox)
    for op in self.buttons.keys():
      self.eventManager.addWidgetEvent(self.buttons[op], self.onPortButtonsPressed, True)
      self.replacePointWidgetsAndCallbacks.append({'widget': self.buttons[op], 'action': self.onPortButtonsPressed})
    self._fillRPForwardPorts()

  def _fillRPForwardPorts(self):
    '''
    fill current forwarding ports into replace point
    '''
    settings = self._zoneSettings()
    if settings:
      ports = settings.getForwardPorts()
      current_port = ""
      current = self.portForwardList.selectedItem()
      #### TODO try to select the same

      v = []
      for port in ports:
        item = MUI.YTableItem()
        item.addCell(port)
        #item.setSelected(service == current_service)
        v.append(item)

      self.portForwardList.deleteAllItems()
      self.portForwardList.addItems(v)

  def onRPICMPFilterChecked(self, widgetEvent):
    '''
    works on enabling/disabling icmp filter for zone
    '''
    if (widgetEvent.reason() == MUI.YEventReason.ValueChanged) :
      item = self.icmpFilterList.changedItem()
      if item:
        cb_column = 0
        label_column = 1
        selected_zone = self._currentItem
        if selected_zone:
          name = item.cell(label_column).label()
          if self.runtime_view:
            if item.checked(cb_column):
              self.fw.addIcmpBlock(selected_zone, name)
            else:
              self.fw.removeIcmpBlock(selected_zone, name)
          else:
            zone = self.fw.config().getZoneByName(selected_zone)
            if item.checked(cb_column):
              zone.addIcmpBlock(name)
            else:
              zone.removeIcmpBlock(name)

  def OnICMPFilterInversionChecked(self):
    '''
    manages ICMP Block Inversion checked (Accept if checked)
    '''
    selected_zone = self._currentItem
    if selected_zone:
      if self.runtime_view:
        if self.icmpFilterInversionCheck.isChecked():
          if not self.fw.queryIcmpBlockInversion(selected_zone):
            self.fw.addIcmpBlockInversion(selected_zone)
        else:
          if self.fw.queryIcmpBlockInversion(selected_zone):
            self.fw.removeIcmpBlockInversion(selected_zone)
      else:
        zone = self.fw.config().getZoneByName(selected_zone)
        zone.setIcmpBlockInversion(self.icmpFilterInversionCheck.isChecked())

  def onRPServiceChecked(self, widgetEvent):
    '''
    works on enabling/disabling service for zone
    '''
    if (widgetEvent.reason() == MUI.YEventReason.ValueChanged) :
      item = self.serviceList.changedItem()
      if item:
        cb_column = 0
        label_column = 1
        selected_zone = self._currentItem
        if selected_zone:
          service_name = item.cell(label_column).label()
          if self.runtime_view:
            if item.checked(cb_column):
              self.fw.addService(selected_zone, service_name)
            else:
              self.fw.removeService(selected_zone, service_name)
          else:
            zone = self.fw.config().getZoneByName(selected_zone)
            if item.checked(cb_column):
              zone.addService(service_name)
            else:
              zone.removeService(service_name)

  def _del_edit_port(self):
    '''
    remove the selected port
    '''
    selected_zone = self._currentItem
    if selected_zone:
      selected_portitem = self.portList.selectedItem()
      if selected_portitem:
        port_range = selected_portitem.cell(0).label()
        protocol   = selected_portitem.cell(1).label()

        if self.runtime_view:
          self.fw.removePort(selected_zone, port_range, protocol)
        else:
          zone = self.fw.config().getZoneByName(selected_zone)
          zone.removePort(port_range, protocol)

  def _add_edit_port(self, add):
    '''
    add or edit port (add is True for new port)
    '''
    selected_zone = self._currentItem
    if selected_zone:

      oldPortInfo = {'port_range': "", 'protocol': ""}
      if not add:
        selected_portitem = self.portList.selectedItem()
        if selected_portitem:
          oldPortInfo['port_range'] = selected_portitem.cell(0).label()
          oldPortInfo['protocol']   = selected_portitem.cell(1).label()

      dlg = portDialog.PortDialog(oldPortInfo)
      newPortInfo = dlg.run()
      # Cancelled if None is returned
      if newPortInfo is None:
        return

      if oldPortInfo['port_range'] == newPortInfo['port_range'] and \
          oldPortInfo['protocol'] == newPortInfo['protocol']:
        # nothing to change
        return

      if self.runtime_view:
        if not self.fw.queryPort(selected_zone, newPortInfo['port_range'], newPortInfo['protocol']):
          self.fw.addPort(selected_zone, newPortInfo['port_range'], newPortInfo['protocol'])
          if not add:
            self.fw.removePort(selected_zone, oldPortInfo['port_range'], oldPortInfo['protocol'])
      else:
        zone = self.fw.config().getZoneByName(selected_zone)
        if not zone.queryPort(newPortInfo['port_range'], newPortInfo['protocol']):
          if not add:
            zone.removePort(oldPortInfo['port_range'], oldPortInfo['protocol'])
          zone.addPort(newPortInfo['port_range'], newPortInfo['protocol'])

  def _service_conf_del_edit_port(self):
    '''
    remove the selected port from a service
    '''
    active_service = self._currentItem
    if active_service:
      selected_portitem = self.portList.selectedItem()
      if selected_portitem:
        port_range = selected_portitem.cell(0).label()
        protocol   = selected_portitem.cell(1).label()

        service = self.fw.config().getServiceByName(active_service)
        service.removePort(port_range, protocol)

  def _service_conf_add_edit_port(self, add):
    '''
    add, edit or remove port from a service (add is True for new port)
    '''
    active_service = self._currentItem
    if active_service:

      oldPortInfo = {'port_range': "", 'protocol': ""}
      if not add:
        selected_portitem = self.portList.selectedItem()
        if selected_portitem:
          oldPortInfo['port_range'] = selected_portitem.cell(0).label()
          oldPortInfo['protocol']   = selected_portitem.cell(1).label()

      dlg = portDialog.PortDialog(oldPortInfo)
      newPortInfo = dlg.run()
      if newPortInfo is None:
        # Cancelled if None is returned
        return

      if oldPortInfo['port_range'] == newPortInfo['port_range'] and \
          oldPortInfo['protocol'] == newPortInfo['protocol']:
        # nothing to change
        return

      service = self.fw.config().getServiceByName(active_service)
      if not service.queryPort(newPortInfo['port_range'], newPortInfo['protocol']):
        if not add:
          service.removePort(oldPortInfo['port_range'], oldPortInfo['protocol'])
        service.addPort(newPortInfo['port_range'], newPortInfo['protocol'])

  def _add_edit_protocol(self, add):
    '''
    add or edit protocol (add is True for new protocol)
    '''
    selected_zone = self._currentItem
    if selected_zone:

      oldInfo = {'protocol': ""}
      if not add:
        selected_protocol = self.protocolList.selectedItem()
        if selected_protocol:
          oldInfo['protocol'] = selected_protocol.cell(0).label()

      dlg = protocolDialog.ProtocolDialog(oldInfo)
      newInfo = dlg.run()
      # Cancelled if None is returned
      if newInfo is None:
        return

      if oldInfo['protocol'] == newInfo['protocol']:
        # nothing to change
        return

      if self.runtime_view:
        if not self.fw.queryProtocol(selected_zone, newInfo['protocol']):
          self.fw.addProtocol(selected_zone, newInfo['protocol'])
          if not add:
            self.fw.removeProtocol(selected_zone, oldInfo['protocol'])
      else:
        zone = self.fw.config().getZoneByName(selected_zone)
        if not zone.queryProtocol(newInfo['protocol']):
          if not add:
            zone.removeProtocol(oldInfo['protocol'])
          zone.addProtocol(newInfo['protocol'])

  def _del_edit_protocol(self):
    '''
    remove the selected protocol
    '''
    selected_zone = self._currentItem
    if selected_zone:
      selected_portitem = self.protocolList.selectedItem()
      if selected_portitem:
        protocol   = selected_portitem.cell(0).label()

        if self.runtime_view:
          self.fw.removeProtocol(selected_zone, protocol)
        else:
          zone = self.fw.config().getZoneByName(selected_zone)
          zone.removeProtocol(protocol)

  def _add_edit_source_port(self, add):
    '''
    add or edit source port from zone (add is True for new port)
    '''
    selected_zone = self._currentItem
    if selected_zone:

      oldPortInfo = {'port_range': "", 'protocol': ""}
      if not add:
        selected_portitem = self.portList.selectedItem()
        if selected_portitem:
          oldPortInfo['port_range'] = selected_portitem.cell(0).label()
          oldPortInfo['protocol']   = selected_portitem.cell(1).label()

      dlg = portDialog.PortDialog(oldPortInfo)
      newPortInfo = dlg.run()
      # Cancelled if None is returned
      if newPortInfo is None:
        return

      if oldPortInfo['port_range'] == newPortInfo['port_range'] and \
          oldPortInfo['protocol'] == newPortInfo['protocol']:
        # nothing to change
        return

      if self.runtime_view:
        if not self.fw.querySourcePort(selected_zone, newPortInfo['port_range'], newPortInfo['protocol']):
          self.fw.addSourcePort(selected_zone, newPortInfo['port_range'], newPortInfo['protocol'])
          if not add:
            self.fw.removeSourcePort(selected_zone, oldPortInfo['port_range'], oldPortInfo['protocol'])
      else:
        zone = self.fw.config().getZoneByName(selected_zone)
        if not zone.querySourcePort(newPortInfo['port_range'], newPortInfo['protocol']):
          if not add:
            zone.removeSourcePort(oldPortInfo['port_range'], oldPortInfo['protocol'])
          zone.addSourcePort(newPortInfo['port_range'], newPortInfo['protocol'])

  def _del_edit_source_port(self):
    '''
    remove the selected source port
    '''
    selected_zone = self._currentItem
    if selected_zone:
      selected_portitem = self.portList.selectedItem()
      if selected_portitem:
        port_range = selected_portitem.cell(0).label()
        protocol   = selected_portitem.cell(1).label()

        if self.runtime_view:
          self.fw.removeSourcePort(selected_zone, port_range, protocol)
        else:
          zone = self.fw.config().getZoneByName(selected_zone)
          zone.removeSourcePort(port_range, protocol)

  def _service_conf_del_edit_source_port(self):
    '''
    remove the selected source port from a service
    '''
    active_service = self._currentItem
    if active_service:
      selected_portitem = self.portList.selectedItem()
      if selected_portitem:
        port_range = selected_portitem.cell(0).label()
        protocol   = selected_portitem.cell(1).label()

        service = self.fw.config().getServiceByName(active_service)
        service.removeSourcePort(port_range, protocol)

  def _service_conf_add_edit_source_port(self, add):
    '''
    add or edit source port from a service (add is True for new port)
    '''
    active_service = self._currentItem
    if active_service:

      oldPortInfo = {'port_range': "", 'protocol': ""}
      if not add:
        selected_portitem = self.portList.selectedItem()
        if selected_portitem:
          oldPortInfo['port_range'] = selected_portitem.cell(0).label()
          oldPortInfo['protocol']   = selected_portitem.cell(1).label()

      dlg = portDialog.PortDialog(oldPortInfo)
      newPortInfo = dlg.run()
      if newPortInfo is None:
        # Cancelled if None is returned
        return

      if oldPortInfo['port_range'] == newPortInfo['port_range'] and \
          oldPortInfo['protocol'] == newPortInfo['protocol']:
        # nothing to change
        return

      service = self.fw.config().getServiceByName(active_service)
      if not service.querySourcePort(newPortInfo['port_range'], newPortInfo['protocol']):
        if not add:
          service.removeSourcePort(oldPortInfo['port_range'], oldPortInfo['protocol'])
        service.addSourcePort(newPortInfo['port_range'], newPortInfo['protocol'])

  def _add_edit_forward_port(self, add):
    '''
    add or edit forward port from zone (add is True for new port)
    '''
    selected_zone = self._currentItem
    if selected_zone:

      oldPortForwardingInfo = {'port': "", 'protocol': "", 'to_port': "", 'to_address': "" }
      if not add:
        selected_portitem = self.portForwardList.selectedItem()
        if selected_portitem:
          oldPortForwardingInfo['port']       = selected_portitem.cell(0).label() if selected_portitem.cell(0) else ""
          oldPortForwardingInfo['protocol']   = selected_portitem.cell(1).label() if selected_portitem.cell(1) else ""
          oldPortForwardingInfo['to_port']    = selected_portitem.cell(2).label() if selected_portitem.cell(2) else ""
          oldPortForwardingInfo['to_address'] = selected_portitem.cell(3).label() if selected_portitem.cell(3) else ""

      dlg = forwardDialog.PortForwardingDialog(oldPortForwardingInfo)
      newPortForwardingInfo = dlg.run()
      # Cancelled if None is returned
      if newPortForwardingInfo is None:
        return

      if oldPortForwardingInfo['port'] == newPortForwardingInfo['port'] and \
          oldPortForwardingInfo['to_port'] == newPortForwardingInfo['to_port'] and \
          oldPortForwardingInfo['to_address'] == newPortForwardingInfo['to_address'] and \
          oldPortForwardingInfo['protocol'] == newPortForwardingInfo['protocol']:
        # nothing to change
        return

      if self.runtime_view:
        if not self.fw.queryForwardPort(selected_zone, newPortForwardingInfo['port'], newPortForwardingInfo['protocol'],
                                        newPortForwardingInfo['to_port'], newPortForwardingInfo['to_address']):
          self.fw.addForwardPort(selected_zone, newPortForwardingInfo['port'], newPortForwardingInfo['protocol'],
                                 newPortForwardingInfo['to_port'], newPortForwardingInfo['to_address'])
          if not add:
            self.fw.removeForwardPort(selected_zone, oldPortForwardingInfo['port'], oldPortForwardingInfo['protocol'],
                                       oldPortForwardingInfo['to_port'], oldPortForwardingInfo['to_address'])
          if add and newPortForwardingInfo['to_address'] and not self.fw.queryMasquerade(selected_zone):
            if common.askYesOrNo({'title': _("Information needed"),
                                  'text': _("Forwarding to another system is only useful if the interface is masqueraded.<br>Do you want to masquerade this zone?"),
                                  'richtext': True, 'default_button': 1}):
              self.fw.addMasquerade(selected_zone)
      else:
        zone = self.fw.config().getZoneByName(selected_zone)
        if not zone.queryForwardPort(newPortForwardingInfo['port'], newPortForwardingInfo['protocol'],
                                     newPortForwardingInfo['to_port'], newPortForwardingInfo['to_address']):
          if not add:
            zone.removeForwardPort(oldPortForwardingInfo['port'], oldPortForwardingInfo['protocol'],
                                   oldPortForwardingInfo['to_port'], oldPortForwardingInfo['to_address'])
            zone.addForwardPort(newPortForwardingInfo['port'], newPortForwardingInfo['protocol'],
                                newPortForwardingInfo['to_port'], newPortForwardingInfo['to_address'])
            if add and newPortForwardingInfo['to_address'] and not zone.getMasquerade():
              if common.askYesOrNo({'title': _("Information needed"),
                                    'text': _("Forwarding to another system is only useful if the interface is masqueraded.<br>Do you want to masquerade this zone?"),
                                    'richtext': True, 'default_button': 1}):
                zone.setMasquerade(True)

  def _del_edit_forward_port(self):
    '''
    remove the selected forward port
    '''
    selected_zone = self._currentItem
    if selected_zone:
      selected_portitem = self.portForwardList.selectedItem()
      if selected_portitem:
        port       = selected_portitem.cell(0).label() if selected_portitem.cell(0) else ""
        protocol   = selected_portitem.cell(1).label() if selected_portitem.cell(1) else ""
        to_port    = selected_portitem.cell(2).label() if selected_portitem.cell(2) else ""
        to_address = selected_portitem.cell(3).label() if selected_portitem.cell(3) else ""

        if self.runtime_view:
            self.fw.removeForwardPort(selected_zone, port, protocol,
                                      to_port, to_address)
        else:
            zone = self.fw.config().getZoneByName(selected_zone)
            zone.removeForwardPort(port, protocol, to_port, to_address)

  def _service_conf_add_edit_protocol(self, add):
    '''
    add or edit protocol from a service (add is True for new protocol)
    '''
    active_service = self._currentItem
    if active_service:

      oldInfo = {'protocol': ""}
      if not add:
        selected_protocol = self.protocolList.selectedItem()
        if selected_protocol:
          oldInfo['protocol'] = selected_protocol.cell(0).label()

      dlg = protocolDialog.ProtocolDialog(oldInfo)
      newInfo = dlg.run()
      if newInfo is None:
        # Cancelled if None is returned
        return

      if oldInfo['protocol'] == newInfo['protocol']:
        # nothing to change
        return

      service = self.fw.config().getServiceByName(active_service)
      if not service.queryProtocol(newInfo['protocol']):
        if not add:
          service.removeProtocol(oldInfo['protocol'])
        service.addProtocol(newInfo['protocol'])

  def _service_conf_del_edit_protocol(self):
    '''
    remove the selected protocol from a service
    '''
    active_service = self._currentItem
    if active_service:
      selected_portitem = self.protocolList.selectedItem()
      if selected_portitem:
        protocol   = selected_portitem.cell(0).label()

        service = self.fw.config().getServiceByName(active_service)
        service.removeProtocol(protocol)

  def onZoneMasquerade(self):
    '''
    Zone masquerade has changed
    '''
    if self._currentCategory == 'zones':
      selected_zone = self._currentItem
      if selected_zone:
        checked = self.masquerade.isChecked()
        if self.runtime_view:
          if checked:
            if not self.fw.queryMasquerade(selected_zone):
              self.fw.addMasquerade(selected_zone)
          else:
            if self.fw.queryMasquerade(selected_zone):
              self.fw.removeMasquerade(selected_zone)
        else:
          zone = self.fw.config().getZoneByName(selected_zone)
          zone.setMasquerade(checked)

  def onPortButtonsPressed(self, button):
    '''
    add, edit, remove port has been pressed
    '''
    isZones    = (self._currentCategory == 'zones')
    isServices = (self._currentCategory == 'services')

    isZonePort        = (self._currentRightTab == 'ports')
    isZoneSourcePort  = (self._currentRightTab == 'source_ports')
    isZoneForwardPort = (self._currentRightTab == 'forwarding')
    isZoneProtocol    = (self._currentRightTab == 'protocols')
    isServicePort        = isZonePort
    isServiceSourcePort  = isZoneSourcePort
    isServiceProtocol    = isZoneProtocol

    if button.widgetClass() == "YPushButton":
      if button == self.buttons['add']:
        logger.debug('Add')
        if isZones:
          if isZonePort:
            self._add_edit_port(True)
          elif isZoneSourcePort:
            self._add_edit_source_port(True)
          elif isZoneForwardPort:
            self._add_edit_forward_port(True)
          elif isZoneProtocol:
            self._add_edit_protocol(True)
        elif isServices:
          if isServicePort:
            self._service_conf_add_edit_port(True)
          elif isServiceSourcePort:
            self._service_conf_add_edit_source_port(True)
          elif isServiceProtocol:
            self._service_conf_add_edit_protocol(True)
      elif button == self.buttons['edit']:
        logger.debug('Edit')
        if isZones:
          if isZonePort:
            self._add_edit_port(False)
          elif isZoneSourcePort:
            self._add_edit_source_port(False)
          elif isZoneForwardPort:
            self._add_edit_forward_port(False)
          elif isZoneProtocol:
            self._add_edit_protocol(False)
        elif isServices:
          if isServicePort:
            self._service_conf_add_edit_port(False)
          elif isServiceSourcePort:
            self._service_conf_add_edit_source_port(False)
          elif isServiceProtocol:
            self._service_conf_add_edit_protocol(False)
      elif button == self.buttons['remove']:
        logger.debug('Remove')
        if isZones:
          if isZonePort:
            self._del_edit_port()
          elif isZoneSourcePort:
            self._del_edit_source_port()
          elif isZoneForwardPort:
            self._del_edit_forward_port()
          elif isZoneProtocol:
            self._del_edit_protocol()
        elif isServices:
          if isServicePort:
            self._service_conf_del_edit_port()
          elif isServiceSourcePort:
            self._service_conf_del_edit_source_port()
          elif isServiceProtocol:
            self._service_conf_del_edit_protocol()
      else:
        logger.debug('Why here?')


  def _zoneConfigurationViewCollection(self):
    '''
    returns an YItemCollection containing Zone configuration views
    '''
    ordered_configureViews = [ 'services',
                               'ports',
                               'protocols',
                               'source_ports',
                               'masquerading',
                               'port_forwarding',
                               'icmp_filter',
                               'rich_rules',
                               'interfaces',
                               'sources'
    ]
    itemColl = []
    for v in ordered_configureViews:
      item = MUI.YItem(self.zoneConfigurationView[v]['title'], False)
      show_item = 'services'
      if show_item == v :
          item.setSelected(True)
      # adding item to views to find the item selected
      self.zoneConfigurationView[v]['item'] = item
      itemColl.append(item)

    return itemColl

  def _serviceConfigurationViewCollection(self):
    '''
    returns an YItemCollection containing Service configuration views
    '''
    ordered_Views = [
      'ports',
      'protocols',
      'source_ports',
      'modules',
      'destinations'
    ]
    itemColl = []
    for v in ordered_Views:
      item = MUI.YItem(self.serviceConfigurationView[v]['title'], False)
      show_item = 'ports'
      if show_item == v :
          item.setSelected(True)
      # adding item to views to find the item selected
      self.serviceConfigurationView[v]['item'] = item
      itemColl.append(item)
    return itemColl

  def _ipsecConfigurationViewCollection(self):
    '''
    returns an YItemCollection containing IPSEC configuration views
    '''
    ordered_Views = [
      'entries',
    ]
    itemColl = []
    for v in ordered_Views:
      item = MUI.YItem(self.ipsecConfigurationView[v]['title'], False)
      show_item = 'entries'
      if show_item == v :
          item.setSelected(True)
      # adding item to views to find the item selected
      self.ipsecConfigurationView[v]['item'] = item
      itemColl.append(item)

    return itemColl

  # ─────────────────────────────────────────────────────────────────────────
  # New UX: left-pane fill helpers
  # ─────────────────────────────────────────────────────────────────────────

  def _fillLeftCategory(self):
    '''Dispatch to the correct fill method for the current category.'''
    if self._currentCategory == 'zones':
      self._fillLeftZones(self._currentItem)
    elif self._currentCategory == 'services':
      self._fillLeftServices(self._currentItem)
    elif self._currentCategory == 'ipsets':
      self._fillLeftIPSets()
    self._updateRightTabState()
    self._refreshRightPane()

  def _cleanLeftCallbacks(self):
    '''Remove widget events registered for the current left-pane content.'''
    for e in self.leftReplacePointWidgetsAndCallbacks:
      self.eventManager.removeWidgetEvent(e['widget'], e['action'])
    self.leftReplacePointWidgetsAndCallbacks.clear()

  def _fillLeftZones(self, selected=None):
    '''Fill leftReplacePoint with a zone tree (all zones, active bindings as children).'''
    self._cleanLeftCallbacks()
    self.leftReplacePoint.deleteChildren()
    self.activeBindingsTree = None
    self._connectionsTreeItem = None

    zones = []
    active_zones = {}
    default_zone = ''
    try:
      if self.runtime_view:
        zones = sorted(self.fw.getZones())
      else:
        zones = sorted(self.fw.config().getZoneNames())
      active_zones = self.fw.getActiveZones()
      default_zone = self.fw.getDefaultZone()
    except Exception:
      pass

    # Build NM connection map
    self._nm_connections_data = {}
    _connections      = {}
    _connections_name = {}
    if nm_is_imported():
      try:
        nm_get_connections(_connections, _connections_name)
      except Exception:
        pass
      for zone_name, data in active_zones.items():
        for iface in data.get('interfaces', []):
          if iface in _connections:
            conn_id = _connections[iface]
            if conn_id not in self._nm_connections_data:
              try:
                nm_zone = nm_get_zone_of_connection(conn_id)
              except Exception:
                nm_zone = ''
              self._nm_connections_data[conn_id] = [
                nm_zone if nm_zone else zone_name, [],
                _connections_name.get(conn_id, conn_id)
              ]
            self._nm_connections_data[conn_id][1].append(iface)

    nm_ifaces = {iface for _, ifaces_l, _ in self._nm_connections_data.values()
                 for iface in ifaces_l}

    # Build the zone tree
    self.activeBindingsTree = self.factory.createTree(self.factory.createHBox(self.leftReplacePoint), '')
    self.activeBindingsTree.setStretchable(MUI.YUIDimension.YD_VERT, True)
    self.activeBindingsTree.setNotify(True)

    itemColl = []
    selected_zone = selected if selected in zones else \
                    (default_zone if default_zone in zones else (zones[0] if zones else None))

    for zone in zones:
      label = '{} [{}]'.format(zone, _('default')) if zone == default_zone else zone
      zone_item = MUI.YTreeItem(label=label, is_open=True)
      zone_item.setData(('zone', zone))

      zone_data  = active_zones.get(zone, {})
      interfaces = sorted(zone_data.get('interfaces', []))
      sources    = sorted(zone_data.get('sources', []))

      # NM-managed connections
      for conn_id in sorted(self._nm_connections_data):
        z, ifaces, name = self._nm_connections_data[conn_id]
        if z == zone:
          child = MUI.YTreeItem(
            parent=zone_item,
            label='{} ({})'.format(name, ', '.join(sorted(ifaces))))
          child.setData(('connection', conn_id))

      # Bare interfaces (not NM-managed)
      for iface in interfaces:
        if iface not in nm_ifaces:
          MUI.YTreeItem(parent=zone_item, label=iface)

      # Sources
      for src in sources:
        MUI.YTreeItem(parent=zone_item, label=src)

      itemColl.append(zone_item)

    self.activeBindingsTree.addItems(itemColl)

    # Pre-select zone
    if selected_zone:
      for zi in itemColl:
        if zi.data() == ('zone', selected_zone):
          self.activeBindingsTree.selectItem(zi, True)
          break
      self._currentItem = selected_zone

    self.eventManager.addWidgetEvent(self.activeBindingsTree, self._onZoneTreeSelected, True)
    self.leftReplacePointWidgetsAndCallbacks.append(
      {'widget': self.activeBindingsTree, 'action': self._onZoneTreeSelected})

    self.leftReplacePoint.showChild()
    self.changeBindingsButton.setEnabled(False)

  def _fillLeftServices(self, selected=None):
    '''Fill leftReplacePoint with a services list.'''
    self._cleanLeftCallbacks()
    self.leftReplacePoint.deleteChildren()
    self.activeBindingsTree = None
    self._leftList = None

    services = []
    try:
      if self.runtime_view:
        services = sorted(self.fw.listServices())
      else:
        services = sorted(self.fw.config().getServiceNames())
    except Exception:
      pass

    table_header = MUI.YTableHeader()
    table_header.addColumn(_('Service'), False)
    self._leftList = self.factory.createTable(self.factory.createHBox(self.leftReplacePoint), table_header)
    self._leftList.setStretchable(MUI.YUIDimension.YD_VERT, True)
    self._leftList.setNotify(True)

    selected_service = selected if selected in services else (services[0] if services else None)
    itemColl = []
    for svc in services:
      it = MUI.YTableItem()
      it.addCell(svc)
      if svc == selected_service:
        it.setSelected(True)
      itemColl.append(it)
    self._leftList.addItems(itemColl)

    if selected_service:
      self._currentItem = selected_service

    self.eventManager.addWidgetEvent(self._leftList, self._onLeftListSelected, True)
    self.leftReplacePointWidgetsAndCallbacks.append(
      {'widget': self._leftList, 'action': self._onLeftListSelected})

    self.leftReplacePoint.showChild()
    self.changeBindingsButton.setEnabled(False)

  def _fillLeftIPSets(self):
    '''Fill leftReplacePoint with an IP Sets list.'''
    self._cleanLeftCallbacks()
    self.leftReplacePoint.deleteChildren()
    self.activeBindingsTree = None
    self._leftList = None

    ipsets = []
    try:
      if self.runtime_view:
        ipsets = sorted(self.fw.getIPSets())
      else:
        ipsets = sorted(self.fw.config().getIPSetNames())
    except Exception:
      pass

    table_header = MUI.YTableHeader()
    table_header.addColumn(_('IP Set'), False)
    self._leftList = self.factory.createTable(self.factory.createHBox(self.leftReplacePoint), table_header)
    self._leftList.setStretchable(MUI.YUIDimension.YD_VERT, True)
    self._leftList.setNotify(True)

    first_ipset = None
    itemColl = []
    for ipset in ipsets:
      it = MUI.YTableItem()
      it.addCell(ipset)
      if first_ipset is None:
        first_ipset = ipset
        it.setSelected(True)
      itemColl.append(it)
    self._leftList.addItems(itemColl)

    if first_ipset:
      self._currentItem = first_ipset

    self.eventManager.addWidgetEvent(self._leftList, self._onLeftListSelected, True)
    self.leftReplacePointWidgetsAndCallbacks.append(
      {'widget': self._leftList, 'action': self._onLeftListSelected})

    self.leftReplacePoint.showChild()
    self.changeBindingsButton.setEnabled(False)

  # ─────────────────────────────────────────────────────────────────────────
  # New UX: left-pane event handlers
  # ─────────────────────────────────────────────────────────────────────────

  def _onZoneTreeSelected(self, obj):
    '''Handle a selection change in the zones tree.'''
    if self.activeBindingsTree is None:
      return
    item = self.activeBindingsTree.selectedItem()
    if item is None:
      self.changeBindingsButton.setEnabled(False)
      return
    data = item.data()
    if data and isinstance(data, tuple):
      dtype, value = data
      if dtype == 'zone':
        if self._currentItem != value:
          self._currentItem = value
          self._updateRightTabState()
          self._refreshRightPane()
        self.changeBindingsButton.setEnabled(False)
      elif dtype == 'connection':
        # Keep parent zone as current item
        parent = item.parentItem()
        if parent:
          pdata = parent.data()
          if pdata and isinstance(pdata, tuple) and pdata[0] == 'zone':
            if self._currentItem != pdata[1]:
              self._currentItem = pdata[1]
              self._updateRightTabState()
              self._refreshRightPane()
        self.changeBindingsButton.setEnabled(True)
    else:
      self.changeBindingsButton.setEnabled(False)

  def _onLeftListSelected(self, obj):
    '''Handle a selection change in the services/ipsets list.'''
    if self._leftList is None:
      return
    item = self._leftList.selectedItem()
    if item is None:
      return
    cell = item.cell(0)
    if cell:
      name = cell.label()
      if self._currentItem != name:
        self._currentItem = name
        self._updateRightTabState()
        self._refreshRightPane()

  def onLeftTabChanged(self):
    '''Handle left DumbTab selection change (Zones / Services / IP Sets).'''
    item = self.leftTab.selectedItem()
    if item == self._zonesTabItem:
      new_category = 'zones'
    elif item == self._servicesTabItem:
      new_category = 'services'
    elif item == self._ipsetsTabItem:
      new_category = 'ipsets'
    else:
      return
    if new_category != self._currentCategory:
      self._currentCategory = new_category
      self._currentItem = None
      self._currentRightTab = 'summary'
    self._fillLeftCategory()

  def onLeftAddButton(self):
    if self._currentCategory == 'zones':
      self.onAddZone()
    elif self._currentCategory == 'services':
      self.onServiceConfAddService()

  def onLeftEditButton(self):
    if self._currentCategory == 'zones':
      self.onEditZone()
    elif self._currentCategory == 'services':
      self.onServiceConfEditService()

  def onLeftRemoveButton(self):
    if self._currentCategory == 'zones':
      self.onRemoveZone()
    elif self._currentCategory == 'services':
      self.onServiceConfRemoveService()

  def onLeftLoadDefaultsButton(self):
    if self._currentCategory == 'zones':
      self.onLoadDefaultsZone()
    elif self._currentCategory == 'services':
      self.onServiceConfLoadDefaultsService()

  # ─────────────────────────────────────────────────────────────────────────
  # New UX: right-pane tab and refresh helpers
  # ─────────────────────────────────────────────────────────────────────────

  def _rightTabKeyToItem(self, key):
    _map = {
      'summary':      self._summaryTabItem,
      'services':     self._svcTabItem,
      'ports':        self._portsTabItem,
      'protocols':    self._protosTabItem,
      'source_ports': self._srcPortsTabItem,
      'masquerade':   self._masqTabItem,
      'forwarding':   self._fwdTabItem,
      'icmp_filter':  self._icmpTabItem,
      'modules':      self._modulesTabItem,
      'destinations': self._destTabItem,
      'entries':      self._entriesTabItem,
      'interfaces':   self._ifacesTabItem,
      'sources':      self._sourcesTabItem,
      'rich_rules':   self._richRulesTabItem,
    }
    return _map.get(key)

  def _rebuildRightTabs(self):
    '''Rebuild the right DumbTab with only the tabs relevant to the current category.

    Called after every left-tab category change or item selection change.
    Expert zone tabs (Interfaces, Sources, Rich Rules) are only included when
    enabled in Layout options (userPreferences['settings']).
    '''
    # Read expert-tab settings
    show_interfaces = False
    show_sources    = False
    show_rich_rules = False
    try:
      prefs = getattr(self.config, 'userPreferences', None) or {}
      s = prefs.get('settings', {})
      show_interfaces = s.get('show_interfaces_tab', False)
      show_sources    = s.get('show_sources_tab',    False)
      show_rich_rules = s.get('show_rich_rules_tab', False)
    except Exception:
      pass

    # Build tab-key list for the current category
    if self._currentCategory == 'zones':
      tab_keys = ['summary', 'services', 'ports', 'protocols', 'source_ports',
                  'masquerade', 'forwarding', 'icmp_filter']
      if show_interfaces:
        tab_keys.append('interfaces')
      if show_sources:
        tab_keys.append('sources')
      if show_rich_rules:
        tab_keys.append('rich_rules')
    elif self._currentCategory == 'services':
      tab_keys = ['summary', 'ports', 'protocols', 'source_ports', 'modules', 'destinations']
    elif self._currentCategory == 'ipsets':
      tab_keys = ['summary', 'entries']
    else:
      tab_keys = ['summary']

    # Ensure the selected tab is in the new set
    if self._currentRightTab not in tab_keys:
      self._currentRightTab = 'summary'

    # Rebuild the DumbTab bar
    try:
      self.rightTab.deleteAllItems()
    except Exception:
      pass

    for key in tab_keys:
      item = self._rightTabKeyToItem(key)
      if item is not None:
        item.setSelected(key == self._currentRightTab)
        self.rightTab.addItem(item)

    # Force the correct tab to show as selected
    cur_item = self._rightTabKeyToItem(self._currentRightTab)
    if cur_item is not None:
      try:
        self.rightTab.selectItem(cur_item, True)
      except Exception:
        pass

  # kept for backwards compat in call sites that still reference it
  def _updateRightTabState(self):
    self._rebuildRightTabs()

  def onRightTabChanged(self):
    '''Handle right DumbTab selection.'''
    item = self.rightTab.selectedItem()
    _item_to_key = {
      self._summaryTabItem:   'summary',
      self._svcTabItem:       'services',
      self._portsTabItem:     'ports',
      self._protosTabItem:    'protocols',
      self._srcPortsTabItem:  'source_ports',
      self._masqTabItem:      'masquerade',
      self._fwdTabItem:       'forwarding',
      self._icmpTabItem:      'icmp_filter',
      self._modulesTabItem:   'modules',
      self._destTabItem:      'destinations',
      self._entriesTabItem:   'entries',
      self._ifacesTabItem:    'interfaces',
      self._sourcesTabItem:   'sources',
      self._richRulesTabItem: 'rich_rules',
    }
    key = _item_to_key.get(item)
    if key and key != self._currentRightTab:
      self._currentRightTab = key
      self._refreshRightPane()

  def _refreshRightPane(self):
    '''Swap replacePoint content for the currently selected right tab and item.'''
    for rpwc in self.replacePointWidgetsAndCallbacks:
      self.eventManager.removeWidgetEvent(rpwc['widget'], rpwc['action'])
    self.replacePointWidgetsAndCallbacks.clear()
    self.replacePoint.deleteChildren()
    self.portForwardList = None
    self.portList        = None
    self.serviceList     = None
    self.protocolList    = None
    self.icmpFilterList  = None
    self.modulesList     = None
    self._destIpv4Input  = None
    self._destIpv6Input  = None

    if self._currentItem is None:
      # No item selected — show blank pane (placeholder keeps ReplacePoint non-empty)
      self.factory.createVStretch(self.replacePoint)
      self.replacePoint.showChild()
      return

    tab = self._currentRightTab

    if tab == 'summary':
      self._replacePointSummary()
    elif tab == 'services' and self._currentCategory == 'zones':
      self._replacePointServices()
    elif tab == 'ports':
      if self._currentCategory == 'zones':
        self._replacePointPort('zone_ports')
        if self.buttons is not None:
          self.buttons['edit'].setEnabled(self.portList is not None and self.portList.itemsCount() > 0)
          self.buttons['remove'].setEnabled(self.portList is not None and self.portList.itemsCount() > 0)
      elif self._currentCategory == 'services':
        self._replacePointPort('service_ports')
        if self.buttons is not None:
          self.buttons['add'].setEnabled(not self.runtime_view)
          self.buttons['edit'].setEnabled(not self.runtime_view and self.portList is not None and self.portList.itemsCount() > 0)
          self.buttons['remove'].setEnabled(not self.runtime_view and self.portList is not None and self.portList.itemsCount() > 0)
    elif tab == 'protocols':
      if self._currentCategory == 'zones':
        self._replacePointProtocols('zone_protocols')
        if self.buttons is not None:
          self.buttons['edit'].setEnabled(self.protocolList is not None and self.protocolList.itemsCount() > 0)
          self.buttons['remove'].setEnabled(self.protocolList is not None and self.protocolList.itemsCount() > 0)
      elif self._currentCategory == 'services':
        self._replacePointProtocols('service_protocols')
        if self.buttons is not None:
          self.buttons['add'].setEnabled(not self.runtime_view)
          self.buttons['edit'].setEnabled(not self.runtime_view and self.protocolList is not None and self.protocolList.itemsCount() > 0)
          self.buttons['remove'].setEnabled(not self.runtime_view and self.protocolList is not None and self.protocolList.itemsCount() > 0)
    elif tab == 'source_ports':
      if self._currentCategory == 'zones':
        self._replacePointPort('zone_sourceports')
        if self.buttons is not None:
          self.buttons['edit'].setEnabled(self.portList is not None and self.portList.itemsCount() > 0)
          self.buttons['remove'].setEnabled(self.portList is not None and self.portList.itemsCount() > 0)
      elif self._currentCategory == 'services':
        self._replacePointPort('service_sourceports')
        if self.buttons is not None:
          self.buttons['add'].setEnabled(not self.runtime_view)
          self.buttons['edit'].setEnabled(not self.runtime_view and self.portList is not None and self.portList.itemsCount() > 0)
          self.buttons['remove'].setEnabled(not self.runtime_view and self.portList is not None and self.portList.itemsCount() > 0)
    elif tab == 'masquerade' and self._currentCategory == 'zones':
      self._replacePointMasquerade()
    elif tab == 'forwarding' and self._currentCategory == 'zones':
      self._replacePointForwardPorts()
      if self.buttons is not None:
        self.buttons['edit'].setEnabled(self.portForwardList is not None and self.portForwardList.itemsCount() > 0)
        self.buttons['remove'].setEnabled(self.portForwardList is not None and self.portForwardList.itemsCount() > 0)
    elif tab == 'icmp_filter' and self._currentCategory == 'zones':
      self._replacePointICMP()
    elif tab == 'modules' and self._currentCategory == 'services':
      self._replacePointModules()
    elif tab == 'destinations' and self._currentCategory == 'services':
      self._replacePointDestinations()
    elif tab == 'interfaces' and self._currentCategory == 'zones':
      self._replacePointZoneInterfaces()
    elif tab == 'sources' and self._currentCategory == 'zones':
      self._replacePointZoneSources()
    elif tab == 'rich_rules' and self._currentCategory == 'zones':
      self._replacePointZoneRichRules()
    else:
      # Tab has no content for this category — keep ReplacePoint non-empty
      self.factory.createVStretch(self.replacePoint)

    self.replacePoint.showChild()

  def _replacePointZoneInterfaces(self):
    '''Show interfaces bound to the selected zone (read-only, expert tab).'''
    vbox = self.factory.createVBox(self.replacePoint)
    try:
      zone_data = self.fw.getActiveZones().get(self._currentItem, {})
      ifaces = sorted(zone_data.get('interfaces', []))
    except Exception:
      ifaces = []
    hdr = MUI.YTableHeader()
    hdr.addColumn(_('Interface'))
    tbl = self.factory.createTable(vbox, hdr, False)
    tbl.setStretchable(MUI.YUIDimension.YD_VERT, True)
    items = []
    for iface in ifaces:
      it = MUI.YTableItem()
      it.addCell(iface)
      items.append(it)
    tbl.addItems(items)

  def _replacePointZoneSources(self):
    '''Show sources bound to the selected zone (read-only, expert tab).'''
    vbox = self.factory.createVBox(self.replacePoint)
    try:
      zone_data = self.fw.getActiveZones().get(self._currentItem, {})
      sources = sorted(zone_data.get('sources', []))
    except Exception:
      sources = []
    hdr = MUI.YTableHeader()
    hdr.addColumn(_('Source'))
    tbl = self.factory.createTable(vbox, hdr, False)
    tbl.setStretchable(MUI.YUIDimension.YD_VERT, True)
    items = []
    for src in sources:
      it = MUI.YTableItem()
      it.addCell(src)
      items.append(it)
    tbl.addItems(items)

  def _replacePointZoneRichRules(self):
    '''Show rich rules for the selected zone (read-only, expert tab).'''
    vbox = self.factory.createVBox(self.replacePoint)
    try:
      if self.runtime_view:
        rules = sorted(str(r) for r in self.fw.getRichRules(self._currentItem))
      else:
        zone = self.fw.config().getZoneByName(self._currentItem)
        rules = sorted(str(r) for r in zone.getSettings().getRichRules())
    except Exception:
      rules = []
    hdr = MUI.YTableHeader()
    hdr.addColumn(_('Rich Rule'))
    tbl = self.factory.createTable(vbox, hdr, False)
    tbl.setStretchable(MUI.YUIDimension.YD_VERT, True)
    tbl.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
    items = []
    for rule in rules:
      it = MUI.YTableItem()
      it.addCell(rule)
      items.append(it)
    tbl.addItems(items)

  def _replacePointModules(self):
    '''Fill replacePoint with kernel modules for the selected service (permanent only).'''
    if len(self.replacePointWidgetsAndCallbacks) > 0:
      logger.error("Error there are still widget events for ReplacePoint")
      return
    if self.replacePoint.hasChildren():
      logger.error("Error there are still widgets into ReplacePoint")
      return
    vbox = self.factory.createVBox(self.replacePoint)
    mod_header = MUI.YTableHeader()
    mod_header.addColumn(_('Module'))
    self.modulesList = self.factory.createTable(vbox, mod_header, False)
    self.modulesList.setStretchable(MUI.YUIDimension.YD_VERT, True)
    align = self.factory.createLeft(vbox)
    hbox = self.factory.createHBox(align)
    self._modulesAddButton    = self.factory.createIconButton(hbox, 'list-add',    _('&Add'))
    self._modulesRemoveButton = self.factory.createIconButton(hbox, 'list-remove', _('&Remove'))
    # modules can only be edited in permanent mode
    self._modulesAddButton.setEnabled(not self.runtime_view)
    self._modulesRemoveButton.setEnabled(False)  # enabled when a row is selected
    self.eventManager.addWidgetEvent(self._modulesAddButton,    self._onModuleAdd)
    self.eventManager.addWidgetEvent(self._modulesRemoveButton, self._onModuleRemove)
    self.eventManager.addWidgetEvent(self.modulesList, self._onModuleSelected, True)
    self.replacePointWidgetsAndCallbacks += [
      {'widget': self._modulesAddButton,    'action': self._onModuleAdd},
      {'widget': self._modulesRemoveButton, 'action': self._onModuleRemove},
      {'widget': self.modulesList,          'action': self._onModuleSelected},
    ]
    self._fillRPModules()

  def _fillRPModules(self):
    '''Populate the modules table from current service settings.'''
    settings = self._serviceSettings()
    modules = settings.getModules() if settings else []
    current = self.modulesList.selectedItem()
    current_mod = current.cell(0).label() if current else ''
    v = []
    for mod in sorted(modules):
      item = MUI.YTableItem()
      item.addCell(mod)
      item.setSelected(mod == current_mod)
      v.append(item)
    self.modulesList.deleteAllItems()
    self.modulesList.addItems(v)
    has_rows = self.modulesList.itemsCount() > 0
    self._modulesRemoveButton.setEnabled(not self.runtime_view and has_rows)

  def _onModuleSelected(self, obj):
    item = self.modulesList.selectedItem()
    self._modulesRemoveButton.setEnabled(not self.runtime_view and item is not None)

  def _onModuleAdd(self):
    if self.runtime_view or not self._currentItem:
      return
    service = self.fw.config().getServiceByName(self._currentItem)
    settings = service.getSettings()
    existing = list(settings.getModules()) if settings else []
    dlg = moduleDialog.HelperDialog(self.fw, existing=existing)
    helper_name = dlg.run()
    if not helper_name:
      return
    if not settings.queryModule(helper_name):
      settings.addModule(helper_name)
      service.update(settings)
    self._fillRPModules()

  def _onModuleRemove(self):
    if self.runtime_view or not self._currentItem:
      return
    item = self.modulesList.selectedItem()
    if item is None:
      return
    mod_name = item.cell(0).label()
    service = self.fw.config().getServiceByName(self._currentItem)
    settings = service.getSettings()
    if settings.queryModule(mod_name):
      settings.removeModule(mod_name)
      service.update(settings)
    self._fillRPModules()

  def _replacePointDestinations(self):
    '''Fill replacePoint with IPv4/IPv6 destination for the selected service (permanent only).'''
    if len(self.replacePointWidgetsAndCallbacks) > 0:
      logger.error("Error there are still widget events for ReplacePoint")
      return
    if self.replacePoint.hasChildren():
      logger.error("Error there are still widgets into ReplacePoint")
      return
    vbox = self.factory.createVBox(self.replacePoint)
    self.factory.createLabel(vbox, _(
      "Destination address restricts the service to IPv4 or IPv6 only.\n"
      "Leave empty to allow both.  Format: IP or CIDR (e.g. 0.0.0.0/0 or ::/0)."
    ))
    self.factory.createVSpacing(vbox, 0.3)
    align = self.factory.createLeft(vbox)
    self._destIpv4Input = self.factory.createInputField(align, _('IPv4 destination'))
    self._destIpv4Input.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
    self._destIpv4Input.setEnabled(not self.runtime_view)
    align = self.factory.createLeft(vbox)
    self._destIpv6Input = self.factory.createInputField(align, _('IPv6 destination'))
    self._destIpv6Input.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
    self._destIpv6Input.setEnabled(not self.runtime_view)
    self._fillRPDestinations()
    if not self.runtime_view:
      align = self.factory.createRight(vbox)
      saveBtn = self.factory.createPushButton(align, _('&Apply'))
      self.eventManager.addWidgetEvent(saveBtn, self._onDestinationSave)
      self.replacePointWidgetsAndCallbacks.append({'widget': saveBtn, 'action': self._onDestinationSave})

  def _fillRPDestinations(self):
    '''Populate IPv4/IPv6 input fields from current service settings.'''
    settings = self._serviceSettings()
    destinations = settings.getDestinations() if settings else {}
    if self._destIpv4Input is not None:
      self._destIpv4Input.setValue(destinations.get('ipv4', ''))
    if self._destIpv6Input is not None:
      self._destIpv6Input.setValue(destinations.get('ipv6', ''))

  def _onDestinationSave(self):
    if self.runtime_view or not self._currentItem:
      return
    ipv4 = self._destIpv4Input.value().strip() if self._destIpv4Input else ''
    ipv6 = self._destIpv6Input.value().strip() if self._destIpv6Input else ''
    service = self.fw.config().getServiceByName(self._currentItem)
    settings = service.getSettings()
    # Build new destinations dict; omit empty entries
    new_dest = {}
    if ipv4:
      new_dest['ipv4'] = ipv4
    if ipv6:
      new_dest['ipv6'] = ipv6
    settings.setDestinations(new_dest)
    service.update(settings)

  def _replacePointSummary(self):
    '''Fill replacePoint with a summary for the current item.
    Called from _refreshRightPane() which already cleared replacePoint.'''
    vbox = self.factory.createVBox(self.replacePoint)

    if not self._currentItem:
      self.factory.createLabel(vbox, _("No item selected."))
      return

    if self._currentCategory == 'zones':
      default_zone = ''
      active_zones = {}
      try:
        default_zone = self.fw.getDefaultZone()
        active_zones = self.fw.getActiveZones()
      except Exception:
        pass

      name = self._currentItem
      header = '{} ({})'.format(name, _('default zone')) if name == default_zone else name
      self.factory.createHeading(vbox, header)
      self.factory.createVSpacing(vbox, 0.3)

      settings = self._zoneSettings()
      if settings:
        target = settings.getTarget()
        short  = settings.getShort()
        desc   = settings.getDescription()
        if target:
          self.factory.createLabel(vbox, _("Target: {}").format(target))
        if short:
          self.factory.createLabel(vbox, short)
        if desc:
          lbl = self.factory.createLabel(vbox, desc)
          try:
            lbl.setAutoWrap()
          except Exception:
            pass

      zone_data  = active_zones.get(name, {})
      interfaces = sorted(zone_data.get('interfaces', []))
      sources    = sorted(zone_data.get('sources', []))
      if interfaces:
        self.factory.createLabel(vbox, _("Interfaces: {}").format(', '.join(interfaces)))
      if sources:
        self.factory.createLabel(vbox, _("Sources: {}").format(', '.join(sources)))

    elif self._currentCategory == 'services':
      self.factory.createHeading(vbox, _("Service: {}").format(self._currentItem))
      self.factory.createVSpacing(vbox, 0.3)
      settings = self._serviceSettings()
      if settings:
        short = settings.getShort()
        desc  = settings.getDescription()
        if short:
          self.factory.createLabel(vbox, short)
        if desc:
          lbl = self.factory.createLabel(vbox, desc)
          try:
            lbl.setAutoWrap()
          except Exception:
            pass

    elif self._currentCategory == 'ipsets':
      self.factory.createHeading(vbox, _("IP Set: {}").format(self._currentItem))

  # ─────────────────────────────────────────────────────────────────────────
  # New UX: mode bar handler
  # ─────────────────────────────────────────────────────────────────────────

  def onModeChanged(self):
    '''Handle Runtime / Permanent switch.'''
    if self._runtimeRadio is not None:
      self.runtime_view = self._runtimeRadio.value()
    elif hasattr(self, 'currentViewCombobox'):
      item = self.currentViewCombobox.selectedItem()
      self.runtime_view = (item == self.views['runtime']['item'])
    self._fillLeftCategory()

  def _exception_handler(self, exception_message):
    if not self.__use_exception_handler:
      raise

  def initFWClient(self):
    '''
    initialize firewall client
    '''
    self.fw = client.FirewallClient(wait=1)
    self.__use_exception_handler = True
    self.fw.setExceptionHandler(self._exception_handler)
    self.fw.setNotAuthorizedLoop(True)

    self.fw.connect("connection-changed", self.fwConnectionChanged)
    self.fw.connect("panic-mode-enabled", self.panic_mode_enabled_cb)
    self.fw.connect("panic-mode-disabled", self.panic_mode_disabled_cb)
    self.fw.connect("default-zone-changed", self.default_zone_changed_cb)
    self.fw.connect("service-added", self.service_added_cb)
    self.fw.connect("service-removed", self.service_removed_cb)
    self.fw.connect("port-added", self.port_added_cb)
    self.fw.connect("port-removed", self.port_removed_cb)
    self.fw.connect("protocol-added", self.protocol_added_cb)
    self.fw.connect("protocol-removed", self.protocol_removed_cb)
    self.fw.connect("source-port-added", self.source_port_added_cb)
    self.fw.connect("source-port-removed", self.source_port_removed_cb)
    self.fw.connect("masquerade-added", self.masquerade_added_cb)
    self.fw.connect("masquerade-removed", self.masquerade_removed_cb)
    self.fw.connect("forward-port-added", self.forward_port_added_cb)
    self.fw.connect("forward-port-removed", self.forward_port_removed_cb)
    self.fw.connect("icmp-block-added", self.icmp_added_cb)
    self.fw.connect("icmp-block-removed", self.icmp_removed_cb)
    self.fw.connect("icmp-block-inversion-added", self.icmp_inversion_added_cb)
    self.fw.connect("icmp-block-inversion-removed", self.icmp_inversion_removed_cb)

    self.fw.connect("config:zone-added",   self.conf_zone_added_cb)
    self.fw.connect("config:zone-updated", self.conf_zone_updated_cb)
    self.fw.connect("config:zone-removed", self.conf_zone_removed_cb)
    self.fw.connect("config:zone-renamed", self.conf_zone_renamed_cb)
    self.fw.connect("config:service-added", self.conf_service_added_cb)
    self.fw.connect("config:service-updated", self.conf_service_updated_cb)
    self.fw.connect("config:service-removed", self.conf_service_removed_cb)
    self.fw.connect("config:service-renamed", self.conf_service_renamed_cb)

    self.fw.connect("log-denied-changed", self.log_denied_changed_cb)
    self.fw.connect("zone-of-interface-changed", self.zone_of_interface_changed_cb)
    self.fw.connect("reloaded", self.reload_cb)

  def load_zones(self, selected = None):
    '''
    load zones into selectedConfigurationCombo
    '''
    self.selectedConfigurationCombo.deleteAllItems()

    self.selectedConfigurationCombo.setEnabled(True)
    self.selectedConfigurationCombo.setLabel(self.configureViews['zones']['title'])

    zones = []
    if self.runtime_view:
      zones = self.fw.getZones()
    else:
      zones = self.fw.config().getZoneNames()

    selected_zone = selected
    if selected not in zones:
      selected_zone = self.fw.getDefaultZone()

    # zones
    itemColl = []
    for zone in zones:
      item = MUI.YItem(zone, False)
      if zone == selected_zone:
        item.setSelected(True)
      itemColl.append(item)

    self.selectedConfigurationCombo.addItems(itemColl)


  def load_services(self, service_name = None):
    '''
    load services into selectedConfigurationCombo
    '''
    self.selectedConfigurationCombo.deleteAllItems()

    self.selectedConfigurationCombo.setEnabled(True)
    self.selectedConfigurationCombo.setLabel(self.configureViews['services']['title'])

    services = []
    if self.runtime_view:
      services = self.fw.listServices()
    else:
      services = self.fw.config().getServiceNames()

    selected_service = service_name
    if selected_service not in services:
      selected_service = services[0] if services else None

    # services
    itemColl = []
    for service in services:
      item = MUI.YItem(service, False)
      if service == selected_service:
        item.setSelected(True)
      itemColl.append(item)

    self.selectedConfigurationCombo.addItems(itemColl)


  def load_ipsets(self):
    '''
    load ipsets into selectedConfigurationCombo
    '''
    self.selectedConfigurationCombo.deleteAllItems()

    self.selectedConfigurationCombo.setEnabled(True)
    self.selectedConfigurationCombo.setLabel(self.configureViews['ipsets']['title'])

    ipsets = []
    if self.runtime_view:
        ipsets = self.fw.getIPSets()
    else:
        ipsets = self.fw.config().getIPSetNames()

    # ipsets
    itemColl = []
    for ipset in ipsets:
      item = MUI.YItem(ipset, False)
      itemColl.append(item)

    self.selectedConfigurationCombo.addItems(itemColl)


#### Firewall events

  def fwConnectionChanged(self):
    '''
    connection changed
    '''
    if self.fw.connected:
      self.fwEventQueue.put({'event': "connection-changed", 'value': True})
      logger.info("Firewalld connected")
    else:
      self.fwEventQueue.put({'event': "connection-changed", 'value': False})
      logger.info("Firewalld disconnected")

  def panic_mode_enabled_cb(self):
    '''
    manage panicmode enabled evend from firewalld
    '''
    self.fwEventQueue.put({'event': "panicmode-changed", 'value': True})

  def panic_mode_disabled_cb(self):
    '''
    manage panicmode disabled evend from firewalld
    '''
    self.fwEventQueue.put({'event': "panicmode-changed", 'value': False})

  def default_zone_changed_cb(self, zone):
    '''
    manage default zone changed from firewalld
    '''
    self.fwEventQueue.put({'event': "default-zone-changed", 'value': zone})

  def conf_zone_added_cb(self, zone):
    '''
    config zone has been added
    '''
    if self._reloading:
      self._reload_pending_zones.append(zone)
    else:
      self.fwEventQueue.put({'event': "config-zone-added", 'value': zone})

  def conf_zone_updated_cb(self, zone):
    '''
    config zone has been updated
    '''
    self.fwEventQueue.put({'event': "config-zone-updated", 'value': zone})

  def conf_zone_removed_cb(self, zone):
    '''
    config zone has been removed
    '''
    self.fwEventQueue.put({'event': "config-zone-removed", 'value': zone})

  def conf_zone_renamed_cb(self, zone):
    '''
    config zone has been removed
    '''
    self.fwEventQueue.put({'event': "config-zone-renamed", 'value': zone})

  def conf_service_added_cb(self, service):
    '''
    config service has been added
    '''
    if self._reloading:
      self._reload_pending_services.append(service)
    else:
      self.fwEventQueue.put({'event': "config-service-added", 'value': service})

  def conf_service_updated_cb(self, service):
    '''
    config service has been updated
    '''
    self.fwEventQueue.put({'event': "config-service-updated", 'value': service})

  def conf_service_removed_cb(self, service):
    '''
    config service has been removed
    '''
    self.fwEventQueue.put({'event': "config-service-removed", 'value': service})

  def conf_service_renamed_cb(self, service):
    '''
    config service has been removed
    '''
    self.fwEventQueue.put({'event': "config-service-renamed", 'value': service})

  def service_added_cb(self, zone, service, timeout):
    '''
    service has been added at run time
    '''
    self.fwEventQueue.put({'event': "service-added", 'value': {'zone' : zone, 'service': service } })

  def service_removed_cb(self, zone, service):
    '''
    service has been removed at run time
    '''
    self.fwEventQueue.put({'event': "service-removed", 'value': {'zone' : zone, 'service': service } })

  def port_added_cb(self, zone, port, protocol, timeout):
    '''
    port has been added at run time
    '''
    self.fwEventQueue.put({'event': "port-added", 'value': {'zone' : zone, 'port': port, 'protocol' : protocol } })

  def port_removed_cb(self, zone, port, protocol):
    '''
    port has been removed at run time
    '''
    self.fwEventQueue.put({'event': "port-removed", 'value': {'zone' : zone, 'port': port, 'protocol' : protocol } })

  def protocol_added_cb(self, zone, protocol, timeout):
    '''
    protocol has been added at run time
    '''
    self.fwEventQueue.put({'event': "protocol-added", 'value': {'zone' : zone, 'protocol' : protocol}})

  def protocol_removed_cb(self, zone, protocol):
    '''
    protocol has been added at run time
    '''
    self.fwEventQueue.put({'event': "protocol-removed", 'value': {'zone' : zone, 'protocol' : protocol}})

  def source_port_added_cb(self, zone, port, protocol, timeout):
    '''
    source port has been added at run time
    '''
    self.fwEventQueue.put({'event': "source-port-added", 'value': {'zone' : zone, 'port': port, 'protocol' : protocol } })

  def source_port_removed_cb(self, zone, port, protocol):
    '''
    source port has been removed at run time
    '''
    self.fwEventQueue.put({'event': "source-port-removed", 'value': {'zone' : zone, 'port': port, 'protocol' : protocol } })

  def masquerade_added_cb(self, zone, timeout):
    '''
    masquerade has been added at run time
    '''
    self.fwEventQueue.put({'event': "masquerade-added", 'value': zone})

  def masquerade_removed_cb(self, zone):
    '''
    masquerade has been added at run time
    '''
    self.fwEventQueue.put({'event': "masquerade-removed", 'value': zone})

  def forward_port_added_cb(self, zone, port, protocol, to_port, to_address, timeout):
    '''
    forward port has been added at run time
    '''
    self.fwEventQueue.put({'event': "forward-port-added", 'value': {'zone' : zone, 'to_port': to_port, 'protocol' : protocol, 'to_address': to_address } })

  def forward_port_removed_cb(self, zone, port, protocol, to_port, to_address):
    '''
    forward port has been removed at run time
    '''
    self.fwEventQueue.put({'event': "forward-port-removed", 'value': {'zone' : zone, 'to_port': to_port, 'protocol' : protocol, 'to_address': to_address } })

  def icmp_added_cb(self, zone, icmp, timeout):
    '''
    ICMP filter has been added at run time
    '''
    self.fwEventQueue.put({'event': "icmp-changed", 'value': {'zone' : zone, 'icmp': icmp, 'added': True} })

  def icmp_removed_cb(self, zone, icmp):
    '''
    ICMP filter has been removed at run time
    '''
    self.fwEventQueue.put({'event': "icmp-changed", 'value': {'zone' : zone, 'icmp': icmp, 'added': False}})

  def icmp_inversion_added_cb(self, zone):
    '''
    ICMP inversion has been added at run time
    '''
    self.fwEventQueue.put({'event': "icmp-inversion", 'value': {'zone' : zone, 'inversion': True}})

  def icmp_inversion_removed_cb(self, zone):
    '''
    ICMP inversion has been removed at run time
    '''
    self.fwEventQueue.put({'event': "icmp-inversion", 'value': {'zone' : zone, 'inversion': False}})


  def log_denied_changed_cb(self, value):
    '''
    log-denied setting changed in firewalld
    '''
    self.fwEventQueue.put({'event': "log-denied-changed", 'value': value})

  def zone_of_interface_changed_cb(self, zone, interface):
    logger.debug("zone_of_interface_changed_cb %s - %s", zone, interface)

  def reload_cb(self):
    '''
    firewalld reloaded event — emitted after all config signals of the burst.
    Sets _reloading so that any late callbacks (daemon-triggered reload) are
    accumulated; then queues group events for whatever was collected, then
    queues the reloaded event.
    '''
    self._reloading = True
    if self._reload_pending_zones:
      self.fwEventQueue.put({'event': "config-zones-group-added",
                             'value': list(self._reload_pending_zones)})
      self._reload_pending_zones.clear()
    if self._reload_pending_services:
      self.fwEventQueue.put({'event': "config-services-group-added",
                             'value': list(self._reload_pending_services)})
      self._reload_pending_services.clear()
    self.fwEventQueue.put({'event': "reloaded", 'value': True})

  def saveUserPreference(self):
    '''
    Save user preferences on exit and view layout if needed
    '''

    self.config.saveUserPreferences()


#### GUI events

  def onCancelEvent(self) :
    '''
    Exit by using cancel event
    '''
    logger.info("Got a cancel event")
    self.saveUserPreference()
    # In text mode a GLib.MainLoop is running in a background thread
    # (needed for firewalld D-Bus signals).  The quit button handler
    # (onQuitEvent) stops it explicitly, but CancelEvent (e.g. F10 in ncurses)
    # also exits the event loop without going through onQuitEvent.  Without
    # stopping the loop here the non-daemon glib_thread keeps the process
    # alive and the terminal appears to hang after F10.
    if MUI.YUI.app().isTextMode():
      try:
        self.glib_loop.quit()
      except Exception:
        pass
      try:
        self.glib_thread.join(timeout=2)
      except Exception:
        pass

  def onQuitEvent(self, obj) :
    '''
    Exit by using quit button or menu
    '''
    if isinstance(obj, MUI.YItem):
      logger.info("Quit menu pressed")
    else:
      logger.info("Quit button pressed")
    self.saveUserPreference()

    if MUI.YUI.app().isTextMode():
      self.glib_loop.quit()
    # BaseDialog needs to force to exit the handle event loop
    self.ExitLoop()
    if MUI.YUI.app().isTextMode():
      self.glib_thread.join()

  def onOptionSettings(self):
    '''
    Show optionDialog for extended settings
    '''
    self.dialog.setEnabled(False)
    up = optionDialog.OptionDialog(self)
    up.run()
    if self._reloading:
      # If we are reloading, the dialog will be closed by the reload callback, so we don't need to re-enable it
      return
    self.dialog.setEnabled(True)

  def onActiveBindings(self):
    '''
    Show active zone bindings (runtime: connections, interfaces, sources).
    '''
    self.dialog.setEnabled(False)
    dlg = activeBindingsDialog.ActiveBindingsDialog(self.fw)
    dlg.run()
    self.dialog.setEnabled(True)

  def onReloadFirewalld(self):
    '''
    Reload Firewalld menu pressed
    '''
    self._reloading = True
    self.dialog.setEnabled(False)
    self.fw.reload()

  def onRuntimeToPermanent(self):
    '''
    Make runtime configuration permanent
    '''
    self.fw.runtimeToPermanent()

  def update_active_bindings(self):
    '''
    Refresh the active bindings tree (Connections / Interfaces / Sources).
    Called on connection-changed (connected), reloaded, and default-zone-changed events.
    '''
    self.changeBindingsButton.setEnabled(False)
    self.activeBindingsTree.deleteAllItems()
    self._connectionsTreeItem = None
    self._interfacesTreeItem  = None
    self._sourcesTreeItem     = None

    if not self.fw.connected:
      return

    active_zones = {}
    try:
      active_zones = self.fw.getActiveZones()
    except Exception:
      pass
    default_zone = ""
    try:
      default_zone = self.fw.getDefaultZone()
    except Exception:
      pass

    # Separate NM connections, bare interfaces, sources
    self._nm_connections_data = {}   # {conn_id: [zone, [ifaces], display_name]}
    bare_interfaces = {}             # {iface: zone}
    sources = {}                     # {source: zone}

    if nm_is_imported():
      _connections = {}       # {iface_path: conn_id}
      _connections_name = {}  # {conn_id: display_name}
      try:
        nm_get_connections(_connections, _connections_name)
      except Exception:
        pass
      for zone, data in active_zones.items():
        for iface in data.get("interfaces", []):
          if iface in _connections:
            conn_id = _connections[iface]
            if conn_id not in self._nm_connections_data:
              try:
                nm_zone = nm_get_zone_of_connection(conn_id)
              except Exception:
                nm_zone = ""
              self._nm_connections_data[conn_id] = [
                nm_zone if nm_zone else zone,
                [],
                _connections_name.get(conn_id, conn_id)
              ]
            self._nm_connections_data[conn_id][1].append(iface)
          else:
            bare_interfaces[iface] = zone
        for source in data.get("sources", []):
          sources[source] = zone
    else:
      for zone, data in active_zones.items():
        for iface in data.get("interfaces", []):
          bare_interfaces[iface] = zone
        for source in data.get("sources", []):
          sources[source] = zone

    # Build tree
    itemColl = []

    connParent = MUI.YTreeItem(label=_("Connections"), is_open=True)
    for conn_id in sorted(self._nm_connections_data):
      z, ifaces, name = self._nm_connections_data[conn_id]
      zone_str = z if z else default_zone
      label = "{} ({})\nZone: {}".format(name, ", ".join(sorted(ifaces)), zone_str)
      child = MUI.YTreeItem(parent=connParent, label=label)
      child.setData(conn_id)
    itemColl.append(connParent)

    ifaceParent = MUI.YTreeItem(label=_("Interfaces"), is_open=True)
    for iface in sorted(bare_interfaces):
      label = "{}\nZone: {}".format(iface, bare_interfaces[iface])
      MUI.YTreeItem(parent=ifaceParent, label=label)
    itemColl.append(ifaceParent)

    srcParent = MUI.YTreeItem(label=_("Sources"), is_open=True)
    for source in sorted(sources):
      label = "{}\nZone: {}".format(source, sources[source])
      MUI.YTreeItem(parent=srcParent, label=label)
    itemColl.append(srcParent)

    self.activeBindingsTree.addItems(itemColl)
    self._connectionsTreeItem = connParent
    self._interfacesTreeItem  = ifaceParent
    self._sourcesTreeItem     = srcParent

  def _onBindingSelected(self, obj):
    '''Legacy stub — new handler is _onZoneTreeSelected.'''
    self._onZoneTreeSelected(obj)

  def onChangeBinding(self, obj):
    '''
    Change Zone button pressed — open zone selector for the selected connection.
    '''
    if self.activeBindingsTree is None:
      return
    item = self.activeBindingsTree.selectedItem()
    if item is None:
      return
    data = item.data()
    if not (data and isinstance(data, tuple) and data[0] == 'connection'):
      return
    conn_id = data[1]
    if conn_id not in self._nm_connections_data:
      return
    zone, ifaces, name = self._nm_connections_data[conn_id]
    self.dialog.setEnabled(False)
    dlg = changeZoneConnectionDialog.ChangeZoneConnectionDialog(self.fw, conn_id, name, zone)
    new_zone = dlg.run()
    self.dialog.setEnabled(True)
    if new_zone is not None:
      try:
        nm_set_zone_of_connection(new_zone, conn_id)
        self._fillLeftZones(self._currentItem)
      except Exception as e:
        logger.error("Failed to change zone of connection %s: %s", conn_id, e)

  def onAbout(self) :
    '''
    About dialog invoked
    '''
    common.AboutDialog(
        dialog_mode=common.AboutDialogMode.TABBED,
        size={'width': 360, 'height': 300},
    )

  def onHelp(self):
    '''
    Help menu invoked
    '''
    info = helpinfo.ManaFirewallHelpInfo()
    hd = helpdialog.HelpDialog(info)
    hd.run()


  # Legacy stubs — kept so old menu signal bindings don't crash
  def onChangeView(self):
    self.onModeChanged()

  def onEditFrameAddButtonEvent(self):
    self.onLeftAddButton()

  def onEditFrameEditButtonEvent(self):
    self.onLeftEditButton()

  def onEditFrameRemoveButtonEvent(self):
    self.onLeftRemoveButton()

  def onEditFrameLoadDefaultsButtonEvent(self):
    self.onLeftLoadDefaultsButton()

  def onAddZone(self):
    '''
    manages add zone button
    '''
    if self.runtime_view:
      return
    self._add_edit_zone(True)
    self._fillLeftZones(self._currentItem)

  def onRemoveZone(self):
    '''
    manages remove zone button
    '''
    if self.runtime_view or not self._currentItem:
      return
    zone = self.fw.config().getZoneByName(self._currentItem)
    zone.remove()
    self._currentItem = None
    self._fillLeftZones()

  def onEditZone(self):
    '''
    manages edit zone button
    '''
    if self.runtime_view:
      return
    self._add_edit_zone(False)
    self._fillLeftZones(self._currentItem)

  def onLoadDefaultsZone(self):
    '''
    manages load defaults zone Button
    '''
    if self.runtime_view or not self._currentItem:
      return
    zone = self.fw.config().getZoneByName(self._currentItem)
    zone.loadDefaults()

  def _add_edit_zone(self, add):
    '''
    adds or edit zone (parameter add True if adding)
    '''
    zoneBaseInfo = {}
    zoneBaseInfo['max_zone_name_len'] = functions.max_zone_name_len()
    if not add:
      if not self._currentItem:
        return
      zone = self.fw.config().getZoneByName(self._currentItem)
      settings = zone.getSettings()
      props = zone.get_properties()
      zoneBaseInfo['name']        = zone.get_property("name")
      zoneBaseInfo['version']     = settings.getVersion()
      zoneBaseInfo['short']       = settings.getShort()
      zoneBaseInfo['description'] = settings.getDescription()
      zoneBaseInfo['default']     = props["default"]
      zoneBaseInfo['builtin']     = props["builtin"]
      zoneBaseInfo['target']      = settings.getTarget()
      if zoneBaseInfo['target'] == DEFAULT_ZONE_TARGET:
        zoneBaseInfo['target'] = 'default'

    zoneBaseDlg = zoneBaseDialog.ZoneBaseDialog(zoneBaseInfo)
    newZoneBaseInfo = zoneBaseDlg.run()
    if newZoneBaseInfo is None:
      return

    if not add:
      if zoneBaseInfo['name']        == newZoneBaseInfo['name'] and \
         zoneBaseInfo['version']     == newZoneBaseInfo['version'] and \
         zoneBaseInfo['short']       == newZoneBaseInfo['short'] and \
         zoneBaseInfo['description'] == newZoneBaseInfo['description'] and \
         zoneBaseInfo['target']      == newZoneBaseInfo['target']:
        return
      zone = self.fw.config().getZoneByName(self._currentItem)
      if zoneBaseInfo['version']     != newZoneBaseInfo['version'] or \
         zoneBaseInfo['short']       != newZoneBaseInfo['short'] or \
         zoneBaseInfo['description'] != newZoneBaseInfo['description'] or \
         zoneBaseInfo['target']      != newZoneBaseInfo['target']:
        settings = zone.getSettings()
        settings.setVersion(newZoneBaseInfo['version'])
        settings.setShort(newZoneBaseInfo['short'])
        settings.setDescription(newZoneBaseInfo['description'])
        settings.setTarget(newZoneBaseInfo['target'])
        zone.update(settings)
      if zoneBaseInfo['name'] == newZoneBaseInfo['name']:
        return
      zone.rename(newZoneBaseInfo['name'])
      self._currentItem = newZoneBaseInfo['name']
    else:
      settings = client.FirewallClientZoneSettings()
      settings.setVersion(newZoneBaseInfo['version'])
      settings.setShort(newZoneBaseInfo['short'])
      settings.setDescription(newZoneBaseInfo['description'])
      settings.setTarget(newZoneBaseInfo['target'])
      self.fw.config().addZone(newZoneBaseInfo['name'], settings)

  def onServiceConfAddService(self, *args):
    '''
    manages add service button
    '''
    if self.runtime_view:
      return
    self._add_edit_service(True)

  def onServiceConfRemoveService(self, *args):
    '''
    manages remove service
    '''
    if self.runtime_view or not self._currentItem:
      return
    service = self.fw.config().getServiceByName(self._currentItem)
    service.remove()
    self._currentItem = None
    self._fillLeftServices()

  def onServiceConfEditService(self, *args):
    if self.runtime_view:
      return
    self._add_edit_service(False)
    self._fillLeftServices(self._currentItem)

  def onServiceConfLoadDefaultsService(self, *args):
    '''
    manages load defaults service Button
    '''
    if self.runtime_view or not self._currentItem:
      return
    service = self.fw.config().getServiceByName(self._currentItem)
    service.loadDefaults()

  def _add_edit_service(self, add):
    '''
    adds or edit service (parameter add True if adding)
    '''
    serviceBaseInfo = {}
    if not add:
      if not self._currentItem:
        return
      active_service = self._currentItem
      service = self.fw.config().getServiceByName(active_service)
      settings = service.getSettings()
      props = service.get_properties()
      serviceBaseInfo['default']     = props["default"]
      serviceBaseInfo['builtin']     = props["builtin"]
      serviceBaseInfo['name']        = service.get_property("name")
      serviceBaseInfo['version']     = settings.getVersion()
      serviceBaseInfo['short']       = settings.getShort()
      serviceBaseInfo['description'] = settings.getDescription()

    serviceBaseDlg = serviceBaseDialog.ServiceBaseDialog(serviceBaseInfo)
    newServiceBaseInfo = serviceBaseDlg.run()
    if newServiceBaseInfo is None:
      return

    if not add:
      if serviceBaseInfo['name']        == newServiceBaseInfo['name'] and \
         serviceBaseInfo['version']     == newServiceBaseInfo['version'] and \
         serviceBaseInfo['short']       == newServiceBaseInfo['short'] and \
         serviceBaseInfo['description'] == newServiceBaseInfo['description']:
        return
      service = self.fw.config().getServiceByName(self._currentItem)
      if serviceBaseInfo['version']     != newServiceBaseInfo['version'] or \
         serviceBaseInfo['short']       != newServiceBaseInfo['short'] or \
         serviceBaseInfo['description'] != newServiceBaseInfo['description']:
        settings = service.getSettings()
        settings.setVersion(newServiceBaseInfo['version'])
        settings.setShort(newServiceBaseInfo['short'])
        settings.setDescription(newServiceBaseInfo['description'])
        service.update(settings)
      if serviceBaseInfo['name'] == newServiceBaseInfo['name']:
        return
      service.rename(newServiceBaseInfo['name'])
      self._currentItem = newServiceBaseInfo['name']
    else:
      settings = client.FirewallClientServiceSettings()
      settings.setVersion(newServiceBaseInfo['version'])
      settings.setShort(newServiceBaseInfo['short'])
      settings.setDescription(newServiceBaseInfo['description'])
      self.fw.config().addService(newServiceBaseInfo['name'], settings)

  # Legacy stubs — no longer wired to any widget, kept for safety
  def onSelectedConfigurationComboChanged(self):
    self._refreshRightPane()

  def onConfigurationViewChanged(self):
    self._fillLeftCategory()

  def onSelectedConfigurationChanged(self, widgetEvent=None):
    self._refreshRightPane()


  def onTimeOutEvent(self):
    logger.debug ("Timeout occurred")

  def doSomethingIntoLoop(self):
    '''
    check on internal queue if any fw event has been managed
    '''
    try:
      # firewalld can be chatty during reload; drain up to 20 events per tick
      counter = 0
      count_max = 20 if self._reloading else 1

      while counter < count_max:
        counter += 1
        item = self.fwEventQueue.get_nowait()

        if item['event'] == 'connection-changed':
          connected = item['value']
          self.connection_lost = not connected
          t = self.connected_label if connected else self.trying_to_connect_label
          self.statusLabel.setText(t)
          if connected:
            self.fw.authorizeAll()
            default_zone = self.fw.getDefaultZone()
            self.defaultZoneLabel.setText(_("Default Zone: {}").format(default_zone))
            self.log_denied = self.fw.getLogDenied()
            self.logDeniedLabel.setText(_("  Log Denied: {}").format(self.log_denied))
            self.automatic_helpers = self.fw.getAutomaticHelpers()
            self.automaticHelpersLabel.setText(_("  Automatic Helpers: {}").format(self.automatic_helpers))
            panic = self.fw.queryPanicMode()
            t = self.enabled if panic else self.disabled
            self.panicLabel.setText(_("  Panic Mode: {}").format(t))
            self._fillLeftCategory()
            self.dialog.setEnabled(True)
          else:
            self.defaultZoneLabel.setText(_("Default Zone: {}").format("--------"))
            self.logDeniedLabel.setText(_("  Log Denied: {}").format("--------"))
            self.automaticHelpersLabel.setText(_("  Automatic Helpers: {}").format("--------"))
            self.panicLabel.setText(_("  Panic Mode: {}").format("--------"))
            self.dialog.setEnabled(False)

        elif item['event'] == 'log-denied-changed':
          self.log_denied = item['value']
          self.logDeniedLabel.setText(_("  Log Denied: {}").format(self.log_denied))
          self.dialog.setEnabled(True)
          logger.debug("Log denied changed to %s", self.log_denied)

        elif item['event'] == 'panicmode-changed':
          t = self.enabled if item['value'] else self.disabled
          self.panicLabel.setText(_("  Panic Mode: {}").format(t))

        elif item['event'] == 'default-zone-changed':
          zone = item['value']
          self.defaultZoneLabel.setText(_("Default Zone: {}").format(zone))
          # Refresh zone tree so default marker updates
          if self._currentCategory == 'zones':
            self._fillLeftZones(self._currentItem)

        elif item['event'] in ('config-zone-added', 'config-zone-updated',
                               'config-zone-renamed', 'config-zone-removed'):
          if not self.runtime_view and self._currentCategory == 'zones':
            self._fillLeftZones(self._currentItem)
            if item['event'] == 'config-zone-updated':
              self._refreshRightPane()

        elif item['event'] in ('config-service-added', 'config-service-updated',
                               'config-service-renamed', 'config-service-removed'):
          if not self.runtime_view and self._currentCategory == 'services':
            self._fillLeftServices(self._currentItem)
            if item['event'] == 'config-service-updated':
              self._refreshRightPane()

        elif item['event'] == 'config-zones-group-added':
          logger.debug("Zones group-added: %d zones", len(item['value']))
          if not self.runtime_view and self._currentCategory == 'zones':
            self._fillLeftZones(self._currentItem)

        elif item['event'] == 'config-services-group-added':
          logger.debug("Services group-added: %d services", len(item['value']))
          if not self.runtime_view and self._currentCategory == 'services':
            self._fillLeftServices(self._currentItem)

        elif item['event'] in ('service-added', 'service-removed'):
          if self.runtime_view and self._currentCategory == 'zones' and \
             self._currentRightTab == 'services':
            value = item['value']
            if value['zone'] == self._currentItem:
              self._fillRPServices()

        elif item['event'] in ('port-added', 'port-removed'):
          if self.runtime_view and self._currentCategory == 'zones' and \
             self._currentRightTab == 'ports':
            value = item['value']
            if value['zone'] == self._currentItem:
              self._fillRPPort("zone_ports")
              if self.buttons is not None:
                self.buttons['edit'].setEnabled(self.portList.itemsCount() > 0)
                self.buttons['remove'].setEnabled(self.portList.itemsCount() > 0)

        elif item['event'] in ('source-port-added', 'source-port-removed'):
          if self.runtime_view and self._currentCategory == 'zones' and \
             self._currentRightTab == 'source_ports':
            value = item['value']
            if value['zone'] == self._currentItem:
              self._fillRPPort("zone_sourceports")
              if self.buttons is not None:
                self.buttons['edit'].setEnabled(self.portList.itemsCount() > 0)
                self.buttons['remove'].setEnabled(self.portList.itemsCount() > 0)

        elif item['event'] in ('forward-port-added', 'forward-port-removed'):
          if self.runtime_view and self._currentCategory == 'zones' and \
             self._currentRightTab == 'forwarding':
            value = item['value']
            if value['zone'] == self._currentItem:
              self._fillRPForwardPorts()
              if self.buttons is not None:
                self.buttons['edit'].setEnabled(self.portForwardList.itemsCount() > 0)
                self.buttons['remove'].setEnabled(self.portForwardList.itemsCount() > 0)

        elif item['event'] in ('icmp-changed', 'icmp-inversion'):
          if self.runtime_view and self._currentCategory == 'zones' and \
             self._currentRightTab == 'icmp_filter':
            value = item['value']
            if value['zone'] == self._currentItem:
              self._fillRPICMPFilter()

        elif item['event'] in ('protocol-added', 'protocol-removed'):
          if self.runtime_view and self._currentCategory == 'zones' and \
             self._currentRightTab == 'protocols':
            value = item['value']
            if value['zone'] == self._currentItem:
              self._fillRPProtocols('zone_protocols')
              if self.buttons is not None:
                self.buttons['edit'].setEnabled(self.protocolList.itemsCount() > 0)
                self.buttons['remove'].setEnabled(self.protocolList.itemsCount() > 0)

        elif item['event'] == 'masquerade-added':
          if self.runtime_view and self._currentCategory == 'zones' and \
             self._currentRightTab == 'masquerade':
            if item['value'] == self._currentItem and not self.masquerade.isChecked():
              self.masquerade.setNotify(False)
              self.masquerade.setValue(MUI.YCheckBoxState.YCheckBox_on)
              self.masquerade.setNotify(True)

        elif item['event'] == 'masquerade-removed':
          if self.runtime_view and self._currentCategory == 'zones' and \
             self._currentRightTab == 'masquerade':
            if item['value'] == self._currentItem and self.masquerade.isChecked():
              self.masquerade.setNotify(False)
              self.masquerade.setValue(MUI.YCheckBoxState.YCheckBox_off)
              self.masquerade.setNotify(True)

        elif item['event'] == 'reloaded':
          logger.debug("Firewall reloaded event received")
          self._fillLeftCategory()
          self._reloading = False
          self.dialog.setEnabled(True)

        else:
          logger.warning("Unmanaged event: %s - value: %s",
                         item['event'], item.get('value', 'None'))

    except Empty:
      pass

