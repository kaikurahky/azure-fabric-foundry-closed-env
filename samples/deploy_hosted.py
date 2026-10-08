import json
import os
import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AgentEndpointProtocol,
    ContainerConfiguration,
    HostedAgentDefinition,
    ProtocolVersionRecord,
)
from azure.identity import DefaultAzureCredential


def main():
    with DefaultAzureCredential() as credential:
        with AIProjectClient(
            endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential
        ) as project:
            name = os.environ["HOSTED_AGENT_NAME"]
            agent = project.agents.create_version(
                agent_name=name,
                definition=HostedAgentDefinition(
                    protocol_versions=[
                        ProtocolVersionRecord(
                            protocol=AgentEndpointProtocol.RESPONSES, version="2.0.0"
                        )
                    ],
                    cpu="1",
                    memory="2Gi",
                    container_configuration=ContainerConfiguration(
                        image=os.environ["HOSTED_IMAGE"]
                    ),
                    environment_variables={
                        "FOUNDRY_PROJECT_ENDPOINT": os.environ["FOUNDRY_PROJECT_ENDPOINT"],
                        "FOUNDRY_MODEL_NAME": os.environ["FOUNDRY_MODEL_NAME"],
                        "STORAGE_ACCOUNT": os.environ["STORAGE_ACCOUNT"],
                        "PGHOST": os.environ["PGHOST"],
                        "PGUSER": os.environ["PGUSER"],
                        "PGSSLROOTCERT": "/etc/ssl/certs/ca-certificates.crt",
                        "EXPECTED_MARKER": os.environ["EXPECTED_MARKER"],
                        "EXECUTION_LABEL": name,
                    },
                ),
            )
            print(json.dumps({"agent_name": agent.name, "agent_version": agent.version}))
            deadline = time.monotonic() + 900
            while time.monotonic() < deadline:
                version = project.agents.get_version(
                    agent_name=name, agent_version=agent.version
                )
                status = version["status"]
                print(f"Version {agent.version} status: {status}")
                if status == "active":
                    return
                if status == "failed":
                    raise RuntimeError(f"Hosted provisioning failed: {version['error']}")
                time.sleep(10)
            raise TimeoutError("Hosted version did not become active within 15 minutes")


if __name__ == "__main__":
    main()
