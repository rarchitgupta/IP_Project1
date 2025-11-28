# P2P-CI System: Peer-to-Peer with Centralized Index

A Python implementation of a P2P file-sharing system for downloading RFCs (Requests for Comments).

## Project Structure

```
project_1/
├── src/                    # Source code
│   ├── __init__.py
│   ├── server.py          # Central server
│   ├── peer.py            # Peer client implementation
│   ├── protocol.py        # Protocol parsing/formatting utilities
│   └── constants.py       # Constants and configuration
├── tests/                 # Unit tests
├── data/                  # Sample RFCs and peer data
├── Makefile              # Build commands
├── requirements.txt      # Python dependencies
└── README.md
```

## Setup & Installation

1. **Set up virtual environment:**
   ```bash
   make setup
   ```

2. **Activate virtual environment:**
   ```bash
   source .venv/bin/activate
   ```

## Running the System

### Start the Central Server

```bash
make run-server
```

The server will listen on port 7734.

### Start a Peer

```bash
make run-peer PEER_DIR=/path/to/peer/data
```

Example with a test peer directory:

```bash
mkdir -p data/peer1
make run-peer PEER_DIR=data/peer1
```

## Development

### Run Tests

```bash
make test
```

### Clean Up

```bash
make clean
```

## Implementation Notes

- **Language:** Python 3
- **Concurrency:** Uses multiprocessing for handling multiple peer connections
- **Protocol:** Custom P2P-CI protocol over TCP
- **Port:** Server runs on port 7734 (well-known port)

## Protocols

### P2S (Peer-to-Server)
- **ADD:** Register RFC at server
- **LOOKUP:** Find peers with specific RFC
- **LIST:** Get complete RFC index

### P2P (Peer-to-Peer)
- **GET:** Download RFC from peer
- **Response:** File data with headers

See PROJECT.md for detailed protocol specifications.
