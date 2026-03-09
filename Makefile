.PHONY: deploy build start stop logs

deploy:
	@./scripts/deploy.sh

build start stop logs:
	@$(MAKE) -C app $@
