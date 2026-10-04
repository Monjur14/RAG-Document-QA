import json

import httpx
import pytest

from app.providers import OllamaProvider, ProviderError


def make(handler, **kw):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OllamaProvider(model="m1", base_url="http://ollama.test/", client=client, **kw)


def ok(request):
    return httpx.Response(200, json={"message": {"content": "hi"}, "prompt_eval_count": 12, "eval_count": 3})


def test_request_shape_and_response_parsing():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return ok(request)

    r = make(handler, think=None, num_ctx=4096).generate("question?", system="be nice")
    assert seen["url"] == "http://ollama.test/api/chat"
    b = seen["body"]
    assert b["model"] == "m1" and b["stream"] is False
    assert b["messages"] == [{"role": "system", "content": "be nice"}, {"role": "user", "content": "question?"}]
    assert b["options"] == {"temperature": 0, "num_ctx": 4096}
    assert "think" not in b                      # not sent unless configured
    assert (r.text, r.prompt_tokens, r.completion_tokens, r.model) == ("hi", 12, 3, "m1")


def test_think_flag_sent_when_configured():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return ok(request)

    make(handler, think=False).generate("q")
    assert seen["body"]["think"] is False
    assert seen["body"]["messages"] == [{"role": "user", "content": "q"}]


def test_inline_think_blocks_are_stripped():
    def handler(request):
        return httpx.Response(200, json={"message": {"content": "<think>hmm\nlet me see</think>\nFinal [1]."}})

    assert make(handler).generate("q").text == "Final [1]."


@pytest.mark.parametrize(
    "handler, fragment",
    [
        (lambda r: httpx.Response(500, text="model not found"), "HTTP 500"),
        (lambda r: httpx.Response(200, json={"oops": 1}), "no message content"),
        (lambda r: (_ for _ in ()).throw(httpx.ReadTimeout("slow")), "timed out"),
        (lambda r: (_ for _ in ()).throw(httpx.ConnectError("refused")), "Cannot reach Ollama"),
    ],
)
def test_failures_become_provider_error(handler, fragment):
    with pytest.raises(ProviderError, match=fragment):
        make(handler).generate("q")
