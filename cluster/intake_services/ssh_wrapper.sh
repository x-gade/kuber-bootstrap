#!/bin/bash
# Принудительный запуск node_intake_client.py с аргументами SSH
exec /usr/bin/python3 /opt/kuber-bootstrap/cluster/intake_services/node_intake_client.py $SSH_ORIGINAL_COMMAND
