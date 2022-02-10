sources = nannyml

.PHONY: test format lint unittest coverage pre-commit clean
test: format lint unittest

format:
	isort $(sources) tests
	black $(sources) tests

lint:
	flake8 $(sources) tests
	mypy $(sources) tests

unittest:
	pytest

coverage:
	pytest --cov=$(sources) --cov-branch --cov-report=term-missing tests

pre-commit:
	pre-commit run --all-files

clean:
	rm -rf .mypy_cache .pytest_cache
	rm -rf *.egg-info
	rm -rf .tox dist site
	rm -rf coverage.xml .coverage

docs: ## generate Sphinx HTML documentation, including API docs
	rm -f docs/nannyml.rst
	rm -f docs/modules.rst
	sphinx-apidoc -o docs/ nannyml
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	$(BROWSER) docs/_build/html/index.html
