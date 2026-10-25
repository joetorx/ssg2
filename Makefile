# Copyright (c) 2026 Joel Torres
# Licensed under the MIT License. See the file LICENSE for details.

VENV = .venv
PY = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
CONTENT = content
PUBLIC = public
CACHE = __pycache__

default: build

build: venv
	@"$(PY)" build.py

serve: build
	@"$(PY)" -m http.server -d public

venv:
	@if [ ! -d "$(VENV)" ]; then \
		echo "Creating Python venv..." ; \
		python3 -m venv "$(VENV)" && \
		"$(PIP)" install -r requirements.txt ; \
	fi

init: venv
	@"$(PY)" build.py --bootstrap

post:
	@"$(PY)" build.py --post

clean:
	@echo "Warning: this will delete the following folders: $(CONTENT) $(PUBLIC) $(CACHE) $(VENV)"
	@while true; do \
		read -p "Proceed? [y/n] " choice ; \
		if [ $$choice == "y" ]; then \
			rm -rf "$(CONTENT)" ; \
			rm -rf "$(PUBLIC)" ; \
			rm -rf "$(CACHE)" ; \
			rm -rf "$(VENV)" ; \
			break ; \
		elif [ $$choice == "n" ]; then \
			break ; \
		fi ; \
	done
