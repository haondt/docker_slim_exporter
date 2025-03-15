# Docker Slim Exporter

A lightweight Prometheus exporter for Docker container status and health, designed to fill in the gaps from [cAdvisor](https://github.com/google/cadvisor).

## Features

- Monitors Docker container status and health metrics
- Includes container labels in cAdvisor-compatible format
- Configurable through environment variables

## Metrics

The exporter provides two main metrics:

1. `container_status` - Shows the container state with labels
2. `container_health` - Shows the container health check status with labels

Each metric includes:
- `container_id` - Short ID of the container
- `name` - Name of the container
- `status` - Container status (running, exited, etc.) or health status (healthy, unhealthy, none)
- Container labels with `container_label_` prefix (if enabled)

## Configuration

| Environment Variable     | Default | Description                                             |
|--------------------------|---------|---------------------------------------------------------|
| `EXPORTER_PORT`          | 9090    | Port to expose Prometheus metrics on                    |
| `METRICS_PREFIX`         | ""      | Optional prefix for all metrics                         |
| `SCRAPE_INTERVAL`        | 15      | Time between metric collections in seconds              |
| `DOCKER_HOST`            | None    | Docker host URL (default: local Docker socket)          |
| `INCLUDE_STOPPED`        | true    | Whether to include stopped containers                   |
| `DISABLE_DEFAULT_METRICS`| true    | Whether to disable default Python metrics               |
| `INCLUDE_LABELS`         | true    | Whether to include container labels in metrics          |
| `LOG_LEVEL`              | INFO    | Logging level (DEBUG, INFO, WARNING, ERROR)             |

## Installation

### Using Docker

```bash
docker run -d \
  --name docker-slim-exporter \
  -p 9090:9090 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  docker-slim-exporter:latest
```

### Using Docker Compose

```yaml
version: '3'
services:
  docker-slim-exporter:
    build: .
    ports:
      - "9090:9090"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - METRICS_PREFIX=docker
      - SCRAPE_INTERVAL=30
      - LOG_LEVEL=INFO
```

### Direct Installation

1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the exporter:
   ```bash
   python exporter.py
   ```

## Example Prometheus Queries

Count containers by status:
```
count(container_status) by (status)
```

Find unhealthy containers:
```
container_health{health_status="unhealthy"}
```

Filter containers by Docker Compose project:
```
container_status{container_label_com_docker_compose_project="myproject"}
```

## Adding to Prometheus

Add the following job to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'docker'
    static_configs:
      - targets: ['docker-slim-exporter:9090']
```
