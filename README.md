# Capitalizing on SDN-Based SCADA Systems: An Anti-Eavesdropping Case-Study

This repository contains the POX multipath controller and Mininet topology for the paper published at IM 2015. The paper evaluates how rotating routes affects the share of a substation's traffic visible from a single link near the master station.

Eduardo Germano da Silva, Luis Augusto Dias Knob, Juliano Araujo Wickboldt, Luciano Paschoal Gaspary, Lisandro Zambenedetti Granville, and Alberto Schaeffer-Filho (2015). *Capitalizing on SDN-Based SCADA Systems: An Anti-Eavesdropping Case-Study*. IFIP/IEEE International Symposium on Integrated Network Management. [Paper](https://doi.org/10.1109/INM.2015.7140289)

## Release Note

> [!NOTE]
> This post-publication release is part of an ongoing effort to improve the reproducibility and verifiability of my research. For this paper, I am making the source code and experimental configurations publicly available. I plan to gradually release artifacts from more of my research projects over time.
>
> Some files needed to rerun the experiments were unavailable. I used GPT-6.2 Sol to help reconstruct the experiment runner, the ten-host Mininet scenario, and a synthetic Modbus/TCP workload on the `reproduction` branch. I also used it to adapt Mininet to work with the interface names reported by newer Linux kernels.

## Source and Scenario

- [POX controller](code/graphcontrol.py)
- [Mininet topology and configuration](code/topo-mesh.py)
- The [original source ZIP](archive/im2015-original-source.zip) preserves the source bytes and the modification times recorded on the surviving copies. [Checksums](MANIFEST.sha256)

The `reproduction` branch contains a runnable scenario based on the paper and instructions for generating fresh results.

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
