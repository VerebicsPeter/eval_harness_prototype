from typing import Iterable, Iterator, TypeVar
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def validate_stream(data: Iterable, model: type[T]) -> Iterator[T]:
    for i, d in enumerate(data):
        try:
            yield model.model_validate(d)
        except ValidationError as e:
            print(f"Validation failed at index {i}: {e}")  # add proper logging 
            raise
