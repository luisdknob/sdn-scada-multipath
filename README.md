# Capitalizing on SDN-Based SCADA Systems: An Anti-Eavesdropping Case-Study

This repository contains the POX multipath controller and Mininet topology for the paper published at IM 2015. The paper evaluates how rotating routes affects the share of a substation's traffic visible from a single link near the master station.

Eduardo Germano da Silva, Luis Augusto Dias Knob, Juliano Araujo Wickboldt, Luciano Paschoal Gaspary, Lisandro Zambenedetti Granville, and Alberto Schaeffer-Filho (2015). *Capitalizing on SDN-Based SCADA Systems: An Anti-Eavesdropping Case-Study*. IFIP/IEEE International Symposium on Integrated Network Management. [Paper](https://doi.org/10.1109/INM.2015.7140289)

## Release Note

> [!NOTE]
> This post-publication release is part of an ongoing effort to improve the reproducibility and verifiability of my research. For this paper, I am making the source code and experimental configurations publicly available. I plan to gradually release artifacts from more of my research projects over time.
>
> Some files needed to rerun the experiments were unavailable. I used GPT-6.2 Sol to help reconstruct the experiment runner, the ten-host Mininet scenario, and a synthetic Modbus/TCP workload on the `reproduction` branch. I also used it to adapt Mininet to work with the interface names reported by newer Linux kernels. I also used GPT-6.2 Sol to help fix the forwarding of the packet that triggers a route change.

## Source and Scenario

- [POX controller with the route-change fix](code/graphcontrol.py)
- [Mininet topology and configuration](code/topo-mesh.py)
- The [original source ZIP](archive/im2015-original-source.zip) preserves the source bytes and the modification times recorded on the surviving copies. [Checksums](MANIFEST.sha256)

## Reproduction

The results below come from fresh runs of the reconstructed experiment.

### Scenario

Nine substations each send 512 bytes of register data to the master every 15 seconds. Each report uses one TCP connection and three Modbus/TCP Write Multiple Registers requests so each request fits within the protocol limits. The [scenario configuration](data/scenario.json) defines the 17 switch links and the five links monitored next to the master station.

| Case | Routing |
| --- | --- |
| A | POX learning switch with spanning tree |
| C | Multipath with route-change forwarding fixed and a 10-second hard timeout |

The default pair runs for 120 seconds per case on unshaped virtual links. The paper specifies 600 seconds and 10 Gb/s links. The baseline uses POX's startup hold-down so the spanning tree can settle before forwarding flooded traffic.

### Settings and Execution

Use a dedicated x86-64 Ubuntu 14.04 Linux guest with Python 2.7, `dpkg-deb`, `tcpdump`, `ip`, `tc`, and `flock`. The guest must support network namespaces, virtual Ethernet devices, and the Open vSwitch kernel datapath. An LXC guest with nesting enabled was used for validation.

```sh
bash scripts/fetch_dependencies.sh
bash scripts/prepare.sh
sudo bash scripts/run.sh modbus-pilot
```

The dependency scripts verify the [package checksums](data/dependencies.sha256) and extract the pinned Mininet, Open vSwitch, POX, and NetworkX versions locally. The only source compatibility change is a Mininet interface-name check. To prepare an offline guest, call `bash scripts/fetch_dependencies.sh /path/to/packages` on a connected Linux machine, transfer that directory, then call `bash scripts/prepare.sh /path/to/packages` in the guest.

To run both cases for 600 seconds each, use `sudo bash scripts/run.sh modbus-full 40`. Each run directory contains packet captures, client logs, and received register data.

### Results

Copy the run directory to a machine with Python 3.10 or newer and run this command from the repository root.

```sh
python3 scripts/analyze.py runs/modbus-pilot/baseline runs/modbus-pilot/multipath
```

The analyzer reports the largest share of each substation's register data and TCP traffic visible on any one monitored link. Repeated transmissions of the same register data count once per link. The analyzer counts controller-link frames and OpenFlow `Packet-In` messages separately.

These results use the archived controller on `reproduction`.

| Measurement | A · Single path | C · Multipath |
| --- | ---: | ---: |
| Completed Modbus/TCP reports | 72/72 | 72/72 |
| Register data visible on the busiest link per substation | 100% | 50% |
| TCP packets visible on the busiest link per substation | 100% | 72.81–75.22% |

The [pilot results](expected/pilot.json) include the counts for each substation and link. Table II of the paper reports 75% TCP packet exposure on the busiest link with multipath.

### Route-change forwarding

When an existing route expires, the controller includes the packet that triggered the change when it installs the next rule. This lets the switch forward that packet without waiting for a TCP retransmission. Initial path setup still follows the archived controller.

| Multipath measurement | Archived controller | Route-change fix |
| --- | ---: | ---: |
| Completed reports | 72/72 | 72/72 |
| Median time to complete a report | 1.0474 s | 0.0259 s |
| Register data visible on the busiest link per substation | 50% | 50% |
| TCP packets visible on the busiest link per substation | 72.81–75.22% | 72.81–75.44% |

Both multipath runs lasted 120 seconds and used the same Modbus/TCP workload. [Fixed pilot results](expected/pilot-fixed.json)

## Citation

```bibtex
@inproceedings{silva2015capitalizing,
  author    = {da Silva, Eduardo Germano and Dias Knob, Luis Augusto and Wickboldt, Juliano Araujo and Gaspary, Luciano Paschoal and Granville, Lisandro Zambenedetti and Schaeffer-Filho, Alberto},
  title     = {Capitalizing on {SDN}-Based {SCADA} Systems: An Anti-Eavesdropping Case-Study},
  booktitle = {2015 IFIP/IEEE International Symposium on Integrated Network Management (IM)},
  year      = {2015},
  pages     = {165--173},
  doi       = {10.1109/INM.2015.7140289}
}
```
