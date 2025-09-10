#!/bin/bash
set -e

# Parse command line arguments
ENV_FILE_ARG=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --env-file)
      ENV_FILE_ARG="--env-file $2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--env-file <path-to-env-file>]"
      exit 1
      ;;
  esac
done

function wait_server_ready {
  for backoff in 0 1 2 4 8; do
    echo "Waiting for tracking server to be ready..."
    sleep $backoff
    if curl --fail --silent --show-error --output /dev/null $1; then
      echo "Server is ready"
      return 0
    fi
  done
  echo -e "\nFailed to launch tracking server"
  return 1
}

mkdir -p outputs
echo 'Running tracking server in the background'

# When using --env-file, don't pass any backend/registry store URIs
# The mlflow server will read them from the env file
if [ -n "$ENV_FILE_ARG" ]; then
  backend_store_uri=""
  default_artifact_root=""
  registry_store_uri=""
  echo "Using environment file configuration"
else
  # Handle backend store URI (tracking store) from environment
  if [ -n "$MLFLOW_TRACKING_URI" ]; then
    backend_store_uri="--backend-store-uri $MLFLOW_TRACKING_URI"
    default_artifact_root="--default-artifact-root mlruns"
  elif [ -n "$MLFLOW_BACKEND_STORE_URI" ]; then
    backend_store_uri="--backend-store-uri $MLFLOW_BACKEND_STORE_URI"
    default_artifact_root="--default-artifact-root mlruns"
  else
    backend_store_uri=""
    default_artifact_root=""
  fi

  # Handle registry store URI (model registry) from environment
  if [ -n "$MLFLOW_REGISTRY_URI" ]; then
    registry_store_uri="--registry-store-uri $MLFLOW_REGISTRY_URI"
  else
    registry_store_uri=""
  fi
  
  # Display configuration
  echo "MLflow Server Configuration:"
  echo "  MLFLOW_TRACKING_URI: ${MLFLOW_TRACKING_URI:-<not set>}"
  echo "  MLFLOW_REGISTRY_URI: ${MLFLOW_REGISTRY_URI:-<not set>}"
  if [ -n "$DATABRICKS_HOST" ]; then
    echo "  DATABRICKS_HOST: $DATABRICKS_HOST"
  fi
fi

if [ ! -d "mlflow/server/js/node_modules" ]; then
  pushd mlflow/server/js
  yarn install
  popd
fi

# Run mlflow server with the loaded environment variables
# Use python -m mlflow to run from local source code
python -m mlflow $ENV_FILE_ARG server $backend_store_uri $default_artifact_root $registry_store_uri --dev &
wait_server_ready localhost:5000/health
yarn --cwd mlflow/server/js start