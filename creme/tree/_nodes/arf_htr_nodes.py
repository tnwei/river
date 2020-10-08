from creme.tree._attribute_observer import NominalAttributeRegressionObserver
from creme.tree._attribute_observer import NumericAttributeRegressionObserver
from creme.utils.skmultiflow_utils import check_random_state

from .htr_nodes import LearningNodeMean
from .htr_nodes import LearningNodeModel
from .htr_nodes import LearningNodeAdaptive
from .arf_htc_nodes import RandomActiveLeafClass


class RandomActiveLeafRegressor(RandomActiveLeafClass):
    @staticmethod
    def new_nominal_attribute_observer():
        return NominalAttributeRegressionObserver()

    @staticmethod
    def new_numeric_attribute_observer():
        return NumericAttributeRegressionObserver()

    def manage_memory(self, criterion, last_check_ratio, last_check_sdr, last_check_e):
        """ Trigger Attribute Observers' memory management routines.

        Currently, only `NumericAttributeRegressionObserver` has support to this feature.

        Parameters
        ----------
            criterion: SplitCriterion
                Split criterion
            last_check_ratio: float
                The ratio between the second best candidate's merit and the merit of the best
                split candidate.
            last_check_sdr: float
                The best candidate's split merit.
            last_check_e: float
                Hoeffding bound value calculated in the last split attempt.
        """
        for obs in self.attribute_observers.values():
            if isinstance(obs, NumericAttributeRegressionObserver):
                obs.remove_bad_splits(criterion=criterion, last_check_ratio=last_check_ratio,
                                      last_check_vr=last_check_sdr, last_check_e=last_check_e,
                                      pre_split_dist=self._stats)


class RandomActiveLearningNodeMean(LearningNodeMean, RandomActiveLeafRegressor):
    """ Learning Node for regression tasks that always use the average target
    value as response.

    Parameters
    ----------
    initial_stats
        In regression tasks this dictionary carries the sufficient to perform
        online variance calculation. They refer to the number of observations
        (key '0'), the sum of the target values (key '1'), and the sum of the
        squared target values (key '2').
    depth
        The depth of the node.
    max_features
        Number of attributes per subset for each node split.
    seed
        If int, seed is the seed used by the random number generator;
        If RandomState instance, seed is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.
    """
    def __init__(self, initial_stats, depth, max_features, seed):
        super().__init__(initial_stats, depth)

        self.max_features = max_features
        self.feature_indices = []
        self.seed = seed
        self._rng = check_random_state(self.seed)


class RandomActiveLearningNodeModel(LearningNodeModel, RandomActiveLeafRegressor):
    """ Learning Node for regression tasks that always use a learning model to provide
    responses.

    Parameters
    ----------
    initial_stats
        In regression tasks this dictionary carries the sufficient to perform
        online variance calculation. They refer to the number of observations
        (key '0'), the sum of the target values (key '1'), and the sum of the
        squared target values (key '2').
    depth
        The depth of the node.
    leaf_model
        A river.base.Regressor instance used to learn from instances and provide
        responses.
    max_features
        Number of attributes per subset for each node split.
    seed
        If int, seed is the seed used by the random number generator;
        If RandomState instance, seed is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.
    """
    def __init__(self, initial_stats, depth, leaf_model, max_features, seed):
        super().__init__(initial_stats, depth, leaf_model)
        self.max_features = max_features
        self.seed = seed
        self._rng = check_random_state(self.seed)
        self.feature_indices = []


class RandomActiveLearningNodeAdaptive(LearningNodeAdaptive, RandomActiveLeafRegressor):
    """ Learning Node for regression tasks that dynamically selects between the target mean
    and the output of a learning model to provide responses.

    Parameters
    ----------
    initial_stats
        In regression tasks this dictionary carries the sufficient to perform
        online variance calculation. They refer to the number of observations
        (key '0'), the sum of the target values (key '1'), and the sum of the
        squared target values (key '2').
    depth
        The depth of the node.
    leaf_model
        A river.base.Regressor instance used to learn from instances and provide
        responses.
    max_features
        Number of attributes per subset for each node split.
    seed
        If int, seed is the seed used by the random number generator;
        If RandomState instance, seed is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.
    """
    def __init__(self, initial_stats, depth, leaf_model, max_features, seed):
        super().__init__(initial_stats, depth, leaf_model)
        self.max_features = max_features
        self.seed = seed
        self._rng = check_random_state(self.seed)
        self.feature_indices = []
