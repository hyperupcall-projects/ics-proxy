SHELL := /usr/bin/bash
.SHELLFLAGS := -eo pipefail -c
.ONESHELL:
HERE := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

.PHONY: install
install:
	cd "$(HERE)"
	mkdir -p "$${XDG_CONFIG_HOME:-"$$HOME/.config"}/systemd/user"
	ln -sf "$$PWD/ics-proxy.service" "$${XDG_CONFIG_HOME:-"$$HOME/.config"}/systemd/user/ics-proxy.service"
	systemctl --user daemon-reload
	systemctl --user enable --now ics-proxy
