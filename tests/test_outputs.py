from pathlib import Path

from constructor.build_outputs import dump_hash


def test_hash_dump(tmp_path):
    testfile = tmp_path / "test.txt"
    testfile.write_text("test string")
    testfile = tmp_path / "test2.txt"
    testfile.write_text("another test")
    expected = (
        "d5579c46dfcc7f18207013e65b44e4cb4e2c2298f4ac457ba8f82743f31e930b",
        "64320dd12e5c2caeac673b91454dac750c08ba333639d129671c2f58cb5d0ad1",
    )
    info = {
        "_outpath": [
            str(tmp_path / "test.txt"),
            str(tmp_path / "test2.txt"),
        ],
        "_output_dir": str(tmp_path),
    }
    outpath = dump_hash(info, algorithm="sha256")
    assert outpath == str(tmp_path / "hash.sha256")
    filecontent = Path(outpath).read_text()
    lines = filecontent.split("\n")
    for i in range(len(lines) - 1):
        filehash, filename = lines[i].split()
        assert filehash.strip() == expected[i]
        assert filename.strip() == Path(info["_outpath"][i]).name
