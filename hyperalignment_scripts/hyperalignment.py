import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from typing import List, Tuple, Optional, Union
from scipy.spatial.distance import cdist

class Hyperalignment(BaseEstimator, TransformerMixin):
    """
    Hyperalignment transformer that follows scikit-learn's API conventions.
    
    Parameters
    ----------
    n_iterations : int, default=10
        Maximum number of iterations for hyperalignment optimization.
    
    scaling : bool, default=True
        Whether to apply scaling during Procrustes transformations.
    
    convergence_threshold : float, default=0.1
        Early stopping threshold for mean disparity between aligned datasets.
    
    verbose : bool, default=False
        If True, print progress during iterations.
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
        X -= np.mean(X, axis=0)
        norm = np.linalg.norm(X)
        if norm == 0: 
            raise ValueError("input matrix must have >1 unique points")
        if self.center_only:
            return X
        return  X / norm
    
    def _disparity(self, M1: np.ndarray, M2: np.ndarray) -> float:
        return np.sum(np.square(M1 - M2))
    
    def _procrustes(self, source: np.ndarray, target: np.ndarray, 
                   reduction: bool = False, scaling: Optional[bool] = None) -> Tuple:
        if scaling is None: scaling = self.scaling
            
        n_features_source = source.shape[-1]
        n_features_target = target.shape[-1]
        
        target_norm = self._normalize_data(target)
        source_norm = self._normalize_data(source)
        scale = 1.0
        
        if n_features_source > n_features_target:
            reduction = True
            temp = np.zeros_like(source)
            temp[:, :n_features_target] = target_norm
            target_norm = temp
        
        U, s, vt = np.linalg.svd((target_norm.T @ np.conjugate(source_norm)).T)
        R = U @ vt
        if reduction:
            R = R[:n_features_source, :n_features_target]
            target_norm = target_norm[:,:n_features_target]
            s=s[:n_features_target]
            
        if scaling:
            scale = s.sum()
        
        R *= scale
        new_source = source_norm @ R
        
        if np.isinf(np.linalg.norm(new_source)):
            return
        
        disp = self._disparity(target_norm, new_source)
        return R, new_source, disp, scale
    
    def _create_initial_template(self) -> np.ndarray:
        for i, x in enumerate(self.training_data):
            if i == 0:
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
        new_template = np.zeros_like(template_prev)
        for x in datasets:
            _, aligned, _, _ = self._procrustes(template_prev, x)
            new_template += aligned
        new_template /= len(datasets)
        return new_template
    
    def fit(self, X: List[np.ndarray], y=None) -> 'Hyperalignment':
        if not (isinstance(X, np.ndarray) and X.ndim == 3 or isinstance(X, list)):
            raise ValueError("Input should be a 3D array or list of 2D arrays")
        
        if len(X) < 2:
            raise ValueError("At least two datasets are required for hyperalignment")
        
        self.n_features_in = X[0].shape[1]
        self.training_data = X
        reduction = False
        if self.n_features_target == 0: 
            self.n_features_target = self.n_features_in
           
        if self.n_features_target < self.n_features_in:
            reduction = True
            
        if not all(x.shape[1] == self.n_features_in for x in X):
            raise ValueError("All datasets must have the same number of features")
        
        template = self._create_initial_template()
        if template.ndim == 1:
            if self.verbose: print("Normalizing data...")
            self.center_only = False
            template = self._create_initial_template()

        aligned = X.copy()
        transformations = None
        
        for i in range(self.n_iterations):
            template = self._create_level2_template(aligned, template)
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
        
        final_template = template
        
        if reduction:
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
        if self.verbose:
            print('Reducing dimensionality of template')
        template -= np.mean(template, axis=0)
        n_components, n_samples, n_features = self.n_features_target, template.shape[0], template.shape[1]
        U, s, Vh = np.linalg.svd(template, full_matrices=False)
        explained_variance = (s ** 2) / (n_samples - 1)
        explained_variance_ratio = explained_variance / explained_variance.sum()
        if self.verbose:
            print(f'running PCA over the template; first {n_components} components explain {np.sum(explained_variance_ratio[:n_components])*100:.4f} percent variance')
        components = Vh[:n_components].T
        template_transformed = template @ components
        return template_transformed, components
    
    def transform(self, X: Union[np.ndarray, List[np.ndarray]]) -> Union[np.ndarray, List[np.ndarray]]:
        transformations = self.get_transformations()
        if not len(X) == len(transformations):
            raise ValueError(f"Length of new datasets {len(X)} not equal to number of transformations")
        
        transformed_data = []
        for x, T in zip(X, transformations):
            x = self._normalize_data(x)
            transformed = x @ T
            transformed_data.append(transformed)
        return transformed_data
        
    def fit_transform(self, X: List[np.ndarray], y=None) -> List[np.ndarray]:
        self.fit(X)
        return self.aligned_data
    
    def get_transformations(self) -> List[np.ndarray]:
        if not hasattr(self, 'transformations'):
            raise ValueError("Model not fitted yet. Call 'fit' first.")
        return self.transformations
    
    def transform_new_dataset(self, X) -> Tuple:
        if not X.shape != self.template.shape: 
            raise ValueError(f"Shape of new dataset {X.shape} does not match the template {self.template.shape}")
        R, aligned_ds, _, _ = self._procrustes(X, self.template)
        return (aligned_ds, R)
    
    def get_template(self) -> np.ndarray:
        if not hasattr(self, 'template'):
            raise ValueError("Model not fitted yet. Call 'fit' first.")
        return self.template
    
    def _run_isc(self, X: List[np.ndarray]):
        if len(np.shape(X)) == 2:
            X = X[:,:,np.newaxis]
        results = np.zeros((len(X), X[0].shape[-1]))
        for i in range(len(X)):
            test = X[i]
            tr_idx = np.setdiff1d(np.arange(len(X)),i)
            train = np.mean(np.array([X[j] for j in tr_idx]), axis=0)
            cmat = cdist(test.T, train.T, 'correlation')
            corrs = [1-cmat[i,i] for i in range(cmat.shape[0])]
            results[i]= corrs
        return results
    
    def evaluate_isc(self):
        original_isc = self._run_isc(self.training_data)
        aligned_isc = self._run_isc(self.aligned_data)
        if self.verbose: 
            print(f"Pre-alignment ISC: {np.mean(original_isc):.4f}\nPost-alignment ISC: {np.mean(aligned_isc):.4f}")
        return {"Pre-alignment":original_isc, "Post-alignment":aligned_isc}
