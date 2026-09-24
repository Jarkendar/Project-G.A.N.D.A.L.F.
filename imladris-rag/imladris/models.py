"""Embedding models: a registry of pinned checkpoints and a loader that suits a
CPU-only board (float32, capped sequence length)."""

from dataclasses import dataclass, field

# Every model is pinned to a Hub commit, never the moving `main` branch, so a
# re-download on another machine or after a rebuild yields the same weights.
# Prefixes are what each model was trained with: e5 wants "query: " /
# "passage: ", arctic only a query prefix, granite and MiniLM none.
MODEL_REGISTRY = {
    "minilm": {"name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
               "revision": "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"},
    "e5-small": {"name": "intfloat/multilingual-e5-small",
                 "revision": "614241f622f53c4eeff9890bdc4f31cfecc418b3",
                 "query_prefix": "query: ", "passage_prefix": "passage: "},
    "granite-97m": {"name": "ibm-granite/granite-embedding-97m-multilingual-r2",
                    "revision": "835ad14087e140460703cf0fae09f97d469d65c2"},
    "granite-311m": {"name": "ibm-granite/granite-embedding-311m-multilingual-r2",
                     "revision": "44399559930365213510b1ee2eb15ded83374f0e"},
    # Kept as a record only: its bundled 2024 modeling code (trust_remote_code)
    # needs xformers unless configured off, and even then produces invalid
    # position ids under transformers 5.
    "arctic-m": {"name": "Snowflake/snowflake-arctic-embed-m-v2.0",
                 "revision": "95c2741480856aa9666782eb4afe11959938017f",
                 "query_prefix": "query: ", "trust_remote_code": True,
                 "config_kwargs": {"use_memory_efficient_attention": False,
                                   "unpad_inputs": False}},
}
DEFAULT_MODEL = "minilm"

# Long-window models accept 8K-32K tokens; chunks never get near that, and an
# uncapped window only costs memory on an outlier.
MAX_SEQ_CAP = 1024


@dataclass(frozen=True)
class ModelSpec:
    name: str
    revision: str = "main"
    query_prefix: str = ""
    passage_prefix: str = ""
    trust_remote_code: bool = False
    config_kwargs: dict = field(default_factory=dict, hash=False, compare=False)


def resolve_model(key_or_name: str, revision: str | None = None) -> ModelSpec:
    """A registry key or a full Hub name (then unpinned unless `revision` is
    given). An explicit `revision` overrides the registry's pin."""
    entry = MODEL_REGISTRY.get(key_or_name) or next(
        (m for m in MODEL_REGISTRY.values() if m["name"] == key_or_name), None)
    entry = dict(entry) if entry else {"name": key_or_name}
    if revision:
        entry["revision"] = revision
    return ModelSpec(**entry)


_cache: dict = {}


def load_model(spec: ModelSpec):
    """Cached sentence-transformers load. Imports lazily so callers that never
    embed (a dry run, keyword search) never pay the torch import."""
    key = (spec.name, spec.revision)
    if key not in _cache:
        import torch
        from sentence_transformers import SentenceTransformer
        # float32 explicitly: transformers 5 keeps a checkpoint's saved dtype,
        # and bf16 weights (granite) fall back to a ~150x slower matmul on CPUs
        # without bf16 support, such as the Raspberry Pi 5's Cortex-A76.
        model = SentenceTransformer(spec.name, revision=spec.revision,
                                    trust_remote_code=spec.trust_remote_code,
                                    model_kwargs={"dtype": torch.float32},
                                    config_kwargs=spec.config_kwargs or None)
        model.max_seq_length = min(model.max_seq_length or MAX_SEQ_CAP, MAX_SEQ_CAP)
        _cache[key] = model
    return _cache[key]


def token_counter(model):
    """Token count under the model's own tokenizer, without special tokens."""
    tokenizer = model.tokenizer
    return lambda text: len(tokenizer(text, add_special_tokens=False)["input_ids"])
