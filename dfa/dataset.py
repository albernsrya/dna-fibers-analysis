"""
Example dataset management of the DNA fiber analysis package.

Use this module to decompress, load and use the example dataset.
"""
import zipfile
import os

import pandas as pd
from skimage import io
import numpy as np

from dfa import utilities as ut


class Dataset:
    """
    This class is meant to manage example dataset for DFA project.
    """
    def __init__(self, archive, storing_path='/tmp', force_decompress=False,
                 shuffle=True):
        """
        Constructor.

        The dataset archive is first decompressed in the storing path. If the
        decompressed path already exists (for instance when the archive has
        already been decompressed there, when it has already been loaded), it
        is not decompressed again, until the force_decompress flag is set to
        True.

        Parameters
        ----------
        archive : str
            Path to dataset archive.

        storing_path : str
            Path used to store the decompressed dataset.

        force_decompress : bool
            Use this flag to force the decompression.

        shuffle : bool
            If True, the dataset is shuffled, it is not otherwise.
        """
        self.archive = archive
        self.storing_path = storing_path
        self.dataset_path = os.path.join(storing_path,
                                         os.path.splitext(
                                             os.path.basename(archive))[0])

        if force_decompress or not os.path.exists(self.dataset_path):
            self._decompress()

        self.summary = pd.read_csv(
            os.path.join(self.dataset_path, 'summary.csv'),
            index_col=list(range(3))).sort_index()

        tmp = self.summary.copy()
        if shuffle:
            tmp = tmp.sample(frac=1)

        self.image_index = tmp.index.droplevel('fiber').unique()
        self.profile_index = tmp.index.unique()

        self._n_image = 0
        self._n_profile = 0

    def _decompress(self):
        """
        Utility method used to decompress the dataset at the correct path.
        """
        with zipfile.ZipFile(self.archive) as zipfiles:
            zipfiles.extractall(path=self.storing_path)

    def next_batch(self, index, n, mapping, batch_size=None):
        """
        Get the next batch of the given size as a generator.

        Parameters
        ----------
        index : str
            Name of the index used for selecting batches.

        n : str
            Name of the current offset of reading

        mapping : (int,) -> T
            Function that maps an index to elements to return.

        batch_size : 0 < int | None
            Size of the next batch. When None, the batch size is set to the
            size of the dataset (default behaviour).

        Yields
        ------
        T
            The next batch.
        """
        if getattr(self, n) < getattr(self, index).size:
            if batch_size is None:
                batch_size = getattr(self, index).size

            begin = getattr(self, n)
            end = getattr(self, n) + batch_size
            setattr(self, n, end)

            for index in getattr(self, index)[begin:end]:
                yield mapping(index)
        else:
            return None

    def next_image_batch(self, batch_size=None):
        """
        Get the next image batch of the given size as a generator.

        Parameters
        ----------
        batch_size : strictly positive int or None
            Size of the next batch. When None, the batch size is set to the
            size of the dataset (default behaviour).

        Yields
        ------
        (int, numpy.ndarray, List[numpy.ndarray])
            The next batch (index, image, fibers).
        """
        return self.next_batch(
            batch_size=batch_size, index='image_index', n='_n_image',
            mapping=lambda index: (
                index,
                io.imread(os.path.join(self.dataset_path, 'input',
                                       '{}-{}.tif'.format(*index))),
                ut.read_points_from_imagej_zip(
                    os.path.join(self.dataset_path, 'fibers',
                                 '{}-{}.zip'.format(*index)))))

    def next_profile_batch(self, batch_size=None):
        """
        Get the next profile batch of the given size as a generator.

        Parameters
        ----------
        batch_size : strictly positive int or None
            Size of the next batch. When None, the batch size is set to the
            size of the dataset (default behaviour).

        Returns
        -------
        generator
            Tuples of the next batch as a generator. The tuples contain the
            index, the profiles and the data view to the ground truth.

        Yields
        ------
        (int, numpy.ndarray, pandas.DataFrame)
            The next batch (index, profiles, analysis).
        """
        return self.next_batch(
            batch_size=batch_size, index='profile_index', n='_n_profile',
            mapping=lambda index: (
                index,
                np.loadtxt(os.path.join(
                    self.dataset_path, 'profiles',
                    '{}-{}-Profiles #{}.csv'.format(*index)),
                    delimiter=',', skiprows=1, usecols=(0, 1, 2)),
                self.summary.ix[index]))

    @staticmethod
    def _save(summary, output_path, images_path, fibers_path, profiles_path):
        """
        Save dataset defined by input as zip file to given path.

        Parameters
        ----------
        summary : pandas.DataFrame
            Data frame used to select files belonging to dataset.

        output_path : str
            Path to output file (the zip file containing dataset).

        images_path : str
            Path to the images.

        fibers_path : str
            Path to the fibers.

        profiles_path : str
            Path to the profiles.
        """
        with zipfile.ZipFile(output_path, mode='w',
                             compression=zipfile.ZIP_DEFLATED) as archive:
            for ix in summary.index.droplevel('fiber').unique():
                name = '-'.join([str(e) for e in ix])

                archive.write(
                    filename=os.path.join(images_path,
                                          '{}.tif'.format(name)),
                    arcname=os.path.join(os.path.basename(images_path),
                                         '{}.tif'.format(name)))
                archive.write(
                    filename=os.path.join(fibers_path,
                                          '{}.zip'.format(name)),
                    arcname=os.path.join(os.path.basename(fibers_path),
                                         '{}.zip'.format(name)))

            for ix in summary.index.unique():
                name = '{}{}{}.csv'.format(
                    '-'.join([str(e) for e in ix[:-1]]),
                    ut.fiber_indicator,
                    ix[-1])

                archive.write(
                    filename=os.path.join(profiles_path, name),
                    arcname=os.path.join(os.path.basename(profiles_path), name))

    def save(self, path):
        """
        Save dataset as zip file to given path.

        Parameters
        ----------
        path : str
            Path of the zip file in which the dataset will be saved.
        """
        Dataset._save(self.summary, path,
                      os.path.join(self.dataset_path, 'images'),
                      os.path.join(self.dataset_path, 'fibers'),
                      os.path.join(self.dataset_path, 'profiles'))

    @staticmethod
    def create(summary_path, images_path, fibers_path, profiles_path,
               output_path):
        """
        Create a new dataset from paths to data.

        The summary is important since it is red to search the corresponding
        images, fibers and profiles in their respective paths.

        Parameters
        ----------
        summary_path : str
            Path to detailed analysis of the dataset.

        images_path : str
            Path to the images.

        fibers_path : str
            Path to the fibers.

        profiles_path : str
            Path to the profiles.

        output_path : str
            Path to output file (the zip file containing dataset).
        """
        summary = pd.read_csv(summary_path,
                              index_col=['experiment', 'image', 'fiber'])
        Dataset._save(summary, output_path, images_path,
                      fibers_path, profiles_path)
