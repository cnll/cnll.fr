.PHONY: all serve build push

run: serve

serve:
	./main.py serve

build:
	./main.py build

push:
	rsync -e ssh -avz ./ dedi:cnll.fr/

clean:
	find . -name "*.pyc" | xargs rm -f
