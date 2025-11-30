VENV=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

setup:
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

run-server:
	PYTHONPATH=. $(PY) -m src.server

run-peer:
	@if [ -z "$(PEER_DIR)" ]; then echo "Usage: make run-peer PEER_DIR=data/peer1"; exit 1; fi
	PYTHONPATH=. $(PY) -m src.peer --peer-dir $(PEER_DIR) --server-host 127.0.0.1

test:
	PYTHONPATH=. $(PY) -m pytest tests/ -v

test-coverage:
	PYTHONPATH=. $(PY) -m pytest tests/ -v --cov=src --cov-report=term-missing

clean:
	rm -rf $(VENV) __pycache__ src/__pycache__ tests/__pycache__
