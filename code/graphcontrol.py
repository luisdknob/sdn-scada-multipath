# Luis Augusto Dias Knob
# Controlador para redes em Grafo

######################### IMPORTTS #########################

from pox.core import core
import pox.openflow.libopenflow_01 as of
import pox.lib.addresses as adr
import copy
import time
from pox.lib.recoco import Timer

import networkx as nx


######################### GLOBAL VARIABLES #########################

#FLOW_IDLE_TIMEOUT = 5
FLOW_HARD_TIMEOUT = 10

grafo = nx.Graph()
groups = []

lock = False
tmp_mac = {}
tmp_flows = []

######################### FUNCTIONS #########################

def resend_packet(con, packet_in, out_port):

    msg = of.ofp_packet_out()
    msg.data = packet_in

    action = of.ofp_action_output(port = out_port)
    msg.actions.append(action)

    con.send(msg)

def flood(con, packet_in, port):
    msg = of.ofp_packet_out()
    msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
    msg.buffer_id = packet_in.buffer_id
    msg.in_port = port
    con.send(msg)

def return_switch(con, packet_in, port):
    msg = of.ofp_packet_out()
    msg.actions.append(of.ofp_action_output(port = of.OFPP_TABLE))
    msg.buffer_id = packet_in.buffer_id
    msg.in_port = port
    con.send(msg)

def packet_discard(con, packet_in):
    resend_packet(con, packet_in, of.OFPP_NONE)

def isRouteCalculated(src, dst):
    for grupo in groups:
        if grupo['dst'] == dst and grupo['src'] == src:
            return grupo
    return None

def install_rule(sw, match, out_port, hard_timeout):
    msg = of.ofp_flow_mod()
    msg.match = match
    msg.hard_timeout = hard_timeout
    msg.actions.append(of.ofp_action_output(port = out_port))
    event = core.openflow.getConnection(sw)
    event.send(msg)

def install_path(src, dst, sport, dport, match, graph):

    fpath = nx.shortest_path(graph, src, dst)

    change_path_weight = copy.deepcopy(graph)
    for l in range(0, len(fpath)-1):
        change_path_weight[fpath[l]][fpath[l+1]]['weight'] = 5

    spath = nx.shortest_path(change_path_weight, src, dst, 'weight')

    pathWithPorts = make_path(fpath, dst, dport, graph)
    spathWithPorts = make_path(spath, dst, dport, graph)

    groups.append({'src': src,'dst': dst,'timestamp': time.time(),'num': 1,'paths': [pathWithPorts[0], spathWithPorts[0]]})

    print fpath
    print spath

    for path in pathWithPorts[1:]:
        install_rule(path[0], match, path[1], 0)

    for path in spathWithPorts[1:]:
        install_rule(path[0], match, path[1], 0)

    install_rule(pathWithPorts[0][0], match, pathWithPorts[0][1], FLOW_HARD_TIMEOUT)

    pathReverse = make_path(fpath[::-1], src, sport, graph)

    #print pathReverse

    for path in pathReverse:
        install_rule(path[0], match.flip(), path[1], 0)

# Cria o path a partir do shortest path
def make_path(path, dst, dport, graph):
    tmp_path = []

    for i in range(0, len(path)-1):
        for portnum, port in graph.node[path[i]]['ports'].iteritems():

            if port['con'] == path[i+1]:
                conPort = portnum
                break
            else:
                conPort = None

        if conPort is None:
            return 0

        tmp_path.append([path[i],conPort])
    tmp_path.append([dst,dport])
    return tmp_path

######################### HANDLES #########################

# Adiciona as entre os nodos do grafo
def _handle_LinkEvent(event):

    for l in core.openflow_discovery.adjacency:
        grafo.add_edge(l.dpid1,l.dpid2)

        grafo.node[l.dpid1]['ports'][l.port1] = { 'con': l.dpid2 }
        grafo.node[l.dpid2]['ports'][l.port2] = { 'con': l.dpid1 }

# Adiciona os nodos no grafo
def _handle_ConnectionUp(event):

    con = event.connection

    grafo.add_node(con.dpid, ports={})

# Handle de PacketIn, encaminha para as  de flood e escolha do melhor caminho
def _handle_PacketIn(event):
    #print tmp_mac

    con = event.connection
    # Pacote Limpo
    packet = event.parsed
    # Pacote Encapsulado
    packet_in = event.ofp

    loc = (con.dpid, event.port)
    oldloc = tmp_mac.get(packet.src)

    if oldloc is None:
        if packet.src.is_multicast is False:
            tmp_mac[packet.src] = loc
    elif oldloc != loc:
        if loc[1] not in grafo.node[loc[0]]['ports']:
            if packet.src.is_multicast is False:
                tmp_mac[packet.src] = loc

    if packet.dst.is_multicast:
        flood(event.connection, packet_in, event.port)
    else:
        if packet.type == packet.ARP_TYPE:
            flood(event.connection, packet_in, event.port)
        elif packet.dst not in tmp_mac:
            flood(event.connection, packet_in, event.port)
        else:
            match = of.ofp_match(dl_src=adr.EthAddr(packet.src),dl_dst=adr.EthAddr(packet.dst))
            calculated = isRouteCalculated(con.dpid,tmp_mac[packet.dst][0])
            print calculated
            if calculated is None:
                install_path(con.dpid,tmp_mac[packet.dst][0],event.port,tmp_mac[packet.dst][1],match,grafo)
            else:
                if time.time() < (calculated['timestamp']+FLOW_HARD_TIMEOUT):
                    return
                else:
                    groups.remove(calculated)
                    print(calculated['paths'][calculated['num']])
                    install_rule(calculated['paths'][calculated['num']][0], match, calculated['paths'][calculated['num']][1], FLOW_HARD_TIMEOUT)
                    calculated['timestamp'] = time.time()
                    if calculated['num'] == 0:
                        num = 1
                    else:
                        num = 0
                    calculated['num'] = num
                    groups.append(calculated)

######################### LAUNCH #########################

def launch():
    import pox.log.color
    pox.log.color.launch()
    import pox.log
    pox.log.launch(format="[@@@bold@@@level%(name)-22s@@@reset] " +
                          "@@@bold%(message)s@@@normal")

    import pox.openflow.discovery
    pox.openflow.discovery.launch()

    import pox.openflow.spanning_tree
    pox.openflow.spanning_tree.launch()

    core.openflow_discovery.addListenerByName("LinkEvent", _handle_LinkEvent)
    core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp)
    core.openflow.addListenerByName("PacketIn", _handle_PacketIn)
