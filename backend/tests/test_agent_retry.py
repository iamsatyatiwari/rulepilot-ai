import asyncio
from dataclasses import replace

import app.agent.agent as agent_module
from app.agent.tools import InvestigationContext, InvestigationToolkit
from app.config import get_settings
from app.datasets import SCENARIO_DATASET_ID, get_dataset
from app.intel.advisories import load_curated_advisories

ADVISORY = load_curated_advisories()["jpm-card-testing"]


def toolkit():
    info, records = get_dataset(SCENARIO_DATASET_ID)
    return InvestigationToolkit(InvestigationContext("retry-run", info, records, 41))


def settings():
    return replace(get_settings(), gemini_model="primary", gemini_fallback_models=("fallback",))


def test_transient_error_mid_run_discards_partial_state_and_falls_back(monkeypatch):
    calls = []

    async def fake_run_once(kit, advisory, config, model, timeout, stats):
        calls.append(model)
        kit.get_rule_catalog()
        stats.llm_calls += 2
        if model == "primary":
            return "ResourceExhaustedError: 429 RESOURCE_EXHAUSTED"
        return None

    monkeypatch.setattr(agent_module, "_run_once", fake_run_once)
    monkeypatch.setattr(agent_module, "RETRY_DELAYS_SECONDS", ())
    kit = toolkit()
    stats = asyncio.run(agent_module.run_adk_agent(kit, ADVISORY, settings()))

    assert calls == ["primary", "fallback"]
    assert stats.model_used == "fallback"
    assert stats.llm_calls == 2
    assert len(kit.context.tool_calls) == 1
    assert "discarded" in stats.errors[0]


def test_non_transient_error_stops_without_fallback(monkeypatch):
    calls = []

    async def fake_run_once(kit, advisory, config, model, timeout, stats):
        calls.append(model)
        return "ValueError: invalid request"

    monkeypatch.setattr(agent_module, "_run_once", fake_run_once)
    stats = asyncio.run(agent_module.run_adk_agent(toolkit(), ADVISORY, settings()))
    assert calls == ["primary"]
    assert stats.errors == ["primary attempt 1: ValueError: invalid request"]
