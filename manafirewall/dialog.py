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
import yui

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
import manafirewall.portDialog as portDialog
import manafirewall.forwardDialog as forwardDialog
import manafirewall.protocolDialog as protocolDialog
import manafirewall.optionDialog as optionDialog
import manafirewall.helpinfo as helpinfo

logger = logging.getLogger('manafirewall.dialog')

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

    yui.YUI.app().setApplicationIcon("manafirewall")

    basedialog.BaseDialog.__init__(self, _("Manatools - firewalld configurator"), "manafirewall", basedialog.DialogType.MAIN, 80, 20)
    self._application_name = _("{} - ManaTools firewalld configurator").format(PROJECT)

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
    self.replacePointWidgetsAndCallbacks = []
    self._reloaded = False

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

    if yui.YUI.app().isTextMode():
      self.glib_loop = GLib.MainLoop()
      self.glib_thread = threading.Thread(target=self.glib_mainloop, args=(self.glib_loop,))
      self.glib_thread.start()


  def _logger_setup(self,
                    file_name='manafirewall.log',
                    logroot='manafirewall',
                    logfmt='%(asctime)s: %(message)s',
                    loglvl=logging.INFO):
    """Setup Python logging."""
    maxbytes=10*1024*1024
    handler = logging.handlers.RotatingFileHandler(
              file_name, maxBytes=maxbytes, backupCount=5)
    logging.basicConfig(filename=file_name, format='%(asctime)s [%(name)s]{%(filename)s:%(lineno)d}(%(levelname)s) %(message)s', level=loglvl)
    logger.addHandler(handler)


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
          'quit'      : yui.YMenuItem(mItem, _("&Quit"), "application-exit"),
      }
      #Items must be "disowned"
      for k in self.fileMenu.keys():
          self.fileMenu[k].this.own(False)
      self.eventManager.addMenuEvent(self.fileMenu['quit'], self.onQuitEvent, sendObjOnEvent)

      # building Options menu
      mItem = self.menubar.addMenu(_("&Options"))
      self.optionsMenu = {
          'menu_name'  : mItem,
          'runtime_to_permanent': yui.YMenuItem(mItem, _("Runtime To Permanent"), 'document-save'),
          'reload' : yui.YMenuItem(mItem, _("&Reload Firewalld"), 'view-refresh'),
          'sep0'     : mItem.addSeparator(),
          'settings' : yui.YMenuItem(mItem, _("&Settings"), 'preferences-system'),
      }
      #Items must be "disowned"
      for k in self.optionsMenu.keys():
          self.optionsMenu[k].this.own(False)
      self.eventManager.addMenuEvent(self.optionsMenu['runtime_to_permanent'], self.onRuntimeToPermanent)
      self.eventManager.addMenuEvent(self.optionsMenu['reload'], self.onReloadFirewalld)
      self.eventManager.addMenuEvent(self.optionsMenu['settings'], self.onOptionSettings)

      # building Help menu
      mItem = self.menubar.addMenu(_("&Help"))
      self.helpMenu = {
          'menu_name': mItem,
          'help'     : yui.YMenuItem(mItem, _("&Manual"), 'help-contents'),
          'sep0'     : mItem.addSeparator(),
          'about'    : yui.YMenuItem(mItem, _("&About"), 'manafirewall'),
      }
      #Items must be "disowned"
      for k in self.helpMenu.keys():
          self.helpMenu[k].this.own(False)
      self.eventManager.addMenuEvent(self.helpMenu['help'], self.onHelp)
      self.eventManager.addMenuEvent(self.helpMenu['about'], self.onAbout)

      self.menubar.resolveShortcutConflicts()
      self.menubar.rebuildMenuTree()
    else:
      # Legacy support to YMenuButton widgets
      # Menu widget
      self.file_menu = self.factory.createMenuButton(menu_line, _("&File"))
      qm = yui.YMenuItem(_("&Quit"))
      self.file_menu.addItem(qm)
      self.file_menu.rebuildMenuTree()
      self.eventManager.addMenuEvent(qm, self.onQuitEvent, sendObjOnEvent)

      self.option_menu = self.factory.createMenuButton(menu_line, _("&Options"))
      rfwm = yui.YMenuItem(_("&Reload Firewalld"))
      self.option_menu.addItem(rfwm)
      self.option_menu.rebuildMenuTree()
      self.eventManager.addMenuEvent(rfwm, self.onReloadFirewalld)

      # Help menu is the last on the right
      align = self.factory.createRight(menu_line)
      self.help_menu = self.factory.createMenuButton(align, _("&Help"))
      hm = yui.YMenuItem(_("&Manual"))
      self.help_menu.addItem(hm)
      am = yui.YMenuItem(_("&About"))
      self.help_menu.addItem(am)
      self.help_menu.rebuildMenuTree()
      self.eventManager.addMenuEvent(hm, self.onHelp)
      self.eventManager.addMenuEvent(am, self.onAbout)
    ### END Menus #########################


    # _______
    #|   |   |
    #
    cols = self.factory.createHBox(layout)
    col1 = self.factory.createVBox(cols)
    col2 = self.factory.createVBox(cols)

    # Column 1
    self.activeBindingsTree = self.factory.createTree(col1, _("Active bindings"))
    col1.setWeight(yui.YD_HORIZ, 30)
    changeBindingsButton = self.factory.createPushButton(col1, _("&Change binding") )
    self.eventManager.addWidgetEvent(changeBindingsButton, self.onChangeBinding, sendObjOnEvent)
    #### editFrameBox contains button to modify zones (add, remove, edit, load defaults)
    self.editFrameBox = self.factory.createFrame(col1, _("Edit zones"))
    hbox = self.factory.createHBox( self.editFrameBox )
    vbox1 = self.factory.createVBox(hbox)
    vbox2 = self.factory.createVBox(hbox)
    editFrameAddButton          = self.factory.createPushButton(vbox1, _("&Add") )
    self.eventManager.addWidgetEvent(editFrameAddButton, self.onEditFrameAddButtonEvent)
    editFrameEditButton         = self.factory.createPushButton(vbox1, _("&Edit") )
    self.eventManager.addWidgetEvent(editFrameEditButton, self.onEditFrameEditButtonEvent)
    editFrameRemoveButton       = self.factory.createPushButton(vbox2, _("&Remove") )
    self.eventManager.addWidgetEvent(editFrameRemoveButton, self.onEditFrameRemoveButtonEvent)
    editFrameLoadDefaultsButton = self.factory.createPushButton(vbox2, _("&Load default") )
    self.eventManager.addWidgetEvent(editFrameLoadDefaultsButton, self.onEditFrameLoadDefaultsButtonEvent)
    self.editFrameBox.setEnabled(False)

    # Column 2
    align = self.factory.createTop(col2) #self.factory.createLeft(col2)
    align = self.factory.createLeft(align)
    hbox = self.factory.createHBox(align)
    col2.setWeight(yui.YD_HORIZ, 80)

    self.views = {
            'runtime'   : {'title' : _("Runtime"), 'item' : None},
            'permanent' : {'title' : _("Permanent"), 'item' : None},
        }
    ordered_views = [ 'runtime', 'permanent' ]

    self.currentViewCombobox = self.factory.createComboBox(hbox,_("Configuration"))
    itemColl = yui.YItemCollection()

    for v in ordered_views:
      item = yui.YItem(self.views[v]['title'], False)
      show_item = 'runtime'
      if show_item == v :
          item.setSelected(True)
      # adding item to views to find the item selected
      self.views[v]['item'] = item
      itemColl.push_back(item)
      item.this.own(False)

    self.currentViewCombobox.addItems(itemColl)
    self.currentViewCombobox.setNotify(True)
    self.eventManager.addWidgetEvent(self.currentViewCombobox, self.onChangeView)

    # mainNotebook (configure combo box)
    # TODO icmp_types, helpers, direct_configurations, lockdown_whitelist
    self.configureViews = {
            'zones'    : {'title' : _("Zones"), 'item' : None},
            'services' : {'title' : _("Services"), 'item' : None},
            'ipsets'   : {'title' : _("IP Sets"), 'item' : None},
    }
    ordered_configureViews = [ 'zones', 'services', 'ipsets' ]
    self.configureViewCombobox = self.factory.createComboBox(hbox,_("View"))
    itemColl = yui.YItemCollection()

    for v in ordered_configureViews:
      item = yui.YItem(self.configureViews[v]['title'], False)
      show_item = 'zones'
      if show_item == v :
          item.setSelected(True)
      # adding item to views to find the item selected
      self.configureViews[v]['item'] = item
      itemColl.push_back(item)
      item.this.own(False)

    self.configureViewCombobox.addItems(itemColl)
    self.configureViewCombobox.setNotify(True)
    self.eventManager.addWidgetEvent(self.configureViewCombobox, self.onConfigurationViewChanged)

    # selectedConfigurationCombo is filled if requested by selected configuration view (which zones, services ...)
    self.selectedConfigurationCombo = self.factory.createComboBox(hbox,"     ")
    # adding a dummy item to enlarge combobox
    item = yui.YItem("--------------------", False)
    item.this.own(False)
    self.selectedConfigurationCombo.addItem(item)
    self.selectedConfigurationCombo.setEnabled(False)
    self.selectedConfigurationCombo.setNotify(True)
    self.eventManager.addWidgetEvent(self.selectedConfigurationCombo, self.onSelectedConfigurationComboChanged)

    ###
    # ZoneNotebook and other (combo box to configure selected thing)
    self.zoneConfigurationView = {
            'services'        : {'title' : _("Services"), 'item' : None},
            'ports'           : {'title' : _("Ports"), 'item' : None},
            'protocols'       : {'title' : _("Protocols"), 'item' : None},
            'source_ports'    : {'title' : _("Source Ports"), 'item' : None},
            'masquerading'    : {'title' : _("Masquerading"), 'item' : None},
            'port_forwarding' : {'title' : _("Port Forwarding"), 'item' : None},
            'icmp_filter'     : {'title' : _("ICMP Filter"), 'item' : None},
            'rich_rules'      : {'title' : _("Rich Rules"), 'item' : None},
            'interfaces'      : {'title' : _("Interfaces"), 'item' : None},
            'sources'         : {'title' : _("Sources"), 'item' : None},
    }
    # ServiceNotebook
    self.serviceConfigurationView = {
      'ports'         : {'title' : _("Ports"), 'item' : None},
      'protocols'     : {'title' : _("Protocols"), 'item' : None},
      'source_ports'  : {'title' : _("Source Ports"), 'item' : None},
      'modules'       : {'title' : _("Modules"), 'item' : None},
      'destinations'  : {'title' : _("Destinations"), 'item' : None},
    }
    # ServiceNotebook
    self.ipsecConfigurationView = {
      'entries'       : {'title' : _("Entries"), 'item' : None},
    }
    self.configureCombobox = self.factory.createComboBox(hbox,_("Configure"))
    # adding a dummy item to enlarge combobox
    itemColl = self._zoneConfigurationViewCollection()
    self.configureCombobox.addItems(itemColl)
    self.configureCombobox.setNotify(True)
    self.eventManager.addWidgetEvent(self.configureCombobox, self.onSelectedConfigurationChanged)
    ###

    #### Replace Point to change configuration view
    self.replacePoint = self.factory.createReplacePoint(col2)
    self.replacePoint.setWeight(yui.YD_VERT, 80)

    #### bottom status lines
    align = self.factory.createLeft(layout)
    statusLine = self.factory.createHBox(align)
    self.statusLabel = self.factory.createLabel(statusLine, self.failed_to_connect_label)
    align = self.factory.createLeft(layout)
    statusLine = self.factory.createHBox(align)
    self.defaultZoneLabel  = self.factory.createLabel(statusLine,     _("Default Zone: {}").format("--------"))
    self.logDeniedLabel = self.factory.createLabel(statusLine,        _("Log Denied: {}").format("--------"))
    self.panicLabel = self.factory.createLabel(statusLine,            _("Panic Mode: {}").format("--------"))
    self.automaticHelpersLabel = self.factory.createLabel(statusLine, _("Automatic Helpers: {}").format("--------"))
    self.lockdownLabel = self.factory.createLabel(statusLine,         _("Lockdown: {}").format("--------"))

    #### buttons on the last line
    align = self.factory.createRight(layout)
    bottomLine = self.factory.createHBox(align)
    aboutButton = self.factory.createPushButton(bottomLine, _("&About") )
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
    settings = None
    selected_serviceitem = self.selectedConfigurationCombo.selectedItem()
    if selected_serviceitem:
      selected_service = selected_serviceitem.label()
      if self.runtime_view:
        # load runtime configuration
        settings = self.fw.getServiceSettings(selected_service)
      else:
        try:
          service = self.fw.config().getServiceByName(selected_service)
        except:
          return settings
        # load permanent configuration
        settings = service.getSettings()

    return settings

  def _zoneSettings(self):
    '''
    returns current zone settings
    '''
    settings = None
    selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
    if selected_zoneitem:
      selected_zone = selected_zoneitem.label()
      if self.runtime_view:
        # load runtime configuration
        try:
          settings = self.fw.getZoneSettings(selected_zone)
        except:
          return settings
      else:
        # load permanent configuration
        try:
          zone = self.fw.config().getZoneByName(selected_zone)
        except:
          return settings
        settings = zone.getSettings()

    return settings

  def _AddEditRemoveButtons(self, container):
    '''
    adds Add, Edit and Remove buttons on the left of the given container
    returns a widget dictionary which keys are 'add', 'edit' and 'remove'
    '''
    buttons = None
    if isinstance(container, yui.YLayoutBox):
      buttons = { 'add' : None, 'edit': None, 'remove': None }
      align = self.factory.createLeft(container)
      hbox = self.factory.createHBox(align)
      buttons['add']    = self.factory.createPushButton(hbox, _("A&dd"))
      buttons['edit']   = self.factory.createPushButton(hbox, _("&Edit"))
      buttons['remove'] = self.factory.createPushButton(hbox, _("&Remove"))
    return buttons

  def _createSingleCBItem(self, checked, strValue):
    '''
    create a YCBTableItem with given data and return it
    Note that it also disowns either cells or item itself
    '''
    cells =  list([
                    yui.YCBTableCell( checked ),
                    yui.YCBTableCell( strValue ),
                    ])
    for cell in cells:
        cell.this.own(False)
    item = yui.YCBTableItem( *cells )
    item.this.own(False)
    return item

  def _replacePointICMP(self):
    '''
    draw icmp filter frame
    '''
    if len(self.replacePointWidgetsAndCallbacks) > 0:
      logger.error("Error there are still widget events for ReplacePoint")
      return

    if self.replacePoint.hasChildren():
      logger.error("Error there are still widgets into ReplacePoint")
      return

    hbox = self.factory.createHBox(self.replacePoint)

    table_header = yui.YCBTableHeader()
    columns = [ _('ICMP Filter') ]

    checkboxed = True
    table_header.addColumn("", checkboxed)
    for col in (columns):
        table_header.addColumn(col, not checkboxed)

    self.icmpFilterList = self.mgaFactory.createCBTable(hbox, table_header)
    self.icmpFilterInversionCheck   = self.factory.createCheckBox(hbox, _("Selected are accepted"), False)
    self.icmpFilterInversionCheck.setNotify(True)


    self._fillRPICMPFilter()
    self.icmpFilterList.setImmediateMode(True)

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
      if current:
        current = yui.toYTableItem(current)
      current_icmp = current.cell(0).label() if current else ""
      v = []
      for icmp in icmp_types:
        item = self._createSingleCBItem(icmp in configured_icmp, icmp)
        item.setSelected(icmp == current_icmp)
        v.append(item)

      #NOTE workaround to get YItemCollection working in python
      itemCollection = yui.YItemCollection(v)
      self.icmpFilterList.startMultipleChanges()
      # cleanup old changed items since we are removing all of them
      self.icmpFilterList.setChangedItem(None)
      self.icmpFilterList.deleteAllItems()
      self.icmpFilterList.addItems(itemCollection)
      self.icmpFilterList.doneMultipleChanges()

      self.icmpFilterInversionCheck.setNotify(False)
      self.icmpFilterInversionCheck.setValue(yui.YCheckBox_on if icmp_block_inversion else yui.YCheckBox_off)
      self.icmpFilterInversionCheck.setNotify(True)


  def _replacePointMasquerade(self):
    '''
    draw Port frame
    '''
    if len(self.replacePointWidgetsAndCallbacks) > 0:
      logger.error("Error there are still widget events for ReplacePoint")
      return

    if self.replacePoint.hasChildren():
      logger.error("Error there are still widgets into ReplacePoint")
      return

    vbox = self.factory.createVBox(self.replacePoint)
    align = self.factory.createLeft(vbox)
    self.masquerade   = self.factory.createCheckBox(align, _("Masquerade zone"), False)
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
    self.masquerade.setValue(yui.YCheckBox_on if masquerade else yui.YCheckBox_off)
    self.masquerade.setNotify(True)

  def _replacePointProtocols(self, context):
    '''
    draw Port frame
    '''
    if len(self.replacePointWidgetsAndCallbacks) > 0:
      logger.error("Error there are still widget events for ReplacePoint")
      return

    if self.replacePoint.hasChildren():
      logger.error("Error there are still widgets into ReplacePoint")
      return

    vbox = self.factory.createVBox(self.replacePoint)

    port_header = yui.YTableHeader()
    columns = [ _('Protocol') ]

    for col in (columns):
        port_header.addColumn(col)

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

    current_protocol = ""
    current = self.protocolList.selectedItem()
    if current:
      current_protocol = current.label()

    v = []
    for protocol in protocols:
      item = yui.YTableItem(protocol)
      item.setSelected(protocol == current_protocol)
      item.this.own(False)
      v.append(item)

    #NOTE workaround to get YItemCollection working in python
    itemCollection = yui.YItemCollection(v)
    self.protocolList.startMultipleChanges()
    self.protocolList.deleteAllItems()
    self.protocolList.addItems(itemCollection)
    self.protocolList.doneMultipleChanges()

  def _replacePointPort(self, context):
    '''
    draw Port frame
    '''
    if len(self.replacePointWidgetsAndCallbacks) > 0:
      logger.error("Error there are still widget events for ReplacePoint")
      return

    if self.replacePoint.hasChildren():
      logger.error("Error there are still widgets into ReplacePoint")
      return

    vbox = self.factory.createVBox(self.replacePoint)

    port_header = yui.YTableHeader()
    columns = [ _('Port'), _('Protocol') ]

    for col in (columns):
        port_header.addColumn(col)

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
    ports = None
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

    current_port = ""
    current = self.portList.selectedItem()
    #### TODO try to select the same

    v = []
    for port in ports:
      item = yui.YTableItem(*port)
      #item.setSelected(service == current_service)
      item.this.own(False)
      v.append(item)

    #NOTE workaround to get YItemCollection working in python
    itemCollection = yui.YItemCollection(v)
    self.portList.startMultipleChanges()
    self.portList.deleteAllItems()
    self.portList.addItems(itemCollection)
    self.portList.doneMultipleChanges()

  def _replacePointServices(self):
    '''
    draw services frame
    '''
    if len(self.replacePointWidgetsAndCallbacks) > 0:
      logger.error("Error there are still widget events for ReplacePoint")
      return

    if self.replacePoint.hasChildren():
      logger.error("Error there are still widgets into ReplacePoint")
      return

    vbox = self.factory.createVBox(self.replacePoint)

    services_header = yui.YCBTableHeader()
    columns = [ _('Service') ]

    checkboxed = True
    services_header.addColumn("", checkboxed)
    for col in (columns):
        services_header.addColumn(col, not checkboxed)

    self.serviceList = self.mgaFactory.createCBTable(vbox, services_header)

    self._fillRPServices()
    self.serviceList.setImmediateMode(True)

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
      if current:
        current = yui.toYTableItem(current)
      current_service = current.cell(0).label() if current else ""
      v = []
      for service in services:
        item = self._createSingleCBItem(service in configured_services, service)
        item.setSelected(service == current_service)
        v.append(item)

      #NOTE workaround to get YItemCollection working in python
      itemCollection = yui.YItemCollection(v)
      self.serviceList.startMultipleChanges()
      # cleanup old changed items since we are removing all of them
      self.serviceList.setChangedItem(None)
      self.serviceList.deleteAllItems()
      self.serviceList.addItems(itemCollection)
      self.serviceList.doneMultipleChanges()

  def _replacePointForwardPorts(self):
    '''
    draw Port frame
    '''
    if len(self.replacePointWidgetsAndCallbacks) > 0:
      logger.error("Error there are still widget events for ReplacePoint")
      return

    if self.replacePoint.hasChildren():
      logger.error("Error there are still widgets into ReplacePoint")
      return

    vbox = self.factory.createVBox(self.replacePoint)

    port_header = yui.YTableHeader()
    columns = [ _('Port'), _('Protocol'), _("To Port"), _("To Address") ]

    for col in (columns):
        port_header.addColumn(col)

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
        item = yui.YTableItem(*port)
        #item.setSelected(service == current_service)
        item.this.own(False)
        v.append(item)

      #NOTE workaround to get YItemCollection working in python
      itemCollection = yui.YItemCollection(v)
      self.portForwardList.startMultipleChanges()
      self.portForwardList.deleteAllItems()
      self.portForwardList.addItems(itemCollection)
      self.portForwardList.doneMultipleChanges()

  def onRPICMPFilterChecked(self, widgetEvent):
    '''
    works on enabling/disabling icmp filter for zone
    '''
    if (widgetEvent.reason() == yui.YEvent.ValueChanged) :
      item = self.icmpFilterList.changedItem()
      if item:
        cb_column = 0
        label_column = 1
        selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
        if selected_zoneitem:
          selected_zone = selected_zoneitem.label()
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
    selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
    if selected_zoneitem:
      selected_zone = selected_zoneitem.label()
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
    if (widgetEvent.reason() == yui.YEvent.ValueChanged) :
      item = self.serviceList.changedItem()
      if item:
        cb_column = 0
        label_column = 1
        selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
        if selected_zoneitem:
          selected_zone = selected_zoneitem.label()
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
    selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
    if selected_zoneitem:
      selected_zone = selected_zoneitem.label()
      selected_portitem = yui.toYTableItem(self.portList.selectedItem());
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
    selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
    if selected_zoneitem:
      selected_zone = selected_zoneitem.label()

      oldPortInfo = {'port_range': "", 'protocol': ""}
      if not add:
        selected_portitem = yui.toYTableItem(self.portList.selectedItem());
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
    selected_serviceitem = self.selectedConfigurationCombo.selectedItem()
    if selected_serviceitem:
      active_service = selected_serviceitem.label()
      selected_portitem = yui.toYTableItem(self.portList.selectedItem());
      if selected_portitem:
        port_range = selected_portitem.cell(0).label()
        protocol   = selected_portitem.cell(1).label()

        service = self.fw.config().getServiceByName(active_service)
        service.removePort(port_range, protocol)

  def _service_conf_add_edit_port(self, add):
    '''
    add, edit or remove port from a service (add is True for new port)
    '''
    selected_serviceitem = self.selectedConfigurationCombo.selectedItem()
    if selected_serviceitem:
      active_service = selected_serviceitem.label()

      oldPortInfo = {'port_range': "", 'protocol': ""}
      if not add:
        selected_portitem = yui.toYTableItem(self.portList.selectedItem());
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
    selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
    if selected_zoneitem:
      selected_zone = selected_zoneitem.label()

      oldInfo = {'protocol': ""}
      if not add:
        selected_protocol = yui.toYTableItem(self.protocolList.selectedItem());
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
    selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
    if selected_zoneitem:
      selected_zone = selected_zoneitem.label()
      selected_portitem = yui.toYTableItem(self.protocolList.selectedItem());
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
    selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
    if selected_zoneitem:
      selected_zone = selected_zoneitem.label()

      oldPortInfo = {'port_range': "", 'protocol': ""}
      if not add:
        selected_portitem = yui.toYTableItem(self.portList.selectedItem());
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
    selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
    if selected_zoneitem:
      selected_zone = selected_zoneitem.label()
      selected_portitem = yui.toYTableItem(self.portList.selectedItem());
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
    selected_serviceitem = self.selectedConfigurationCombo.selectedItem()
    if selected_serviceitem:
      active_service = selected_serviceitem.label()
      selected_portitem = yui.toYTableItem(self.portList.selectedItem());
      if selected_portitem:
        port_range = selected_portitem.cell(0).label()
        protocol   = selected_portitem.cell(1).label()

        service = self.fw.config().getServiceByName(active_service)
        service.removeSourcePort(port_range, protocol)

  def _service_conf_add_edit_source_port(self, add):
    '''
    add or edit source port from a service (add is True for new port)
    '''
    selected_serviceitem = self.selectedConfigurationCombo.selectedItem()
    if selected_serviceitem:
      active_service = selected_serviceitem.label()

      oldPortInfo = {'port_range': "", 'protocol': ""}
      if not add:
        selected_portitem = yui.toYTableItem(self.portList.selectedItem());
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
    selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
    if selected_zoneitem:
      selected_zone = selected_zoneitem.label()

      oldPortForwardingInfo = {'port': "", 'protocol': "", 'to_port': "", 'to_address': "" }
      if not add:
        selected_portitem = yui.toYTableItem(self.portForwardList.selectedItem());
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
    selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
    if selected_zoneitem:
      selected_zone = selected_zoneitem.label()
      selected_portitem = yui.toYTableItem(self.portForwardList.selectedItem());
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
    selected_serviceitem = self.selectedConfigurationCombo.selectedItem()
    if selected_serviceitem:
      active_service = selected_serviceitem.label()

      oldInfo = {'protocol': ""}
      if not add:
        selected_protocol = yui.toYTableItem(self.protocolList.selectedItem());
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
    selected_serviceitem = self.selectedConfigurationCombo.selectedItem()
    if selected_serviceitem:
      active_service = selected_serviceitem.label()
      selected_portitem = yui.toYTableItem(self.protocolList.selectedItem());
      if selected_portitem:
        protocol   = selected_portitem.cell(0).label()

        service = self.fw.config().getServiceByName(active_service)
        service.removeProtocol(protocol)

  def onZoneMasquerade(self):
    '''
    Zone masquerade has changed
    '''
    view_item = self.configureViewCombobox.selectedItem()
    if view_item == self.configureViews['zones']['item']:
      selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
      if selected_zoneitem:
        selected_zone = selected_zoneitem.label()
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
    view_item = self.configureViewCombobox.selectedItem()
    isZones = (view_item == self.configureViews['zones']['item'])
    isServices = (view_item == self.configureViews['services']['item'])

    configure_item = self.configureCombobox.selectedItem()
    isZonePort = (configure_item == self.zoneConfigurationView['ports']['item'])
    isZoneSourcePort = (configure_item == self.zoneConfigurationView['source_ports']['item'])
    isZoneForwardPort = (configure_item == self.zoneConfigurationView['port_forwarding']['item'])
    isZoneProtocol = (configure_item == self.zoneConfigurationView['protocols']['item'])
    isServicePort = (configure_item == self.serviceConfigurationView['ports']['item'])
    isServiceSourcePort = (configure_item == self.serviceConfigurationView['source_ports']['item'])
    isServiceProtocol = (configure_item == self.serviceConfigurationView['protocols']['item'])

    if isinstance(button, yui.YPushButton):
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
    itemColl = yui.YItemCollection()
    for v in ordered_configureViews:
      item = yui.YItem(self.zoneConfigurationView[v]['title'], False)
      show_item = 'services'
      if show_item == v :
          item.setSelected(True)
      # adding item to views to find the item selected
      self.zoneConfigurationView[v]['item'] = item
      itemColl.push_back(item)
      item.this.own(False)

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
    itemColl = yui.YItemCollection()
    for v in ordered_Views:
      item = yui.YItem(self.serviceConfigurationView[v]['title'], False)
      show_item = 'ports'
      if show_item == v :
          item.setSelected(True)
      # adding item to views to find the item selected
      self.serviceConfigurationView[v]['item'] = item
      itemColl.push_back(item)
      item.this.own(False)
    return itemColl

  def _ipsecConfigurationViewCollection(self):
    '''
    returns an YItemCollection containing IPSEC configuration views
    '''
    ordered_Views = [
      'entries',
    ]
    itemColl = yui.YItemCollection()
    for v in ordered_Views:
      item = yui.YItem(self.ipsecConfigurationView[v]['title'], False)
      show_item = 'entries'
      if show_item == v :
          item.setSelected(True)
      # adding item to views to find the item selected
      self.ipsecConfigurationView[v]['item'] = item
      itemColl.push_back(item)
      item.this.own(False)

    return itemColl

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
    self.fw.connect("lockdown-enabled", self.lockdown_enabled_cb)
    self.fw.connect("lockdown-disabled", self.lockdown_disabled_cb)
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

    self.fw.connect("zone-of-interface-changed", self.zone_of_interface_changed_cb)
    self.fw.connect("reloaded", self.reload_cb)

  def load_zones(self, selected = None):
    '''
    load zones into selectedConfigurationCombo
    '''
    self.selectedConfigurationCombo.startMultipleChanges()
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
    itemColl = yui.YItemCollection()
    for zone in zones:
      item = yui.YItem(zone, False)
      if zone == selected_zone:
        item.setSelected(True)
      itemColl.push_back(item)
      item.this.own(False)

    self.selectedConfigurationCombo.addItems(itemColl)
    self.selectedConfigurationCombo.doneMultipleChanges()


  def load_services(self, service_name = None):
    '''
    load services into selectedConfigurationCombo
    '''
    self.selectedConfigurationCombo.startMultipleChanges()
    self.selectedConfigurationCombo.deleteAllItems()

    self.selectedConfigurationCombo.setEnabled(True)
    self.selectedConfigurationCombo.setLabel(self.configureViews['services']['title'])

    services = []
    if self.runtime_view:
      services = self.fw.listServices()
    else:
      services = self.fw.config().getServiceNames()

    # services
    itemColl = yui.YItemCollection()
    for service in services:
      item = yui.YItem(service, False)
      if service == service_name:
        item.setSelected(True)
      itemColl.push_back(item)
      item.this.own(False)

    self.selectedConfigurationCombo.addItems(itemColl)
    self.selectedConfigurationCombo.doneMultipleChanges()


  def load_ipsets(self):
    '''
    load ipsets into selectedConfigurationCombo
    '''
    self.selectedConfigurationCombo.startMultipleChanges()
    self.selectedConfigurationCombo.deleteAllItems()

    self.selectedConfigurationCombo.setEnabled(True)
    self.selectedConfigurationCombo.setLabel(self.configureViews['ipsets']['title'])

    ipsets = []
    if self.runtime_view:
        ipsets = self.fw.getIPSets()
    else:
        ipsets = self.fw.config().getIPSetNames()

    # ipsets
    itemColl = yui.YItemCollection()
    for ipset in ipsets:
      item = yui.YItem(ipset, False)
      itemColl.push_back(item)
      item.this.own(False)

    self.selectedConfigurationCombo.addItems(itemColl)
    self.selectedConfigurationCombo.doneMultipleChanges()


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

  def lockdown_enabled_cb(self):
    '''
    manage lockdown enabled evend from firewalld
    '''
    self.fwEventQueue.put({'event': "lockdown-changed", 'value': True})

  def lockdown_disabled_cb(self):
    '''
    manage lockdown disabled evend from firewalld
    '''
    self.fwEventQueue.put({'event': "lockdown-changed", 'value': False})

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


  def zone_of_interface_changed_cb(self, zone, interface):
    logger.debug("zone_of_interface_changed_cb %s - %s", zone, interface)

  def reload_cb(self):
    '''
    firewalld reloaded event
    '''
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

  def onQuitEvent(self, obj) :
    '''
    Exit by using quit button or menu
    '''
    if isinstance(obj, yui.YItem):
      logger.info("Quit menu pressed")
    else:
      logger.info("Quit button pressed")
    self.saveUserPreference()

    if yui.YUI.app().isTextMode():
      self.glib_loop.quit()
    # BaseDialog needs to force to exit the handle event loop
    self.ExitLoop()
    if yui.YUI.app().isTextMode():
      self.glib_thread.join()

  def onOptionSettings(self):
    '''
    Show optionDialog for extended settings
    '''
    up = optionDialog.OptionDialog(self)
    up.run()

  def onReloadFirewalld(self):
    '''
    Reload Firewalld menu pressed
    '''
    self._reloaded = True
    self.dialog.setEnabled(False)
    self.fw.reload()

  def onRuntimeToPermanent(self):
    '''
    Make runtime configuration permanent
    '''
    self.fw.runtimeToPermanent()

  def onChangeBinding(self, obj):
    '''
    manages changeBindingsButton button pressed
    '''
    logger.debug ("TODO: Change binding pressed")

  def onAbout(self) :
    '''
    About dialog invoked
    '''
    ok = common.AboutDialog({
          'name' : self._application_name,
          'dialog_mode' : common.AboutDialogMode.TABBED,
          'version' : VERSION,
          'credits' : _("Credits {}").format("2019-2022 Angelo Naselli"),
          'license' : 'GPLv2+',
          'authors' : 'Angelo Naselli &lt;anaselli@linux.it&gt;',
          'description' : _("{}  is a graphical configuration tool for firewalld.").format(PROJECT),
          'size': {'column': 50, 'lines': 6},
    })

  def onHelp(self):
    '''
    Help menu invoked
    '''
    info = helpinfo.ManaFirewallHelpInfo()
    hd = helpdialog.HelpDialog(info)
    hd.run()


  def onChangeView(self):
    '''
    manages currentViewCombobox chenges
    '''
    item = self.currentViewCombobox.selectedItem()
    self.runtime_view = item == self.views['runtime']['item']
    # Let's change view as if a new configuration has been chosen
    self.onConfigurationViewChanged()
    self.editFrameBox.setEnabled(not self.runtime_view)


  def onEditFrameAddButtonEvent(self):
    '''
    from edit frame Add has benn pressed, let's call the right add event
    '''
    item = self.configureViewCombobox.selectedItem()
    if item == self.configureViews['zones']['item']:
      #Zones selected
      self.onAddZone()
    elif item == self.configureViews['services']['item']:
      #Services selected
      self.onServiceConfAddService()
    elif item == self.configureViews['ipsets']['item']:
      # ip sets selected
      pass

  def onEditFrameEditButtonEvent(self):
    '''
    from edit frame Edit has benn pressed, let's call the right edit event
    '''
    item = self.configureViewCombobox.selectedItem()
    if item == self.configureViews['zones']['item']:
      #Zones selected
      self.onEditZone()
    elif item == self.configureViews['services']['item']:
      #Services selected
      self.onServiceConfEditService()
    elif item == self.configureViews['ipsets']['item']:
      # ip sets selected
      pass

  def onEditFrameRemoveButtonEvent(self):
    '''
    from edit frame Remove has benn pressed, let's call the right remove event
    '''
    item = self.configureViewCombobox.selectedItem()
    if item == self.configureViews['zones']['item']:
      #Zones selected
      self.onRemoveZone()
    elif item == self.configureViews['services']['item']:
      #Services selected
      self.onServiceConfRemoveService()
    elif item == self.configureViews['ipsets']['item']:
      # ip sets selected
      pass

  def onEditFrameLoadDefaultsButtonEvent(self):
    '''
    from edit frame Remove has benn pressed, let's call the right remove event
    '''
    item = self.configureViewCombobox.selectedItem()
    if item == self.configureViews['zones']['item']:
      #Zones selected
      self.onLoadDefaultsZone()
    elif item == self.configureViews['services']['item']:
      #Services selected
      self.onServiceConfLoadDefaultsService()
    elif item == self.configureViews['ipsets']['item']:
      # ip sets selected
      pass

  def onAddZone(self):
    '''
    manages add zone button
    '''
    if self.runtime_view:
      return
    self._add_edit_zone(True)
    self.load_zones()

  def onRemoveZone(self):
    '''
    manages remove zone button
    '''
    if self.runtime_view:
      return
    selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
    if selected_zoneitem:
      selected_zone = selected_zoneitem.label()
      zone = self.fw.config().getZoneByName(selected_zone)
      zone.remove()
      self.load_zones()
      # TODO self.onChangeZone()

  def onEditZone(self):
    '''
    manages edit zone button
    '''
    if self.runtime_view:
      return
    self._add_edit_zone(False)
    selected_zone = None
    selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
    if selected_zoneitem:
      selected_zone = selected_zoneitem.label()
    self.load_zones(selected_zone)

  def onLoadDefaultsZone(self):
    '''
    manages load defaults zone Button
    '''
    if self.runtime_view:
      return
    selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
    if selected_zoneitem:
      selected_zone = selected_zoneitem.label()
      zone = self.fw.config().getZoneByName(selected_zone)
      zone.loadDefaults()
      # TODO self.onChangeZone()

  def _add_edit_zone(self, add):
    '''
    adds or edit zone (parameter add True if adding)
    '''
    zoneBaseInfo = {}
    zoneBaseInfo['max_zone_name_len'] = functions.max_zone_name_len()
    if not add:
      # fill zoneBaseInfo for zoneBaseDialog fields
      selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
      if selected_zoneitem:
        selected_zone = selected_zoneitem.label()
        zone = self.fw.config().getZoneByName(selected_zone)
        settings = zone.getSettings()
        props = zone.get_properties()
        zoneBaseInfo['name'] = zone.get_property("name")
        zoneBaseInfo['version'] = settings.getVersion()
        zoneBaseInfo['short'] = settings.getShort()
        zoneBaseInfo['description'] = settings.getDescription()
        zoneBaseInfo['default'] = props["default"]
        zoneBaseInfo['builtin'] = props["builtin"]
        zoneBaseInfo['target'] = settings.getTarget()
        if zoneBaseInfo['target'] == DEFAULT_ZONE_TARGET:
          zoneBaseInfo['target'] = 'default'

    zoneBaseDlg = zoneBaseDialog.ZoneBaseDialog(zoneBaseInfo)
    newZoneBaseInfo = zoneBaseDlg.run()
    # Cancelled if None is returned
    if newZoneBaseInfo is None:
      return

    if not add:
      if zoneBaseInfo['name']        == newZoneBaseInfo['name'] and \
         zoneBaseInfo['version']     == newZoneBaseInfo['version'] and  \
         zoneBaseInfo['short']       == newZoneBaseInfo['short'] and \
         zoneBaseInfo['description'] == newZoneBaseInfo['description'] and \
         zoneBaseInfo['target']      == newZoneBaseInfo['target']:
        # no changes
        return
      selected_zoneitem = self.selectedConfigurationCombo.selectedItem()
      if selected_zoneitem:
        selected_zone = selected_zoneitem.label()
        zone = self.fw.config().getZoneByName(selected_zone)
        if zoneBaseInfo['version'] != newZoneBaseInfo['version'] or  \
         zoneBaseInfo['short'] != newZoneBaseInfo['short'] or \
         zoneBaseInfo['description'] != newZoneBaseInfo['description'] or \
         zoneBaseInfo['target'] != newZoneBaseInfo['target']:
          settings = zone.getSettings()
          settings.setVersion(newZoneBaseInfo['version'])
          settings.setShort(newZoneBaseInfo['short'])
          settings.setDescription(newZoneBaseInfo['description'])
          settings.setTarget(newZoneBaseInfo['target'])
          zone.update(settings)
        if zoneBaseInfo['name'] == newZoneBaseInfo['name']:
          return
        zone.rename(newZoneBaseInfo['name'])
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
    manages remove zone button
    '''
    if self.runtime_view:
      return
    selected_item = self.selectedConfigurationCombo.selectedItem()
    if selected_item:
      active_service = selected_item.label()
      service = self.fw.config().getServiceByName(active_service)
      service.remove()
      self.load_services()
      # TODO self.onChangeService()

  def onServiceConfEditService(self, *args):
    if self.runtime_view:
      return
    self._add_edit_service(False)

  def onServiceConfLoadDefaultsService(self, *args):
    '''
    manages load defaults service Button
    '''
    if self.runtime_view:
      return
    selected_item = self.selectedConfigurationCombo.selectedItem()
    if selected_item:
      active_service = selected_item.label()
      service = self.fw.config().getServiceByName(active_service)
      service.loadDefaults()
      # TODO self.onChangeService()

  def _add_edit_service(self, add):
    '''
    adds or edit service (parameter add True if adding)
    '''
    serviceBaseInfo = {}
    if not add:
      # fill serviceBaseInfo for serviceBaseDialog fields
      selected_serviceitem = self.selectedConfigurationCombo.selectedItem()
      if selected_serviceitem:
        active_service = selected_serviceitem.label()
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
    # Cancelled if None is returned
    if newServiceBaseInfo is None:
      return

    if not add:
      if serviceBaseInfo['name']        == newServiceBaseInfo['name'] and \
         serviceBaseInfo['version']     == newServiceBaseInfo['version'] and  \
         serviceBaseInfo['short']       == newServiceBaseInfo['short'] and \
         serviceBaseInfo['description'] == newServiceBaseInfo['description']:
        # no changes
        return

      selected_serviceitem = self.selectedConfigurationCombo.selectedItem()
      if selected_serviceitem:
        selected_service = selected_serviceitem.label()
        service = self.fw.config().getServiceByName(active_service)

        if serviceBaseInfo['version'] != newServiceBaseInfo['version'] or  \
           serviceBaseInfo['short'] != newServiceBaseInfo['short'] or \
           serviceBaseInfo['description'] != newServiceBaseInfo['description']:
          settings = service.getSettings()
          settings.setVersion(newServiceBaseInfo['version'])
          settings.setShort(newServiceBaseInfo['short'])
          settings.setDescription(newServiceBaseInfo['description'])
          service.update(settings)
        if serviceBaseInfo['name'] == newServiceBaseInfo['name']:
          return
        service.rename(newServiceBaseInfo['name'])
    else:
      settings = client.FirewallClientServiceSettings()
      settings.setVersion(newServiceBaseInfo['version'])
      settings.setShort(newServiceBaseInfo['short'])
      settings.setDescription(newServiceBaseInfo['description'])
      self.fw.config().addService(newServiceBaseInfo['name'], settings)

  def onSelectedConfigurationComboChanged(self):
    '''
    depending on what configuration view is selected it manages zones,
    services, etc
    '''
    item = self.configureViewCombobox.selectedItem()
    if item == self.configureViews['zones']['item']:
      #Zones selected
      # self.onChangeZone()
      pass
    elif item == self.configureViews['services']['item']:
      #Services selected
      pass
    elif item == self.configureViews['ipsets']['item']:
      # ip sets selected
      pass
    self.onSelectedConfigurationChanged()

  def onConfigurationViewChanged(self):
    '''
    manages configureViewCombobox changes
    '''
    item = self.configureViewCombobox.selectedItem()
    if item == self.configureViews['zones']['item']:
      #Zones selected
      self.load_zones()
      self.configureCombobox.startMultipleChanges()
      self.configureCombobox.deleteAllItems()
      itemColl = self._zoneConfigurationViewCollection()
      self.configureCombobox.addItems(itemColl)
      self.configureCombobox.setEnabled(True)
      self.configureCombobox.doneMultipleChanges()
      self.editFrameBox.setLabel(_("Edit zones"))
    elif item == self.configureViews['services']['item']:
      #Services selected
      self.load_services()
      self.configureCombobox.startMultipleChanges()
      self.configureCombobox.deleteAllItems()
      itemColl = self._serviceConfigurationViewCollection()
      self.configureCombobox.addItems(itemColl)
      self.configureCombobox.setEnabled(True)
      self.configureCombobox.doneMultipleChanges()
      self.editFrameBox.setLabel(_("Edit services"))
    elif item == self.configureViews['ipsets']['item']:
      # ip sets selected
      self.load_ipsets()
      self.configureCombobox.startMultipleChanges()
      self.configureCombobox.deleteAllItems()
      itemColl = self._ipsecConfigurationViewCollection()
      self.configureCombobox.addItems(itemColl)
      self.configureCombobox.setEnabled(True)
      self.configureCombobox.doneMultipleChanges()
      self.editFrameBox.setLabel(_("Edit ipsets"))
    else:
      # disabling info combo
      self.selectedConfigurationCombo.startMultipleChanges()
      self.selectedConfigurationCombo.deleteAllItems()
      self.selectedConfigurationCombo.setLabel("     ")
      self.selectedConfigurationCombo.setEnabled(False)
      self.selectedConfigurationCombo.doneMultipleChanges()
      #disabling configure view
      self.configureCombobox.startMultipleChanges()
      self.configureCombobox.deleteAllItems()
      self.configureCombobox.setEnabled(False)
      self.configureCombobox.doneMultipleChanges()
      self.editFrameBox.setLabel("")
    self.onSelectedConfigurationComboChanged()


  def onSelectedConfigurationChanged(self, widgetEvent=None):
    '''
    manages configureCombobox changes
    '''
    if (widgetEvent is None or (widgetEvent is not None and widgetEvent.reason() == yui.YEvent.ValueChanged)) :
      config_item = self.configureCombobox.selectedItem()
      # cleanup replace point
      self.dialog.startMultipleChanges()

      for rpwc in self.replacePointWidgetsAndCallbacks:
        self.eventManager.removeWidgetEvent(rpwc['widget'], rpwc['action'])
      self.replacePointWidgetsAndCallbacks.clear()

      self.replacePoint.deleteChildren()
      # cleaning entry points (we could use just one)
      self.portForwardList = None
      self.portList        = None
      self.serviceList     = None
      self.protocolList    = None
      self.icmpFilterList  = None

      item = self.configureViewCombobox.selectedItem()
      if item == self.configureViews['zones']['item']:
        #Zones selected
        if config_item == self.zoneConfigurationView['services']['item']:
          self._replacePointServices()
        elif config_item == self.zoneConfigurationView['ports']['item']:
          # ports
          self._replacePointPort('zone_ports')
          if self.buttons is not None:
            self.buttons['edit'].setEnabled(self.portList.itemsCount() > 0)
            self.buttons['remove'].setEnabled(self.portList.itemsCount() > 0)
        elif config_item == self.zoneConfigurationView['source_ports']['item']:
          #source port
          self._replacePointPort('zone_sourceports')
          if self.buttons is not None:
            self.buttons['edit'].setEnabled(self.portList.itemsCount() > 0)
            self.buttons['remove'].setEnabled(self.portList.itemsCount() > 0)
        elif config_item == self.zoneConfigurationView['port_forwarding']['item']:
          # port forwarding
          self._replacePointForwardPorts()
          if self.buttons is not None:
            self.buttons['edit'].setEnabled(self.portForwardList.itemsCount() > 0)
            self.buttons['remove'].setEnabled(self.portForwardList.itemsCount() > 0)
        elif config_item == self.zoneConfigurationView['protocols']['item']:
          # protocols
          self._replacePointProtocols('zone_protocols')
          if self.buttons is not None:
            self.buttons['edit'].setEnabled(self.protocolList.itemsCount() > 0)
            self.buttons['remove'].setEnabled(self.protocolList.itemsCount() > 0)
        elif config_item == self.zoneConfigurationView['masquerading']['item']:
          self._replacePointMasquerade()
        elif config_item == self.zoneConfigurationView['icmp_filter']['item']:
          self._replacePointICMP()
      elif item == self.configureViews['services']['item']:
        #Services selected
        if config_item == self.serviceConfigurationView['ports']['item']:
          # ports
          self._replacePointPort('service_ports')
          if self.buttons is not None:
            self.buttons['add'].setEnabled(not self.runtime_view)
            self.buttons['edit'].setEnabled(not self.runtime_view and self.portList.itemsCount() > 0)
            self.buttons['remove'].setEnabled(not self.runtime_view and self.portList.itemsCount() > 0)
        elif config_item == self.serviceConfigurationView['source_ports']['item']:
          # source ports
          self._replacePointPort('service_sourceports')
          if self.buttons is not None:
            self.buttons['add'].setEnabled(not self.runtime_view)
            self.buttons['edit'].setEnabled(not self.runtime_view and self.portList.itemsCount() > 0)
            self.buttons['remove'].setEnabled(not self.runtime_view and self.portList.itemsCount() > 0)
        elif config_item == self.serviceConfigurationView['protocols']['item']:
          # protocols
          self._replacePointProtocols('service_protocols')
          if self.buttons is not None:
            self.buttons['add'].setEnabled(not self.runtime_view)
            self.buttons['edit'].setEnabled(not self.runtime_view and self.protocolList.itemsCount() > 0)
            self.buttons['remove'].setEnabled(not self.runtime_view and self.protocolList.itemsCount() > 0)
      elif item == self.configureViews['ipsets']['item']:
        # ip sets selected
        pass

      self.replacePoint.showChild()
      self.dialog.recalcLayout()
      self.dialog.doneMultipleChanges()

  def onTimeOutEvent(self):
    logger.debug ("Timeout occurred")

  def doSomethingIntoLoop(self):
    '''
    check on internal queue if any fw event has been managed
    '''
    try:

      #firewald should not be chatty, but reloaded events produce addition of service and zone one by one,
      #let's check 20 by 20 events in that case to avoid stopping GUI too much
      #if there are no events, get_nowait rise an exception so it exits the loop
      counter = 0
      count_max = 20 if self._reloaded else 1

      while counter < count_max:
        counter = counter + 1
        item = self.fwEventQueue.get_nowait()
        logger.debug("%s %s", item['event'], item['value']) #TODO remove

        # managing deferred firewall events
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
            self.logDeniedLabel.setText(("Log Denied: {}").format(self.log_denied))
            self.automatic_helpers = self.fw.getAutomaticHelpers()
            self.automaticHelpersLabel.setText(_("Automatic Helpers: {}").format(self.automatic_helpers))
            #### TODO self.set_automaticHelpersLabel(self.automatic_helpers)
            lockdown = self.fw.queryLockdown()
            t = self.enabled if lockdown else self.disabled
            self.lockdownLabel.setText(_("Lockdown: {}").format(t))
            panic = self.fw.queryPanicMode()
            t = self.enabled if panic else self.disabled
            self.panicLabel.setText(_("Panic Mode: {}").format(t))
            self.onChangeView()
            item = self.configureViewCombobox.selectedItem()
            if item == self.configureViews['zones']['item']:
              self.load_zones()
            elif item == self.configureViews['services']['item']:
              self.load_services()
            self.dialog.setEnabled(True)
          else:
            self.defaultZoneLabel.setText(_("Default Zone: {}").format("--------"))
            self.logDeniedLabel.setText(("Log Denied: {}").format("--------"))
            self.automaticHelpersLabel.setText(_("Automatic Helpers: {}").format("--------"))
            self.lockdownLabel.setText(_("Lockdown: {}").format("--------"))
            self.panicLabel.setText(_("Panic Mode: {}").format("--------"))
            self.dialog.setEnabled(False)
        elif item['event'] == 'lockdown-changed':
          t = self.enabled if item['value'] else self.disabled
          self.lockdownLabel.setText(_("Lockdown: {}").format(t))
          # TODO manage menu items if needed
        elif item['event'] == 'panicmode-changed':
          t = self.enabled if item['value'] else self.disabled
          self.panicLabel.setText(_("Panic Mode: {}").format(t))
          # TODO manage menu items if needed
        elif item['event'] == 'default-zone-changed':
          zone = item['value']
          self.defaultZoneLabel.setText(_("Default Zone: {}").format(zone))
          # TODO self.update_active_zones()
        elif item['event'] == 'config-zone-added' or item['event'] == 'config-zone-updated' or \
            item['event'] == 'config-zone-renamed' or item['event'] == 'config-zone-removed':
          zone = item['value']
          if not self.runtime_view:
            selected_configureViewItem = self.configureViewCombobox.selectedItem()
            if selected_configureViewItem == self.configureViews['zones']['item']:
              # Zones selected
              selected_zone = None
              selected_item = self.selectedConfigurationCombo.selectedItem()
              if selected_item:
                selected_zone = selected_item.label()
              self.load_zones(selected_zone)
              if item['event'] == 'config-zone-updated':
                configure_item = self.configureCombobox.selectedItem()
                port_type = None
                if configure_item == self.zoneConfigurationView['ports']['item']:
                  port_type = "zone_ports"
                  self._fillRPPort(port_type)
                  if self.buttons is not None:
                    # disabling/enabling edit and remove buttons accordingly
                    self.buttons['edit'].setEnabled(self.portList.itemsCount() > 0)
                    self.buttons['remove'].setEnabled(self.portList.itemsCount() > 0)
                elif configure_item == self.zoneConfigurationView['source_ports']['item']:
                  port_type = "zone_sourceports"
                  self._fillRPPort(port_type)
                  if self.buttons is not None:
                    # disabling/enabling edit and remove buttons accordingly
                    self.buttons['edit'].setEnabled(self.portList.itemsCount() > 0)
                    self.buttons['remove'].setEnabled(self.portList.itemsCount() > 0)
                elif configure_item == self.zoneConfigurationView['port_forwarding']['item']:
                  self._fillRPForwardPorts()
                  if self.buttons is not None:
                    # disabling/enabling edit and remove buttons accordingly
                    self.buttons['edit'].setEnabled(self.portForwardList.itemsCount() > 0)
                    self.buttons['remove'].setEnabled(self.portForwardList.itemsCount() > 0)
                elif configure_item == self.zoneConfigurationView['protocols']['item']:
                  self._fillRPProtocols('zone_protocols')
                  if self.buttons is not None:
                    # disabling/enabling edit and remove buttons accordingly
                    self.buttons['edit'].setEnabled(self.protocolList.itemsCount() > 0)
                    self.buttons['remove'].setEnabled(self.protocolList.itemsCount() > 0)
                elif configure_item == self.zoneConfigurationView['masquerading']['item']:
                  self._fillRPMasquerade()
                elif configure_item == self.zoneConfigurationView['icmp_filter']['item']:
                  self._fillRPICMPFilter()
        elif item['event'] == 'config-service-added' or item['event'] == 'config-service-updated' or \
            item['event'] == 'config-service-renamed' or item['event'] == 'config-service-removed':
          service = item['value']
          if not self.runtime_view:
            selected_configureViewItem = self.configureViewCombobox.selectedItem()
            if selected_configureViewItem == self.configureViews['services']['item']:
              # Services selected
              selected_service = None
              selected_item = self.selectedConfigurationCombo.selectedItem()
              if selected_item:
                selected_service = selected_item.label()
              self.load_services(selected_service)
              if item['event'] == 'config-service-updated':
                configure_item = self.configureCombobox.selectedItem()
                port_type = None
                if configure_item == self.serviceConfigurationView['ports']['item']:
                  port_type = "service_ports"
                  self._fillRPPort(port_type)
                  if self.buttons is not None:
                    # disabling/enabling edit and remove buttons accordingly
                    self.buttons['edit'].setEnabled(self.portList.itemsCount() > 0)
                    self.buttons['remove'].setEnabled(self.portList.itemsCount() > 0)
                elif configure_item == self.serviceConfigurationView['source_ports']['item']:
                  port_type = "service_sourceports"
                  self._fillRPPort(port_type)
                  if self.buttons is not None:
                    # disabling/enabling edit and remove buttons accordingly
                    self.buttons['edit'].setEnabled(self.portList.itemsCount() > 0)
                    self.buttons['remove'].setEnabled(self.portList.itemsCount() > 0)
                elif configure_item == self.serviceConfigurationView['protocols']['item']:
                  self._fillRPProtocols('service_protocols')
                  if self.buttons is not None:
                    # disabling/enabling edit and remove buttons accordingly
                    self.buttons['edit'].setEnabled(self.protocolList.itemsCount() > 0)
                    self.buttons['remove'].setEnabled(self.protocolList.itemsCount() > 0)
        elif item['event'] == 'service-added' or item['event'] == 'service-removed':
          # runtime and view zone and service is selected
          view_item      = self.configureViewCombobox.selectedItem()
          configure_item = self.configureCombobox.selectedItem()
          if self.runtime_view and \
            view_item == self.configureViews['zones']['item'] and \
            configure_item == self.zoneConfigurationView['services']['item']:
            value = item['value']
            selected_zone = self.selectedConfigurationCombo.selectedItem()
            if selected_zone:
              if value['zone'] == selected_zone.label():
                self._fillRPServices()
        elif item['event'] == 'port-added' or item['event'] == 'port-removed':
          # runtime and view zone and port is selected
          view_item      = self.configureViewCombobox.selectedItem()
          configure_item = self.configureCombobox.selectedItem()
          if self.runtime_view and \
            view_item == self.configureViews['zones']['item'] and \
            configure_item == self.zoneConfigurationView['ports']['item']:
            value = item['value']
            selected_zone = self.selectedConfigurationCombo.selectedItem()
            if selected_zone:
              if value['zone'] == selected_zone.label():
                self._fillRPPort("zone_ports")
                if self.buttons is not None:
                  # disabling/enabling edit and remove buttons accordingly
                  self.buttons['edit'].setEnabled(self.portList.itemsCount() > 0)
                  self.buttons['remove'].setEnabled(self.portList.itemsCount() > 0)
        elif item['event'] == 'source-port-added' or item['event'] == 'source-port-removed':
          # runtime and view zone and port is selected
          view_item      = self.configureViewCombobox.selectedItem()
          configure_item = self.configureCombobox.selectedItem()
          if self.runtime_view and \
            view_item == self.configureViews['zones']['item'] and \
            configure_item == self.zoneConfigurationView['source_ports']['item']:
            value = item['value']
            selected_zone = self.selectedConfigurationCombo.selectedItem()
            if selected_zone:
              if value['zone'] == selected_zone.label():
                self._fillRPPort("zone_sourceports")
                if self.buttons is not None:
                  # disabling/enabling edit and remove buttons accordingly
                  self.buttons['edit'].setEnabled(self.portList.itemsCount() > 0)
                  self.buttons['remove'].setEnabled(self.portList.itemsCount() > 0)
        elif item['event'] == 'forward-port-added' or item['event'] == 'forward-port-removed':
          # runtime and view zone and port forwarding is selected
          view_item      = self.configureViewCombobox.selectedItem()
          configure_item = self.configureCombobox.selectedItem()
          if self.runtime_view and \
            view_item == self.configureViews['zones']['item'] and \
            configure_item == self.zoneConfigurationView['port_forwarding']['item']:
            value = item['value']
            selected_zone = self.selectedConfigurationCombo.selectedItem()
            if selected_zone:
              if value['zone'] == selected_zone.label():
                self._fillRPForwardPorts()
                if self.buttons is not None:
                  # disabling/enabling edit and remove buttons accordingly
                  self.buttons['edit'].setEnabled(self.portForwardList.itemsCount() > 0)
                  self.buttons['remove'].setEnabled(self.portForwardList.itemsCount() > 0)
        elif item['event'] == 'icmp-changed' or item['event'] == 'icmp-inversion':
          # runtime and view zone and ICMP filter is selected
          view_item      = self.configureViewCombobox.selectedItem()
          configure_item = self.configureCombobox.selectedItem()
          if self.runtime_view and \
            view_item == self.configureViews['zones']['item'] and \
            configure_item == self.zoneConfigurationView['icmp_filter']['item']:
            value = item['value']
            selected_zone = self.selectedConfigurationCombo.selectedItem()
            if selected_zone:
              if value['zone'] == selected_zone.label():
                self._fillRPICMPFilter()
        elif item['event'] == 'protocol-added' or item['event'] == 'protocol-removed':
          # runtime and view zone and port forwarding is selected
          view_item      = self.configureViewCombobox.selectedItem()
          configure_item = self.configureCombobox.selectedItem()
          if self.runtime_view and \
            view_item == self.configureViews['zones']['item'] and \
            configure_item == self.zoneConfigurationView['protocols']['item']:
            value = item['value']
            selected_zone = self.selectedConfigurationCombo.selectedItem()
            if selected_zone:
              if value['zone'] == selected_zone.label():
                self._fillRPProtocols('zone_protocols')
                if self.buttons is not None:
                  # disabling/enabling edit and remove buttons accordingly
                  self.buttons['edit'].setEnabled(self.protocolList.itemsCount() > 0)
                  self.buttons['remove'].setEnabled(self.protocolList.itemsCount() > 0)
        elif item['event'] == 'masquerade-added':
          view_item      = self.configureViewCombobox.selectedItem()
          configure_item = self.configureCombobox.selectedItem()
          if self.runtime_view and \
            view_item == self.configureViews['zones']['item'] and \
            configure_item == self.zoneConfigurationView['masquerading']['item']:
            zone = item['value']
            selected_zone = self.selectedConfigurationCombo.selectedItem()
            if selected_zone:
              if zone == selected_zone.label():
                if not self.masquerade.isChecked():
                  self.masquerade.setNotify(False)
                  self.masquerade.setValue(yui.YCheckBox_on)
                  self.masquerade.setNotify(True)
        elif item['event'] == 'masquerade-removed':
          view_item      = self.configureViewCombobox.selectedItem()
          configure_item = self.configureCombobox.selectedItem()
          if self.runtime_view and \
            view_item == self.configureViews['zones']['item'] and \
            configure_item == self.zoneConfigurationView['masquerading']['item']:
            zone = item['value']
            selected_zone = self.selectedConfigurationCombo.selectedItem()
            if selected_zone:
              if zone == selected_zone.label():
                if self.masquerade.isChecked():
                  self.masquerade.setNotify(False)
                  self.masquerade.setValue(yui.YCheckBox_off)
                  self.masquerade.setNotify(True)
        elif item['event'] == 'reloaded':
          if self.runtime_view:
            self.onSelectedConfigurationChanged()
          self._reloaded = False
          self.dialog.setEnabled(True)

      self.dialog.pollEvent()
    except Empty as e:
      pass

