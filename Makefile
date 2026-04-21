API_VERSION := $(shell sed -n 's/^__version__ = "\([^"]*\)"/\1/p' src/memory_demo/__init__.py)
WEB_VERSION := $(shell python3 -c "import json; print(json.load(open('web/package.json'))['version'])")

.PHONY: docker-api docker-web docker-api-tag docker-web-tag docker-api-push docker-web-push

docker-api:
	docker buildx build --platform linux/amd64,linux/arm64 --no-cache -t agent-memory-demo-api:$(API_VERSION) -f Dockerfile.grpc . --load

docker-web:
	docker buildx build --platform linux/amd64,linux/arm64 --no-cache -t agent-memory-demo-web:$(WEB_VERSION) -f web/Dockerfile web --load

docker-api-tag:
	docker tag agent-memory-demo-api:$(API_VERSION) mminichino/agent-memory-demo-api:$(API_VERSION)
	docker tag agent-memory-demo-api:$(API_VERSION) mminichino/agent-memory-demo-api:latest

docker-web-tag:
	docker tag agent-memory-demo-web:$(WEB_VERSION) mminichino/agent-memory-demo-web:$(WEB_VERSION)
	docker tag agent-memory-demo-web:$(WEB_VERSION) mminichino/agent-memory-demo-web:latest

docker-api-push:
	docker push mminichino/agent-memory-demo-api:$(API_VERSION)
	docker push mminichino/agent-memory-demo-api:latest

docker-web-push:
	docker push mminichino/agent-memory-demo-web:$(WEB_VERSION)
	docker push mminichino/agent-memory-demo-web:latest
