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
    zones_view_lnk = '<b>%s</b>'%self._formatLink(_("Zones view"), 'zones_view_cbx')
    services_view_lnk = '<b>%s</b>'%self._formatLink(_("Services view"), 'services_view_cbx')
    ipsets_view_lnk = '<b>%s</b>'%self._formatLink(_("IP sets view"), 'ipsets_view_cbx')
    home_lnk = '<b>%s</b>'%self._formatLink(_("Go to index"), 'home')

    index = '%s<br>%s<br>'%(configuration_lnk, view_lnk)
    view_index = '%s<br>%s<br>%s<br>'%(zones_view_lnk, services_view_lnk, ipsets_view_lnk)

    permanent = _("Permanent mode allows to configure things that are not active immediately. If you want to have changes also in the runtime environment, then either add the changes there also or reload firewalld.")
    runtime = _("Runtime mode allows to configure things at runtime. Things changed at runtime will not present at next start up or reloading firewalld, if you want that you need to add those changes in permanent mode also. ")
    zones = _('A zone is a set of services that can be applied to a binding. A collection of zones is predefined for different levels of trust. If you select the "Permanent" configuration, you can also add, edit or delete your own zone and define which services will be allowed in your zone. ') +\
          _("For a zone, available fields are name, version, short as more descriptive name, and description. A check box allows to activate default target or to select the default behaviour for packets that don't match any rule. Targets are DROP, REJECT or ACCEPT. ") +\
          _("Predefined zones are: block - dmz - drop - external - home - home - internal - public - trusted - work")
    configure_zone = _('After selecting "Zones" for view and one of the Zones, you can configure said zone. There are some parameters for each zone:') +\
          _('<ul><li><b>Services</b>: when selected in "Configure" option, you see a list of services that are predefined. According to the zone, some services are already selected. If you tick or untick a checkbox in regard to a service, the according rules will applying to allow said service on interfaces having the zone. In permanent mode, the configuration is registered directly, but not applied. It will be applied after a firewalld reload.</li>') +\
          _('<li><b>Ports</b>: this configure option allows to specify a rule with "Add" button with a port number or range and a protocol selected in the list tcp, udp, sctp and dccp. The list view displays the already defined rules. A range is defined with a hyphen between two numbers, for example with 80-88. The effect will be that these ports will be open.</li>') +\
          _('<li><b>Protocols</b>: Here, you can add a protocol among a list of supported protocols by firewalld or to add a specific one that you can name. (to complete with what is the effect of this addition)</li>') +\
          _('<li><b>Source Ports</b>: this configure option allows to specify a rule with "Add" button with a port number or range and a protocol selected in the list tcp, udp, sctp and dccp. The list view displays the already defined rules.(to complete with what is the effect of this addition)</li>') +\
          _('<li><b>Masquerading</b>: this option allows to tick or untick a "Masquerade zone". Thus this zone is used for masquerading (only for IPv4). (to complete with what is the effect of this addition)</li>') +\
          _('<li><b>Port Forwarding</b>: port forwarding is an application of network address translation (NAT) that redirects a communication request from one address and port number combination to another while the packets are traversing the firewall in IPv4 technology. Adding a rule needs to specify a port or port range of incoming requests and its protocol (source) and either a port or range for the destination for local forwarding or address of the destination and optionally port or range if port is changed.</li>') +\
          _('<li><b>ICMP Filter</b>: not yet implemented</li>') +\
          _('<li><b>Rich Rules</b>: not yet implemented</li>') +\
          _('<li><b>Interfaces</b>: not yet implemented</li>') +\
          _('<li><b>Sources</b>: not yet implemented</li></ul>')

    services = _('A service is a collection of rules that are applied together in relation to an application. This concept helps to apply what is need for an application by just ticking a checkbox. A lot of services are already defined, but you can add your own for an application which is not provided.') +\
               _('In view "Services", the "Configure" button next to the combobox allows to choose a service. Selecting one updates the table with a list of couples Port-Protocol ')
    configure_services = _('For each service, you can define:') +\
          _('<ul><li><b>Ports</b>: when selected, the list view contains the ports already defined. Each port is defined by a number or a range, and a protocol.</li>') +\
          _('<li><b>Protocols</b>: not yet implemented</li>') +\
          _('<li><b>Source Ports</b>: not yet implemented</li>') +\
          _('<li><b>Modules</b>: not yet implemented</li>') +\
          _('<li><b>Destination</b>: not yet implemented</li></ul>')

    self.text = {
      'home': '<h1>Manafirewall</h1>%s<br>%s<br>%s<br>%s<br>%s<br>%s<br><br>%s'%(
        _("ManaFirewall is a graphical configuration tool for firewall features provided by firewalld."),
        _("firewalld provides a dynamically managed firewall with support for network/firewall “zones” to assign a level of trust to a network and its associated connections, interfaces or sources."),
        _("It has support for IPv4, IPv6, Ethernet bridges and also for IPSet firewall settings. There is a separation of the runtime and permanent configuration options."),
        _("ManaFirewall is part of manatools and it is based on libyui so that it can work using Gtk, Qt or ncurses, i.e. graphical or textual user interfaces."),
        _("On the left there is the overview of the active bindings. These are the zones, that have a connection, interface or source bound or added to it. Here it is possible to easily change the\
          zone of these bindings."),
        _("On the right there are comboboxes to select what to look or configure such as zones, services etc."),
        index
      ),
      'configuration_cbx' : '<h1>%s</h1><h2>%s</h2>%s<h2>%s</h2>%s<br><br>%s'%(_("Duration"), _("Permanent"), permanent, _("Runtime"), runtime, home_lnk
      ),
      'view_cbx' : '<h1>%s</h1>%s<br><br>%s'%(_("View"),view_index, home_lnk
      ),
      'zones_view_cbx' : '<h1>%s</h1> <br>%s<br><h2>%s</h2>%s<br><br>%s'%(_("Zones view"),zones,_("Configure zone"), configure_zone, home_lnk
      ),
      'services_view_cbx' : '<h1>%s</h1> <br>%s<br><h2>%s</h2>%s<br><br>%s'%(_("Services view"),services,_("Configure services"), configure_services, home_lnk
      ),
      'ipsets_view_cbx' : '<h1>%s</h1> <br><br>%s'%(_("IP Sets view"),home_lnk)
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
  
  
