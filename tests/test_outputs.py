from contextlib import nullcontext
from pathlib import Path

import pytest

from constructor.build_outputs import dump_hash

TEST_FILES = {
    "test.txt": {
        "content": "test string",
        "sha256": "d5579c46dfcc7f18207013e65b44e4cb4e2c2298f4ac457ba8f82743f31e930b",
        "md5": "6f8db599de986fab7a21625b7916589c",
    },
    "test2.txt": {
        "content": "another test",
        "sha256": "64320dd12e5c2caeac673b91454dac750c08ba333639d129671c2f58cb5d0ad1",
        "md5": "5e8862cd73694287ff341e75c95e3c6a",
    },
}


@pytest.mark.parametrize(
    "algorithm,context",
    (
        pytest.param("bad algorithm", pytest.raises(ValueError), id="invalid algorithm"),
        pytest.param("sha256", nullcontext(), id="string"),
        pytest.param(["sha256", "md5"], nullcontext(), id="list"),
    ),

)
def test_hash_dump(tmp_path, algorithm, context):
    info = {
        "_outpath": []
    }
    for file, data in TEST_FILES.items():
        testfile = tmp_path / file
        testfile.write_text(data["content"])
        info["_outpath"].append(str(testfile))
    with context:
        dump_hash(info, algorithm=algorithm)
        if isinstance(algorithm, str):
            algorithm = [algorithm]
        for file in info["_outpath"]:
            for algo in algorithm:
                hashfile = Path(f"{file}.{algo}")
                assert hashfile.exists()
                filehash, filename = hashfile.read_text().strip().split()
                assert filename == Path(file).name
                assert filehash == TEST_FILES[filename][algo]
