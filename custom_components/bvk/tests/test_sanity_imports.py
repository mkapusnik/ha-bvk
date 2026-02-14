def test_imports_smoke():
    # Basic sanity check that module imports don't crash.
    import custom_components.bvk.config_flow  # noqa: F401
    import custom_components.bvk.const  # noqa: F401
    import custom_components.bvk.sensor  # noqa: F401
