SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:

MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules


./ : *.c
	poetry install

.PHONY : trace
trace : *.c
	CYTHON_TRACE=1 poetry install

*.c :


.PHONY : no-cython
no-cython :
	NO_CYTHON=1 poetry install

.PHONY : test
test :
	poetry run pytest tests typic --doctest-modules --cov --cov-report xml


.PHONY : test-cython
test-cython : trace test


.PHONY : test-no-cython
test-no-cython : no-cython test


.PHONY : flake8
flake8 : typic
	poetry run flake8 typic

.PHONY : black-check
black-check : ./
	poetry run black typic tests --check


.PHONY : black
black : ./
	poetry run black typic tests


.PHONY : black
mypy : ./
	poetry run mypy typic


.PHONY : lint
lint : no-cython flake8 black-check mypy

.PHONY : clean
clean :
	rm -rf \
	build \
	dist \
	*.egg-info \
	pip-wheel-metadata \
	.coverage \
	htmlcov \
	coverage.xml

	rm -rf `find . -name __pycache__` \
	&& rm -rf `find . -name .pytest_cache` \
	&& rm -rf `find . -name .mypy_cache` \
    && rm -rf `find . -type f -name '*.py[co]' ` \
    && rm -rf `find typic/ -type f -name '*.c' ` \
    && rm -rf `find typic/ -type f -name '*.so' ` \
