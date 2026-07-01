from __future__ import annotations

from typing import Any, Iterable, Protocol, TypeVar

from datasets import load_dataset


class SupportsLoad(Protocol):
    def load(self) -> Iterable[str] | str:
        ...


T = TypeVar("T", bound=SupportsLoad)


class AssertTestLoader:
    def __init__(self, loader: T, assert_statements: str) -> None:
        self._loader = loader
        self._assert_statements = assert_statements

    def load(self) -> list[str]:
        raw_items = self._loader.load()
        if isinstance(raw_items, str):
            items = [raw_items]
        else:
            items = [str(item) for item in raw_items]

        if not self._assert_statements.strip():
            return items

        appended = []
        for item in items:
            if item.strip():
                appended.append(f"{item}\n\n{self._assert_statements}")
            else:
                appended.append(self._assert_statements)
        return appended


class HuggingFaceDatasetLoader:
    def __init__(self, dataset_name: str, split: str = "test", limit: int | None = None) -> None:
        self.dataset_name = dataset_name
        self.split = split
        self.limit = limit

    def load(self) -> list[dict[str, Any]]:
        dataset = load_dataset(self.dataset_name, split=self.split)
        records = list(dataset)
        if self.limit is not None:
            records = records[: self.limit]
        return [dict(record) for record in records]
