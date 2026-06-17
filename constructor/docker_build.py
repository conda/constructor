"""Logic for creating a Dockerfile and/or building portable Docker images from Constructor installers."""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from jinja2 import Template

from . import __version__
from .utils import check_version, format_conda_exe_name

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).parent / "dockerfile_template.tmpl"

DOCKER_PLATFORM_MAP = {
    "linux-64": "linux/amd64",
    "linux-aarch64": "linux/arm64",
    "linux-armv7l": "linux/arm/v7",
    "linux-32": "linux/386",
    "linux-ppc64le": "linux/ppc64le",
    "linux-s390x": "linux/s390x",
}


def _build_init_run_block(info):
    from .conda_interface import MatchSpec

    specs = {MatchSpec(spec).name for spec in info.get("specs", ())}
    has_mamba = "mamba" in specs
    has_conda = "conda" in specs
    initialize_conda = info.get("initialize_conda")

    if not (has_conda or has_mamba) or not initialize_conda or initialize_conda == "condabin":
        return ""
    run = 'RUN "${PREFIX}/bin/conda" init --all'

    if has_mamba:
        mamba_version = None
        for record in info.get("_all_pkg_records", ()):
            if record.name == "mamba":
                mamba_version = record.version
                break
        if check_version(mamba_version, min_version="2.0.0"):
            run += ' && "${PREFIX}/bin/mamba" shell init'
        else:
            run += ' && "${PREFIX}/bin/python" -m mamba.mamba init'
    return run


def generate_dockerfile(info: dict, docker_dir: Path) -> Path:
    """
    Render the Dockerfile template and write it to the Docker build directory.

    Parameters
    ----------
    info: dict
        Constructor installer info dict.
    docker_dir: Path
        Path to the Docker build directory returned by prepare_docker_context().

    Returns
    -------
    Path
        Path to the generated Dockerfile.
    """

    rendered_dockerfile = Template(TEMPLATE_PATH.read_text()).render(
        constructor_version=__version__,
        base_image=info.get("docker_base_image"),
        default_prefix=info.get("default_prefix", f"/opt/{info['name'].lower()}"),
        installer_filename=Path(info["_outpath"]).name,
        conda_exe_name=format_conda_exe_name(info["_conda_exe"]),
        name=info["name"],
        version=info["version"],
        labels=info.get("docker_labels", {}),
        initialize_conda=info.get("initialize_conda"),
        register_envs=info.get("register_envs"),
        keep_pkgs=info.get("keep_pkgs"),
        init_run_block=_build_init_run_block(info),
    )

    logger.info("Writing Dockerfile...")
    dockerfile_path = docker_dir / "Dockerfile"
    dockerfile_path.write_text(rendered_dockerfile)
    return dockerfile_path


def build_image(info: dict, docker_dir: Path) -> Path:
    """Optionally build the docker image from the generated Dockerfile.
    Currently supported on linux and macOS platforms.

    Parameters
    ----------
    info: dict
        Constructor installer info dict.
    docker_dir: Path
        Path to the Docker directory containing the Docker outputs.

    Returns
    -------
    Path
        Path to the saved Docker image tarball.

    """
    if not (docker_platform := DOCKER_PLATFORM_MAP.get(info["_platform"])):
        raise RuntimeError(
            f"Unsupported platform for Docker build: {info['_platform']}. "
            f"Supported platforms are: {', '.join(DOCKER_PLATFORM_MAP.keys())}."
        )

    tag = info.get("docker_tag", f"{info['name'].lower()}:{info['version']}")
    tarball_dest = docker_dir / f"{Path(info['_outpath']).stem}-docker.tar"

    cmd = [
        "docker",
        "buildx",
        "build",
        str(docker_dir),
        "--platform",
        docker_platform,
        "-t",
        tag,
        "--load",
    ]

    logger.info("Building Docker image: '%s'", tag)
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        # Gather diagnostics on failure
        docker_version = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        buildx_version = subprocess.run(
            ["docker", "buildx", "version"], capture_output=True, text=True
        )
        buildx_ls = subprocess.run(["docker", "buildx", "ls"], capture_output=True, text=True)
        raise RuntimeError(
            f"Docker build failed.\n"
            f"Docker version: {docker_version.stdout.strip()}\n"
            f"Buildx version: {buildx_version.stdout.strip() or buildx_version.stderr.strip()}\n"
            f"Buildx builders: {buildx_ls.stdout.strip()}"
        ) from e

    logger.info("Saving Docker image to tarball: '%s'", tarball_dest)
    subprocess.run(["docker", "save", tag, "-o", str(tarball_dest)], check=True)
    subprocess.run(["docker", "rmi", tag], check=False)
    return tarball_dest


def create(info: dict, verbose: bool = False) -> None:
    """Build a Docker output from a previously built ``.sh`` installer.

    The ``.sh`` installer is built in the preceding ``sh`` iteration of the
    installer loop in ``main_build`` and must exist at ``info["_outpath"]``
    before this function is called.

    Parameters
    ----------
    info: dict
        Constructor installer info dict.
    verbose: bool, optional
        If ``True``, enables verbose logging.
        Defaults to ``False``.

    """
    with tempfile.TemporaryDirectory() as temp_dir:
        docker_tmp_dir = Path(temp_dir)

        installer_path = Path(info["_outpath"])
        if not installer_path.exists():
            raise RuntimeError(f"Expected .sh installer not found: {installer_path}")
        shutil.copy(installer_path, docker_tmp_dir / installer_path.name)
        logger.info("Copied installer to build directory.")

        generate_dockerfile(info, docker_tmp_dir)

        if info.get("docker_image_format"):
            tarball = build_image(info, docker_tmp_dir)
            shutil.copy(tarball, Path(info["_output_dir"]) / tarball.name)
        else:
            output_dir = Path(info["_output_dir"]) / installer_path.stem
            output_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(docker_tmp_dir / "Dockerfile", output_dir / "Dockerfile")
            shutil.copy(
                docker_tmp_dir / Path(info["_outpath"]).name,
                output_dir / Path(info["_outpath"]).name,
            )

    logger.info("Docker output complete. Docker directory: '%s'", info["_output_dir"])

    installer_path.unlink(missing_ok=True)
