#!/bin/bash

MODE=$1       # Argumento para seleccionar el modo (local o distributed)
SERVICE=$2    # Servicio específico (central, taxi, customer, sensor)

# Según el modo, definimos ENV_FILE
if [ "$MODE" == "distributed" ]; then
  echo "Running in distributed mode..."
  export ENV_FILE=".env.distributed"
else
  echo "Running in local mode..."
  export ENV_FILE=".env.local"
fi

# Levantar servicios en el orden correcto según el perfil
if [ "$MODE" == "local" ]; then
  echo "Starting all services in local mode..."
  docker-compose --profile central --profile taxi --profile customer --profile sensor up --build

elif [ "$MODE" == "distributed" ]; then
  case "$SERVICE" in
    central)
      echo "Starting Central and Kafka services..."
      docker-compose --profile central up --build
      ;;
    taxi)
      echo "Starting Taxi service (requires Central running)..."
      docker-compose --profile taxi up --build
      ;;
    customer)
      echo "Starting Customer service (requires Central running)..."
      docker-compose --profile customer up --build
      ;;
    sensor)
      echo "Starting Sensor service (requires Central and Taxi running)..."
      docker-compose --profile sensor up --build
      ;;
    *)
      echo "Invalid service specified. Use: central, taxi, customer, or sensor."
      ;;
  esac

else
  echo "Invalid mode specified. Use: local or distributed."
fi
