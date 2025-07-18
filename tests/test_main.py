from textwrap import dedent

from constructor.main import main


def test_dry_run(tmp_path):
    inputfile = dedent(
        """
        name: test_schema_validation
        version: X
        installer_type: all
        channels:
          - http://repo.anaconda.com/pkgs/main/
        specs:
          - ca-certificates
        """
    )
    (tmp_path / "construct.yaml").write_text(inputfile)
    main([str(tmp_path), "--dry-run"])
