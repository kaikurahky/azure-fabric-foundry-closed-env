import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


def main():
    with DefaultAzureCredential() as credential:
        with AIProjectClient(
            endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential
        ) as project:
            with project.get_openai_client() as client:
                response = client.responses.create(
                    input=(
                        "Call read_private_marker once now and return the complete tool "
                        "JSON including resolved_ips and the current marker."
                    ),
                    extra_body={
                        "agent_reference": {
                            "type": "agent_reference",
                            "name": os.environ["HOSTED_AGENT_NAME"],
                            "version": os.environ["HOSTED_AGENT_VERSION"],
                        }
                    },
                )
                print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
