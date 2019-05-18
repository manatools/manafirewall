# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:

'''
HelpInfo contains text for help menu

License: LGPLv2+

Author:  Angelo Naselli <anaselli@linux.it>

@package manafirewall
'''

import manatools.basehelpinfo as helpdata
import gettext

class ManaFirewallHelpInfo(helpdata.HelpInfoBase):
  '''
  ManaFirewallHelpInfo class implements HelpInfoBase show() and home()
  '''
  def __init__(self):
    '''
    HelpInfo constructor
    '''
    helpdata.HelpInfoBase.__init__(self)
    configuration_lnk = '<b>%s</b>'%self._formatLink(_("Configuration"), 'configuration_cbx')
    view_lnk = '<b>%s</b>'%self._formatLink(_("View"), 'view_cbx')
    home_lnk = '<b>%s</b>'%self._formatLink(_("Go to index"), 'home')

    index = '%s<br>%s<br>'%(configuration_lnk, view_lnk)

    permanent = _("Permanent mode allows to configure things that are not active immediately. If you want to have changes also in the runtime environment, then either add the changes there also or reload firewalld.")
    runtime = _("Runtime mode allows to configure things at runtime. Things changed at runtime will not present at next start up or relading firewalld, if you want that you need to add those changes in permanent mode also. ")



    self.text = {
      'home': '<h1>Manafirewall</h1>%s<br>%s<br>%s<br>%s<br>%s<br><br>%s'%(
        _("ManaFirewall is a graphical configuration tool for firewalld."),
        _("ManaFirewall is part of manatools and it is based on libyui so that it can work using Gtk, Qt or ncureses, e.g. graphical or textual user interfaces."),
        _("On the left there is the overview of the active bindings. These are the zones, that have a connection, interface or source bound or added to it. Here it is possible to easily change the\
          zone of these bindings."),
        _("On the right there are comboboxes to select what to look or configure such as zones, services etc."),
        _("On top a menu bar with File, Options and Help. While at the bottom Quit and About button are present"),
        index
      ),
      'configuration_cbx' : '<h1>%s</h1><h2>%s</h2>%s<h2>%s</h2>%s<br><br>%s'%(_("Configuration"), _("Permanent"), permanent, _("Runtime"), runtime, home_lnk
      ),
      'view_cbx' : '<h1>%s</h1> <br><br>%s'%(_("View"), home_lnk
      ),
      }

  def _formatLink(self, description, url) :
    '''
    @param description: Description to be shown as link
    @param url: to be reach when click on $description link
    returns href string to be published
    '''
    webref = '<a href="%s">%s</a>'%(url, description)
    return webref

  def show(self, index):
    '''
    implement show
    '''
    if index in self.text.keys():
      return self.text[index]

    return ""

  def home(self):
    '''
    implement home
    '''
    return self.text['home']


if __name__ == '__main__':

  info = HelpInfo()
  td = helpdialog.HelpDialog(info)
  td.run()
  
  
