# vim: set fileencoding=utf-8 :
'''
manafirewall is a graphical package management tool based on libyui python bindings

License: GPLv3

Author:  Angelo Naselli <anaselli@linux.it>

@package manafirewall
'''
import manatools.aui.yui as MUI
import sys
import os

from firewall import config
import manatools.ui.basedialog as basedialog
import gettext
import logging
logger = logging.getLogger('manafirewall.optiondialog')


class OptionDialog(basedialog.BaseDialog):
  def __init__(self, parent):
    basedialog.BaseDialog.__init__(self, "manafirewall options", "manafirewall", basedialog.DialogType.POPUP, 320, 200)
    self.parent = parent
    self.log_vbox = None
    self.widget_callbacks = []
    self._HSPACING_PX = 6
    self._VSPACING_PX = 12

  # ------------------------------------------------------------------
  # Safe config-access helpers
  # ------------------------------------------------------------------

  @staticmethod
  def _safe_cfg_get(cfg, *keys, default=None):
    """Navigate a nested dict safely; return *default* if any level is None or missing."""
    try:
      node = cfg if cfg is not None else {}
      for key in keys:
        if not isinstance(node, dict):
          return default
        node = node.get(key)
        if node is None:
          return default
      return node
    except Exception:
      return default

  def _user_prefs(self):
    """Return config.userPreferences as a dict, or {} if None/missing."""
    config = getattr(self.parent, 'config', None)
    return getattr(config, 'userPreferences', None) or {}

  def _system_settings(self):
    """Return config.systemSettings as a dict, or {} if None/missing."""
    config = getattr(self.parent, 'config', None)
    return getattr(config, 'systemSettings', None) or {}

  def _ensure_settings(self):
    """Return config.userPreferences['settings'] dict, creating the key path if needed.
    Safe to use both for reads and writes."""
    config = getattr(self.parent, 'config', None)
    if config is None:
      return {}  # throwaway – at least we won't crash
    if not isinstance(getattr(config, 'userPreferences', None), dict):
      config.userPreferences = {}
    return config.userPreferences.setdefault('settings', {})

  def UIlayout(self, layout):
    '''
    manafirewall options layout implementation
    '''

    hbox_config = self.factory.createHBox(layout)
    self.factory.createVStretch(layout)
    hbox_bottom = self.factory.createHBox(layout)
    # Wrap the tree in MinSize to guarantee a minimum column width regardless
    # of the ReplacePoint content on the right (long labels in System options
    # would otherwise squeeze the tree below its usable width).
    tree_col = self.factory.createMinSize(hbox_config, 20, 3)
    tree_col.setWeight(MUI.YUIDimension.YD_HORIZ, 25)
    self.config_tree = self.factory.createTree(tree_col, "")
    self.config_tree.setStretchable(MUI.YUIDimension.YD_VERT, True)
    self.config_tree.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
    self.eventManager.addWidgetEvent(self.config_tree, self.onChangeConfig, sendWidget=True)

    itemVect = []
    self.option_items = {
      "firewalld" : None,
      "layout" : None,
      "logging" : None,
      }
    self.selected_option = None
    ### Options items
    #YTreeItem self, std::string const & label, std::string const & iconName, bool isOpen=False)
    # TODO add icons
    item = MUI.YTreeItem(label=_("firewalld"))
    itemVect.append(item)
    self.option_items ["firewalld"] = item

    item = MUI.YTreeItem(label=_("Layout"))
    itemVect.append(item)
    self.option_items ["layout"] = item

    item = MUI.YTreeItem(label=_("Logging"))
    itemVect.append(item)
    self.option_items ["logging"] = item

    self.config_tree.addItems(itemVect)
    self.config_tree.selectItem(itemVect[0], True)

    frame = self.factory.createFrame(hbox_config)
    frame.setStretchable(MUI.YUIDimension.YD_VERT, True)
    frame.setStretchable(MUI.YUIDimension.YD_HORIZ, True)
    frame.setWeight(MUI.YUIDimension.YD_HORIZ, 75)
    self.config_tab = self.factory.createReplacePoint(frame)

    self.RestoreButton = self.factory.createIconButton(hbox_bottom,"edit-undo",_("Restore &default"))
    self.RestoreButton.setHelpText(_("Restore default configuration for the selected section"))
    self.eventManager.addWidgetEvent(self.RestoreButton, self.onRestoreButton)
    self.RestoreButton.setWeight(0,1)

    st = self.factory.createHStretch(hbox_bottom)
    st.setWeight(0,1)

    self.quitButton = self.factory.createIconButton(hbox_bottom,"window-close",_("&Close"))
    self.eventManager.addWidgetEvent(self.quitButton, self.onQuitEvent)
    self.quitButton.setWeight(0,1)
    self.dialog.setDefaultButton(self.quitButton)

    self.eventManager.addCancelEvent(self.onCancelEvent)
    self.onChangeConfig(self.config_tree)


  def onChangeConfig(self, obj):
    '''
    fill option configuration data starting from config tree selection
    '''
    logger.debug('Config tab %s', self.selected_option)
    if obj.widgetClass() == "YTree":
      item = self.config_tree.selectedItem()
      for k in self.option_items.keys():
        if self.option_items[k] == item:
          if k != self.selected_option :
            self.log_vbox = None
            logger.debug('Config tab changed to %s', k)
            self._cleanCallbacks()
            if k == "firewalld":
              self._openSystemOptions()
            elif  k == "layout":
              self._openLayoutOptions()
            elif k == "logging":
              self._openLoggingOptions()

            self.selected_option = k
            break

  def _cleanCallbacks(self):
    '''
    clean old selectaion call backs
    '''
    logger.debug('Removing %d callbacks', len( self.widget_callbacks))
    for e in self.widget_callbacks:
      self.eventManager.removeWidgetEvent(e['widget'], e['handler'])
    self.widget_callbacks = []

  def _openSystemOptions(self):
    '''
    show system configuration options
    '''
    if self.config_tab.hasChildren():
      self.config_tab.deleteChildren()

    self.RestoreButton.setDisabled()

    hbox = self.factory.createHBox(self.config_tab)
    self.factory.createHSpacing(hbox)
    vbox = self.factory.createVBox(hbox)

    # Title
    heading = self.factory.createHeading( vbox, _("firewalld options") )
    self.factory.createVSpacing(vbox, 0.3)
    heading.setAutoWrap()

    hbox = self.factory.createHBox(self.factory.createLeft(vbox))
    defaultZoneCombo = self.factory.createComboBox( hbox, _("Default Zone") )
    defaultZoneCombo.setNotify(True)
    self.eventManager.addWidgetEvent(defaultZoneCombo, self.onDefaultZoneChange, True)
    self.widget_callbacks.append( { 'widget': defaultZoneCombo, 'handler': self.onDefaultZoneChange} )
    # fill combo with zones
    zones = self.parent.fw.getZones()
    selected_zone = self.parent.fw.getDefaultZone()
    itemColl = []
    for zone in zones:
      item = MUI.YItem(zone, False)
      if zone == selected_zone:
        item.setSelected(True)
      itemColl.append(item)
    defaultZoneCombo.addItems(itemColl)

    logDeniedCombo = self.factory.createComboBox( hbox, _("Log Denied") )
    logDeniedCombo.setNotify(True)
    self.eventManager.addWidgetEvent(logDeniedCombo, self.onLogDeniedChange, True)
    self.widget_callbacks.append( { 'widget': logDeniedCombo, 'handler': self.onLogDeniedChange} )
    # fill log denied values
    ldValues = config.LOG_DENIED_VALUES
    selected_ld = self.parent.fw.getLogDenied()
    itemColl = []
    for ldValue in ldValues:
      item = MUI.YItem(ldValue, False)
      if ldValue == selected_ld:
        item.setSelected(True)
      itemColl.append(item)
    logDeniedCombo.addItems(itemColl)

    autoHelperAssignCombo = self.factory.createComboBox( hbox, _("Automatic Helper Assignment") )
    autoHelperAssignCombo.setNotify(True)
    self.eventManager.addWidgetEvent(autoHelperAssignCombo, self.onAutoHelperAssignChange, True)
    self.widget_callbacks.append( { 'widget': autoHelperAssignCombo, 'handler': self.onAutoHelperAssignChange} )
    # fill log denied values
    values = config.AUTOMATIC_HELPERS_VALUES
    selected_value = self.parent.fw.getAutomaticHelpers()
    itemColl = []
    for val in values:
      item = MUI.YItem(val, False)
      if val == selected_value:
        item.setSelected(True)
      itemColl.append(item)
    autoHelperAssignCombo.addItems(itemColl)

    self.factory.createVSpacing(vbox)
    pmButton = self.factory.createCheckBox(self.factory.createLeft(vbox), _("Panic Mode"), self.parent.fw.queryPanicMode() )
    pmButton.setNotify(True)
    self.eventManager.addWidgetEvent(pmButton, self.onPanicModeChange, True)
    self.widget_callbacks.append( { 'widget': pmButton, 'handler': self.onPanicModeChange} )

    ldButton = self.factory.createCheckBox(self.factory.createLeft(vbox), _("Lockdown"), self.parent.fw.queryLockdown() )
    ldButton.setNotify(True)
    self.eventManager.addWidgetEvent(ldButton, self.onLockdownChange, True)
    self.widget_callbacks.append( { 'widget': ldButton, 'handler': self.onLockdownChange} )

    self.factory.createVStretch(vbox)

    self.config_tab.showChild()

  def _openLayoutOptions(self):
    '''
    show layout configuration options
    '''
    if self.config_tab.hasChildren():
      self.config_tab.deleteChildren()

    self.RestoreButton.setEnabled()

    hbox = self.factory.createHBox(self.config_tab)
    self.factory.createHSpacing(hbox)
    vbox = self.factory.createVBox(hbox)
    self.factory.createHSpacing(hbox)

    # Title
    heading = self.factory.createHeading( vbox, _("Layout options (active at next startup)") )
    self.factory.createVSpacing(vbox, 0.3)
    heading.setAutoWrap()

    ### TODO showUpdates = self.parent.config.userPreferences['settings']['show updates at startup'] \
    ### TODO   if 'settings' in self.parent.config.userPreferences.keys() \
    ### TODO     and 'show updates at startup' in self.parent.config.userPreferences['settings'].keys() \
    ### TODO   else False
    ### TODO
    ### TODO showAll =  self.parent.config.userPreferences['settings']['do not show groups at startup']\
    ### TODO   if 'settings' in self.parent.config.userPreferences.keys() \
    ### TODO     and 'do not show groups at startup' in self.parent.config.userPreferences['settings'].keys() \
    ### TODO   else False
    ### TODO
    ### TODO
    ### TODO self.showUpdates =  self.factory.createCheckBox(self.factory.createLeft(vbox) , _("Show updates"), showUpdates )
    ### TODO self.showUpdates.setNotify(True)
    ### TODO self.eventManager.addWidgetEvent(self.showUpdates, self.onShowUpdates, True)
    ### TODO self.widget_callbacks.append( { 'widget': self.showUpdates, 'handler': self.onShowUpdates} )
    ### TODO
    ### TODO self.showAll  =  self.factory.createCheckBox(self.factory.createLeft(vbox) , _("Do not show groups view"), showAll )
    ### TODO self.showAll.setNotify(True)
    ### TODO self.eventManager.addWidgetEvent(self.showAll, self.onShowAll, True)
    ### TODO self.widget_callbacks.append( { 'widget': self.showAll, 'handler': self.onShowAll} )

    self.factory.createVStretch(vbox)
    self.config_tab.showChild()

  def _openLoggingOptions(self):
    '''
    show logging configuration options
    '''
    if self.config_tab.hasChildren():
      self.config_tab.deleteChildren()

    hbox = self.factory.createHBox(self.config_tab)
    self.factory.createHSpacing(hbox, 1.5*self._HSPACING_PX)
    vbox = self.factory.createVBox(hbox)
    self.factory.createHSpacing(hbox, 1.5*self._HSPACING_PX)

    # Title
    heading=self.factory.createHeading( vbox, _("Logging options (active at next startup)") )
    self.factory.createVSpacing(vbox, 0.3*self._VSPACING_PX)
    heading.setAutoWrap()

    log_enabled = self._safe_cfg_get(self._user_prefs(), 'settings', 'log', 'enabled',
                                      default=False)

    log_directory = self._safe_cfg_get(self._user_prefs(), 'settings', 'log', 'directory',
                                        default=os.path.expanduser("~"))

    level_debug = self._safe_cfg_get(self._user_prefs(), 'settings', 'log', 'level_debug',
                                      default=False)

    # Ensure the 'log' sub-dict exists in userPreferences['settings'] for later writes
    self._ensure_settings().setdefault('log', {})

    ####
    self.log_enabled = self.factory.createCheckBoxFrame(vbox, _("Enable logging"), log_enabled)
    self.log_enabled.setNotify(True)
    self.eventManager.addWidgetEvent(self.log_enabled, self.onEnableLogging, True)
    self.widget_callbacks.append( { 'widget': self.log_enabled, 'handler': self.onEnableLogging} )
    
    self.log_vbox = self.factory.createVBox(self.log_enabled)
    hbox = self.factory.createHBox(self.log_vbox)    
    self.log_directory = self.factory.createLabel(self.factory.createLeft(hbox), "")
    self.factory.createHSpacing(hbox)
    self.choose_dir = self.factory.createIconButton(hbox, "folder", _("Change &directory"))
    self.eventManager.addWidgetEvent(self.choose_dir, self.onChangeLogDirectory)
    self.widget_callbacks.append( { 'widget': self.choose_dir, 'handler': self.onChangeLogDirectory} )
    self.log_directory.setText(log_directory)
        
    self.level_debug = self.factory.createCheckBox(self.log_vbox , _("Debug level"), level_debug )
    self.level_debug.setNotify(True)
    self.eventManager.addWidgetEvent(self.level_debug, self.onLevelDebugChange, True)
    self.widget_callbacks.append( { 'widget': self.level_debug, 'handler': self.onLevelDebugChange} )

    self.log_vbox.setEnabled(log_enabled)

    self.factory.createVStretch(vbox)
    self.config_tab.showChild()

  def onEnableLogging(self, obj) :
    '''
    enable logging check box event
    '''
    if obj.widgetClass() == "YCheckBox":
      self.log_vbox.setEnabled(obj.isChecked())
      try:
        self.parent.config.userPreferences['settings']['log']['enabled'] = obj.isChecked()
      except:
        self.parent.config.userPreferences['settings']['log'] = { 'enabled' : obj.isChecked() }
    else:
      logger.error("Invalid object passed %s", obj.widgetClass())

  def onChangeLogDirectory(self):
    '''
    Change directory button has been invoked
    '''
    start_dir = self.log_directory.text() if self.log_directory.text() else os.path.expanduser("~")
    log_directory = MUI.YUI.app().askForExistingDirectory(
          start_dir,
          _("Choose log destination directory"))
    if log_directory:
      self.log_directory.setText(log_directory)
      try:
        self.parent.config.userPreferences['settings']['log']['directory'] = self.log_directory.text()
      except:
        self.parent.config.userPreferences['settings']['log'] = { 'directory' : self.log_directory.text() }

  def onShowAll(self, obj):
    '''
    Show All Changing
    '''
    if obj.widgetClass() == "YCheckBox":
      self.parent.config.userPreferences['settings']['do not show groups at startup'] = obj.isChecked()
    else:
      logger.error("Invalid object passed %s", obj.widgetClass())

  def onShowUpdates(self, obj):
    '''
    Show Updates Changing
    '''
    if obj.widgetClass() == "YCheckBox":
      self.parent.config.userPreferences['settings']['show updates at startup'] = obj.isChecked()
    else:
      logger.error("Invalid object passed %s", obj.widgetClass())

  def onLevelDebugChange(self, obj):
    '''
    Debug level Changing
    '''
    if obj.widgetClass() == "YCheckBox":
      try:
        self.parent.config.userPreferences['settings']['log']['level_debug'] = obj.isChecked()
      except:
        self.parent.config.userPreferences['settings']['log'] = { 'level_debug' : obj.isChecked() }
    else:
      logger.error("Invalid object passed %s", obj.widgetClass())

  def onPanicModeChange(self, obj):
    '''
    Panic Mode Changing
    '''
    if obj.widgetClass() == "YCheckBox":
      if obj.isChecked():
        self.parent.fw.enablePanicMode()
      else:
        self.parent.fw.disablePanicMode()
      logger.debug("Panic Mode %d", obj.value())
    else:
      logger.error("Invalid object passed %s", obj.widgetClass())

  def onLockdownChange (self, obj):
    '''
    Lockdown Changing
    '''
    if obj.widgetClass() == "YCheckBox":
      if obj.isChecked():
        if not self.parent.fw.queryLockdown():
          logger.debug("Setting Lockdown")
          self.parent.fw.config().set_property("Lockdown", "yes")   # permanent
          self.parent.fw.enableLockdown()                           # runtime
      else:
        if self.parent.fw.queryLockdown():
          logger.debug("Disabling Lockdown")
          self.parent.fw.config().set_property("Lockdown", "no")    # permanent
          self.parent.fw.disableLockdown()                          # runtime
      logger.debug("onLockdownChange %d", obj.value())
    else:
      logger.error("Invalid object passed %s", obj.widgetClass())

  def onDefaultZoneChange(self, obj):
    '''
    Manage default zone changing
    '''
    if obj.widgetClass() == "YComboBox":
      new_default_zone = obj.value()
      default_zone = self.parent.fw.getDefaultZone()
      logger.debug("New default zone %s", new_default_zone)
      if new_default_zone != default_zone:
        self.parent.fw.setDefaultZone(new_default_zone)
    else:
      logger.error("Invalid object passed %s", obj.widgetClass())

  def onLogDeniedChange(self, obj):
    '''
    Manage log denied changing
    '''
    if obj.widgetClass() == "YComboBox":
      new_ldValue = obj.value()
      old_ldValue = self.parent.fw.getLogDenied()
      logger.debug("New Log Denied %s", new_ldValue)
      if new_ldValue != old_ldValue:
        self.parent.fw.setLogDenied(new_ldValue)
    else:
      logger.error("Invalid object passed %s", obj.widgetClass())

  def onAutoHelperAssignChange(self, obj):
    '''
    Manage Automatic Helper Assignment Change
    '''
    if obj.widgetClass() == "YComboBox":
      new_ldValue = obj.value()
      old_ldValue = self.parent.fw.getAutomaticHelpers()
      logger.debug("New Helper Assignment %s", new_ldValue)
      if new_ldValue != old_ldValue:
        self.parent.fw.setAutomaticHelpers(new_ldValue)
    else:
      logger.error("Invalid object passed %s", obj.widgetClass())

  def onRestoreButton(self) :
    logger.debug('Restore pressed')
    k = self.selected_option
    if k == "firewalld":
      self.parent.config.userPreferences['settings']['always_yes'] = False
      self.parent.always_yes = False
      self.parent.config.userPreferences['settings']['interval for checking updates'] = 180
      self.parent.config.userPreferences['settings']['metadata'] = {
        'update_interval' :  48
      }
      self.parent.md_update_interval = 48
      self._openSystemOptions()
    elif  k == "layout":
      self.parent.config.userPreferences['settings']['show updates at startup'] = False
      self.parent.config.userPreferences['settings']['do not show groups at startup'] = False
      self._openLayoutOptions()
    elif k == "logging":
      self.parent.config.userPreferences['settings']['log'] = {
        'enabled': False,
        'directory': os.path.expanduser("~"),
        'level_debug': False,
      }
      self._openLoggingOptions()

  def onCancelEvent(self) :
    logger.debug("Got a cancel event")

  def onQuitEvent(self) :
    logger.debug("Quit button pressed")
    self.parent.saveUserPreference()
    # BaseDialog needs to force to exit the handle event loop
    self.ExitLoop()

