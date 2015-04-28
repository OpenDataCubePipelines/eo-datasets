# coding=utf-8
from __future__ import absolute_import
import logging
import re
import string

from pathlib import Path
from eodatasets.metadata import mdf, mtl, adsfolder, rccfile, passinfo, image as md_image
from eodatasets import type as ptype, metadata


_LOG = logging.getLogger(__name__)


def find_file(path, file_pattern):
    # Crude but effective. TODO: multiple/no result handling.
    return next(path.glob(file_pattern))


class DatasetDriver(object):
    def get_id(self):
        """
        A short identifier for this type of dataset.

        eg. 'ortho'

        :rtype: str
        """
        raise NotImplementedError()

    def fill_metadata(self, dataset, path):
        """
        Populate the given dataset metadata from the path.

        :type dataset: ptype.DatasetMetadata
        :type path: Path
        """
        raise NotImplementedError()

    def get_ga_label(self, dataset):
        """
        Generate the GA Label ("dataset id") for a dataset.
        :type dataset:  ptype.DatasetMetadata
        :rtype: str
        """
        raise NotImplementedError()

    def expected_source(self):
        """
        Expected source dataset (driver).
        :rtype: DatasetDriver
        """
        raise NotImplementedError()

    def file_is_pertinent(self, file_path):
        """
        Should the given file be included in this dataset package?
        :type file_path: Path
        :rtype: bool
        """
        return True

    def fill_provenance(self, provenance):
        """
        Fill any provenance for software used to produce the datset.

        :type provenance: eodatasets.provenance.SoftwareProvenance
        :rtype: eodatasets.provenance.SoftwareProvenance
        """
        raise NotImplementedError()

    def browse_image_bands(self, d):
        """
        Band ids for for an rgb browse image.
        :type d: ptype.DatasetMetadata
        :rtype (str, str, str)
        """
        # Defaults for satellites. Different products may override this.
        # These values come from the ARG25 spec.
        _SATELLITE_BROWSE_BANDS = {
            'LANDSAT_5': ('7', '4', '1'),
            'LANDSAT_7': ('7', '4', '1'),
            'LANDSAT_8': ('7', '5', '2'),
        }
        browse_bands = _SATELLITE_BROWSE_BANDS.get(d.platform.code)
        if not browse_bands:
            raise ValueError('Unknown browse bands for satellite %s' % d.platform.code)

        return browse_bands


def get_groundstation_code(gsi):
    """
    Translate a GSI code into an EODS domain code.

    Domain codes are used in dataset_ids.

    It will also translate common gsi aliases if needed.

    :type gsi: str
    :rtype: str

    >>> get_groundstation_code('ASA')
    '002'
    >>> get_groundstation_code('HOA')
    '011'
    >>> # Aliases should work too.
    >>> get_groundstation_code('ALSP')
    '002'
    """
    groundstation = metadata.get_groundstation(gsi)
    if not groundstation:
        return None

    return groundstation.eods_domain_code


def _format_path_row(start_point, end_point=None):
    """
    Format path-row for display in a dataset id.

    :type start_point: ptype.Point or None
    :type end_point: ptype.Point or None
    :rtype: (str, str)

    >>> _format_path_row(ptype.Point(78, 132))
    ('078', '132')
    >>> _format_path_row(ptype.Point(12, 4))
    ('012', '004')
    >>> # Show the range of rows
    >>> _format_path_row(ptype.Point(78, 78), end_point=ptype.Point(78, 80))
    ('078', '078-080')
    >>> # Identical rows: don't show a range
    >>> _format_path_row(ptype.Point(78, 132), end_point=ptype.Point(78, 132))
    ('078', '132')
    >>> # This is odd behaviour, but we're doing it for consistency with the old codebases.
    >>> # Lack of path/rows are represented as single-digit zeros.
    >>> _format_path_row(None)
    ('0', '0')
    >>> _format_path_row(ptype.Point(None, None))
    ('0', '0')
    """
    if start_point is None:
        return '0', '0'

    def _format_val(val):
        if val:
            return '%03d' % val
        else:
            return '0'

    path = _format_val(start_point.x)
    rows = _format_val(start_point.y)

    # Add ending row if different.
    if end_point and start_point.y != end_point.y:
        rows += '-' + _format_val(end_point.y)

    return path, rows


def _get_process_code(dataset):
    """

    :type dataset: ptype.DatasetMetadata
    :return:
    """
    level = dataset.product_level

    if level:
        level = level.upper()

    orientation = None
    if dataset.grid_spatial and dataset.grid_spatial.projection:
        orientation = dataset.grid_spatial.projection.orientation

    if level == 'L1T':
        return 'OTH', 'P51'

    if orientation == 'NORTH_UP':
        if level == 'L1G':
            return 'SYS', 'P31'
        if level == 'L1GT':
            return 'OTH', 'P41'

    # Path
    if orientation in ('NOMINAL', 'NOM'):
        return 'SYS', 'P11'

    if dataset.ga_level == 'P00':
        return 'RAW', 'P00'

    _LOG.warn('No process code mapped for level/orientation: %r, %r', level, orientation)
    return None, None


def _fill_dataset_label(dataset, format_str):
    def _get_short_satellite_code(dataset_):
        assert dataset_.platform.code.startswith('LANDSAT_')
        sat_number = 'LS' + dataset_.platform.code.split('_')[-1]
        return sat_number

    path, row = _format_path_row(
        start_point=dataset.image.satellite_ref_point_start if dataset.image else None,
        end_point=dataset.image.satellite_ref_point_end if dataset.image else None
    )

    def _format_dt(d):
        if not d:
            return None
        return d.strftime("%Y%m%dT%H%M%S")

    def _format_day(dataset_):
        day = (dataset_.extent and dataset_.extent.center_dt) or \
              (dataset_.acquisition and dataset_.acquisition.aos)
        return day.strftime('%Y%m%d')

    level, ga_level = _get_process_code(dataset)

    station_code = None
    start = None
    end = None
    if dataset.acquisition:
        if dataset.acquisition.groundstation:
            station_code = get_groundstation_code(dataset.acquisition.groundstation.code)
        if dataset.acquisition.aos:
            start = _format_dt(dataset.acquisition.aos)
        if dataset.acquisition.los:
            end = _format_dt(dataset.acquisition.los)

    formatted_params = {
        'satnumber': _get_short_satellite_code(dataset),
        'sensor': _remove_chars(string.punctuation, dataset.instrument.name),
        'format': dataset.format_.name.upper(),
        'level': level,
        'galevel': ga_level,
        'usgsid': dataset.usgs_dataset_id,
        'path': path,
        'rows': row,
        'stationcode': station_code,
        'startdt': start,
        'enddt': end,
        'day': _format_day(dataset)
    }
    return format_str.format(**formatted_params)


def _remove_chars(chars, s):
    """

    :param chars: string of characters to remove.
    :param s: input string
    :rtype: str

    >>> _remove_chars(string.punctuation, 'OLI_TIRS+')
    'OLITIRS'
    >>> _remove_chars('_', 'A_B_C')
    'ABC'
    >>> _remove_chars(string.punctuation, None)
    """
    if not s:
        return s
    return re.sub('[' + re.escape(''.join(chars)) + ']', '', s)


class RawDriver(DatasetDriver):
    def get_id(self):
        return 'raw'

    def expected_source(self):
        # Raw dataset has no source.
        return None

    def get_ga_label(self, dataset):
        """
        :type dataset: ptype.DatasetMetadata
        :rtype: str
        """
        # Examples for each Landsat raw:
        # 'LS8_OLITIRS_STD-MDF_P00_LC81160740742015089ASA00_116_074-084_20150330T022553Z20150330T022657'
        # 'LS7_ETM_STD-RCC_P00_L7ET2005007020028ASA123_0_0_20050107T020028Z20050107T020719'
        # 'LS5_TM_STD-RCC_P00_L5TB2005152015110ASA111_0_0_20050601T015110Z20050107T020719'

        return _fill_dataset_label(
            dataset,
            '{satnumber}_{sensor}_STD-{format}_P00_{usgsid}_{path}_{rows}_{startdt}Z{enddt}'
        )

    def fill_metadata(self, dataset, path):
        dataset = adsfolder.extract_md(dataset, path)
        dataset = rccfile.extract_md(dataset, path)
        dataset = mdf.extract_md(dataset, path)
        dataset = passinfo.extract_md(dataset, path)

        # TODO: Antenna coords for groundstation? Heading?
        # TODO: Bands? (or eg. I/Q files?)
        return dataset


class OrthoDriver(DatasetDriver):
    def get_id(self):
        return 'ortho'

    def expected_source(self):
        return RawDriver()

    def fill_metadata(self, d, package_directory):
        """
        :type package_directory: Path
        :type d: ptype.DatasetMetadata
        :return:
        """
        mtl_path = find_file(package_directory, '*_MTL.txt')
        _LOG.info('Reading MTL %r', mtl_path)

        d = mtl.populate_from_mtl(d, mtl_path)

        return d

    def get_ga_label(self, dataset):
        # Examples:
        #     "LS8_OLITIRS_OTH_P41_GALPGS01-002_101_078_20141012"
        #     "LS7_ETM_SYS_P31_GALPGS01-002_114_73_20050107"
        #     "LS5_TM_OTH_P51_GALPGS01-002_113_063_20050601"

        return _fill_dataset_label(
            dataset,
            '{satnumber}_{sensor}_{level}_{galevel}_GALPGS01-{stationcode}_{path}_{rows}_{day}'
        )


class NbarDriver(DatasetDriver):
    def __init__(self, subset_name):
        # Subset is typically "brdf" or "terrain" -- which NBAR portion to package.
        self.subset_name = subset_name

    def get_id(self):
        return 'nbar_{}'.format(self.subset_name)

    def expected_source(self):
        return OrthoDriver()

    def file_is_pertinent(self, file_path):
        return file_path.name.startswith('reflectance_{}'.format(self.subset_name))

    @staticmethod
    def _find_nbar_bands(package_directory):
        bands = {}
        for band in Path(package_directory).glob('*.tif'):
            band_number = band.stem.split('_')[-1]
            bands[band_number] = ptype.BandMetadata(path=band.absolute(), number=band_number)
        return bands

    def get_ga_label(self, dataset):
        # Exmaple: LS8_OLITIRS_NBAR_P51_GALPGS01-032_090_085_20140115
        # TODO
        return None
        # return _fill_dataset_label(
        #     dataset,
        #     '{satnumber}_{sensor}_NBAR_{galevel}_GALPGS01-{stationcode}_{path}_{rows}_{day}'
        # )

    def fill_metadata(self, dataset, path):
        """
        :type dataset: ptype.DatasetMetadata
        :type path: Path
        :rtype: ptype.DatasetMetadata
        """
        # TODO: Detect
        dataset.platform = ptype.PlatformMetadata(code='LANDSAT_8')
        dataset.instrument = ptype.InstrumentMetadata(name='OLI_TIRS')
        # d.product_type
        if not dataset.image:
            dataset.image = ptype.ImageMetadata(bands={})

        dataset.image.bands.update(self._find_nbar_bands(path))

        dataset.format_ = ptype.FormatMetadata('GeoTIFF')

        md_image.populate_from_image_metadata(dataset)
        return dataset


PACKAGE_DRIVERS = {
    'raw': RawDriver(),
    'ortho': OrthoDriver(),
    'nbar_brdf': NbarDriver('brdf'),
    'nbar_terrain': NbarDriver('terrain')
}
