# `sam build` invokes build-RehearsalFn (referenced in template.yaml). The targets below it
# are human conveniences — run `make` (or `make help`) to see them.
.DEFAULT_GOAL := help

build-RehearsalFn:
	mkdir -p "$(ARTIFACTS_DIR)"
	cp -r engine web questions "$(ARTIFACTS_DIR)/"
	python3 -m pip install -r requirements-cloud.txt \
	  --platform manylinux2014_aarch64 --python-version 3.12 \
	  --implementation cp --only-binary=:all: --target "$(ARTIFACTS_DIR)"

.PHONY: help setup run docker test secrets deploy
help: ; @printf 'rehearsal — common commands:\n\
  make setup    one-time local setup (venv, deps, pull the model)\n\
  make run      run locally  — Ollama + faster-whisper, browser coach voice\n\
  make docker   run locally in containers (app + Ollama)\n\
  make test     run the test suite\n\
\n\
  make secrets  store cloud secrets in AWS SSM (run once):\n\
                OPENAI_API_KEY=sk-... ACCESS_CODE=<long random> make secrets\n\
  make deploy   build + deploy to AWS Lambda (after make secrets)\n'
setup:   ; ./setup.sh
run:     ; ./run.sh
docker:  ; docker compose up
test:    ; .venv/bin/pytest -q
secrets: ; bash scripts/put_secrets.sh
deploy:  ; bash scripts/deploy.sh
