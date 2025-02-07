from abc import abstractmethod
from typing import Protocol, Sequence, Union, runtime_checkable


@runtime_checkable
class Device(Protocol):
    @property
    @abstractmethod
    def name(self) -> str:
        """Used to populate object_keys in the Event DataKey

        https://blueskyproject.io/event-model/event-descriptors.html#object-keys"""
        ...


DeviceQuery = Union[str, Device]

DevicesQuery = Union[str, Device, Sequence[DeviceQuery]]
