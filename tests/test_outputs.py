from pathlib import Path

import pytest

from constructor.build_outputs import dump_hash


def test_hash_dump(tmp_path):
    testfile = tmp_path / "test.txt"
    testfile.write_text("test string")
    testfile = tmp_path / "test2.txt"
    testfile.write_text("another test")
    expected = {
        "sha256": (
            "d5579c46dfcc7f18207013e65b44e4cb4e2c2298f4ac457ba8f82743f31e930b",
            "64320dd12e5c2caeac673b91454dac750c08ba333639d129671c2f58cb5d0ad1",
        ),
        "md5": (
            "6f8db599de986fab7a21625b7916589c",
            "5e8862cd73694287ff341e75c95e3c6a",
        ),
    }
    info = {
        "_outpath": [
            str(tmp_path / "test.txt"),
            str(tmp_path / "test2.txt"),
        ]
    }
    with pytest.raises(ValueError):
        dump_hash(info, algorithm="bad_algorithm")
    dump_hash(info, algorithm=["sha256", "md5"])
    for f, file in enumerate(info["_outpath"]):
        for algorithm in expected:
            hashfile = Path(f"{file}.{algorithm}")
            assert hashfile.exists()
            filehash, filename = hashfile.read_text().strip().split()
            assert filehash == expected[algorithm][f]
            assert filename == Path(file).name
