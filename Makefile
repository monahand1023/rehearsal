build-RehearsalFn:
	mkdir -p "$(ARTIFACTS_DIR)"
	cp -r engine web questions "$(ARTIFACTS_DIR)/"
	python3 -m pip install -r requirements-cloud.txt \
	  --platform manylinux2014_aarch64 --python-version 3.12 \
	  --implementation cp --only-binary=:all: --target "$(ARTIFACTS_DIR)"
