class ComponentNotFound(KeyError):
    """Registry looked for a component, but it wasn't registered."""

    ...


class MultipleComponentsFound(KeyError):
    """Registry looked for a single component, but found more than one."""

    ...


class InvalidComponentLabel(TypeError):
    """Registry looked for a component, but the label provided is not vlaid."""

    ...
