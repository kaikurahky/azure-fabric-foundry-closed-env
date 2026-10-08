import json
import logging
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential

from network_probe import run_probe


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lab-hosted")


def read_private_marker() -> str:
    """Read the current marker from private Blob and PostgreSQL from this hosted container."""
    result = run_probe()
    logger.info("Hosted data probe: %s", json.dumps(result))
    return json.dumps(result)


def read_private_marker_with_files() -> str:
    """Read the current marker from private Blob, PostgreSQL, and Azure Files."""
    result = run_probe(include_files=True)
    logger.info("Hosted data probe with Files: %s", json.dumps(result))
    return json.dumps(result)


def main():
    with DefaultAzureCredential() as credential:
        client = FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["FOUNDRY_MODEL_NAME"],
            credential=credential,
        )
        agent = Agent(
            client=client,
            tools=[read_private_marker, read_private_marker_with_files],
            instructions=(
                "You are a network verification assistant. For every data verification "
                "request, call the requested read_private_marker tool exactly once. "
                "Report its JSON without inventing values. If a tool fails, report failure; "
                "never claim connectivity succeeded based on prior chat messages."
            ),
            default_options={"store": False},
        )
        ResponsesHostServer(agent).run()


if __name__ == "__main__":
    main()
