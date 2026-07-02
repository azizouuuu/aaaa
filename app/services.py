"""Singleton wiring: one Store + PipelineRegistry per process."""

from . import config
from .db import Store
from .pipelines.base import PipelineRegistry
from .pipelines.comtrade import ComtradePipeline
from .pipelines.eurostat_comext import EurostatComextPipeline
from .pipelines.sample import SamplePipeline

_store: Store | None = None
_registry: PipelineRegistry | None = None
_sample: SamplePipeline | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store(config.DB_PATH)
    return _store


def get_registry() -> PipelineRegistry:
    global _registry, _sample
    if _registry is None:
        store = get_store()
        _sample = SamplePipeline(store, config.SAMPLE_DATA_PATH)
        comtrade = ComtradePipeline(store, config.COMTRADE_API_KEY)
        eurostat = EurostatComextPipeline(store)
        _registry = PipelineRegistry([eurostat, comtrade], _sample, config.DATA_MODE)
    return _registry


def sample_disclaimer() -> str:
    get_registry()
    return _sample.disclaimer if _sample else ""


def reset() -> None:  # for tests
    global _store, _registry, _sample
    _store = _registry = _sample = None
