#!/usr/bin/env bash

set -eo pipefail
set -x

# Find and change to repo root directory
OS=$(uname)
if [[ "$OS" == "Darwin" ]]; then
	# OSX uses BSD readlink
	BASEDIR="$(dirname "$0")"
else
	BASEDIR=$(readlink -e "$(dirname "$0")")
fi
cd "${BASEDIR}/../.." || exit 1

CORE_SERVICE_CONTAINER="dss_sandbox_local-dss-core-service_1"
OAUTH_CONTAINER="dss_sandbox_local-dss-dummy-oauth_1"
declare -a localhost_containers=("$CORE_SERVICE_CONTAINER" "$OAUTH_CONTAINER")

for container_name in "${localhost_containers[@]}"; do
	if [ "$( docker container inspect -f '{{.State.Status}}' "$container_name" )" == "running" ]; then
		echo "$container_name available!"
	else
    echo '#########################################################################'
    echo '## Prerequisite to run this command is:                                ##'
    echo '## Local DSS instance + Dummy OAuth server (/build/dev/run_locally.sh) ##'
    echo '#########################################################################'
		echo "Error: $container_name not running. Execute 'build/dev/run_locally.sh up' before running monitoring/prober/run_locally.sh";
		exit 1;
	fi
done

OUTPUT_DIR="monitoring/prober/output"
mkdir -p "$OUTPUT_DIR"

# TODO(#17): Remove F3411_22A_ALTITUDE_REFERENCE environment variable once DSS behaves correctly
if ! docker run --link "$OAUTH_CONTAINER":oauth \
	--link "$CORE_SERVICE_CONTAINER":core-service \
	-u "$(id -u):$(id -g)" \
	--network dss_sandbox_default \
	-v "$(pwd)/$OUTPUT_DIR:/app/$OUTPUT_DIR" \
	-w /app/monitoring/prober \
	interuss/monitoring \
	pytest \
	"${1:-.}" \
	-rsx \
	--junitxml="/app/$OUTPUT_DIR/e2e_test_result" \
	--dss-endpoint http://core-service:8082 \
	--rid-auth "DummyOAuth(http://oauth:8085/token,sub=fake_uss)" \
	--rid-v2-auth "DummyOAuth(http://oauth:8085/token,sub=fake_uss)" \
	--scd-auth1 "DummyOAuth(http://oauth:8085/token,sub=fake_uss)" \
	--scd-auth2 "DummyOAuth(http://oauth:8085/token,sub=fake_uss2)"	\
	--scd-api-version 1.0.0; then

    if [ "$CI" == "true" ]; then
        echo "=== END OF TEST RESULTS ==="
        echo "Dumping core-service logs"
        docker logs "$CORE_SERVICE_CONTAINER"
    fi
    echo "Prober did not succeed."
    exit 1
else
    echo "Prober succeeded."
fi
