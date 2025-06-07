# EasyCab

This repository contains a multi-service taxi dispatch example. Services are
coordinated via Docker Compose. The project supports running all components on a
single machine (local mode) or splitting them across several machines
(distributed mode).

## Local execution

Use `.env.local` as the environment file and start every service with
Docker Compose. Two approaches are provided in **Guia.txt**:

```bash
# Método A: con variable ENV_FILE en tu shell
export ENV_FILE=.env.local
docker-compose up --build -d

# Método B: con un "override" en cada servicio
docker-compose --env-file .env.local up --build -d
```

Alternatively the helper script can be used:

```bash
bash start.sh local
```

Services can be scaled while running:

```bash
docker-compose --env-file .env.local up --scale taxi=3 --scale customer=2
```

## Distributed execution

To run components across multiple machines, copy `.env.distributed` and pass it
with `docker-compose`. The script also accepts a `distributed` parameter:

```bash
bash start.sh distributed
```

The guide describes starting each profile separately:

```text
1. En la Máquina Central (PC1):
   docker-compose --env-file .env.distributed --profile central up --build

2. En la Máquina de Taxis (PC2):
   docker-compose --env-file .env.distributed --profile taxi up --build
   docker-compose --env-file .env.distributed --profile taxi up --scale taxi=5

3. En la Máquina de Clientes (PC3):
   docker-compose --env-file .env.distributed --profile customer up --build
   docker-compose --env-file .env.distributed --profile customer up --scale customer=3
```

## Testing

Install the Python dependencies from the service requirements and run the test
suite with **pytest**:

```bash
pip install kafka-python requests cryptography Flask werkzeug
pytest -q
```

