from __future__ import print_function

import json
import os
import socket
import struct
import sys
import time

try:
    from socketserver import BaseRequestHandler, ThreadingTCPServer
except ImportError:
    from SocketServer import BaseRequestHandler, ThreadingTCPServer


MASTER = "10.0.0.1"
PORT = 502
BLOCKS = ((0, 123), (123, 123), (246, 10))
WRITE_REGISTERS = 16


def read_exact(sock, size):
    chunks = []
    while size:
        chunk = sock.recv(size)
        if not chunk:
            raise EOFError("Incomplete Modbus message")
        chunks.append(chunk)
        size -= len(chunk)
    return b"".join(chunks)


def receive(sock):
    transaction, protocol, length, unit = struct.unpack("!HHHB", read_exact(sock, 7))
    if protocol != 0 or unit != 1 or not 2 <= length <= 254:
        raise ValueError("Invalid Modbus/TCP header")
    return transaction, read_exact(sock, length - 1)


def transmit(sock, transaction, pdu):
    sock.sendall(struct.pack("!HHHB", transaction, 0, len(pdu) + 1, 1) + pdu)


def write_request(address, count, registers):
    return struct.pack("!BHHB", WRITE_REGISTERS, address, count, len(registers)) + registers


def write_bytes(data):
    """Return register bytes in a complete synthetic write request."""
    if len(data) < 13:
        return 0
    _, protocol, length, unit, function, address, count, size = struct.unpack(
        "!HHHBBHHB", data[:13])
    if (protocol == 0 and unit == 1 and function == WRITE_REGISTERS
            and (address, count) in BLOCKS and size == count * 2
            and length == size + 7 and len(data) == size + 13):
        return size
    return 0


class Collector(BaseRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        station = int(self.client_address[0].rsplit(".", 1)[1])
        if not 2 <= station <= 10:
            return
        cycle = None
        reading = []
        for index, (address, count) in enumerate(BLOCKS):
            transaction, request = receive(self.request)
            current_cycle, block = divmod(transaction - 1, len(BLOCKS))
            registers = struct.pack("!H", station) * count
            if index == 0:
                cycle = current_cycle
            if block != index or cycle != current_cycle or cycle < 0:
                raise ValueError("Unexpected Modbus transaction")
            if request != write_request(address, count, registers):
                raise ValueError("Unexpected register write")
            reading.append(registers)
            if index == len(BLOCKS) - 1:
                name = "station-%02d-%03d.dat" % (station, cycle)
                with open(os.path.join(self.server.output, name), "wb") as output:
                    output.write(b"".join(reading))
            transmit(self.request, transaction, request[:5])


class ModbusServer(ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def serve(path):
    server = ModbusServer((MASTER, PORT), Collector)
    server.output = path
    print("Listening for Modbus/TCP reports")
    server.serve_forever()


def send(station, start, cycles, interval):
    for cycle in range(cycles):
        time.sleep(max(0, start + cycle * interval - time.time()))
        began = time.time()
        error = None
        connection = None
        try:
            connection = socket.create_connection((MASTER, PORT), timeout=10)
            for index, (address, count) in enumerate(BLOCKS):
                transaction = cycle * len(BLOCKS) + index + 1
                registers = struct.pack("!H", station) * count
                request = write_request(address, count, registers)
                transmit(connection, transaction, request)
                if receive(connection) != (transaction, request[:5]):
                    raise ValueError("Unexpected Modbus write acknowledgement")
        except (socket.error, EOFError, ValueError) as failure:
            error = str(failure)
        finally:
            if connection is not None:
                connection.close()
        print(json.dumps({"station": station, "cycle": cycle, "start": began,
                          "elapsed": time.time() - began, "error": error}))


if __name__ == "__main__":
    if sys.argv[1] == "server":
        serve(sys.argv[2])
    else:
        send(int(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
