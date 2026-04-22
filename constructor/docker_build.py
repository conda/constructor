import logging
import shutil
import subprocess
from pathlib import Path
from jinja2 import Template

from . import __version__

logger = logging.getLogger(__name__)

DEFAULT_BASE_IMAGE = "debian:13.4-slim"
DEFAULT_BASE_IMAGE_SHA = "4ffb3a1511099754cddc70eb1b12e50ffdb67619aa0ab6c13fcd800a78ef7c7a"
TEMPLATE_PATH = Path(__file__).parent / "dockerfile_template.tmpl"

ARCH_MAP = {
    "64": "amd64",
    "arm64": "arm64",
    "aarch64": "arm64",
}

def prepare_docker_context(info: dict) -> Path:
    """Copy the .sh installer into the Docker build directory.

    Parameters
    ----------
    info: dict
        Constructor installer info dict. Must contain ``_outpath`` and ``_output_dir`` pointing to the built .sh installer and output directory respectively.

    Returns
    -------
    Path
        Path to the Docker build directory (``<_output_dir>/docker``).
    """
    docker_dir = Path(info["_output_dir"]) / "docker"
    docker_dir.mkdir(parents=True, exist_ok=True)

    installer_path = Path(info["_outpath"])
    if not installer_path.exists():
        raise RuntimeError(
            f"Expected .sh installer not found: {installer_path}\n"
        )

    shutil.copy(installer_path, docker_dir / installer_path.name)
    logger.info("Copied installer to Docker directory: %s", docker_dir / installer_path.name)

    return docker_dir


def generate_dockerfile(info: dict, docker_dir: Path) -> Path:
    """
    Render the Dockerfile template and write it to `<docker_dir>/Dockerfile`.

    Parameters
    ----------
    info: dict
        Constructor installer info dict.
    docker_dir: Path
        Path to the Docker build directory (``<_output_dir>/docker``) returned by prepare_docker_context().

    Returns
    -------
    Path
        Path to the generated Dockerfile. ``<docker_dir>/Dockerfile``.
    """
    docker_template = Template(TEMPLATE_PATH.read_text())

    docker_base_image = info.get("docker_base_image", DEFAULT_BASE_IMAGE)
    docker_base_image_sha = ":latest" if not DEFAULT_BASE_IMAGE_SHA else f"@sha256:{DEFAULT_BASE_IMAGE_SHA}"
    docker_base_image_sha = info.get("docker_base_image_sha", docker_base_image_sha)

    rendered_dockerfile = docker_template.render(
        constructor_version=__version__,
        base_image=f"{docker_base_image}{docker_base_image_sha}",
        default_prefix=info.get("default_prefix", "/opt/conda"),
        installer_filename=Path(info["_outpath"]).name,
        name=info["name"],
        version=info["version"],
        labels=info.get("docker_labels", {}),
    )

    dockerfile_path = docker_dir / "Dockerfile"
    dockerfile_path.write_text(rendered_dockerfile)
    logger.info("Dockerfile written to: '%s'", dockerfile_path)
    return dockerfile_path


def build_image(info: dict, docker_dir: Path) -> None:
    """Optionally build the docker image from the generated Dockerfile.

    Parameters
    ----------
    info: dict
        Constructor installer info dict.
    docker_dir: Path
        Path to the Docker directory containing the Dockerfile.

    """
    if shutil.which("docker") is None:
        raise RuntimeError(
            "Building a Docker image requires the 'docker' CLI tool to be installed and available in PATH. "
            "Install Docker Desktop or Docker Engine to proceed, or "
            "use `installer_type: docker  # [linux]` in construct.yaml to "
            "generate the Dockerfile without building the image."
        )

    osname, arch = info["_platform"].split("-")

    if osname == "linux":
        docker_cmd = ["docker", "build"]
    else:
        result = subprocess.run(["docker", "buildx", "version"], capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(
                "Building a Docker image for non-Linux platforms requires 'docker-buildx'. "
                "Install docker-buildx and try again, or run the build on a Linux platform. "
                "Alternatively, use `installer_type: docker  # [linux]` in construct.yaml to "
                "generate the Dockerfile without building the image."
            )
        docker_arch = ARCH_MAP.get(arch)
        if docker_arch is None:
            raise RuntimeError(
                f"Unsupported architecture for Docker build: {arch}\n"
                f"Supported architectures: {', '.join(ARCH_MAP)}"
            )
        docker_cmd = ["docker", "buildx", "build", "--platform", f"linux/{docker_arch}", "--load"]

    image_name = info.get("docker_image_name", info["name"].lower())
    image_version = info.get("docker_image_version", info["version"].split("-")[0])
    tag = f"{image_name}:{image_version}"

    cmd = [*docker_cmd, "-t", tag, str(docker_dir)]

    logger.info("Building Docker image: '%s'", tag)
    subprocess.run(cmd, check=True)
    logger.info("Docker image built: '%s'", tag)

def cleanup(info: dict, docker_dir: Path) -> None:
    """Remove the Docker build context directory after building.

    Parameters
    ----------
    info: dict
        Constructor installer info dict.
    docker_dir: Path
        Path to the Docker directory containing the Dockerfile.

    """
    installer_path = Path(info["_outpath"])

    installer_path.unlink(missing_ok=True)
    docker_dir.joinpath(installer_path.name).unlink(missing_ok=True)
    logger.info("Removing installers from paths: %s, %s", installer_path, docker_dir.joinpath(installer_path.name))

    # TODO: Add option for agressive cleanup which would remove dockerfile if building is enabled.
    # shutil.rmtree(docker_dir)
    # logger.info("Cleaned up Docker build directory: '%s'", docker_dir)


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
    docker_dir = prepare_docker_context(info)
    generate_dockerfile(info, docker_dir)

    if info.get("docker_build"):
        build_image(info, docker_dir)

    cleanup(info, docker_dir)

    logger.info("Docker output complete. Docker directory: '%s'", docker_dir)
