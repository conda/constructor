import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from jinja2 import Template

from . import __version__

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).parent / "dockerfile_template.tmpl"

def prepare_docker_context(info: dict) -> tuple[Path, Path]:
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

    docker_base_image = info.get("docker_base_image")
    if not docker_base_image:
        raise RuntimeError(
            "Base image for Dockerfile not specified. "
            "Please set 'docker_base_image' in construct.yaml, e.g.:\n"
            " docker_base_image: debian:13.4-slim@sha256:4ffb3a1511099754cddc70eb1b12e50ffdb67619aa0ab6c13fcd800a78ef7c7a\n"
        )

    rendered_dockerfile = docker_template.render(
        constructor_version=__version__,
        base_image=docker_base_image,
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
    Currently only supports building on linux/arm64 and linux/amd64.

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

    if osname == "linux" and arch in ("amd64", "arm64"):
       logger.info(f"Building Docker image on supported platform: {info['_platform']}")
    elif osname == "linux" and arch not in ("amd64", "arm64"):
        logger.warning(
            f"Building Docker images on linux/{arch} is not fully supported. "
            "Tread carefully as the resulting image may not work as expected. "
            "The resulting image may fail due to architecture incompatibility. "
    else:
        raise RuntimeError(
            f"Unsupported architecture for Docker build: {info['_platform']}\n"
            "Currently, building Docker images is only supported on linux/amd64 and linux/arm64 platforms. "
            "Please run the build on a Linux platform or alternatively, "
            "use `installer_type: docker  # [linux]` in construct.yaml to "
            "generate the Dockerfile without building the image. Then you can build the Docker image manually using 'docker buildx' on non-Linux platforms. "
        )

    image_name = info.get("docker_image_name", info["name"].lower())
    image_version = info.get("docker_image_version", info["version"].split("-")[0])
    tag = f"{image_name}:{image_version}"

    cmd = ["docker", "build", "-t", tag, str(docker_dir)]

    logger.info("Building Docker image: '%s'", tag)
    subprocess.run(cmd, check=True)
    logger.info("Docker image built: '%s'", tag)

def cleanup(docker_dir: Path, info: dict) -> None:
    """Copy final artifacts to output directory and clean up temporary files.

    Parameters
    ----------
    docker_dir: Path
        Final output directory containing the Dockerfile. (``<_output_dir>/docker``)
    info: dict
        Constructor installer info dict.

    """
    if build_image == success:
        installer_path.unlink(missing_ok=True)
        logger.info("Removing installer from paths: %s, %s", installer_path, docker_dir.joinpath(installer_path.name))

    # TODO: Add option for agressive cleanup which would remove dockerfile and sh installer if building is enabled.


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
