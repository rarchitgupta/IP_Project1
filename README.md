# P2P-CI System: Peer-to-Peer with Centralized Index

A Python implementation of a P2P file-sharing system for downloading RFCs (Requests for Comments).

Run everything from the project root (the folder that contains Makefile and src/).

In the project root, run these commands to create two peers with a few sample RFC files.
	mkdir -p data/peerA data/peerB

# Peer A has RFC 123 and RFC 2000
printf "TCP/IP Illustrated\n(peerA content)\n" > data/peerA/rfc123.txt
printf "Sockets 101\n(peerA content)\n" > data/peerA/rfc2000.txt

# Peer B has RFC 2345
printf "Routing Protocols\n(peerB content)\n" > data/peerB/rfc2345.txt

Terminal A (Server): from the project root, run-
make
make run-server

Starting Peers
Terminal B: start Peer A
make run-peer PEER_DIR=data/peerA
Terminal C: start Peer B
make run-peer PEER_DIR=data/peerB

LIST ALL - Now to demonstrate LIST ALL from Peer A (Terminal B):
p2p> list

Expected: P2P-CI/1.0 200 OK followed by one line per RFC record, e.g.:
123 TCP/IP Illustrated <peerA> <portA>
2345 Routing Protocols <peerB> <portB>

LOOKUP - Next to demonstrate LOOKUP for Peer B’s RFC from Peer A:
p2p> lookup 2345

Expected: 200 OK and at least one matching line for RFC 2345 on peerB.

GET - Download RFC from Peer B to Peer A (GET) and peer disconnect cleanup
	From Peer A (Terminal B), download RFC 2345:
	p2p> get 2345

Expected: Peer A shows a download message, saves file into data/peerA/rfc2345.txt, and then sends an ADD
to the server.

Now close one peer (e.g., Peer B):
In Peer B terminal: 
p2p> quit
Server should remove peer B’s peer record and index entries when the connection closes.

Then from Peer A: 
p2p> list
Expected: peer B’s RFC entries disappear from the list output.
