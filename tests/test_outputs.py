from pathlib import Path

from constructor.build_outputs import dump_hash


def test_hash_dump(tmp_path):
    testfile = tmp_path / "test.txt"
    testfile.write_text("test string\n")
    testfile = tmp_path / "test2.txt"
    testfile.write_text("another test\n")
    expected = (
        "37d2046a395cbfcb2712ff5c96a727b1966876080047c56717009dbbc235f566",
        "60fa80b948a0acc557a6ba7523f4040a7b452736723df20f118d0aacb5c1901b",
    )
    info = {
        "_outpath": [
            str(tmp_path / "test.txt"),
            str(tmp_path / "test2.txt"),
        ],
    }
    outpath = dump_hash(info, algorithm="sha256")
    assert outpath == str(f"{testfile}.sha256")
    filecontent = Path(outpath).read_text()
    filehash, filename = filecontent.split()
    assert filehash.strip() == expected
    assert filename.strip() == testfile.name
