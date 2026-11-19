from __future__ import print_function

import argparse
import json
import os
import signal
import subprocess
import sys
import time

from mininet.link import TCLink
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import Topo
from workload import PORT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PaperTopology(Topo):
    def __init__(self, switch_links):
        Topo.__init__(self)
        for index in range(1, 11):
            self.addSwitch("s%d" % index, protocols="OpenFlow10")
            self.addHost("h%d" % index)
            self.addLink("h%d" % index, "s%d" % index)
        for left, right in switch_links:
            self.addLink("s%d" % left, "s%d" % right)


def wait_for_file(path, process):
    deadline = time.time() + 8
    while time.time() < deadline:
        if os.path.exists(path) and os.path.getsize(path):
            return
        if process.poll() is not None:
            raise RuntimeError("Child process exited before creating %s" % path)
        time.sleep(0.05)
    raise RuntimeError("Timed out waiting for %s" % path)


def stop(process):
    if process is None or process.poll() is not None:
        return
    process.send_signal(signal.SIGINT)
    deadline = time.time() + 3
    while process.poll() is None and time.time() < deadline:
        time.sleep(0.05)
    if process.poll() is None:
        process.kill()
    process.wait()


def run(args):
    with open(os.path.join(ROOT, "data", "scenario.json")) as stream:
        config = json.load(stream)
    cycles = args.cycles if args.cycles is not None else config["pilot_cycles"]
    interval = config["report_interval_seconds"]
    out = os.path.abspath(args.output)
    os.mkdir(out)
    reports = os.path.join(out, "reports")
    os.mkdir(reports)
    script = os.path.join(ROOT, "scripts", "workload.py")

    children = []
    captures = []
    logs = []
    net = None

    def spawn(command, logname, host=None):
        log = open(os.path.join(out, logname), "wb")
        logs.append(log)
        launch = host.popen if host else subprocess.Popen
        child = launch(command, stdout=log, stderr=subprocess.STDOUT)
        children.append(child)
        return child

    def capture(label, interface, packet_filter):
        target = os.path.join(out, label + ".pcap")
        proc = spawn(["tcpdump", "-n", "-U", "-s", "0", "-i", interface, "-w",
                      target, packet_filter], label + ".capture.log")
        captures.append(proc)
        wait_for_file(target, proc)

    try:
        controller = ["python", "-u", args.home + "/pox/pox.py", "openflow.of_01",
                      "--address=127.0.0.1", "--port=6633"]
        if args.scenario == "baseline":
            controller.extend(["openflow.discovery", "openflow.spanning_tree",
                               "--no-flood", "--hold-down",
                               "forwarding.l2_learning"])
        else:
            controller.append("graphcontrol")
        pox = spawn(controller, "pox.log")
        time.sleep(1)
        if pox.poll() is not None:
            raise RuntimeError("POX exited before Mininet startup")

        capture("control", "lo", "tcp port 6633")
        net = Mininet(topo=PaperTopology(config["switch_links"]), controller=None, switch=OVSSwitch,
                      link=TCLink, autoSetMacs=True, autoStaticArp=False)
        net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6633)
        net.start()
        master_switch = net.get("s1")
        master_host = net.get("h1")
        server = spawn(["python", "-u", script, "server", reports],
                       "modbus-server.log", master_host)
        wait_for_file(os.path.join(out, "modbus-server.log"), server)
        # Allow OpenFlow connections, LLDP discovery and spanning tree to settle.
        time.sleep(12)
        connected = [switch.name for switch in net.switches if switch.connected()]
        if len(connected) != 10:
            raise RuntimeError("Only these switches connected: %s" % connected)

        for index in [0] + config["monitored_neighbors"]:
            peer = master_host if index == 0 else net.get("s%d" % index)
            [(interface, _)] = master_switch.connectionsTo(peer)
            label = "master" if index == 0 else "link-s%d" % index
            capture(label, interface.name, "tcp port %d and host 10.0.0.1" % PORT)

        start_at = time.time() + 1
        clients = []
        for index in range(2, 11):
            command = ["python", "-u", script, "client", str(index), str(start_at),
                       str(cycles), str(interval)]
            clients.append(spawn(command, "h%d.jsonl" % index, net.get("h%d" % index)))

        print("%s: switches connected, collecting %d reporting cycles" %
              (args.scenario, cycles))
        sys.stdout.flush()
        end_at = start_at + cycles * interval
        while time.time() < end_at:
            if pox.poll() is not None or server.poll() is not None:
                raise RuntimeError("A required process exited during the workload")
            if time.time() >= start_at + interval - 2 and not os.listdir(reports):
                raise RuntimeError("No reports reached the master during the first cycle")
            time.sleep(min(1, max(0, end_at - time.time())))
        for child in clients:
            if child.poll() is None or child.returncode:
                raise RuntimeError("A workload client did not complete")
        for child in captures:
            if child.poll() is not None:
                raise RuntimeError("A packet capture exited during the workload")
        summary = {"scenario": args.scenario, "cycles": cycles,
                   "senders": 9, "duration_seconds": cycles * interval,
                   "start_epoch": start_at, "end_epoch": end_at,
                   "received_reports": sum(os.path.getsize(os.path.join(reports, name)) == 512
                                           for name in os.listdir(reports)),
                   "kernel": os.uname()[2]}
        with open(os.path.join(out, "run.json"), "w") as stream:
            json.dump(summary, stream, indent=2, sort_keys=True)
        print(summary)
        sys.stdout.flush()
    finally:
        for child in reversed(children):
            stop(child)
        if net is not None:
            net.stop()
        for log in logs:
            log.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=("baseline", "multipath"))
    parser.add_argument("output")
    parser.add_argument("--home", required=True)
    parser.add_argument("--cycles", type=int, choices=range(1, 41), metavar="1-40")
    run(parser.parse_args())
