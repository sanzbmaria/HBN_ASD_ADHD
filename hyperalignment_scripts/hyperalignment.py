import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from typing import List, Tuple, Optional, Union
from scipy.spatial.distance import cdist

class Hyperalignment(BaseEstimator, TransformerMixin):
    """
    Hyperalignment transformer that follows scikit-learn's API conventions.
    
    Parameters
    ----------
    n_iter : int, default=10
        Maximum number of iterations for hyperalignment optimization.
    
    scaling : bool, default=True
        Whether to apply scaling during Procrustes transformations.
    
    convergence_threshold : float, default=0.1
        Early stopping threshold for mean disparity between aligned datasets.
    
    verbose : bool, default=False
        If True, print progress during iterations.
    
    Attributes
    ----------
    transformations : list
        List of transformation matrices for each dataset.
    
    template : ndarray
        Common template space derived from training data.
    
    n_features_in : int
        Number of features in the input datasets.
        
    n_features_target: int
    
    aligned_data : list
        List of datasets aligned to the common space.
    
    n_iterations_ : int
        Number of iterations performed during training.
    """
    
    def __init__(self, n_iterations=10, scaling=True, center_only=True, convergence_threshold=0.001, n_features_target=0, verbose=False): 
        self.n_iterations = n_iterations
        self.scaling = scaling
        self.convergence_threshold = convergence_threshold
        self.verbose = verbose
        self.training_data = None
        self.n_features_target = n_features_target
        self.center_only = center_only
    
    def _normalize_data(self, X: np.ndarray) -> np.ndarray:
        """
        Normalize data by centering and scaling.
        
        Parameters
        ----------
        X : ndarray
            Input data matrix.
            
        Returns
        -------
        ndarray
            Normalized data matrix.
        """
        X -= np.mean(X, axis=0)
        norm = np.linalg.norm(X)
        if norm == 0: 
            raise ValueError("input matrix must have >1 unique points")
        if self.center_only:
            return X
        return  X / norm
    
    def _disparity(self, M1: np.ndarray, M2: np.ndarray) -> float:
        """
        Calculate squared Euclidean distance between two matrices.
        
        Parameters
        ----------
        M1 : ndarray
            First data matrix.
        M2 : ndarray
            Second data matrix.
            
        Returns
        -------
        float
            Sum of squared differences between matrices.
        """
        return np.sum(np.square(M1 - M2))
    
    def _procrustes(self, source: np.ndarray, target: np.ndarray, 
                   reduction: bool = False, scaling: Optional[bool] = None) -> Tuple:
        """
        Perform Procrustes transformation to align source to target.
        
        Parameters
        ----------
        source : ndarray
            Source data matrix to be aligned.
        target : ndarray
            Target data matrix to align to.
        reduction : bool, default=False
            If True, reduce dimensions if source and target have different numbers of features.
        scaling : bool, optional
            Whether to apply scaling. If None, use self.scaling.
            
        Returns
        -------
        tuple
            (R, aligned_source, disparity, scale)
            - R: Transformation matrix
            - aligned_source: Transformed source data
            - disparity: Measure of difference between aligned source and target
            - scale: Scaling factor applied
        """
        if scaling is None: scaling = self.scaling
            
        n_features_source = source.shape[-1]
        n_features_target = target.shape[-1]
        
        # normalize data
        target_norm = self._normalize_data(target)
        source_norm = self._normalize_data(source)
        scale = 1.0
        
        # Account for lower dimensions
        if n_features_source > n_features_target:
            reduction = True
            temp = np.zeros_like(source)
            temp[:, :n_features_target] = target_norm
            target_norm = temp
        
        # calculate optimal rotation
        U, s, vt = np.linalg.svd((target_norm.T @ np.conjugate(source_norm)).T)
        R = U @ vt
        if reduction:
            # select only relevant dimensions of the transformation
            R = R[:n_features_source, :n_features_target]
            target_norm = target_norm[:,:n_features_target]
            s=s[:n_features_target]
            
        
        if scaling:
            # scale by the sum of the singular values
            scale = s.sum()
        
        R *= scale
        
        # Apply transformation
        new_source = source_norm @ R
        
        # Check if overflow
        if np.isinf(np.linalg.norm(new_source)):
            return
        
        # Measure dissimilarity
        disp = self._disparity(target_norm, new_source)
        
        return R, new_source, disp, scale
    
    def _create_initial_template(self) -> np.ndarray:
        """
        Create initial template from a list of datasets.
        
        Parameters
        ----------
        datasets : list of ndarray
            List of datasets to create a template from.
            
        Returns
        -------
        ndarray
            Initial template for alignment.
        """
        # Initialize to the first just for now
        for i, x in enumerate(self.training_data):
            if i == 0:
                # use first data as template
                template = np.copy(x)
            else:
                try:
                    _, aligned, _, _ = self._procrustes(template / i, x)
                except:
                    return np.array([0])
                template += aligned
                
        template /= len(self.training_data)
        return template
    
    def _create_level2_template(self, datasets: List[np.ndarray], 
                               template_prev: np.ndarray) -> np.ndarray:
        """
        Create improved template by aligning datasets to previous template.
        
        Parameters
        ----------
        datasets : list of ndarray
            List of datasets to align.
        template_prev : ndarray
            Previous template to align to.
            
        Returns
        -------
        ndarray
            Improved template for alignment.
        """
        new_template = np.zeros_like(template_prev)
        
        for x in datasets:
            _, aligned, _, _ = self._procrustes(template_prev, x)
            new_template += aligned
        
        new_template /= len(datasets)
        return new_template
    
    def fit(self, X: List[np.ndarray], y=None) -> 'Hyperalignment':
        """
        Fit the hyperalignment model.
        
        Parameters
        ----------
        X : list of ndarray
            List of datasets to align, where each dataset is a 2D array of shape
            (n_samples, n_features). All datasets should have the same number of features and samples.
        y : ignored, present for API consistency.
            
        Returns
        -------
        self : Hyperalignment
            Returns fitted model.
        """
        if not (isinstance(X, np.ndarray) and X.ndim == 3 or isinstance(X, list)):
            raise ValueError("Input should be a 3D array or list of 2D arrays")
        
        if len(X) < 2:
            raise ValueError("At least two datasets are required for hyperalignment")
        
        # Store number of features
        self.n_features_in = X[0].shape[1]
        self.training_data = X
        reduction = False
        if self.n_features_target == 0: 
            self.n_features_target = self.n_features_in
           
        if self.n_features_target < self.n_features_in:
            reduction = True
            
            
        # Check all datasets have the same number of features
        if not all(x.shape[1] == self.n_features_in for x in X):
            raise ValueError("All datasets must have the same number of features")
        
        # Create the initial template
        template = self._create_initial_template()
        if template.ndim == 1:
            if self.verbose: print(f"Normalizing data...")
            self.center_only = False
            template = self._create_initial_template()

         # Initialize as the training data
        aligned = X.copy()
        
        # Initialize as empty
        transformations = None
        # Go through iterations
        for i in range(self.n_iterations):
            template = self._create_level2_template(aligned, template)
            # template = self._normalize_data(template)
            scales, disps, aligned1, transformations1 = [], [], [], []
            for src in aligned:
                R, N, d, s = self._procrustes(src, template, scaling=self.scaling)
                scales.append(s)
                disps.append(d)
                aligned1.append(N)
                transformations1.append(R)
            
            if self.verbose:
                print(f'Iteration {i+1}, disparity={np.mean(disps):.4f}')
            
            if np.mean(disps) < 0.1:
                if self.verbose: print(f'breaking on iter {i}, disp={np.mean(disps):04f}')
                break
                
            aligned = aligned1
            transformations = transformations1
        
        # Now take the training data and align it to the final template
        final_template = template
        
        if reduction:
            # Reduce the dimensionality of the template
            final_template, components = self._reduce_dimensionality(template)
            
        final_aligned, final_transformations, final_disparity, final_scaling = [], [], [], []
        for src in X:
            trans, aligned_ds, disp, s = self._procrustes(src, final_template, scaling=self.scaling, reduction=reduction)
            final_scaling.append(s)
            final_aligned.append(aligned_ds)
            final_transformations.append(trans)
            final_disparity.append(disp)
        if self.verbose: print(f'final average disparity: {np.mean(final_disparity):.4f}')
        
        self.n_iterations = i + 1
        self.transformations = final_transformations
        self.template = final_template
        self.aligned_data = final_aligned    
        self.disparity = final_disparity
        self.scaling_factors=final_scaling
        return self
    
    def _reduce_dimensionality(self, template):
        """
        Apply PCA to transform data into a lower dimensional space, using SVD for numerical stability.

        Parameters
        ----------
        X : ndarray
            Input data matrix of shape (n_samples, n_features)
        Returns
        -------
        X_transformed : ndarray
            Data projected into principal component space, shape (n_samples, n_components)
        components : ndarray
            Principal components (eigenvectors), shape (n_features, n_components)
        """
        
        # Center the data
        if self.verbose:
            print(f'Reducing dimensionality of template')
        template -= np.mean(template, axis=0)
        n_components, n_samples, n_features = self.n_features_target, template.shape[0], template.shape[1]
        # Compute the SVD of the template
        # U: left singular vectors, shape (n_samples, n_samples)
        # s: singular values, shape (min(n_samples, n_features),)
        # Vh: right singular vectors, shape (n_features, n_features)
        U, s, Vh = np.linalg.svd(template, full_matrices=False)
        # Calculate explained variance
        # The singular values are related to eigenvalues of the covariance matrix
        explained_variance = (s ** 2) / (n_samples - 1)
        explained_variance_ratio = explained_variance / explained_variance.sum()
        if self.verbose:
            print(f'running PCA over the template; first {n_components} components explain {np.sum(explained_variance_ratio[:n_components])*100:.4f} percent variance')
        # Get the principal components (eigenvectors)
        # Vh contains the right singular vectors (PCs)
        components = Vh[:n_components].T  # Transpose to get shape (n_features, n_components)
        # Transform the data
        template_transformed = template @ components
        return template_transformed, components
    
    def transform(self, X: Union[np.ndarray, List[np.ndarray]]) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Applies the transformation matrices learned during fitting to new datasets. 
        Assumes that the order of new datasets matches the order of the transformation matrices.
        Parameters
        ----------
        X : list of ndarray
            List of datasets to align.
        
        Returns
        -------
        list of ndarray
            Transformation matrices for each dataset.
        """
        transformations = self.get_transformations()
        if not len(X) == len(transformations):
            raise ValueError(f"Length of new datasets {len(X)} not equal to number of transformations; did you mean to compute a new transformation?")
        
        transformed_data = []
        for x, T in zip(X, transformations):
            # normalize the data
            x = self._normalize_data(x)
            transformed = x @ T
            transformed_data.append(transformed)
        return transformed_data
        
    
    def fit_transform(self, X: List[np.ndarray], y=None) -> List[np.ndarray]:
        """
        Fit the model and transform the training data.
        
        Parameters
        ----------
        X : list of ndarray
            List of datasets to align.
        y : ignored
            Not used, present for API consistency.
            
        Returns
        -------
        list of ndarray
            Aligned versions of the input datasets.
        """
        self.fit(X)
        return self.aligned_data
    
    def get_transformations(self) -> List[np.ndarray]:
        """
        Get the transformation matrices learned during fitting.
        
        Returns
        -------
        list of ndarray
            Transformation matrices for each dataset.
        """
        if not hasattr(self, 'transformations'):
            raise ValueError("Model not fitted yet. Call 'fit' first.")
        return self.transformations
    
    def transform_new_dataset(self, X) -> Tuple:
        """
        Aligns a new dataset, assumed to have the same shape as the training datasets, to the fitted template 
        
        Parameters
        ----------
        X : ndarray
            Dataset to align.
        
        Returns
        -------
        Tuple: (Aligned data, transformation)
        """
        if not X.shape != self.template.shape: 
            raise ValueError(f"Shape of new dataset {X.shape} does not match the template {self.template.shape}")
        
        R, aligned_ds, _, _ = self._procrustes(X, self.template)
        return (aligned_ds, R)
    
    def get_template(self) -> np.ndarray:
        """
        Get the common template space.
        
        Returns
        -------
        ndarray
            Template representing the common space.
        """
        if not hasattr(self, 'template'):
            raise ValueError("Model not fitted yet. Call 'fit' first.")
        return self.template
    
    def _run_isc(self, X: List[np.ndarray]):
        '''
        Intersubject correlation analysis: 
        compares each subject's timeseries with the average of all other subjects' timeseries
        Measure of "synchrony" over time across brains, which should be improved by functional alignment
        '''
        if len(np.shape(X)) == 2:
            X = X[:,:,np.newaxis]
        results = np.zeros((len(X), X[0].shape[-1]))
        for i in range(len(X)):
            test = X[i]
            tr_idx = np.setdiff1d(np.arange(len(X)),i)
            train = np.mean(np.array([X[j] for j in tr_idx]), axis=0)
            # get correlation at each feature
            cmat = cdist(test.T, train.T, 'correlation')
            corrs = [1-cmat[i,i] for i in range(cmat.shape[0])]
            results[i]= corrs
        return results
    
    def evaluate_isc(self):
        '''
        built in function to return ISC scores for the training datasets, pre and post hyperalignment
        '''
        
        original_isc = self._run_isc(self.training_data)
        aligned_isc = self._run_isc(self.aligned_data)
        if self.verbose: 
            print(f"Pre-alignment ISC: {np.mean(original_isc):.4f}\nPost-alignment ISC: {np.mean(aligned_isc):.4f}")
        return {"Pre-alignment":original_isc, "Post-alignment":aligned_isc}
        
