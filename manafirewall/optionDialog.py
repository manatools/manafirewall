# vim: set fileencoding=utf-8 :
'''
manafirewall is a graphical package management tool based on libyui python bindings

License: GPLv3

Author:  Angelo Naselli <anaselli@linux.it>

@package manafirewall
'''
import yui
import sys
import os

from firewall import config
import manatools.ui.basedialog as basedialog
import gettext
import logging
logger = logging.getLogger('manafirewall.optiondialog')


class OptionDialog(basedialog.BaseDialog):
  def __init__(self, parent):
    basedialog.BaseDialog.__init__(self, "manafirewall options", "manafirewall", basedialog.DialogType.POPUP, 80, 15)
    self.parent = parent
    self.log_vbox = None
    self.widget_callbacks = []

  def UIlayout(self, layout):
    '''
    manafirewall options layout implementation
    '''

    hbox_config = self.factory.createHBox(layout)
    hbox_bottom = self.factory.createHBox(layout)
    self.config_tree = self.factory.createTree(hbox_config, "")
    self.config_tree.setWeight(0,30)
    self.config_tree.setNotify(True)
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
    item = yui.YTreeItem(_("firewalld"))
    item.this.own(False)
    itemVect.append(item)
    item.setSelected()
    self.option_items ["firewalld"] = item

    item = yui.YTreeItem(_("Layout"))
    item.this.own(False)
    itemVect.append(item)
    self.option_items ["layout"] = item

    item = yui.YTreeItem(_("Logging"))
    item.this.own(False)
    itemVect.append(item)
    self.option_items ["logging"] = item

    itemCollection = yui.YItemCollection(itemVect)
    self.config_tree.addItems(itemCollection)

    self.config_tab = self.factory.createReplacePoint(hbox_config)
    self.config_tab.setWeight(0,70)

    self.RestoreButton = self.factory.createIconButton(hbox_bottom,"",_("Restore &default"))
    self.eventManager.addWidgetEvent(self.RestoreButton, self.onRestoreButton)
    self.RestoreButton.setWeight(0,1)

    st = self.factory.createHStretch(hbox_bottom)
    st.setWeight(0,1)

    self.quitButton = self.factory.createIconButton(hbox_bottom,"",_("&Close"))
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
    if isinstance(obj, yui.YTree):
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
    self.factory.createHSpacing(hbox)

    # Title
    heading = self.factory.createHeading( vbox, _("firewalld options") )
    self.factory.createVSpacing(vbox, 0.3)
    heading.setAutoWrap()

    hbox = self.factory.createHBox(vbox)
    defaultZoneCombo = self.factory.createComboBox( hbox, _("Default Zone") )
    defaultZoneCombo.setNotify(True)
    self.eventManager.addWidgetEvent(defaultZoneCombo, self.onDefaultZoneChange, True)
    self.widget_callbacks.append( { 'widget': defaultZoneCombo, 'handler': self.onDefaultZoneChange} )
    # fill combo with zones
    zones = self.parent.fw.getZones()
    selected_zone = self.parent.fw.getDefaultZone()
    itemColl = yui.YItemCollection()
    for zone in zones:
      item = yui.YItem(zone, False)
      if zone == selected_zone:
        item.setSelected(True)
      itemColl.push_back(item)
      item.this.own(False)
    defaultZoneCombo.addItems(itemColl)

    logDeniedCombo = self.factory.createComboBox( hbox, _("Log Denied") )
    logDeniedCombo.setNotify(True)
    self.eventManager.addWidgetEvent(logDeniedCombo, self.onLogDeniedChange, True)
    self.widget_callbacks.append( { 'widget': logDeniedCombo, 'handler': self.onLogDeniedChange} )
    # fill log denied values
    ldValues = config.LOG_DENIED_VALUES
    selected_ld = self.parent.fw.getLogDenied()
    itemColl = yui.YItemCollection()
    for ldValue in ldValues:
      item = yui.YItem(ldValue, False)
      if ldValue == selected_ld:
        item.setSelected(True)
      itemColl.push_back(item)
      item.this.own(False)
    logDeniedCombo.addItems(itemColl)

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
    self.dialog.recalcLayout()

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
    self.dialog.recalcLayout()

  def _openLoggingOptions(self):
    '''
    show logging configuration options
    '''
    if self.config_tab.hasChildren():
      self.config_tab.deleteChildren()

    self.RestoreButton.setEnabled()

    hbox = self.factory.createHBox(self.config_tab)
    self.factory.createHSpacing(hbox, 1.5)
    vbox = self.factory.createVBox(hbox)
    self.factory.createHSpacing(hbox, 1.5)

    # Title
    heading=self.factory.createHeading( vbox, _("Logging options (active at next startup)") )
    self.factory.createVSpacing(vbox, 0.3)
    heading.setAutoWrap()

    log_enabled = self.parent.config.userPreferences['settings']['log']['enabled'] \
        if 'settings' in self.parent.config.userPreferences.keys() \
          and 'log' in self.parent.config.userPreferences['settings'].keys() \
          and 'enabled' in self.parent.config.userPreferences['settings']['log'].keys() \
        else False

    log_directory = self.parent.config.userPreferences['settings']['log']['directory'] \
        if 'settings' in self.parent.config.userPreferences.keys() \
          and 'log' in self.parent.config.userPreferences['settings'].keys() \
          and 'directory' in self.parent.config.userPreferences['settings']['log'].keys() \
        else os.path.expanduser("~")

    level_debug = self.parent.config.userPreferences['settings']['log']['level_debug'] \
        if 'settings' in self.parent.config.userPreferences.keys() \
          and 'log' in self.parent.config.userPreferences['settings'].keys() \
          and 'level_debug' in self.parent.config.userPreferences['settings']['log'].keys() \
        else False

    if not 'log' in self.parent.config.userPreferences['settings'].keys():
      self.parent.config.userPreferences['settings']['log'] = {}

    self.log_enabled  = self.factory.createCheckBox(self.factory.createLeft(vbox) , _("Enable logging"), log_enabled )
    self.log_enabled.setNotify(True)
    self.eventManager.addWidgetEvent(self.log_enabled, self.onEnableLogging, True)
    self.widget_callbacks.append( { 'widget': self.log_enabled, 'handler': self.onEnableLogging} )

    self.log_vbox = self.factory.createVBox(vbox)
    hbox = self.factory.createHBox(self.log_vbox)
    self.factory.createHSpacing(hbox, 2.0)
    self.log_directory = self.factory.createLabel(self.factory.createLeft(hbox), "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    self.choose_dir = self.factory.createIconButton(self.factory.createLeft(hbox), "", _("Change &directory"))
    self.eventManager.addWidgetEvent(self.choose_dir, self.onChangeLogDirectory)
    self.widget_callbacks.append( { 'widget': self.choose_dir, 'handler': self.onChangeLogDirectory} )

    self.log_directory.setText(log_directory)
    hbox = self.factory.createHBox(self.log_vbox)
    self.factory.createHSpacing(hbox, 2.0)
    self.level_debug = self.factory.createCheckBox(self.factory.createLeft(hbox) , _("Debug level"), level_debug )
    self.level_debug.setNotify(True)
    self.eventManager.addWidgetEvent(self.level_debug, self.onLevelDebugChange, True)
    self.widget_callbacks.append( { 'widget': self.level_debug, 'handler': self.onLevelDebugChange} )

    self.log_vbox.setEnabled(log_enabled)

    self.factory.createVStretch(vbox)
    self.config_tab.showChild()
    self.dialog.recalcLayout()

  def onEnableLogging(self, obj) :
    '''
    enable logging check box event
    '''
    if isinstance(obj, yui.YCheckBox):
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
    log_directory = yui.YUI.app().askForExistingDirectory(
          start_dir,
          _("Choose log destination directory"))
    if log_directory:
      self.log_directory.setText(log_directory)
      self.dialog.recalcLayout()
      try:
        self.parent.config.userPreferences['settings']['log']['directory'] = self.log_directory.text()
      except:
        self.parent.config.userPreferences['settings']['log'] = { 'directory' : self.log_directory.text() }

  def onShowAll(self, obj):
    '''
    Show All Changing
    '''
    if isinstance(obj, yui.YCheckBox):
      self.parent.config.userPreferences['settings']['do not show groups at startup'] = obj.isChecked()
    else:
      logger.error("Invalid object passed %s", obj.widgetClass())

  def onShowUpdates(self, obj):
    '''
    Show Updates Changing
    '''
    if isinstance(obj, yui.YCheckBox):
      self.parent.config.userPreferences['settings']['show updates at startup'] = obj.isChecked()
    else:
      logger.error("Invalid object passed %s", obj.widgetClass())

  def onLevelDebugChange(self, obj):
    '''
    Debug level Changing
    '''
    if isinstance(obj, yui.YCheckBox):
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
    if isinstance(obj, yui.YCheckBox):
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
    if isinstance(obj, yui.YCheckBox):
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
    if isinstance(obj, yui.YComboBox):
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
    if isinstance(obj, yui.YComboBox):
      new_ldValue = obj.value()
      old_ldValue = self.parent.fw.getLogDenied()
      logger.debug("New default zone %s", new_ldValue)
      if new_ldValue != old_ldValue:
        self.parent.fw.setLogDenied(new_ldValue)
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

