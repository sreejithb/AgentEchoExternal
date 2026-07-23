from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.error
import urllib.request

BUFFER_API_URL = "https://api.buffer.com/graphql"

CREATE_POST_MUTATION = """
mutation CreatePost($channelId: ChannelId!, $text: String, $mode: ShareMode!, $schedulingType: SchedulingType!) {
  createPost(input: {
    channelId: $channelId
    text: $text
    assets: []
    mode: $mode
    schedulingType: $schedulingType
  }) {
    ... on PostActionSuccess {
      post { id }
    }
    ... on NotFoundError { message }
    ... on UnauthorizedError { message }
    ... on UnexpectedError { message }
    ... on RestProxyError { code link message }
    ... on LimitReachedError { message }
    ... on InvalidInputError { message }
  }
}
"""


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length else b"{}"

        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON body"})
            return

        text = (body.get("text") or "").strip()
        if not text:
            self._send_json(400, {"error": "text is required"})
            return

        api_key = os.environ.get("BUFFER_API_KEY")
        channel_id = os.environ.get("BUFFER_LINKEDIN_CHANNEL_ID")
        if not api_key or not channel_id:
            self._send_json(500, {"error": "BUFFER_API_KEY or BUFFER_LINKEDIN_CHANNEL_ID is not configured"})
            return

        payload = {
            "query": CREATE_POST_MUTATION,
            "variables": {
                "channelId": channel_id,
                "text": text,
                "mode": "shareNow",
                "schedulingType": "automatic",
            },
        }
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
                result = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            self._send_json(502, {"error": "Buffer API error", "detail": e.read().decode()})
            return

        self._send_json(200, result)

    def _send_json(self, status: int, payload: dict):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
