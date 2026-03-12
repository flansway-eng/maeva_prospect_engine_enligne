import os
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.openai._transformation.registry import get_transformer
import autogen_ext.models.openai._transformation.registry as registry_mod


def _discover_families() -> list[str]:
    fams = set()
    for name in dir(registry_mod):
        try:
            val = getattr(registry_mod, name)
        except Exception:
            continue
        if isinstance(val, dict) and "openai" in val and isinstance(val["openai"], dict):
            for k in val["openai"].keys():
                fams.add(str(k))
    return sorted(fams)


def _detect_family(model_name: str) -> str:
    fams = _discover_families()
    if not fams:
        raise RuntimeError("No model families discovered in autogen-ext registry.")
    forced = (os.getenv("AUTOGEN_MODEL_FAMILY") or "").strip()
    if forced:
        get_transformer("openai", model_name, forced)
        return forced
    for fam in fams:
        try:
            get_transformer("openai", model_name, fam)
            return fam
        except Exception:
            continue
    raise RuntimeError(f"No compatible transformer. Families={fams}")


def make_deepseek_client() -> OpenAIChatCompletionClient:
    api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    base_url = (os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").strip()
    model = (os.getenv("DEEPSEEK_MODEL") or "deepseek-chat").strip()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY missing (.env)")

    fam = _detect_family(model)

    return OpenAIChatCompletionClient(
        model=model,
        api_key=api_key,
        base_url=base_url,
        model_info={
            "family": fam,
            "vision": False,
            "function_calling": True,
            "json_output": False,
            "structured_output": False,
        },
        include_name_in_message=False,
        add_name_prefixes=True,
    )
