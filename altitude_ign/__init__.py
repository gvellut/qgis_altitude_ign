def classFactory(iface):  # pylint: disable=invalid-name
    from .altitude_ign import AltitudeIgnPlugin

    return AltitudeIgnPlugin(iface)
