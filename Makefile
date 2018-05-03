.PHONY: all serve build push

run: serve

serve:
	./main.py serve

build:
	./main.py build

deploy: push reload

push:
	rsync -e ssh -avz --exclude env ./ websites@trunks:cnll.fr/

reload:
	ssh root@trunks "supervisorctl restart cnll.fr"

clean:
	find . -name "*.pyc" | xargs rm -f
