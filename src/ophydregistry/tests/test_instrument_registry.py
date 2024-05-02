import gc
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import pytest
from ophyd import Device, EpicsMotor, sim

from ophydregistry import ComponentNotFound, MultipleComponentsFound, Registry


@pytest.fixture()
def registry():
    reg = Registry(auto_register=False, use_typhos=False)
    reg._valid_classes = {mock.MagicMock, *reg._valid_classes}
    try:
        yield reg
    finally:
        del reg


def test_register_component(registry):
    # Create an unregistered component
    cpt = sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    # Make sure the component doesn't get found without being registered
    with pytest.raises(ComponentNotFound):
        list(registry.findall(label="ion_chamber"))
    with pytest.raises(ComponentNotFound):
        list(registry.findall(name="I0"))
    # Now register the component
    cpt = registry.register(cpt)
    # Confirm that it's findable by label
    results = registry.findall(label="ion_chamber")
    assert cpt in results
    # Config that it's findable by name
    results = registry.findall(name="I0")
    assert cpt in results


def test_find_missing_components(registry):
    """Test that registry raises an exception if no matches are found."""
    cpt = sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    registry.register(cpt)
    # Now make sure a different query still returns no results
    with pytest.raises(ComponentNotFound):
        registry.findall(label="spam")


def test_find_allow_missing_components(registry):
    """Test that registry tolerates missing components with the
    *allow_none* argument.

    """
    # Get some non-existent devices and check that the right nothing is returned
    assert list(registry.findall(label="spam", allow_none=True)) == []
    assert registry.find(name="eggs", allow_none=True) is None


def test_exceptions(registry):
    registry.register(Device("", name="It"))
    # Test if a non-existent labels throws an exception
    with pytest.raises(ComponentNotFound):
        registry.find(label="spam")


def test_as_class_decorator(registry):
    # Create a dummy decorated class
    IonChamber = type("IonChamber", (Device,), {})
    IonChamber = registry.register(IonChamber)
    # Instantiate the class
    IonChamber("PV_PREFIX", name="I0", labels={"ion_chamber"})
    # Check that it gets retrieved
    result = registry.find(label="ion_chamber")
    assert result.prefix == "PV_PREFIX"
    assert result.name == "I0"


def test_find_component(registry):
    # Create an unregistered component
    cptA = sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    cptB = sim.SynGauss(
        "It",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    # Register the components
    registry.register(cptA)
    registry.register(cptB)
    # Only one match should work fine
    result = registry.find(name="I0")
    assert result is cptA
    # Multiple matches should raise an exception
    with pytest.raises(MultipleComponentsFound):
        result = registry.find(label="ion_chamber")


def test_find_name_by_dot_notation(registry):
    # Create a simulated component
    cptA = sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    registry.register(cptA)
    # Only one match should work fine
    result = registry.find(name="I0.val")
    assert result is cptA.val


def test_find_labels_by_dot_notation(registry):
    # Create a simulated component
    cptA = sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    registry.register(cptA)
    # Only one match should work fine
    result = registry.find(label="ion_chamber.val")
    assert result is cptA.val


def test_find_any(registry):
    # Create an unregistered component
    cptA = sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    cptB = sim.SynGauss(
        "It",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    cptC = sim.SynGauss(
        "ion_chamber",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
    )
    cptD = sim.SynGauss(
        "sample motor",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={},
    )
    # Register the components
    registry.register(cptA)
    registry.register(cptB)
    registry.register(cptC)
    registry.register(cptD)
    # Only one match should work fine
    result = registry.findall(any_of="ion_chamber")
    assert cptA in result
    assert cptB in result
    assert cptC in result
    assert cptD not in result


def test_find_by_device(registry):
    """The registry should just return the device itself if that's what is passed."""
    # Register a component
    cptD = sim.SynGauss(
        "sample_motor",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={},
    )
    registry.register(cptD)
    # Pass the device itself to the find method
    result = registry.find(cptD)
    assert result is cptD


def test_find_by_list_of_names(registry):
    """Will the findall() method handle lists of things to look up."""
    # Register a component
    cptA = sim.SynGauss(
        "sample motor A",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={},
    )
    cptB = sim.SynGauss(
        "sample motor B",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={},
    )
    cptC = sim.SynGauss(
        "sample motor C",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={},
    )
    registry.register(cptA)
    registry.register(cptB)
    registry.register(cptC)
    # Pass the device names into the findall method
    result = registry.findall(["sample motor A", "sample motor B"])
    assert cptA in result
    assert cptB in result
    assert cptC not in result


def test_user_readback(registry):
    """Edge case where EpicsMotor.user_readback is named the same as the motor itself."""
    device = sim.instantiate_fake_device(
        EpicsMotor, prefix="255idVME:m1", name="epics_motor"
    )
    registry.register(device)
    # See if requesting the device.user_readback returns the proper signal
    registry.find("epics_motor_user_readback")


def test_auto_register():
    """Ensure the registry gets devices that aren't explicitly registered.

    Uses ophyds instantiation callback mechanism.

    """
    registry = Registry(auto_register=True)
    sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    registry.find("I0")
    # Delete this registry to avoid warnings about duplicate entries
    registry.auto_register = False


def test_clear(registry):
    """Can the registry be properly cleared."""
    cpt = sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    registry.register(cpt)
    assert registry.find("I0") is cpt
    # Clear the registry and confirm that it's gone
    registry.clear()
    with pytest.raises(ComponentNotFound):
        registry.find("I0")


def test_component_properties(registry):
    """Check that we can get lists of component and devices."""
    I0 = sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    registry.register(I0)
    assert registry.device_names == {"I0"}
    assert registry.component_names == {
        "I0",
        "I0_Imax",
        "I0_center",
        "I0_noise",
        "I0_noise_multiplier",
        "I0_sigma",
    }


def test_root_devices(registry):
    registry.register(sim.motor1)
    registry.register(sim.motor2)
    registry.register(sim.motor3)
    # Check that only root devices are returned
    root_devices = registry.root_devices
    assert len(root_devices) == 3


def test_getitem(registry):
    """Check that the registry can be accessed like a dictionary."""
    registry.register(sim.motor1)
    # Check that the dictionary access works
    result = registry["motor1"]
    assert result is sim.motor1


def test_duplicate_device(caplog, registry):
    """Check that a device doesn't get added twice."""
    motor = sim.motor
    # Set up logging so that we can know what
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        registry.register(motor)
    # Check for the edge case where motor and motor.user_readback have the same name
    assert "Ignoring component with duplicate name" not in caplog.text
    assert "Ignoring readback with duplicate name" in caplog.text
    # Check that truly duplicated entries get a warning
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        with pytest.warns(UserWarning):
            registry.register(motor)
    # Check for the edge case where motor and motor.user_readback have the same name
    assert "Ignoring component with duplicate name" in caplog.text


def test_delete_by_name(registry):
    """Check that we can remove an item from the ophyd registry."""
    # Add an item to the registry
    motor = sim.motor
    registry.register(motor)
    # Delete the item from the registry
    del registry[motor.name]
    # Check that the test fails
    with pytest.raises(ComponentNotFound):
        registry[motor.name]


def test_pop_by_name(registry):
    """Check that we can remove an item from the ophyd registry."""
    # Add an item to the registry
    motor = sim.motor
    registry.register(motor)
    # Pop the item from the registry
    popped = registry.pop(motor.name)
    assert popped is motor
    # Check that the test fails
    with pytest.raises(ComponentNotFound):
        registry[motor.name]
    with pytest.raises(ComponentNotFound):
        registry["motors"]
    # Make sure children get deleted too
    with pytest.raises(ComponentNotFound):
        registry[motor.acceleration.name]


def test_pop_by_object(registry):
    """Check that we can remove an item from the ophyd registry."""
    # Add an item to the registry
    motor = sim.motor
    registry.register(motor)
    # Pop the item from the registry
    popped = registry.pop(motor)
    assert popped is motor
    # Check that the test fails
    with pytest.raises(ComponentNotFound):
        registry[motor.name]
    with pytest.raises(ComponentNotFound):
        registry["motors"]


def test_pop_default(registry):
    """Check that we get a default object if our key is not present."""
    # Add an item to the registry
    motor = sim.motor
    # Pop the item from the registry
    popped = registry.pop("gibberish", motor)
    assert popped is motor
    # Check that the test fails
    with pytest.raises(ComponentNotFound):
        registry[motor.name]
    with pytest.raises(ComponentNotFound):
        registry["motors"]


def test_weak_references():
    """Check that we can make a registry that automatically drops
    objects that are only referenced by this registry.

    """
    motor = sim.SynAxis(name="weak_motor", labels={"motors"})
    registry = Registry(keep_references=False)
    registry.register(motor)
    # Can we still find the object if the test has a reference?
    assert registry.find("weak_motor") is motor
    # Delete the original object
    del motor
    gc.collect()
    # Check that it's not in the registry anymore
    with pytest.raises(ComponentNotFound):
        registry.find("weak_motor")


@pytest.fixture()
def motors(mocker):
    mocker.patch("ophyd.epics_motor.EpicsMotor.connected", new=True)
    good_motor = EpicsMotor("255idVME:m1", name="good_motor")
    good_motor.connected = True
    bad_motor = EpicsMotor("255idVME:m2", name="bad_motor")
    bad_motor.connected = False
    return (good_motor, bad_motor)


def test_pop_disconnected(registry, motors):
    """Check that we can remove disconnected devices."""
    good_motor, bad_motor = motors
    registry.register(good_motor)
    registry.register(bad_motor)
    # Check that the disconnected device gets removed
    popped = registry.pop_disconnected()
    with pytest.raises(ComponentNotFound):
        registry["bad_motor"]
    # Check that the popped device was returned
    assert len(popped) == 1
    assert popped[0] is bad_motor
    # Check that the connected device is still in the registry
    assert registry["good_motor"] is good_motor


def test_pop_disconnected_with_timeout(registry, motors):
    """Check that we can apply a timeout when waiting for disconnected
    devices.

    """
    good_motor, bad_motor = motors
    good_motor.connected = False  # It starts disconnected
    # Register the devices
    registry.register(good_motor)
    registry.register(bad_motor)

    # Remove the devices with a timeout
    def make_connected(dev, wait):
        time.sleep(wait)
        dev.connected = True

    with ThreadPoolExecutor(max_workers=1) as executor:
        # Make the connection happen after 50 ms
        executor.submit(make_connected, good_motor, 0.15)
        registry.pop_disconnected(timeout=0.3)
    # Check that the connected device is still in the registry
    assert registry["good_motor"] is good_motor
