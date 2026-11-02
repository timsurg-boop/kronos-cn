.PHONY: install test lint demo clean

install:
	python -m pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check .

demo:
	kronos-cn demo --out heatmap.html

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
