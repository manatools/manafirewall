#!/usr/bin/python3 -O
#  dialog.py
# -*- coding: utf-8 -*-

'''
Python manatools.config contains an application configuration file management

License: LGPLv2+

Author:  Angelo Naselli <anaselli@linux.it>

@package manafirewall
'''


import manatools.ui.common as common
import manatools.ui.basedialog as basedialog
import manatools.services as mnservices
import yui

from dbus.exceptions import DBusException

from firewall import config
from firewall import client
from firewall import functions
from firewall.core.base import DEFAULT_ZONE_TARGET, REJECT_TYPES, \
                               ZONE_SOURCE_IPSET_TYPES
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

from manafirewall.version import __project_version__ as VERSION
from manafirewall.version import __project_name__ as PROJECT

from queue import SimpleQueue, Empty

def TimeFunction(func):
    """
    This decorator prints execution time
    """
    def newFunc(*args, **kwargs):
        t_start = time.time()
        rc = func(*args, **kwargs)
        t_end = time.time()
        name = func.__name__
        print("%d: %s took %.2f sec"%(t_start, name, t_end - t_start))
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
    gettext.install('manafirewall', localedir='/usr/share/locale', names=('ngettext',))
    basedialog.BaseDialog.__init__(self, _("Manatools - firewalld configurator"), "", basedialog.DialogType.POPUP, 80, 10)
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

    self.fwEventQueue = SimpleQueue()


  def UIlayout(self, layout):
    '''
    layout implementation called in base class to setup UI
    '''

    # Let's test a Menu widget
    self.file_menu = self.factory.createMenuButton(self.factory.createLeft(layout), _("&File"))
    qm = yui.YMenuItem(_("&Quit"))
    self.file_menu.addItem(qm)
    self.file_menu.rebuildMenuTree()
    sendObjOnEvent=True
    self.eventManager.addMenuEvent(qm, self.onQuitEvent, sendObjOnEvent)

    cols = self.factory.createHBox(layout)
    col1 = self.factory.createVBox(cols)
    col2 = self.factory.createVBox(cols)
    self.tree = self.factory.createTree(col1, _("Active bindings"))
    self.tree.setWeight(0,20)
    align = self.factory.createLeft(col2)
    hbox = self.factory.createHBox(align)
    label = self.factory.createLabel(hbox, _("Configuration:"),False,False)
    self.views = {
            'runtime'   : {'title' : _("Runtime")},
            'permanent' : {'title' : _("Permanent")},
        }
    ordered_views = [ 'runtime', 'permanent' ]

    self.currentViewCombobox = self.factory.createComboBox(hbox,"")
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

    #### bottom status lines
    align = self.factory.createLeft(layout)
    hbox = self.factory.createHBox(align)
    self.statusLabel = self.factory.createLabel(hbox, self.failed_to_connect_label)

    #### buttons on the last line
    align = self.factory.createRight(layout)
    hbox = self.factory.createHBox(align)
    aboutButton = self.factory.createPushButton(hbox, _("&About") )
    self.eventManager.addWidgetEvent(aboutButton, self.onAbout)
    quitButton = self.factory.createPushButton(hbox, _("&Quit"))
    self.eventManager.addWidgetEvent(quitButton, self.onQuitEvent, sendObjOnEvent)

    # Let's test a cancel event
    self.eventManager.addCancelEvent(self.onCancelEvent)
    # Let's check external events every 100 msec
    self.timeout = 100
    #self.eventManager.addTimeOutEvent(self.onTimeOutEvent)
    # End Dialof layout

    self.initFWClient()


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


  def fwConnectionChanged(self):
    '''
    connection changed
    '''
    if self.fw.connected:
      self.fw.authorizeAll()
      self.fwEventQueue.put({'event': "connection-changed", 'value': True})
      print("connected")
    else:
      self.fwEventQueue.put({'event': "connection-changed", 'value': False})
      print("disc")

  def onCancelEvent(self) :
    '''
    Exit by using cancel event
    '''
    print ("Got a cancel event")

  def onQuitEvent(self, obj) :
    '''
    Exit by using quit button or menu
    '''
    if isinstance(obj, yui.YItem):
      print ("Quit menu pressed")
    else:
      print ("Quit button pressed")
    # BaseDialog needs to force to exit the handle event loop
    self.ExitLoop()


  def onAbout(self) :
    '''
    About dialog invoked
    '''
    ok = common.AboutDialog({
          'name' : self._application_name,
          'dialog_mode' : common.AboutDialogMode.TABBED,
          'version' : VERSION,
          'credits' : _("Credits {}").format("2019 Angelo Naselli"),
          'license' : 'GPLv2+',
          'authors' : 'Angelo Naselli &lt;anaselli@linux.it&gt;',
          'description' : _("{}  is a graphical configuration tool for firewalld.").format(PROJECT),
          'size': {'column': 50, 'lines': 6},
    })
  
  def onTimeOutEvent(self):
    print ("Timeout occurred")

  def doSomethingIntoLoop(self):
    '''
    check on internal queue if any fw event has been managed
    '''
    try:
      item = self.fwEventQueue.get_nowait()
      if item['event'] == "connection-changed":
        if self.statusLabel.text() == self.connected_label:
          self.connection_lost = True
        t = self.connected_label if item['value'] else self.trying_to_connect_label
        self.statusLabel.setText(t)
        self.pollEvent()

    except Empty as e:
      pass

