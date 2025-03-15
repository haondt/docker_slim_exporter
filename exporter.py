#!/usr/bin/env python3
import os
import time
import logging
import threading
import docker
import re
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, InfoMetricFamily, REGISTRY, CollectorRegistry
from prometheus_client.registry import Collector

# Configure logging
logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('docker_slim_exporter')

# Environment variable configuration with defaults
EXPORTER_PORT = int(os.environ.get('EXPORTER_PORT', 9090))
METRICS_PREFIX = os.environ.get('METRICS_PREFIX', '')
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', 15))
DOCKER_HOST = os.environ.get('DOCKER_HOST', None)
INCLUDE_STOPPED = os.environ.get('INCLUDE_STOPPED', 'true').lower() == 'true'
DISABLE_DEFAULT_METRICS = os.environ.get('DISABLE_DEFAULT_METRICS', 'true').lower() == 'true'
INCLUDE_LABELS = os.environ.get('INCLUDE_LABELS', 'true').lower() == 'true'

# Create custom prefix
prefix = f"{METRICS_PREFIX}_" if METRICS_PREFIX else ""

def sanitize_label_name(name):
    """Convert label name to cAdvisor format: prefix with container_label_ and replace dots with underscores"""
    # Replace invalid characters with underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    return f"container_label_{sanitized}"

class DockerCollector(Collector):
    def __init__(self):
        self.docker_client = docker.from_env() if not DOCKER_HOST else docker.DockerClient(base_url=DOCKER_HOST)
        self.container_metrics_cache = []
        self.lock = threading.Lock()
        
        # Start background collection thread
        self._start_background_collection()
    
    def _start_background_collection(self):
        def collector_thread():
            while True:
                self._collect_container_metrics()
                time.sleep(SCRAPE_INTERVAL)
        
        thread = threading.Thread(target=collector_thread, daemon=True)
        thread.start()
    
    def _collect_container_metrics(self):
        """Collect container metrics and update cache"""
        try:
            # Get all containers
            containers = self.docker_client.containers.list(all=INCLUDE_STOPPED)
            logger.info(f"Collecting metrics for {len(containers)} containers")
            
            # Temporary storage for new metrics
            new_metrics_cache = []
            
            for container in containers:
                try:
                    # Extract container details
                    container_id = container.id[:12]
                    name = container.name
                    status = container.status
                    
                    # Extract container labels if enabled
                    container_labels = {}
                    if INCLUDE_LABELS and container.attrs.get('Config', {}).get('Labels'):
                        # Transform labels to cAdvisor format: container_label_key
                        for key, value in container.attrs['Config']['Labels'].items():
                            sanitized_key = sanitize_label_name(key)
                            container_labels[sanitized_key] = value
                    
                    # Get health status if available
                    health_status = "none"
                    if 'Health' in container.attrs.get('State', {}):
                        health_status = container.attrs['State']['Health']['Status']
                    
                    # Store container info
                    new_metrics_cache.append({
                        'id': container_id,
                        'name': name,
                        'status': status,
                        'health_status': health_status,
                        'labels': container_labels
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing container {container.id}: {e}")
                    
            # Update cache atomically
            with self.lock:
                self.container_metrics_cache = new_metrics_cache
                
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
    
    def collect(self):
        """Return cached metrics when Prometheus scrapes"""
        container_metrics = []
        
        # Get a copy of the cache with lock to prevent race conditions
        with self.lock:
            container_metrics = self.container_metrics_cache.copy()
        
        # Define common labels (including dynamic container labels)
        cadvisor_label_keys = set()
        if INCLUDE_LABELS:
            for container in container_metrics:
                cadvisor_label_keys.update(container['labels'].keys())
        
        # Container status metric
        status_labels = ['container_id', 'name', 'status']
        if INCLUDE_LABELS:
            status_labels.extend(sorted(cadvisor_label_keys))
        
        container_status = GaugeMetricFamily(
            f'{prefix}container_status',
            'Docker container status',
            labels=status_labels
        )
        
        # Container health metric
        health_labels = ['container_id', 'name', 'health_status']
        if INCLUDE_LABELS:
            health_labels.extend(sorted(cadvisor_label_keys))
            
        container_health = GaugeMetricFamily(
            f'{prefix}container_health',
            'Docker container health status',
            labels=health_labels
        )
        
        # Exporter info metric
        exporter_info = InfoMetricFamily(
            f'{prefix}docker_slim_exporter',
            'Docker container state and health exporter information'
        )
        
        # Set exporter info
        exporter_info.add_metric([], {
            'version': '1.0.0',
            'description': 'Slim Docker Container State Exporter'
        })
        
        # Add metrics
        for container in container_metrics:
            # Add status metric
            status_label_values = [container['id'], container['name'], container['status']]
            if INCLUDE_LABELS:
                for label_key in sorted(cadvisor_label_keys):
                    status_label_values.append(container['labels'].get(label_key, ''))
            
            container_status.add_metric(status_label_values, 1)
            
            # Add health metric
            health_label_values = [container['id'], container['name'], container['health_status']]
            if INCLUDE_LABELS:
                for label_key in sorted(cadvisor_label_keys):
                    health_label_values.append(container['labels'].get(label_key, ''))
            
            container_health.add_metric(health_label_values, 1)
        
        yield container_status
        yield container_health
        yield exporter_info


def main():
    # Create custom registry if default metrics should be disabled
    if DISABLE_DEFAULT_METRICS:
        registry = CollectorRegistry()
        registry.register(DockerCollector())
        start_http_server(EXPORTER_PORT, registry=registry)
        logger.info("Default metrics disabled")
    else:
        # Use default registry
        REGISTRY.register(DockerCollector())
        start_http_server(EXPORTER_PORT)
        logger.info("Including default Python metrics")
    
    logger.info(f"Docker Exporter started on port {EXPORTER_PORT}")
    if INCLUDE_LABELS:
        logger.info("Container labels included in metrics (cAdvisor style)")
    
    # Keep the main thread running
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
