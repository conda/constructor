"""Logic for creating a Dockerfile and/or building portable Docker images from Constructor installers."""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from jinja2 import Template

from . import __version__

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


def prepare_docker_context(info: dict, tmp_dir: Path) -> Path:
    """Copy the .sh installer into the Docker build directory.

    Parameters
    ----------
    info: dict
        Constructor installer info dict. Must contain ``_outpath`` and ``_output_dir`` pointing to the built .sh
        installer and output directory respectively.
    tmp_dir: Path
        Path to a temporary directory to stage the Docker build context. The .sh installer will be copied to this directory.

    Returns
    -------
    Path
        Path to the tmp Docker build directory.
    """
    installer_path = Path(info["_outpath"])
    if not installer_path.exists():
        raise RuntimeError(f"Expected .sh installer not found: {installer_path}")

    shutil.copy(installer_path, tmp_dir / installer_path.name)
    logger.info("Copied installer to tmp directory: %s", tmp_dir / installer_path.name)

    return tmp_dir


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
        Path to the generated Dockerfile, or None if generation is skipped.
    """
    from .conda_interface import MatchSpec

    specs = {MatchSpec(spec).name for spec in info.get("specs", ())}

    docker_template = Template(TEMPLATE_PATH.read_text())

    docker_base_image = info.get("docker_base_image")
    if not docker_base_image:
        logger.warning(
            "Skipping Dockerfile generation. 'docker_base_image' not specified in construct.yaml."
        )
        return None

    if "@" not in docker_base_image:
        logger.warning(
            "No SHA256 digest specified for docker_base_image. "
            "Consider specifying a digest to ensure the integrity of the base image used for the build, e.g.:\n"
            " docker_base_image: debian:13.4-slim@sha256:4ffb3a1511099754cddc70eb1b12e50ffdb67619aa0ab6c13fcd800a78ef7c7a\n"
        )

    rendered_dockerfile = docker_template.render(
        constructor_version=__version__,
        base_image=docker_base_image,
        default_prefix=info.get("default_prefix", f"/opt/{info['name'].lower()}"),
        installer_filename=Path(info["_outpath"]).name,
        clean_cmd="$PREFIX/bin/mamba clean -afy"
        if "mamba" in specs
        else "$PREFIX/bin/conda clean -afy",
        name=info["name"],
        version=info["version"],
        labels=info.get("docker_labels", {}),
        init_cmd="$PREFIX/bin/mamba shell" if "mamba" in specs else "$PREFIX/bin/python -m conda",
        register_envs=info.get("register_envs", True),
        keep_pkgs=info.get("keep_pkgs", False),
    )

    dockerfile_path = docker_dir / "Dockerfile"
    dockerfile_path.write_text(rendered_dockerfile)
    logger.info("Dockerfile written to: '%s'", dockerfile_path)
    return dockerfile_path


def build_image(info: dict, docker_dir: Path) -> None:
    """Optionally build the docker image from the generated Dockerfile.
    Currently supported on linux and macOS platforms.

    Parameters
    ----------
    info: dict
        Constructor installer info dict.
    docker_dir: Path
        Path to the Docker directory containing the Docker outputs.

    """
    if info.get("_platform") not in DOCKER_PLATFORM_MAP:
        logger.warning(
            f"Building Docker images is not supported on platform '{info['_platform']}'. "
            "Skipping Docker build. You can still build the image manually using 'docker buildx' on a supported platform or Docker Desktop. "
            "Supported platforms for Docker build are: linux/amd64 and linux/arm64."
        )
        return

    if shutil.which("docker") is None:
        raise RuntimeError(
            "Building a Docker image requires the 'docker' CLI tool to be installed and available in PATH. "
            "Install Docker Desktop or Docker Engine to proceed, or "
            "use `installer_type: docker` in construct.yaml to "
            "generate the Dockerfile without building the image."
        )

    docker_platform = DOCKER_PLATFORM_MAP.get(info["_platform"])
    if docker_platform is None:
        raise RuntimeError(
            f"Unsupported platform for Docker build: '{info['_platform']}'. "
            f"Supported platforms are: {', '.join(DOCKER_PLATFORM_MAP)}."
        )

    tag = info.get("docker_tag", f"{info['name'].lower()}:{info['version'].split('-')[0]}")
    docker_dir = Path(info["_output_dir"]) / "docker"
    tarball_dest = docker_dir / f"{tag.replace(':', '-')}-{docker_platform.replace('/', '-')}.tar"

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
    subprocess.run(cmd, check=True)
    logger.info("Docker image '%s' built successfully.", tag)

    logger.info("Saving Docker image to tarball: '%s'", tarball_dest)
    with open(tarball_dest, "wb") as f:
        subprocess.run(["docker", "save", tag, "-o", str(tarball_dest)], check=True, stdout=f)
    logger.info("Docker image saved to: '%s'", tarball_dest)


def create(info: dict, verbose: bool = False) -> None:
    """Build a Docker output

    Parameters
    ----------
    info: dict
        Constructor installer info dict.
    verbose: bool, optional
        If ``True``, enables verbose logging.
        Defaults to ``False``.

    """
    with tempfile.TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)
        info["_outpath"] = info["_outpath"].replace(".docker", ".sh")
        prepare_docker_context(info, tmp_path)
        dockerfile = generate_dockerfile(info, tmp_path)
        if dockerfile is None:
            logger.warning("Dockerfile generation skipped. Docker image will not be built.")
            return

        output_docker_dir = Path(info["_output_dir"]) / "docker"
        output_docker_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy(tmp_path / "Dockerfile", output_docker_dir / "Dockerfile")
        shutil.copy(
            tmp_path / Path(info["_outpath"]).name, output_docker_dir / Path(info["_outpath"]).name
        )

        if info.get("docker_build"):
            build_image(info, output_docker_dir)

    logger.info("Docker output complete. Docker directory: '%s'", output_docker_dir)
