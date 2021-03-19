from invoke_release.tasks import *  # noqa: F403


configure_release_parameters(  # noqa: F405
    module_name='pilo',
    display_name='Pilo',
    use_pull_request=True,
    use_tag=False,
)
