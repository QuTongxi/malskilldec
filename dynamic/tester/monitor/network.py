"""Network activity, captured with tcpdump inside the container.

Only the *requests* are kept: the names the container resolved and the addresses
it opened a connection to.  A single page fetch produces hundreds of packets and
none of them say more than "it contacted this host", so the capture filter is
DNS plus bare TCP SYNs and nothing else.

The tester agent talks to its own model provider over the same interface, so
those addresses are subtracted before the evidence is handed on.
"""

import os
import re
import subprocess
from urllib.parse import urlparse

LOG = "/tmp/net.log"
FILTER = "udp port 53 or (tcp[tcpflags] & tcp-syn != 0 and tcp[tcpflags] & tcp-ack == 0)"

# 12:00:00.0 IP 172.17.0.2.51201 > 10.0.0.1.53: 4711+ A? example.com. (29)
QUERY = re.compile(r"> \S+\.53: (\d+)\+? .*?\b(?:A|AAAA)\? (\S+?)\.? ")
# 12:00:00.0 IP 10.0.0.1.53 > 172.17.0.2.51201: 4711 1/0/0 A 93.184.216.34 (45)
RESPONSE = re.compile(r"IP6? \S+\.53 > \S+: (\d+)[ *]")
ADDRESS = re.compile(r"\b(?:A|AAAA) ([\d.]+|[0-9a-fA-F:]{6,})\b")
# 12:00:00.0 IP 172.17.0.2.44102 > 93.184.216.34.443: Flags [S], seq 1, length 0
SYN = re.compile(r"IP6? \S+ > ([\d.]+|[0-9a-fA-F:]{6,})\.(\d+): Flags \[S\]")

MAX_ENTRIES = 60


def exec_(container, command, timeout=60):
    return subprocess.run(["docker", "exec", container, "bash", "-lc", command],
                          capture_output=True, text=True, timeout=timeout)


def start(container):
    """Begin capturing.  Returns what `stop` and `parse` need to finish the job."""
    exec_(container, "rm -f %s; nohup tcpdump -i any -n -l '%s' > %s 2>&1 & sleep 1"
          % (LOG, FILTER, LOG), timeout=60)
    started = exec_(container, "cat %s" % LOG).stdout
    if "listening on" not in started:
        raise RuntimeError("tcpdump did not start in %s: %s" % (container, started.strip()))

    host = urlparse(os.environ["openai_api_url"]).hostname
    resolved = exec_(container, "getent ahosts %s | awk '{print $1}' | sort -u" % host).stdout
    return host, set(resolved.split())


def stop(container):
    exec_(container, "pkill -INT tcpdump; sleep 1")
    return exec_(container, "cat %s" % LOG).stdout.splitlines()


def parse(lines, provider):
    """Turn tcpdump output into the reviewer's network evidence."""
    host, addresses = provider
    by_id, names = {}, {}
    queried, connections = [], []

    for line in lines:
        query = QUERY.search(line)
        if query:
            by_id[query.group(1)] = query.group(2)
            if not query.group(2).endswith(host) and query.group(2) not in queried:
                queried.append(query.group(2))
            continue

        response = RESPONSE.search(line)
        if response and response.group(1) in by_id:
            for address in ADDRESS.findall(line):
                names[address] = by_id[response.group(1)]
            continue

        syn = SYN.search(line)
        if syn and syn.group(1) not in addresses:
            name = names.get(syn.group(1), "")
            if name.endswith(host):
                continue
            entry = "%s:%s" % (syn.group(1), syn.group(2))
            if name:
                entry += "  (%s)" % name
            if entry not in connections:
                connections.append(entry)

    evidence = (["resolved  %s" % name for name in queried[:MAX_ENTRIES]]
                + ["connected %s" % entry for entry in connections[:MAX_ENTRIES]])
    return evidence or ["<no outbound request>"]
