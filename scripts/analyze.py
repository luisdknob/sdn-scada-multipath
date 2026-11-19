import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import median
import struct

from workload import PORT, write_bytes


def packets(path):
    with path.open("rb") as stream:
        header = stream.read(24)
        assert header[:4] == b"\xd4\xc3\xb2\xa1", path
        assert int.from_bytes(header[20:24], "little") == 1, path
        while record := stream.read(16):
            seconds, microseconds, captured, size = struct.unpack("<IIII", record)
            packet = stream.read(captured)
            assert len(packet) == captured, path
            yield seconds + microseconds / 1e6, size, packet


def tcp(packet):
    if len(packet) < 54 or packet[12:14] != b"\x08\x00" or packet[23] != 6:
        return None
    ip_end = 14 + int.from_bytes(packet[16:18], "big")
    tcp_start = 14 + (packet[14] & 15) * 4
    header = struct.unpack_from("!HHIIBBHHH", packet, tcp_start)
    source_port, target_port, seq, ack, offset, flags, _, _, _ = header
    data = packet[tcp_start + (offset >> 4) * 4:ip_end]
    return (packet[26:30], packet[30:34], source_port, target_port, seq, ack,
            flags, packet[18:20], data)


def controller(path, start, end):
    frames = total_bytes = 0
    messages = Counter()
    streams = {}
    for now, size, packet in packets(path):
        in_window = start <= now < end
        if in_window:
            frames += 1
            total_bytes += size
        if not (segment := tcp(packet)) or not segment[-1]:
            continue
        src, dst, sport, dport, seq, _, _, _, data = segment
        if dport != 6633:
            continue
        key = src, dst, sport, dport
        following, pending = streams.get(key, (seq, b""))
        if seq > following:
            following, pending = seq, b""
        if seq + len(data) <= following:
            continue
        pending += data[following - seq:]
        offset = 0
        while len(pending) - offset >= 8:
            version, kind, length, _ = struct.unpack_from("!BBHI", pending, offset)
            assert version == 1 and 8 <= length and kind <= 21, (path, version, kind, length)
            if offset + length > len(pending):
                break
            if in_window:
                messages[kind] += 1
            offset += length
        streams[key] = seq + len(data), pending[offset:]
    assert frames and messages[10], path
    return {"frames": frames, "link_bytes": total_bytes, "packet_in": messages[10]}


def station_packets(path, start, end, register_only):
    seen = defaultdict(Counter)
    for now, _, packet in packets(path):
        if not start <= now < end or not (segment := tcp(packet)):
            continue
        src, dst, source_port, target_port, _, _, _, _, payload = segment
        if PORT not in (source_port, target_port):
            continue
        if src[-1] == 1 or dst[-1] == 1:
            station = dst[-1] if src[-1] == 1 else src[-1]
            if 2 <= station <= 10:
                if register_only:
                    if dst[-1] == 1 and write_bytes(payload):
                        # Transaction IDs are unique per substation and report block.
                        seen[station][payload] = 1
                else:
                    seen[station][segment] += 1
    return seen


def exposure(folder, start, end, register_only):
    reference = station_packets(folder / "master.pcap", start, end, register_only)
    by_link = {file.stem: station_packets(file, start, end, register_only)
               for file in sorted(folder.glob("link-*.pcap"))}
    assert len(by_link) == 5

    def weight(counts):
        if register_only:
            return sum(write_bytes(payload) * count for payload, count in counts.items())
        return counts.total()

    per_station = {}
    for station, counts in sorted(reference.items()):
        total = weight(counts)
        shares = {link: weight(linked[station] & counts) for link, linked in by_link.items()}
        field = "register_bytes" if register_only else "packets"
        per_station[station] = {field: total, "by_link": shares,
                                "max_exposure_pct": round(100 * max(shares.values()) / total, 2)}
    return per_station


def analyze(folder):
    run = json.loads((folder / "run.json").read_text())
    start, end = run["start_epoch"], run["end_epoch"]
    duration = run["duration_seconds"]
    control = controller(folder / "control.pcap", start, end)
    attempts = [json.loads(line) for log in sorted(folder.glob("h*.jsonl"))
                for line in log.read_text().splitlines()]
    assert len(attempts) == run["cycles"] * run["senders"]
    completed = [attempt["elapsed"] for attempt in attempts if attempt["error"] is None]
    return {**run,
            "acknowledged_reports": len(completed),
            "median_report_seconds": round(median(completed), 4) if completed else None,
            "frames_per_second": round(control["frames"] / duration, 2),
            "control_kbps": round(8 * control["link_bytes"] / (duration * 1000), 2),
            "packet_ins_per_second": round(control["packet_in"] / duration, 2),
            "register_data_exposure": exposure(folder, start, end, True),
            "all_tcp_exposure": exposure(folder, start, end, False)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+", type=Path)
    print(json.dumps([analyze(path) for path in parser.parse_args().runs], indent=2, sort_keys=True))
