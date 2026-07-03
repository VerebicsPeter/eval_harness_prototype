from __future__ import annotations
from datasets import load_dataset
from typing import Protocol, TypeVar, Generator, Generic
from pydantic import BaseModel

type_T = TypeVar("type_T", covariant=True)


class LoaderMetadata(BaseModel):
    dataset: str
    dataset_url: str


class Loader(Protocol[type_T]):
    def load(self) -> Generator[type_T, None, None]:
        ...

    def get_manifest_metadata(self) -> LoaderMetadata:
        ...


class HuggingFaceDatasetLoader(Loader[dict]):
    def __init__(self, dataset_name: str, split: str, limit: int | None = None) -> None:
        self.dataset_name = dataset_name
        self.split = split
        self.limit = limit

    def load(self):
        dataset = load_dataset(self.dataset_name, split=self.split)
        if self.limit is not None:
            yield from map(dict, dataset.select(range(self.limit)))
        else:
            yield from map(dict, dataset)
    
    def get_manifest_metadata(self) -> LoaderMetadata:
        return LoaderMetadata(
            dataset=self.dataset_name,
            dataset_url=self.dataset_name  # TODO: resolve the HF url
        )
