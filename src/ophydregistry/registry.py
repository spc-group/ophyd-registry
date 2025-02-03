import logging
import time
from collections import OrderedDict
from itertools import chain
from typing import Hashable, List, Mapping, Optional, Sequence, Tuple
from weakref import WeakSet

from ophyd import ophydobj

try:
    from pcdsdevices.signal import _AggregateSignalState
except ImportError:
    _AggregateSignalState = ophydobj.OphydObject

try:
    from ophyd_async.core import Device as AsyncDevice
except ImportError:
    AsyncDevice = ophydobj.OphydObject

from .exceptions import (
    ComponentNotFound,
    InvalidComponentLabel,
    MultipleComponentsFound,
)

# Sentinal value for default parameters
UNSET = object()


try:
    import typhos
except ImportError:
    typhos_available = False
else:
    typhos_available = True


log = logging.getLogger(__name__)


__all__ = ["Registry"]


def is_iterable(obj):
    return (not isinstance(obj, str)) and hasattr(obj, "__iter__")


def remove_duplicates(items, key=None):
    unique_items = list()
    for item in items:
        val = item if key is None else key(item)
        if val not in unique_items:
            yield item
            unique_items.append(val)


def register_typhos_signal(signal):
    """
    Add a new Signal to Typhos' registry.

    The Signal object is kept within ``signal_registry`` for reference by name
    in the :class:`.SignalConnection`. Signals can be added multiple times,
    but only the first register_signal call for each unique signal name
    has any effect.

    Signals can be referenced by their ``name`` attribute or by their
    full dotted path starting from the parent's name.
    """
    # Pick all the name aliases (name, dotted path)
    if signal is signal.root:
        names = (signal.name,)
    else:
        # .dotted_name does not include the root device's name
        names = (
            signal.name,
            ".".join((signal.root.name, signal.dotted_name)),
        )
    # Warn the user if they are adding twice
    signal_registry = typhos.plugins.core.signal_registry
    for name in names:
        if name in signal_registry:
            # Case 1: harmless re-add
            if signal_registry[name] is signal:
                log.debug(
                    "The signal named %s is already registered!",
                    name,
                )
            # Case 2: harmful overwrite! Name collision!
            else:
                log.warning(
                    "A different signal named %s is already registered!",
                    name,
                )
            continue
        else:
            signal_registry[name] = signal
    log.debug("Registering signal with names %s", names)


class Registry:
    """A registry keeps track of devices, signals, etc that have been
    previously registered.

    This mimics the %wa bluesky magic behavior, except that devices
    can be registered outside of the main REPL loop.

    If *auto_register* is False, components can be added to the
    registry using the ``register()`` method.

    Parameters
    ==========
    auto_register
      If true, new ophyd objects will be registered without needing to
      call ``register()``.
    use_typhos
      If true, items added to this registry will also be added to the
      Typhos registry for inclusion in PyDM windows.
    keep_references
      If false, items will be dropped from this registry if the only
      reference comes from this registry. Relies on the garbage
      collector, so to force cleanup use ``gc.collect()``.

    """

    use_typhos: bool
    keep_references: bool
    _auto_register: bool
    _valid_classes: Tuple[type] = (
        ophydobj.OphydObject,
        _AggregateSignalState,
        AsyncDevice,
    )

    # components: Sequence
    _objects_by_name: Mapping
    _objects_by_label: Mapping

    def __init__(
        self,
        auto_register: bool = True,
        use_typhos: bool = False,
        keep_references: bool = True,
    ):
        # Check that Typhos is installed if needed
        if use_typhos and not typhos_available:
            raise ModuleNotFoundError("No module named 'typhos'")
        # Set up empty lists and things for registering components
        self.keep_references = keep_references
        self.use_typhos = use_typhos
        self.clear()
        self.auto_register = auto_register

    @property
    def auto_register(self):
        return self._auto_register

    @auto_register.setter
    def auto_register(self, val):
        """Turn on or off the automatic registration of new devices."""
        self._auto_register = val
        if val:
            # Add a callback to get notified of new objects
            ophydobj.OphydObject.add_instantiation_callback(
                self.register, fail_if_late=False
            )
        else:
            try:
                ophydobj.OphydObject._OphydObject__instantiation_callbacks.remove(
                    self.register
                )
            except ValueError:
                pass

    def __getitem__(self, key):
        """Retrieve the object from the dicionary.

        Equivalent to ``registry.find(key)``.

        """
        return self.find(key)

    def __delitem__(self, key):
        """Remove an object from the dicionary.

        *key* can either be the device OphydObject or the name of an
        OphydObject.

        """
        self.pop(key)

    def pop(self, key, default=UNSET) -> ophydobj.OphydObject:
        """Remove specified OphydObject and return it.

        *key* can either be the device OphydObject or the name of an
        OphydObject.

        A default value can be provided that will be returned if the
        object is not present.

        """
        # Locate the item
        try:
            obj = self[key]
        except ComponentNotFound:
            if default is not UNSET:
                return default
            else:
                raise
        # Remove from the list by name
        try:
            del self._objects_by_name[obj.name]
        except (KeyError, AttributeError):
            pass
        # Remove from the list by label
        if isinstance(obj, Hashable):
            for objects in self._objects_by_label.values():
                objects.discard(obj)
        # Remove children from the lists as well
        sub_signals = getattr(obj, "_signals", {})
        for cpt_name, cpt in sub_signals.items():
            self.pop(cpt)
        return obj

    def clear(self, clear_typhos: bool = True):
        """Remove all previously registered components.

        Parameters
        ==========
        clear_typhos
          If true, also empty the Typhos registry. Has no effect is
          *self.use_typhos* is false.

        """
        self._objects_by_label = OrderedDict()
        self._objects_by_name = OrderedDict()
        if clear_typhos and self.use_typhos:
            typhos.plugins.core.signal_registry.clear()

    def pop_disconnected(self, timeout: float = 0.0) -> List:
        """Remove any registered objects that are disconnected.

        Parameters
        ==========
        timeout
          How long to wait for devices to connect, in seconds.

        Returns
        =======
        disconnected
          The root level devices that were removed.

        """
        remaining = [dev for dev in self.root_devices]
        t0 = time.monotonic()
        timeout_reached = False
        while not timeout_reached:
            # Remove any connected devices for the running list
            remaining = [
                dev for dev in remaining if not getattr(dev, "connected", True)
            ]
            if len(remaining) == 0:
                # All devices are connected, so just end early.
                break
            time.sleep(min((0.05, timeout / 10.0)))
            timeout_reached = (time.monotonic() - t0) > timeout
        # Remove unconnected devices from the registry
        popped = [self.pop(dev) for dev in remaining]
        return popped

    @property
    def component_names(self):
        return set(self._objects_by_name.keys())

    @property
    def root_devices(self):
        """Only return root devices, those without parents."""
        all_devices = [
            dev for devices in self._objects_by_name.values() for dev in devices
        ]
        return {device for device in all_devices if device.parent is None}

    @property
    def device_names(self):
        """Only return root devices, those without parents."""
        return {device.name for device in self.root_devices}

    def find(
        self,
        any_of: Optional[str] = None,
        *,
        label: Optional[str] = None,
        name: Optional[str] = None,
        allow_none: Optional[str] = False,
    ) -> ophydobj.OphydObject:
        """Find registered device components matching parameters.

        The *any_of* keyword is a proxy for all the other
        keywords. For example ``findall(any_of="my_device")`` is
        equivalent to ``findall(name="my_device",
        label="my_device")``.

        The name provided to *any_of*, *label*, or *name* can also
        include dot-separated attributes after the device name. For
        example, looking up ``name="eiger_500K.cam.gain"`` will look
        up the device named "eiger_500K" then return the
        Device.cam.gain attribute.

        Parameters
        ==========
        any_of
          Search by all of the other parameters.
        label
          Search by the component's ``labels={"my_label"}`` parameter.
        name
          Search by the component's ``name="my_name"`` parameter.
        allow_none
          If false, missing components will raise an exception. If
          true, an empty list is returned if no registered components
          are found.


        Returns
        =======
        result
          A list of all the components matching the search parameters.

        Raises
        ======
        ComponentNotFound
          No component was found that matches the given search
          parameters.
        MultipleComponentsFound
          The search parameters matched with more than one registered
          component. Either refine the search terms or use the
          ``self.findall()`` method.

        """
        devices = self.findall(
            any_of=any_of, label=label, name=name, allow_none=allow_none
        )
        # Remove any direct ancestors
        devices = set(dev for dev in devices if dev.parent not in devices)
        # Make sure we have only 1 result
        if len(devices) == 1:
            device = list(devices)[0]
        elif len(devices) > 1:
            raise MultipleComponentsFound(
                f"Found {len(devices)} components matching query "
                f"[any_of={any_of}, label={label}, name={name}]. "
                "Consider using ``findall()``. "
                f"{devices}"
            )
        else:
            device = None
        return device

    def _is_resolved(self, obj):
        """Is the object already resolved into an ophyd device, etc.

        This method checks the type of the object. To extend this to
        other types of objects, override this objects
        ``_valid_classes`` attribute with a new set.

        """
        if isinstance(obj, self._valid_classes):
            return True
        return False

    def _findall_by_label(self, label, allow_none):
        # Check for already created ophyd objects (return as is)
        if self._is_resolved(label):
            yield label
            return
        # Recursively get lists of components
        if is_iterable(label):
            for lbl in label:
                yield from self.findall(label=lbl, allow_none=allow_none)
        else:
            # Split off label attributes
            try:
                label, *attrs = label.split(".")
            except AttributeError:
                attrs = []
            try:
                for cpt_ in self._objects_by_label[label]:
                    # Re-apply the dot-notation filter
                    for attr in attrs:
                        cpt_ = getattr(cpt_, attr)
                    yield cpt_
            except KeyError:
                # No components found so just move on
                pass
            except TypeError:
                raise InvalidComponentLabel(label)

    def _findall_by_name(self, name):
        # Check for already created ophyd objects (return as is)
        if self._is_resolved(name):
            yield name
            return
        # Check for an iterable of names instead of a single name
        if is_iterable(name):
            for n in name:
                yield from self.findall(name=n)
            return
        # Split off any dot notation parameters for later filtering
        try:
            name, *attrs = name.split(".")
        except AttributeError:
            attrs = []
        # Find the matching components
        try:
            devices = self._objects_by_name[name]
        except KeyError:
            pass
        else:
            # Re-apply dot-notation filter
            for device in devices:
                try:
                    for attr in attrs:
                        device = getattr(device, attr)
                except AttributeError:
                    continue
                yield device

    def findall(
        self,
        any_of: Optional[str] = None,
        *,
        label: Optional[str] = None,
        name: Optional[str] = None,
        allow_none: Optional[bool] = False,
    ) -> List[ophydobj.OphydObject]:
        """Find registered device components matching parameters.

        Combining search terms works in an *or* fashion. For example,
        ``findall(name="my_device", label="ion_chambers")`` will find
        all devices that have either the name "my_device" or a label
        "ion_chambers".

        The *any_of* keyword is a proxy for all the other keywords. For
        example ``findall(any_of="my_device")`` is equivalent to
        ``findall(name="my_device", label="my_device")``.

        The name provided to *any_of*, *label*, or *name* can also
        include dot-separated attributes after the device name. For
        example, looking up ``name="eiger_500K.cam.gain"`` will look
        up the device named "eiger_500K" then return the
        Device.cam.gain attribute.

        Parameters
        ==========
        any_of
          Search by all of the other parameters.
        label
          Search by the component's ``labels={"my_label"}`` parameter.
        name
          Search by the component's ``name="my_name"`` parameter.
        allow_none
          If false, missing components will raise an exception. If
          true, an empty list is returned if no registered components
          are found.

        Returns
        =======
        results
          A list of all the components matching the search parameters.

        Raises
        ======
        ComponentNotFound
          No component was found that matches the given search
          parameters.

        """
        results = []
        # If using *any_of*, search by label and name
        _label = label if label is not None else any_of
        _name = name if name is not None else any_of
        # Apply several filters against label, name, etc.
        if is_iterable(any_of):
            for a in any_of:
                results.append(self.findall(any_of=a, allow_none=allow_none))
        else:
            # Filter by label
            if _label is not None:
                results.append(self._findall_by_label(_label, allow_none=allow_none))
            # Filter by name
            if _name is not None:
                results.append(self._findall_by_name(_name))
        # Peek at the first item to check for an empty result
        results = chain(*results)
        try:
            first = next(results)
        except StopIteration:
            # No results were found
            if allow_none:
                results = []
            else:
                raise ComponentNotFound(
                    f'Could not find components matching: label="{_label}", name="{_name}"'
                )
        else:
            # Stick the first entry back in the queue and yield it
            results = chain([first], results)
        return list(remove_duplicates(results))

    def __new__wrapper(self, cls, *args, **kwargs):
        # Create and instantiate the new object
        obj = super(type, cls).__new__(cls)
        obj.__init__(*args, **kwargs)
        # Register the new object
        self.register(obj)
        return obj

    def register(
        self,
        component: ophydobj.OphydObject,
        labels: Optional[Sequence] = None,
    ) -> ophydobj.OphydObject:
        """Register a device, component, etc so that it can be retrieved later.

        If *component* is a class, then any instances created will
        automatically be registered. Else, *component* will be assumed
        to be an instance and will be registered directly.

        Returns
        =======
        component
          The same component as was provided as an input.
        labels
          Device labels to use for registration. If `None` (default),
          the devices *_ophyd_labels_* parameter will be used.

        """
        # Determine how to register the device
        if isinstance(component, type):
            # A class was given, so instances should be auto-registered
            component.__new__ = self.__new__wrapper
            return component
        # An instance was given, so just save it in the register
        try:
            name = component.name
        except AttributeError:
            msg = f"Skipping unnamed component {component}"
            if isinstance(component, _AggregateSignalState):
                log.debug(msg)
            else:
                log.info(msg)
            return component
        # Register this object with Typhos
        if self.use_typhos:
            register_typhos_signal(component)
        # Register this component
        log.debug(f"Registering {name}")
        # Register by name
        if self.keep_references:
            new_set = set
        else:
            new_set = WeakSet
        if component.name != "":
            name = component.name
            if name not in self._objects_by_name.keys():
                self._objects_by_name[name] = new_set()
            self._objects_by_name[name].add(component)
        # Check if this device was previously registered with a
        # different name/label
        old_names = [
            name
            for name, devices in self._objects_by_name.items()
            if component in devices
        ]
        old_names = [name for name in old_names if name != component.name]
        for old_key in old_names:
            print(old_key, component.name)
            self._objects_by_name[old_key].remove(component)
        old_labels = [
            label
            for label, devices in self._objects_by_label.items()
            if component in devices
        ]
        old_labels = [
            label for label in old_labels if label not in component._ophyd_labels_
        ]
        for old_key in old_labels:
            self._objects_by_label[old_key].remove(component)

        # Create a set for this device's labels if it doesn't exist
        if labels is None:
            ophyd_labels = getattr(component, "_ophyd_labels_", [])
        else:
            ophyd_labels = labels
        for label in ophyd_labels:
            if label not in self._objects_by_label.keys():
                self._objects_by_label[label] = new_set()
            self._objects_by_label[label].add(component)
        # Register this object with Typhos
        if self.use_typhos:
            import typhos

            typhos.plugins.register_signal(component)
        # Recusively register sub-components
        if hasattr(component, "_signals"):
            # Vanilla ophyd device
            sub_signals = component._signals.items()
        elif hasattr(component, "children"):
            # Ophyd-async device
            sub_signals = component.children()
        else:
            sub_signals = []
        for cpt_name, cpt in sub_signals:
            self.register(cpt)
        return component
