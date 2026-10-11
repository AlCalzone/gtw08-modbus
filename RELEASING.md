# Releasing `gtw08-modbus`

Publishing a GitHub release publishes the package to PyPI. Nothing else does.

## Tags

Release tags are bare versions without a leading `v`, such as `0.1.5` or `1.0.0`. The workflow writes the tag into `pyproject.toml` as the package version, and the `pypi` environment only accepts tags that match `*.*.*`.

## Steps

1. Check that the `CI` workflow is green on `main`.
2. On GitHub, go to **Releases** and choose **Draft a new release**.
3. Create a new tag with the version, such as `0.1.5`, targeting `main`. Use the version as the title, and write the release notes.
4. Select **Publish release**. This starts the `Publish to PyPI` workflow, which runs the tests and builds the package.
5. Open the run in the **Actions** tab. The publish job waits for approval in the `pypi` environment. Approve it to upload the package.

## PyPI setup

PyPI accepts the upload through trusted publishing. The project's trusted publisher on PyPI must name this repository, the workflow `publish.yml` and the environment `pypi`.
