PY ?= python3

.PHONY: build pdf run test clean
build:            ## Workouts (.zwo), App (web/index.html) und Artifact-Seite (dist/artifact.html) bauen
	$(PY) build/build_zwo.py > /dev/null
	$(PY) build/build_icons.py
	$(PY) build/build_dash.py
pdf:              ## Plan als PDF (braucht: pip install reportlab)
	$(PY) build/build_plan.py
run: build        ## Server starten (http://127.0.0.1:8080)
	$(PY) server/server.py
test:             ## Ende-zu-Ende-Tests (braucht: pip install playwright)
	$(PY) tests/test_all.py
clean:
	rm -rf dist web/index.html tests/testfiles tests/.tmp
