# Ophyd Registry

[![Python Tests](https://github.com/spc-group/ophyd-registry/actions/workflows/ci.yml/badge.svg)](https://github.com/spc-group/ophyd-registry/actions/workflows/ci.yml)

A registry to keep track of, and retrieve, Ophyd objects.

The **Ophyd registry** provides a way to keep track of the devices
(including components, motors, signals, etc.) that have been defined
across a project. In order for the registry to know of a device, that
device must first be registered, though there are ways to do this
automatically.

This allows for a simple way to keep track of the Ophyd devices that were
created in your project.

```python

import ophyd
from ophydregistry import OphydRegistry

# Register the devices when they're created
registry = OphydRegistry()
registry.register(ophyd.sim.motor)

# Then elsewhere in your project, use them...
registry['motor'].set(15.3)

```

Installation
============

The easiest way to install the ophyd registry is with pip from PyPI:

```bash
python -m pip install ophyd-registry
```

To create a **developer installation**:

```bash
git clone https://github.com/spc-group/ophyd-registry.git
python -m pip install "ophyd_registry[dev]"
```

Usage
=====

Registering Devices
-------------------

There are three ways to have an instrument registry know about a
device.

1. Implicitly capture all Ophyd objects
2. Register a device class
3. Register individual objects

By default, a new instrument registry will alert itself to all future
devices:

```python
from ophydregistry import Registry
registry = Registry()

the_device = MyDevice("255id:Dev:", name="my_device")

assert registry.find("my_device") is the_device
```

This greedy behavior can be suppressed with the *auto_register*
parameter. It can also be turned off after initialization by setting
the *auto_register* attribute to ``False``::

```python

registry = Registry(auto_register=False)

# Make a bunch of devices
...

# Turn if off for this one
registry.auto_register = False
device = MyDevice(...)
registry.auto_register = True

# Register some other devices maybe
...

```

If *auto_register* is false, then a device class can be
decorated to allow the registry to find it:

```python
from ophyd import Device
from ophydregistry import Registry

registry = Registry(auto_register=False)

@registry.register
class MyDevice(Device):
    ...

the_device = MyDevice("255id:Dev:", name="my_device")

assert registry.find("my_device") is the_device
```

Lastly, individual instantions of a device can be explicitly
registered.

```python
from ophyd import Device
from ophydregistry import Registry

registry = Registry(auto_register=False)

class MyDevice(Device):
    ...

the_device = MyDevice("255id:Dev:", name="my_device")
registry.register(the_device)

assert registry.find("my_device") is the_device
```

Looking Up Registered Devices/Components
----------------------------------------

Registered objects can be found by *name*, *label*, or both. The
easist way is to treat the registry like a dictionary:
``registry['motor1']``. This will look for an individual device first
by *name* then by *label*. It will raise an exception if the number of
devices is not 1.

For more sophisticated queries, the *Registry.find()* method will
return a single result, while *Registry.findall()* returns more than
one. By default, *findall()* will raise an exception if no objects
match the criteria, but this can be overridden with the *allow_none*
keyword argument.

The registry uses the built-in concept of device labels in Ophyd. The
registry's ``find()`` and ``findall()`` methods allows devices to be
looked up by label or device name. For example, assuming four devices
exist with the label "ion_chambers", then these devices can be
retrieved using the registry:

```python
ion_chambers = registry.findall(label="ion_chambers")
assert len(ion_chambers) == 4
```

Devices can also be found by name:

```python
ion_chambers = registry.find(name="I0")
assert len(ion_chambers) == 4
```

A set of the **root devices**, those without a parent, can be
retrieved at ``Registry.root_devices``.

Looking Up Sub-Components by Dot-Notation
-----------------------------------------

For simple devices, the full name of the sub-component should be
enough to retrieve the device. For example, to find the signal
*preset_time* on the device named "vortex_me4", the following may work
fine:

```python
preset_time = haven.registry.find("vortex_me4_preset_time")
```

However, **if the component is lazy** and has not been accessed prior
to being registered, then **it will not be available in the
registry**. Sub-components can instead be accessed by dot
notation. Unlike the full device name, dot-notation names only resolve
when the component is requested from the registry, at which point the
lazy components can be accessed.

For example, area detectors use many lazy components. If ``sim_det``
is an area detector with a camera component ``sim_det.cam``, then the
name of the gain channel is "sim_det_cam_gain", however this is a lazy
component so is not available. Instead, retrieving the device by
``haven.registry.find("sim_det.cam.gain")`` will first find the area
detector ("sim_det"), then access the *cam* attribute, and then cam's
*gain* attribute. This has the side-effect of instantiating the lazy
components.


Removing Devices
----------------

The ``OphydRegistry`` class behaves similarly to a python dictionary.

To **remove all devices** from the registry, use the ``clear()``
method:

```python

registry.clear()
```

To **remove disconnected devices** from the registry, use the ``pop_disconnected()`` method with an optional timeout:

```python

# Wait 5 seconds to give devices a chance to connect
disconnected_devices = registry.pop_disconnected(timeout=5)

```

To **remove individual objects**, use either the *del* keyword, or the
``pop()`` method. These approaches work with either the
``OphydObject`` instance itself, or the instance's name:

```python

# Just delete the item and move on
# (by name)
del registry["motor1"]
# (by reference)
motor = registry['motor1']
del registry[motor]

# Remove the item and use it
# (return a simulated motor if "motor1" is not in the registry)
motor = registry.pop("motor1", ophyd.sim.motor)
motor.set(5).wait()

```

Keeping References
------------------

It may be useful to not actually keep a strong reference to the
``OphydObject``s. This means that if all other references to the
object are removed, the device may be dropped from the registry.

By default, the registry keeps direct references to the objects that
get registered, but if initalized with ``keep_references=False`` the
Registry will not keep these references. Instead, **it is up to you to
keep references to the registered objects**.

```python

# Create two registers with both referencing behaviors
ref_registry = Registry(keep_references=True)
noref_registry = Registry(keep_references=False)
motor = EpicsMotor(...)

# Check if we can get the motor (should be no problem)
ref_registry[motor.name]  # <- succeeds
noref_registry[motor.name]  # <- succeeds

# Delete the object and try again
del motor
gc.collect()  # <- make sure it's *really* gone

# Check again if we can get the motor (now it gets fun)
ref_registry[motor.name]  # <- succeeds
noref_registry[motor.name]  # <- raises ComponentNotFound

```

Integrating with Typhos
-----------------------

Typhos includes a PyDM plugin that can directly interact with ophyd
devices. It requires ophyd objects to be registered in order to find
them. **ophyd_registry** can automatically register devices with
Typhos by simply passing the *use_typhos* argument when creating the
registry:

```python
    
from ophydregistry import Registry
registry = Registry(use_typos=True)

```

or setting the *use_typhos* attribute on an existing registry:

```python
    
from ophydregistry import Registry
registry = Registry()
registry.use_typhos = True

```

If using the typhos registry, calling the *clear()* method on the
ophyd registry will also clear the Typhos registry.
