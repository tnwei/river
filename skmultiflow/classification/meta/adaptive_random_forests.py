__author__ = 'Anderson Carlos Ferreira da Silva'

from skmultiflow.core.base_object import BaseObject
from skmultiflow.classification.trees.hoeffding_tree import *
from skmultiflow.classification.core.driftdetection.adwin import ADWIN
from skmultiflow.classification.trees.arf_hoeffding_tree import ARFHoeffdingTree

INSTANCE_WEIGHT = np.array([1.0])
FEATURE_MODE_M = ''
FEATURE_MODE_SQRT = 'sqrt'
FEATURE_MODE_SQRT_INV = 'sqrt_inv'
FEATURE_MODE_PERCENTAGE = 'percentage'


class AdaptiveRandomForest(BaseClassifier):
    """Adaptive Random Forest (ARF).

        Parameters
        ----------
        # TODO

        Notes
        -----
        The 3 most important aspects of Adaptive Random Forest [1]_ are:
        (1) inducing diversity through re-sampling;
        (2) inducing diversity through randomly selecting subsets of features for node splits (see
        skmultiflow.classification.trees.arf_hoeffding_tree);
        (3) drift detectors per base tree, which cause selective resets in response to drifts.
        It also allows training background trees, which start training if a warning is detected and replace the active
        tree if the warning escalates to a drift.

        References
        ----------
        .. [1] Heitor Murilo Gomes, Albert Bifet, Jesse Read, Jean Paul Barddal, Fabricio Enembreck,
           Bernhard Pfharinger, Geoff Holmes, Talel Abdessalem.
           Adaptive random forests for evolving data stream classification.
           In Machine Learning, DOI: 10.1007/s10994-017-5642-8, Springer, 2017.

    """

    def __init__(self,
                 nb_ensemble=10,
                 feature_mode='sqrt',
                 nb_attributes=2,
                 disable_background_learner=False,
                 disable_drift_detection=False,
                 disable_weighted_vote=False,
                 lambda_value=6,
                 evaluator_method=None,
                 drift_detection_method=ADWIN,
                 warning_detection_method=ADWIN,
                 drift_delta=0.001,
                 warning_delta=0.01,
                 nominal_attributes=None):
        """AdaptiveRandomForest class constructor."""
        super().__init__()          
        self.nb_ensemble = nb_ensemble        
        self.feature_mode = feature_mode
        self.total_attributes = nb_attributes
        self.disable_background_learner = disable_background_learner   
        self.disable_drift_detection = disable_drift_detection        
        self.disable_weighted_vote = disable_weighted_vote
        self.lambda_value = lambda_value
        if evaluator_method is None:
            self.evaluator_method = ARFBaseClassifierEvaluator
        self.drift_detection_method = drift_detection_method
        self.warning_detection_method = warning_detection_method
        self.instances_seen = 0
        self._train_weight_seen_by_model = 0.0
        self.nb_attributes = None
        self.ensemble = None
        self.warning_delta = warning_delta
        self.drift_delta = drift_delta
        self.nominal_attributes = nominal_attributes

    def fit(self, X, y, classes=None, weight=None):
        raise NotImplementedError
    
    def partial_fit(self, X, y, classes=None, weight=None):
        if y is not None:
            if weight is None:
                weight = INSTANCE_WEIGHT
            row_cnt, _ = get_dimensions(X)
            wrow_cnt, _ = get_dimensions(weight)
            if row_cnt != wrow_cnt:
                weight = [weight[0]] * row_cnt                
            for i in range(row_cnt):
                if weight[i] != 0.0:
                    self._train_weight_seen_by_model += weight[i]
                    self._partial_fit(X[i], y[i], weight[i])
        
    def _partial_fit(self, X, y, weight):
        self.instances_seen += 1
        
        if self.ensemble is None:
            self.init_ensemble(X)
                      
        for i in range(self.nb_ensemble):
            y_predicted = self.ensemble[i].predict(np.asarray([X]))
            self.ensemble[i].evaluator.update(y_predicted, np.asarray([y]), weight)
            k = np.random.poisson(self.lambda_value)
            if k > 0:
                self.ensemble[i].partial_fit(np.asarray([X]), np.asarray([y]), np.asarray([k]), self.instances_seen)
    
    def predict(self, X):
        """Predicts the label of the X instance(s)
        Parameters
        ----------
        X: numpy.ndarray of shape (n_samples, n_features)
            Samples for which we want to predict the labels.
        Returns
        -------
        list
            Predicted labels for all instances in X.
        """
        r, _ = get_dimensions(X)
        predictions = []
        for i in range(r):
            votes = self.get_votes_for_instance(X[i])
            if votes == {}:
                # Tree is empty, all classes equal, default to zero
                predictions.append(0)
            else:
                predict = []                
                for vote in votes:                                        
                    predict.append(max(vote, key=vote.get))
                y, counts = np.unique(predict, return_counts=True)
                value = np.argmax(counts)                
                predictions.append(y[value])                
        return predictions

    def predict_proba(self, X):
        raise NotImplementedError
        
    def reset(self):        
        """Reset ARF."""
        self.ensemble = None
        self.nb_attributes = 0
        self.instances_seen = 0
        self._train_weight_seen_by_model = 0.0
        self.evaluator_method = ARFBaseClassifierEvaluator
        
    def score(self, X, y):
        raise NotImplementedError
        
    def get_info(self):
        return "NotImplementedError"
        
    def get_votes_for_instance(self, X):
        if self.ensemble is None:
            self.init_ensemble(X)
        combined_votes = []
           
        for i in range(self.nb_ensemble):
            vote = self.ensemble[i].get_votes_for_instance(X)
            if sum(vote) > 0:
                combined_votes.append(vote)
        
        return combined_votes
        
    def init_ensemble(self, X):
        self.ensemble = [None] * self.nb_ensemble
        
        self.nb_attributes = self.total_attributes
        
        # The m (total number of attributes) depends on:
        _, n = get_dimensions(X)
        
        if self.feature_mode == FEATURE_MODE_SQRT:
            self.nb_attributes = int(round(math.sqrt(n)) + 1)            
        elif self.feature_mode == FEATURE_MODE_SQRT_INV:
            self.nb_attributes = n - int(round(math.sqrt(n) + 1))
        elif self.feature_mode == FEATURE_MODE_PERCENTAGE:            
            percent = (100 + self.nb_attributes) / 100.0 if self.nb_attributes < 0 else self.nb_attributes / 100.0
            self.nb_attributes = int(round(n * percent))
            
        # Notice that if the selected feature_mode was FEATURE_MODE_M then nothing is performed,
        # still it is necessary to check (and adjusted) for when a negative value was used.
        
        # m is negative, use size(features) + -m
        if self.nb_attributes < 0:
            self.nb_attributes += n
        # Other sanity checks to avoid runtime errors.
        # m <= 0 (m can be negative if nb_attributes was negative and abs(m) > n), then use m = 1
        if self.nb_attributes <= 0:
            self.nb_attributes = 1
        # m > n, then it should use n
        if self.nb_attributes > n:
            self.nb_attributes = n
                               
        for i in range(self.nb_ensemble):            
            self.ensemble[i] = ARFBaseLearner(i,
                                              ARFHoeffdingTree(nominal_attributes=self.nominal_attributes,
                                                               nb_attributes=self.nb_attributes),
                                              self.instances_seen,
                                              not self.disable_background_learner,
                                              not self.disable_drift_detection,
                                              self.evaluator_method,
                                              self.drift_detection_method,
                                              self.warning_detection_method,
                                              self.drift_delta,
                                              self.warning_delta,
                                              False)            
                    
    @staticmethod
    def is_randomizable():
        return True                  


class ARFBaseLearner(BaseObject):
    """
    Inner class that represents a single tree member of the forest.
    Contains analysis information, such as the numberOfDriftsDetected,
    """
    def __init__(self,
                 index_original,
                 classifier,
                 instances_seen,
                 use_background_learner,
                 use_drift_detector,
                 evaluator_method,
                 drift_detection_method,
                 warning_detection_method,
                 drift_delta,
                 warning_delta,
                 is_background_learner):
        self.index_original = index_original
        self.classifier = classifier 
        self.created_on = instances_seen
        self.use_background_learner = use_background_learner
        self.use_drift_detector = use_drift_detector
        self.is_background_learner = is_background_learner
        self.evaluator_method = evaluator_method

        # Drift and warning
        self.drift_detection_method = drift_detection_method
        self.warning_detection_method = warning_detection_method
        self.drift_delta = drift_delta
        self.warning_delta = warning_delta

        self.last_drift_on = 0
        self.last_warning_on = 0
        self.nb_drifts_detected = 0
        self.nb_warnings_detected = 0            

        self.drift_detection = None
        self.warning_detection = None
        self.background_learner = None
        
        self.evaluator = evaluator_method()

        # Initialize drift and warning detectors
        if use_drift_detector:
            self.drift_detection = drift_detection_method(self.drift_delta)

        if use_background_learner:
            self.warning_detection = warning_detection_method(self.warning_delta)
            
    def reset(self, instances_seen):
        if self.use_background_learner and self.background_learner is not None:
            self.classifier = self.background_learner.classifier
            self.warning_detection = self.background_learner.warning_detection
            self.drift_detection = self.background_learner.drift_detection
            self.evaluator_method = self.background_learner.evaluator_method
            self.created_on = self.background_learner.created_on                
            self.background_learner = None
        else:
            self.classifier.reset()
            self.created_on = instances_seen
            self.drift_detection = self.drift_detection_method(self.drift_delta)
        self.evaluator = self.evaluator_method()

    def partial_fit(self, X, y, weight, instances_seen):
        self.classifier.partial_fit(X, y, weight)

        if self.background_learner:
            self.background_learner.classifier.partial_fit(X, y, INSTANCE_WEIGHT)

        if self.use_drift_detector and not self.is_background_learner:
            correctly_classifies = self.classifier.predict(X) == y
            # Check for warning only if use_background_learner is active
            if self.use_background_learner:
                self.warning_detection.add_element(int(not correctly_classifies))
                # Check if there was a change
                if self.warning_detection.detected_change():
                    self.last_warning_on = instances_seen
                    self.nb_warnings_detected += 1
                    # Create a new background tree classifier
                    background_learner = self.classifier.copy()
                    background_learner.reset() 
                    # Create a new background learner object
                    self.background_learner = ARFBaseLearner(self.index_original, background_learner, instances_seen,
                                                             self.use_background_learner, self.use_drift_detector,
                                                             self.evaluator_method, self.drift_detection_method,
                                                             self.warning_detection_method,
                                                             self.drift_delta, self.warning_delta,
                                                             True)
                    """Update the warning detection object for the current object 
                    (this effectively resets changes made to the object while it was still a bkg learner). 
                    """
                    self.warning_detection = self.warning_detection_method(self.warning_delta)

        # Update the drift detection
        self.drift_detection.add_element(int(not correctly_classifies))

        # Check if there was a change
        if self.drift_detection.detected_change():
            self.last_drift_on = instances_seen
            self.nb_drifts_detected += 1
            self.reset(instances_seen)

    def predict(self, X):
        return self.classifier.predict(X)
    
    def get_votes_for_instance(self, X):
        return self.classifier.get_votes_for_instance(X)

    def get_class_type(self):
        raise NotImplementedError

    def get_info(self):
        return "NotImplementedError"


class ARFBaseClassifierEvaluator(BaseObject):
    """Basic Classification Performance Evaluator
    TODO replace with skmultiflow evaluator
    """
    
    def __init__(self):
        self.aggregation = 0
        self.length = 0
        
    def update(self, y_predicted, y, weight):
        if weight > 0: 
            self.aggregation += weight if y_predicted == y else 0

    def get_performance(self):
        return self.aggregation * 100
    
    def reset(self):
        self.aggregation = 0
        self.length = 0
    
    def get_class_type(self):
        raise NotImplementedError

    def get_info(self):
        return NotImplementedError
