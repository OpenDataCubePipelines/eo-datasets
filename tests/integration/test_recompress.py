import tarfile
from pathlib import Path
from typing import List, Dict, Tuple

import pytest
from click.testing import CliRunner, Result

from eodatasets import verify
from eodatasets.scripts import recompress

this_folder = Path(__file__).parent
packaged_path: Path = this_folder.joinpath(
    'recompress_packed/USGS/L1/Landsat/C1/092_091/LT50920911991126',
    'LT05_L1GS_092091_19910506_20170126_01_T2.tar.gz'
)
unpackaged_path: Path = this_folder.joinpath(
    'recompress_unpackaged/USGS/L1/Landsat/C1/092_091/LT50920911991126'
)


@pytest.mark.parametrize(
    "input_path",
    [packaged_path, unpackaged_path],
    ids=('packaged', 'unpackaged')
)
def test_recompress_dataset(input_path: Path, tmp_path: Path):
    assert input_path.exists()

    output_base = tmp_path / 'out'

    _run_recompress(input_path, output_base)

    expected_output = (
            output_base /
            'L1/Landsat/C1/092_091/LT50920911991126' /
            'LT05_L1GS_092091_19910506_20170126_01_T2.tar'
    )

    # Pytest has better error messages for strings than Paths.
    all_output_files = [str(p) for p in output_base.rglob('*') if p.is_file()]

    assert len(all_output_files) == 1, \
        f"Expected one output tar file. Got: \n\t" + '\n\t'.join(all_output_files)
    assert all_output_files == [str(expected_output)]

    assert expected_output.exists(), \
        f"No output produced in expected location {expected_output}."

    # It should contain all of our files
    checksums, members = _get_checksums_members(expected_output)

    member_names = [m.name for m in members]

    # Note that MTL is first. We do this deliberately so it's quick to access.
    # The others are alphabetical, as with USGS tars.
    # (Not that it matters, but reprocessing stability is nice.)
    assert member_names == [
        'LT05_L1GS_092091_19910506_20170126_01_T2_MTL.txt',
        'LT05_L1GS_092091_19910506_20170126_01_T2_ANG.txt',
        'LT05_L1GS_092091_19910506_20170126_01_T2_B1.TIF',
        'LT05_L1GS_092091_19910506_20170126_01_T2_B2.TIF',
        'LT05_L1GS_092091_19910506_20170126_01_T2_B3.TIF',
        'LT05_L1GS_092091_19910506_20170126_01_T2_B4.TIF',
        'LT05_L1GS_092091_19910506_20170126_01_T2_B5.TIF',
        'LT05_L1GS_092091_19910506_20170126_01_T2_B6.TIF',
        'LT05_L1GS_092091_19910506_20170126_01_T2_B7.TIF',
        'LT05_L1GS_092091_19910506_20170126_01_T2_BQA.TIF',
        'README.GTF',
        'extras',
        'extras/example-file.txt',
        'package.sha1',
    ]

    member_sizes = {m.name: m.size for m in members}

    # Text files should be unchanged.
    assert member_sizes['LT05_L1GS_092091_19910506_20170126_01_T2_MTL.txt'] == 6693

    assert 'LT05_L1GS_092091_19910506_20170126_01_T2_MTL.txt' in checksums, "No MTL?"
    assert checksums[
               'LT05_L1GS_092091_19910506_20170126_01_T2_MTL.txt'
           ] == 'beb4d546dc5e2850b2f33384bfbc6cf15b724197'

    # Are they the expected number of bytes?
    assert member_sizes['package.sha1'] == 1010
    assert member_sizes['README.GTF'] == 8686
    assert member_sizes['LT05_L1GS_092091_19910506_20170126_01_T2_ANG.txt'] == 34884


def test_recompress_gap_mask_dataset(tmp_path: Path):
    input_path = this_folder.joinpath(
        'recompress_packed/USGS/L1/Landsat/C1/091_080/LE70910802008014',
        'LE07_L1GT_091080_20080114_20161231_01_T2.tar.gz'
    )
    assert input_path.exists()

    output_base = tmp_path / 'out'

    _run_recompress(input_path, output_base)

    expected_output = (
            output_base /
            'L1/Landsat/C1/091_080/LE70910802008014' /
            'LE07_L1GT_091080_20080114_20161231_01_T2.tar'
    )

    # Pytest has better error messages for strings than Paths.
    all_output_files = [str(p) for p in output_base.rglob('*') if p.is_file()]

    assert len(all_output_files) == 1, \
        f"Expected one output tar file. Got: \n\t" + '\n\t'.join(all_output_files)
    assert all_output_files == [str(expected_output)]

    assert expected_output.exists(), \
        f"No output produced in expected location {expected_output}."

    # It should contain all of our files
    checksums, members = _get_checksums_members(expected_output)

    member_names = [(m.name, f'{m.mode:o}') for m in members]

    # Note that MTL is first. We do this deliberately so it's quick to access.
    # The others are alphabetical, as with USGS tars.
    # (Not that it matters, but reprocessing stability is nice.)
    assert member_names == [
        ('LE07_L1GT_091080_20080114_20161231_01_T2_MTL.txt', '664'),
        ('LE07_L1GT_091080_20080114_20161231_01_T2_ANG.txt', '664'),
        ('LE07_L1GT_091080_20080114_20161231_01_T2_B1.TIF', '664'),
        ('LE07_L1GT_091080_20080114_20161231_01_T2_B2.TIF', '664'),
        ('LE07_L1GT_091080_20080114_20161231_01_T2_B3.TIF', '664'),
        ('LE07_L1GT_091080_20080114_20161231_01_T2_B4.TIF', '664'),
        ('LE07_L1GT_091080_20080114_20161231_01_T2_B5.TIF', '664'),
        ('LE07_L1GT_091080_20080114_20161231_01_T2_B6_VCID_1.TIF', '664'),
        ('LE07_L1GT_091080_20080114_20161231_01_T2_B6_VCID_2.TIF', '664'),
        ('LE07_L1GT_091080_20080114_20161231_01_T2_B7.TIF', '664'),
        ('LE07_L1GT_091080_20080114_20161231_01_T2_B8.TIF', '664'),
        ('LE07_L1GT_091080_20080114_20161231_01_T2_BQA.TIF', '664'),
        ('README.GTF', '664'),
        ('gap_mask', '775'),
        ('gap_mask/LE07_L1GT_091080_20080114_20161231_01_T2_GM_B1.TIF', '664'),
        ('gap_mask/LE07_L1GT_091080_20080114_20161231_01_T2_GM_B2.TIF', '664'),
        ('gap_mask/LE07_L1GT_091080_20080114_20161231_01_T2_GM_B3.TIF', '664'),
        ('gap_mask/LE07_L1GT_091080_20080114_20161231_01_T2_GM_B4.TIF', '664'),
        ('gap_mask/LE07_L1GT_091080_20080114_20161231_01_T2_GM_B5.TIF', '664'),
        ('gap_mask/LE07_L1GT_091080_20080114_20161231_01_T2_GM_B6_VCID_1.TIF', '664'),
        ('gap_mask/LE07_L1GT_091080_20080114_20161231_01_T2_GM_B6_VCID_2.TIF', '664'),
        ('gap_mask/LE07_L1GT_091080_20080114_20161231_01_T2_GM_B7.TIF', '664'),
        ('gap_mask/LE07_L1GT_091080_20080114_20161231_01_T2_GM_B8.TIF', '664'),
        ('package.sha1', '664'),
    ]

    ####
    # If packaging is rerun, the output should not be touched!
    # ie. skip if output exists.
    original_crc32 = verify.calculate_file_crc32(expected_output)
    original_inode = expected_output.stat().st_ino

    _run_recompress(input_path, output_base)

    new_crc32 = verify.calculate_file_crc32(expected_output)
    new_inode = expected_output.stat().st_ino
    assert original_crc32 == new_crc32, "Output file was modified on rerun of compress"
    assert original_inode == new_inode, "Output file was replaced on rerun of compress"


def test_recompress_dirty_dataset(tmp_path: Path):
    # We found some datasets that have been "expanded" and later retarred.
    # They have extra tifs and jpegs created from the bands.
    # The TIFs have compression and multiple bands, unlike USGS tifs.
    # We expect such tifs to be unmodified by this repackager.

    input_path = this_folder.joinpath(
        'recompress_packed/USGS/L1/Landsat/C1/091_075/LC80910752016348',
        'LC08_L1TP_091075_20161213_20170316_01_T2.tar.gz'
    )
    assert input_path.exists()

    output_base = tmp_path / 'out'

    _run_recompress(input_path, output_base)

    expected_output = (
            output_base /
            'L1/Landsat/C1/091_075/LC80910752016348' /
            'LC08_L1TP_091075_20161213_20170316_01_T2.tar'
    )

    # Pytest has better error messages for strings than Paths.
    all_output_files = [str(p) for p in output_base.rglob('*') if p.is_file()]

    assert len(all_output_files) == 1, \
        f"Expected one output tar file. Got: \n\t" + '\n\t'.join(all_output_files)
    assert all_output_files == [str(expected_output)]

    assert expected_output.exists(), \
        f"No output produced in expected location {expected_output}."

    checksums, members = _get_checksums_members(expected_output)

    assert checksums[
               'LC08_L1TP_091075_20161213_20170316_01_T2.tif'
           ] == '57cafe38c2f4f94cd15a05cfd918911889b8b03f', \
        "compressed tif has changed. It should be unmodified."

    member_names = [m.name for m in members]
    # Note that MTL is first. We do this deliberately so it's quick to access.
    # The others are alphabetical, as with USGS tars.
    # (Not that it matters, but reprocessing stability is nice.)
    print('\n'.join(member_names))
    assert member_names == [
        'LC08_L1TP_091075_20161213_20170316_01_T2_MTL.txt',
        'LC08_L1TP_091075_20161213_20170316_01_T2_ANG.txt',
        'LC08_L1TP_091075_20161213_20170316_01_T2_B10.TIF',
        'LC08_L1TP_091075_20161213_20170316_01_T2_B11.TIF',
        'LC08_L1TP_091075_20161213_20170316_01_T2_B1.TIF',
        'LC08_L1TP_091075_20161213_20170316_01_T2_B2.TIF',
        'LC08_L1TP_091075_20161213_20170316_01_T2_B3.TIF',
        'LC08_L1TP_091075_20161213_20170316_01_T2_B4.TIF',
        'LC08_L1TP_091075_20161213_20170316_01_T2_B5.TIF',
        'LC08_L1TP_091075_20161213_20170316_01_T2_B6.TIF',
        'LC08_L1TP_091075_20161213_20170316_01_T2_B7.TIF',
        'LC08_L1TP_091075_20161213_20170316_01_T2_B8.TIF',
        'LC08_L1TP_091075_20161213_20170316_01_T2_B9.TIF',
        'LC08_L1TP_091075_20161213_20170316_01_T2_BQA.TIF',
        'LC08_L1TP_091075_20161213_20170316_01_T2.IMD',
        'LC08_L1TP_091075_20161213_20170316_01_T2.jpeg',
        'LC08_L1TP_091075_20161213_20170316_01_T2_QB.jpeg',
        'LC08_L1TP_091075_20161213_20170316_01_T2_QB.tif',
        'LC08_L1TP_091075_20161213_20170316_01_T2.tif',
        'LC08_L1TP_091075_20161213_20170316_01_T2.tif.msk',
        'LC08_L1TP_091075_20161213_20170316_01_T2_TIR.jpeg',
        'LC08_L1TP_091075_20161213_20170316_01_T2_TIR.tif',
        'package.sha1',
    ]


def test_run_with_corrupt_data(tmp_path: Path):
    output_path = tmp_path / 'out'
    output_path.mkdir()

    # Recompress expects the dataset in a "USGS" folder structure.
    # Should bail otherwise rather than write data to unexpected locations!
    # (we may expand this in the future, but being safe for now)
    non_usgs_path = tmp_path / packaged_path.name
    non_usgs_path.symlink_to(packaged_path)

    with pytest.raises(ValueError, match="Expected AODH input path structure"):
        _run_recompress(
            non_usgs_path,
            output_path,
        )


def _run_recompress(input_path, output_base, expected_return=0):
    res: Result = CliRunner().invoke(
        recompress.main,
        (
            '--output-base',
            str(output_base),
            # Out test data is smaller than the default block size.
            '--block-size', '32',
            str(input_path),
        ),
        catch_exceptions=False,
    )
    if expected_return is not None:
        assert res.exit_code == expected_return, res.output
    return res


def _get_checksums_members(out_tar: Path) -> Tuple[Dict, List[tarfile.TarInfo]]:
    with tarfile.open(out_tar, 'r') as tar:
        members: List[tarfile.TarInfo] = tar.getmembers()

        # Checksum is last (can be calculated while streaming)
        checksum_member = members[-1]
        assert checksum_member.name == 'package.sha1'
        checksums = {}
        for line in tar.extractfile(checksum_member).readlines():
            chksum, path = line.decode('utf-8').split('\t')
            path = path.strip()
            assert path not in checksums, f"Path is repeated in checksum file: {path}"
            checksums[path] = chksum
    return checksums, members


def test_calculate_out_path(tmp_path: Path):
    out_base = tmp_path / 'out'

    # When input is a tar file, use the same name on output.
    path = Path('/test/in/l1-data/USGS/L1/C1/092_091/LT50920911991126/'
                'LT05_L1GS_092091_19910506_20170126_01_T2.tar.gz')
    assert_path_eq(
        out_base.joinpath(
            'L1/C1/092_091/LT50920911991126/'
            'LT05_L1GS_092091_19910506_20170126_01_T2.tar'
        ),
        recompress._output_tar_path(out_base, path),
    )

    # When input is a directory, use the MTL file's name for the output.
    path = tmp_path / 'USGS/L1/092_091/LT50920911991126'
    path.mkdir(parents=True)
    mtl = path / 'LT05_L1GS_092091_19910506_20170126_01_T2_MTL.txt'
    mtl.write_text('fake mtl')
    assert_path_eq(
        out_base.joinpath(
            'L1/092_091/LT50920911991126/'
            'LT05_L1GS_092091_19910506_20170126_01_T2.tar'
        ),
        recompress._output_tar_path_from_directory(out_base, path),
    )


def assert_path_eq(p1: Path, p2: Path):
    """Assert two pathlib paths are equal, with reasonable error output."""
    __tracebackhide__ = True
    # Pytest's error messages are far better for strings than Paths.
    # It shows you the difference between them.
    s1, s2 = str(p1), str(p2)
    # And we use extra s1/s2 variables so that pytest doesn't print the
    # expression "str()" as part of its output.
    assert s1 == s2
