# P2P-CI System: Peer-to-Peer with Centralized Index

A Python implementation of a P2P file-sharing system for downloading RFCs (Requests for Comments).

Run everything from the project root (the folder that contains Makefile and src/).

1. Create Sample Peers and RFC Files
mkdir -p data/peerA data/peerB

Peer A has RFC 123 and RFC 2000
printf "TCP/IP Illustrated\n(peerA content)\n" > data/peerA/rfc123.txt

printf "Sockets 101\n(peerA content)\n" > data/peerA/rfc2000.txt

Peer B has RFC 2345
printf "Routing Protocols\n(peerB content)\n" > data/peerB/rfc2345.txt

2. Start the Server (Terminal A)

From the project root:

make setup
make run-server


You should see:
Starting Peers

3. Start Each Peer
Terminal B — Peer A
make run-peer PEER_DIR=data/peerA

Terminal C — Peer B
make run-peer PEER_DIR=data/peerB

4. LIST ALL (from Peer A)

In Terminal B:

p2p> list

Expected Output
P2P-CI/1.0 200 OK
123  TCP/IP Illustrated   <peerA> <portA>
2345 Routing Protocols    <peerB> <portB>

5. LOOKUP (Peer A looking up Peer B’s RFC)

From Peer A:

p2p> lookup 2345

Expected Output
P2P-CI/1.0 200 OK
2345 Routing Protocols <peerB> <portB>

6. GET (Peer A downloads RFC 2345 from Peer B)

In Peer A:

p2p> get 2345

Expected Behavior

Peer A logs download activity

Saves file to:

data/peerA/rfc2345.txt


Then sends an ADD to the server to register the new RFC

7. Peer Disconnect Cleanup

In Peer B terminal:

p2p> quit


Server should automatically:

Remove Peer B from active peer list

Remove all of Peer B’s RFC index entries

8. LIST AGAIN to Confirm Cleanup

Back in Peer A:

p2p> list

Expected Output

Peer B’s entries should no longer appear.
