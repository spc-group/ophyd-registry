from abc import abstractmethod
from typing import Protocol, runtime_checkable, Optional, Sequence, Optional, Union


@runtime_checkable
class Device(Protocol):
    @property
    @abstractmethod
    def name(self) -> str:
        """Used to populate object_keys in the Event DataKey

        https://blueskyproject.io/event-model/event-descriptors.html#object-keys"""
        ...



DeviceQuery = Union[str, Device, Sequence[Union[str, Device]]]
