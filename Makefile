SHELL := bash

YAMLSTAR-VERSION := 0.1.28

HOST ?= 127.0.0.1
PORT ?= 8000
REPO ?= git@github.com:ingydotnet/kubecon-na-2026-go-yaml-talk.git

M := $(or $(MAKES_REPO_DIR),.cache/makes)
$(shell [[ -d $M ]] || git clone -q https://github.com/makeplus/makes $M)
include $M/init.mk
include $M/perl.mk
include $M/python.mk
include $M/shellcheck.mk
include $M/yamlscript.mk
include $M/gloat.mk
include $M/yamlschema.mk
include $M/yamlstar.mk
include $M/go-yaml.mk
include $M/shell.mk
include $M/clean.mk

MAKES-CLEAN := yamlet go.mod go.sum

YAMLSTAR-DOWN := https://github.com/yaml/yamlstar/releases/download
YAMLSTAR-DOWN := $(YAMLSTAR-DOWN)/v$(YAMLSTAR-VERSION)/$(YAMLSTAR-ARC)

VROOM-DEPS := $(LOCAL-ROOT)/vroom-deps-0.42
VROOM := $(PERL) util/vroom-watch-compile
YS-LINT := /home/ingy/.codex/skills/yamlscript/ys-lint.ys
GO-YAML-DEMO-DIR := $(ROOT)/repos/go-yaml
GO-YAML-DEMO-GIT := $(GO-YAML-DEMO-DIR)/.git
PYTHON-REQUIREMENTS := requirements-python.txt
PYTHON-PIP-WRAPPER := $(PYTHON-VENV)/.pip-wrapper
PYTHON-YAMLSTAR := $(PYTHON-VENV)/.yamlstar-$(YAMLSTAR-VERSION)
YAMLSTAR-PLUGIN-INSTALLER := $(YAMLSTAR-LOCAL)/bin/yamlstar-plugin
GO-YAML-PLUGINS := $(LOCAL-BIN)/go-yaml-plugins
GO-YAML-PLUGIN-PACKAGES := \
  github.com/yamlstar/yamlstar-plugin-parser-json-comments/goyaml@v0.1.1,\
  github.com/yamlstar/yamlstar-plugin-parser-toml/goyaml@v0.1.3
SLIDES-SOURCE := slides.vroom
SLIDES-GENERATOR := util/vroom-to-html.ys
SLIDES-SERVER := util/serve-slides.py
SLIDES-DIR := slides
SLIDES-HTML := $(SLIDES-DIR)/index.html
SLIDES-NOJEKYLL := $(SLIDES-DIR)/.nojekyll
SLIDES-URL := https://ingydotnet.github.io/kubecon-na-2026-go-yaml-talk/

override export PATH := $(GO-YAML-DEMO-DIR):$(PATH)

SHELL-DEPS += $(VROOM-DEPS)
SHELL-DEPS += $(GO-YAML-DEMO-GIT)
SHELL-DEPS += $(PYTHON-YAMLSTAR)
SHELL-DEPS += $(YAMLSTAR-PLUGIN-INSTALLER)
SHELL-DEPS += $(GO-YAML-PLUGINS)

default:: run

run: export VROOM_START_SLIDE := $(s)
run: $(VROOM-DEPS) $(SHELL-DEPS) yamlstar-json-comments-ready \
  yamlstar-toml-ready
	clear
	env -u GOROOT $(VROOM) --run

run-watch: export VROOM_WATCH := 1
run-watch: export VROOM_WATCH_PERL := $(PERL)
run-watch: run

watch-check: $(VROOM-DEPS) $(PYTHON) $(YS)
	VROOM_WATCH_PERL=$(PERL) VROOM_WATCH_YS=$(YS) \
	  $(PYTHON) test/run-watch.py

compile: $(VROOM-DEPS)
	$(VROOM)

slides: $(SLIDES-HTML) $(SLIDES-NOJEKYLL)

$(SLIDES-HTML): $(SLIDES-SOURCE) $(SLIDES-GENERATOR) $(YS)
	$(YS) $(SLIDES-GENERATOR) $(SLIDES-SOURCE) $@

$(SLIDES-NOJEKYLL): $(SLIDES-HTML)
	touch $@

serve: slides $(PYTHON) $(SLIDES-SERVER)
	@set -eu; \
	  (while sleep 1; do \
	    $(MAKE) -q slides >/dev/null 2>&1 || $(MAKE) slides; \
	  done) & \
	  watcher=$$!; \
	  trap 'kill $$watcher 2>/dev/null || true' EXIT INT TERM; \
	  echo 'Serving $(SLIDES-URL) locally at http://$(HOST):$(PORT)/'; \
	  $(PYTHON) $(SLIDES-SERVER) \
	    --directory $(SLIDES-DIR) --host $(HOST) --port $(PORT)

site-check: slides $(YS) $(PERL)
	$(YS) $(YS-LINT) $(SLIDES-GENERATOR)
	$(PERL) test/site-check $(SLIDES-HTML)

publish: site-check
	@set -eu; \
	  trap '$(RM) -r $(ROOT)/$(SLIDES-DIR)/.git' EXIT INT TERM; \
	  git -C $(SLIDES-DIR) init -q; \
	  git -C $(SLIDES-DIR) add -A; \
	  git -C $(SLIDES-DIR) commit -q \
	    -m 'Publish slideshow website' \
	    -m 'Deploy the generated browser presentation from slides.vroom.'; \
	  git -C $(SLIDES-DIR) push -f $(REPO) HEAD:gh-pages; \
	  echo 'Published $(SLIDES-URL)'

preflight: $(VROOM-DEPS) $(YS) $(GLOAT) $(YSD) $(YAMLSTAR) \
  $(GO-YAML-PLUGINS) yamlstar-json-comments-ready yamlstar-toml-ready
	@$(PERL) -Irepos/vroom-pm/lib -MVroom \
	  -e 'print "vroom $$Vroom::VERSION\n"'
	@ys --version
	@gloat --version
	@ysd --version
	@yaml --version
	@go-yaml -h >/dev/null 2>&1
	@echo 'go-yaml current main'
	@go-yaml-plugins -h >/dev/null 2>&1
	@echo 'go-yaml configured plugins ready'
	@echo 'YAMLStar shared plugins ready'

demo-check: $(PERL) $(YS) $(YSD) $(YAMLSTAR) \
  $(PYTHON-YAMLSTAR) \
  $(GO-YAML-DEMO-GIT) \
  $(GO-YAML-PLUGINS) yamlstar-json-comments-ready yamlstar-toml-ready
	test/demo-check

check: compile site-check watch-check $(SHELLCHECK) $(YS)
	$(SHELLCHECK) vroom-slide-runner test/demo-check
	ys $(YS-LINT) demo/config.ys
	$(MAKE) demo-check
	git diff --check

$(VROOM-DEPS): $(PERL)
	cpanm -n File::HomeDir IO::All Template::Toolkit::Simple \
	  Term::Size 'YAML::PP@0.036'
	touch $@

$(PYTHON-PIP-WRAPPER): | $(PYTHON-VENV)
	printf '%s\n' \
	  '#!/usr/bin/env python' \
	  'import os' \
	  'import sys' \
	  "os.execv('$(UV)', ['uv', 'pip', *sys.argv[1:]," \
	  "          '--python', sys.executable])" \
	  > $(PYTHON-VENV)/bin/pip
	chmod +x $(PYTHON-VENV)/bin/pip
	touch $@

$(PYTHON-YAMLSTAR): $(PYTHON-REQUIREMENTS) $(PYTHON-PIP-WRAPPER)
	$(UV) pip install -r $<
	touch $@

$(YAMLSTAR-PLUGIN-INSTALLER): $(YAMLSTAR) \
  repos/yamlstar/util/yamlstar-plugin
	cp repos/yamlstar/util/yamlstar-plugin $@
	chmod +x $@

$(GO-YAML-DEMO-GIT):
	@echo 'Missing required checkout: repos/go-yaml' >&2
	@exit 1

cli: $(GO-YAML-DEMO-GIT)
	env -u GOROOT $(MAKE) -C $(GO-YAML-DEMO-DIR) cli

go-yaml-plugins: $(GO-YAML-PLUGINS)

$(GO-YAML-PLUGINS): Makefile demo/plugin-options.yaml | $(GO-YAML-DEMO-GIT)
	env -u GOROOT $(MAKE) -C $(GO-YAML-DEMO-DIR) cli \
	  CONFIG=$(ROOT)/demo/plugin-options.yaml \
	  PLUGIN-PACKAGE='$(GO-YAML-PLUGIN-PACKAGES)'
	cp $(GO-YAML-DEMO-DIR)/go-yaml $@.tmp
	env -u GOROOT $(MAKE) -C $(GO-YAML-DEMO-DIR) cli
	mv $@.tmp $@

yamlstar-json-comments-ready: $(YAMLSTAR-PLUGIN-INSTALLER) \
  json-comments.yaml
	@yaml --plugin=yaml-parser=json-comments -Y json-comments.yaml >/dev/null

yamlstar-toml-ready: $(YAMLSTAR-PLUGIN-INSTALLER) settings.toml
	@yaml --plugin=yaml-parser=toml -y settings.toml >/dev/null

clean::
	$(RM) -r 0* .help .vimrc .gvimrc run.slide notes.txt bin done
	$(RM) -r .vroom slides hello hello.js hello.html

realclean::
	@if [[ -d go-yaml/.cache ]]; then \
	  set -x; \
	  chmod -R +w go-yaml/.cache; \
	fi
	$(RM) -r go-yaml
