"""--llm pass with a fake client: no network, no cost."""
import json
from types import SimpleNamespace

from spectakeoff.llm import Classifier, is_candidate


class FakeMessages:
    def __init__(self, yes_words):
        self.calls, self.yes_words = [], yes_words

    def create(self, **kw):
        self.calls.append(kw)
        lines = kw["messages"][0]["content"].splitlines()
        yes = [int(l.split(".", 1)[0]) for l in lines if any(w in l for w in self.yes_words)]
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps({"yes": yes}))],
                               usage=SimpleNamespace(input_tokens=100, output_tokens=5, cache_read_input_tokens=0))


def test_candidates_filter():
    assert is_candidate("The Contractor shall hand over the asphalt test data to the RPR.")
    assert not is_candidate("The aggregate shall be clean and durable.")          # no document noun
    assert not is_candidate("Test data.")                                          # too short


def test_classifier_batches_caches_and_counts_tokens(tmp_path):
    fake = SimpleNamespace(messages=FakeMessages(["hand over"]))
    cache = tmp_path / "c.json"
    texts = [f"Sentence {i}: the Contractor shall {'hand over' if i % 3 == 0 else 'keep'} the test log."
             for i in range(200)]
    clf = Classifier("claude-test", cache, client=fake)
    res = clf.classify(texts)
    assert res == [i % 3 == 0 for i in range(200)]
    assert len(fake.messages.calls) == 3 and clf.stats.input_tokens == 300        # 80 + 80 + 40 per batch
    call = fake.messages.calls[0]
    assert call["output_config"]["effort"] == "low" and call["output_config"]["format"]["type"] == "json_schema"
    clf2 = Classifier("claude-test", cache, client=fake)                          # second run: all cached
    assert clf2.classify(texts) == res and len(fake.messages.calls) == 3 and clf2.stats.cached == 200


def test_api_error_keeps_rules_only_result(tmp_path):
    class Boom:
        def create(self, **kw):
            raise ValueError("bad json")
    clf = Classifier("claude-test", None, client=SimpleNamespace(messages=Boom()))
    assert clf.classify(["The Contractor shall submit the test report."]) == [False]
    assert clf.stats.errors


def test_response_without_text_block_keeps_rules_only_result():
    class NoText:
        def create(self, **kw):
            return SimpleNamespace(stop_reason="max_tokens", content=[],
                                   usage=SimpleNamespace(input_tokens=10, output_tokens=0, cache_read_input_tokens=0))
    clf = Classifier("claude-test", None, client=SimpleNamespace(messages=NoText()))
    assert clf.classify(["The Contractor shall submit the test report."]) == [False]
    assert "no text block" in clf.stats.errors[0]
