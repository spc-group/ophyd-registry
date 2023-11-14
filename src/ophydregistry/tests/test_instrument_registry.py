import pytest

from ophyd import sim, Device, EpicsMotor

from ophydregistry import Registry, ComponentNotFound, MultipleComponentsFound


@pytest.fixture()
def registry():
    reg = Registry(auto_register=False)
    return reg


def test_register_component(registry):
    # Prepare registry
    registry = Registry(auto_register=False)
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


def test_find_missing_components():
    """Test that registry raises an exception if no matches are found."""
    reg = Registry()
    cpt = sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    reg.register(cpt)
    # Now make sure a different query still returns no results
    with pytest.raises(ComponentNotFound):
        reg.findall(label="spam")


def test_find_allow_missing_components():
    """Test that registry tolerates missing components with the
    *allow_none* argument.

    """
    reg = Registry()
    # Get some non-existent devices and check that the right nothing is returned
    assert list(reg.findall(label="spam", allow_none=True)) == []
    assert reg.find(name="eggs", allow_none=True) is None


def test_exceptions(registry):
    registry = Registry()
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


def test_find_labels_by_dot_notation():
    # Prepare registry
    reg = Registry()
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
    reg.register(cptA)
    # Only one match should work fine
    result = reg.find(label="ion_chamber.val")
    assert result is cptA.val


def test_find_any():
    # Prepare registry
    reg = Registry()
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
    reg.register(cptA)
    reg.register(cptB)
    reg.register(cptC)
    reg.register(cptD)
    # Only one match should work fine
    result = reg.findall(any_of="ion_chamber")
    assert cptA in result
    assert cptB in result
    assert cptC in result
    assert cptD not in result


def test_find_by_device():
    """The registry should just return the device itself if that's what is passed."""
    # Prepare registry
    reg = Registry()
    # Register a component
    cptD = sim.SynGauss(
        "sample motor",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={},
    )
    reg.register(cptD)
    # Pass the device itself to the find method
    result = reg.find(cptD)
    assert result is cptD


def test_find_by_list_of_names():
    """Will the findall() method handle lists of things to look up."""
    # Prepare registry
    reg = Registry()
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
    reg.register(cptA)
    reg.register(cptB)
    reg.register(cptC)
    # Pass the device names into the findall method
    result = reg.findall(["sample motor A", "sample motor B"])
    assert cptA in result
    assert cptB in result
    assert cptC not in result


def test_user_readback(registry):
    """Edge case where EpicsMotor.user_readback is named the same as the motor itself."""
    device = EpicsMotor("255idVME:m1", name="epics_motor")
    registry.register(device)
    # See if requesting the device.user_readback returns the proper signal
    registry.find("epics_motor_user_readback")


def test_auto_register():
    """Ensure the registry gets devices that aren't explicitly registered.

    Uses ophyds instantiation callback mechanism.

    """
    registry = Registry()
    cptA = sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    registry.find("I0")


def test_clear():
    """Can the registry be properly cleared."""
    registry = Registry()
    cpt = sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    assert registry.find("I0") is cpt
    # Clear the registry and confirm that it's gone
    registry.clear()
    with pytest.raises(ComponentNotFound):
        registry.find("I0")


def test_component_properties():
    """Check that we can get lists of component and devices."""
    registry = Registry()
    cpt = sim.SynGauss(
        "I0",
        sim.motor,
        "motor",
        center=-0.5,
        Imax=1,
        sigma=1,
        labels={"ion_chamber"},
    )
    assert registry.device_names == {"I0"}
    assert registry.component_names == {
        "I0",
        "I0_Imax",
        "I0_center",
        "I0_noise",
        "I0_noise_multiplier",
        "I0_sigma",
        "I0_val",
    }
