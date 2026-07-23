from http.server import BaseHTTPRequestHandler
from typing import Optional
import json
import os
import urllib.error
import urllib.request

BUFFER_API_URL = "https://api.buffer.com/graphql"

ORGANIZATIONS_QUERY = """
query {
  account {
    organizations {
      id
      name
    }
  }
}
"""

CREATE_POST_INPUT_INTROSPECTION = """
query {
  __type(name: "CreatePostInput") {
    inputFields {
      name
      type {
        name
        kind
        ofType { name kind }
      }
    }
  }
}
"""

CHANNELS_QUERY = """
query Channels($organizationId: OrganizationId!) {
  channels(input: { organizationId: $organizationId }) {
    id
    name
    service
  }
}
"""


def _graphql(api_key: str, query: str, variables: Optional[dict] = None) -> dict:
    payload = {"query": query, "variables": variables or {}}
    req = urllib.request.Request(
        BUFFER_API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode()}


class handler(BaseHTTPRequestHandler):
    # TEMPORARY diagnostic endpoint. Read-only: lists Buffer orgs/channels
    # to find the LinkedIn channelId. Remove once that's captured.
    def do_GET(self):
        api_key = os.environ.get("BUFFER_API_KEY")
        if not api_key:
            self._send_json(500, {"error": "BUFFER_API_KEY is not configured"})
            return

        orgs_response = _graphql(api_key, ORGANIZATIONS_QUERY)
        organizations = (
            orgs_response.get("data", {}).get("account", {}).get("organizations", [])
        )

        channels_by_org = {}
        for org in organizations:
            channels_by_org[org["id"]] = _graphql(
                api_key, CHANNELS_QUERY, {"organizationId": org["id"]}
            )

        create_post_input_schema = _graphql(api_key, CREATE_POST_INPUT_INTROSPECTION)

        self._send_json(200, {
            "organizations_response": orgs_response,
            "channels_by_org": channels_by_org,
            "create_post_input_schema": create_post_input_schema,
        })

    def _send_json(self, status: int, payload: dict):
        data = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
