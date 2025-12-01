#!/bin/bash
# Setup demo test data with specific RFC numbers for live demo

rm -rf data/demo_peer_a data/demo_peer_b

mkdir -p data/demo_peer_a data/demo_peer_b

# Peer A has RFC 123
echo "TCP/IP Illustrated
This RFC describes the TCP/IP protocol stack.
It covers network layers, protocols, and implementation details.
Written by Richard Stevens.
This is demonstration content for the demo." > data/demo_peer_a/rfc123.txt

# Peer B has RFC 2345
echo "Routing Protocols
This RFC covers various routing protocols used in networks.
It includes BGP, OSPF, and IS-IS protocols.
Details on convergence and optimization strategies.
This is demonstration content for the demo." > data/demo_peer_b/rfc2345.txt

echo "✓ Demo data created:"
echo "  data/demo_peer_a/rfc123.txt (for Peer A)"
echo "  data/demo_peer_b/rfc2345.txt (for Peer B)"
