# vim: set fileencoding=utf-8 :
# vim: set et ts=4 sw=4:

'''
HelpInfo contains text for help menu

License: GPLv2+

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

    permanent = _("Permanent mode allows you to configure things that are not immediately active. If you also want changes to be active in the runtime environment, either add them there as well or reload firewalld.")
    runtime = _("Runtime mode allows you to configure things at runtime. Things changed at runtime will not persist after the next start up or firewalld reload; if you want them to persist, you need to add those changes in permanent mode as well.")
    zones = _('A zone is a set of services that can be applied to a binding. A collection of zones is predefined for different levels of trust. If you select the "Permanent" configuration, you can also add, edit or delete your own zone and define which services will be allowed in your zone. ') +\
          _("For a zone, available fields are name, version, short (a more descriptive name), and description. A check box allows you to activate the default target or to select the default behaviour for packets that don't match any rule. Targets are DROP, REJECT or ACCEPT. ") +\
          _("Predefined zones are: block - dmz - drop - external - home - internal - public - trusted - work")
    configure_zone = _('After selecting "Zones" as the View and one of the Zones, you can configure the selected zone. There are some parameters for each zone:') +\
          _('<ul><li><b>Services</b>: when selected in the "Configure" option, you see a list of predefined services. According to the zone, some services are already selected. If you tick or untick a checkbox for a service, the corresponding rules will be applied to allow or deny that service on interfaces using the zone. In permanent mode, the configuration is registered directly but not applied immediately; it will be applied after a firewalld reload.</li>') +\
          _('<li><b>Ports</b>: this option allows you to define a rule using the "Add" button, specifying a port number or range and a protocol selected from the list tcp, udp, sctp and dccp. The list view displays the already defined rules. A range is specified with a hyphen between two numbers, for example 80-88. The effect is that those ports will be open.</li>') +\
          _('<li><b>Protocols</b>: Here, you can add a protocol from a list of protocols supported by firewalld, or add a custom one by name.</li>') +\
          _('<li><b>Source Ports</b>: this option allows you to define a rule using the "Add" button, specifying a source port number or range and a protocol selected from the list tcp, udp, sctp and dccp. The list view displays the already defined rules.</li>') +\
          _('<li><b>Masquerading</b>: this option allows you to enable or disable masquerading for the zone (IPv4 only).</li>') +\
          _('<li><b>Port Forwarding</b>: port forwarding is an application of network address translation (NAT) that redirects a communication request from one address and port number combination to another while the packets are traversing the firewall (IPv4 only). Adding a rule requires specifying a port or port range for incoming requests and its protocol (source), and either a port or range for the destination for local forwarding, or an address and optional port or range if the destination address changes.</li>') +\
          _('<li><b>ICMP Filter</b>: not yet implemented</li>') +\
          _('<li><b>Rich Rules</b>: not yet implemented</li>') +\
          _('<li><b>Interfaces</b>: not yet implemented</li>') +\
          _('<li><b>Sources</b>: not yet implemented</li></ul>')

    services = _('A service is a collection of rules that are applied together in relation to an application. This concept helps to apply what is needed for an application by just ticking a checkbox. A lot of services are already defined, but you can add your own for an application that is not provided.') +\
               _('In the "Services" view, the "Configure" button next to the combobox allows you to choose a service. Selecting one updates the table with a list of Port-Protocol pairs.')
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
        _("ManaFirewall is part of manatools and it is based on manatools.aui so that it can work using Qt (PySide6), GTK 4, or ncurses, i.e. both graphical and textual user interfaces."),
        _("On the left there is the overview of the active bindings. These are the zones, that have a connection, interface or source bound or added to it. Here it is possible to easily change the zone of these bindings."),
        _("On the right there are comboboxes to select what to look or configure such as zones, services etc."),
        index
      ),
      'configuration_cbx' : '<h1>%s</h1><h2>%s</h2>%s<br><h2>%s</h2>%s<br><br>%s'%(_("Duration"), _("Permanent"), permanent, _("Runtime"), runtime, home_lnk
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
  
  
