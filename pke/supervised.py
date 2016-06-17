# -*- coding: utf-8 -*-

""" Supervised keyphrase extraction models. """

import re
import math
import string
from collections import defaultdict

from .base import LoadFile
from .base import Candidate

import numpy as np

from nltk.corpus import stopwords

import pickle

from sklearn.naive_bayes import MultinomialNB
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import RFE
from sklearn.utils import shuffle
from sklearn.linear_model import LogisticRegression


class Kea(LoadFile):
    """ Kea keyphrase extraction model. """

    def __init__(self, input_file=None, language='english'):
        """ Redefining initializer for Kea. """

        super(Kea, self).__init__(input_file=input_file, language=language)

        self.instances = {}
        """ The instances container. """


    def __str__(self):
        """ Defining string representation. """

        return "Kea"


    def candidate_selection(self):
        """ Select 1-3 grams as keyphrase candidates. Candidates that start or 
            end with a stopword are discarded.
        """

        # select ngrams from 1 to 3 grams
        self.ngram_selection(n=3)

        # filter candidates containing punctuation marks
        self.candidate_filtering(list(string.punctuation) +
                                 ['-lrb-', '-rrb-', '-lcb-', '-rcb-', '-lsb-',
                                  '-rsb-'])

        # initialize the stoplist
        stoplist = stopwords.words(self.language)

        # filter candidates that start or end with a stopword
        for k, v in self.candidates.items():

            # delete if candidate contains a stopword in first/last position
            words = [u.lower() for u in v.surface_forms[0]]
            if words[0] in stoplist or words[-1] in stoplist:
                del self.candidates[k]


    def feature_extraction(self, df=None, N=144, training=False):
        """ Extract features (tf*idf, first occurrence and length) for each 
            candidate.

            Args:
                df (dict): document frequencies.
                N (int): the number of documents for computing IDF, defaults to
                    144 as in the SemEval dataset.
                training (bool): indicates whether features are computed for the
                    training set for computing IDF weights, defaults to false.
        """

        # find the maximum offset
        maximum_offset = float(sum([s.length for s in self.sentences]))

        for k, v in self.candidates.iteritems():

            # get candidate document frequency
            candidate_df = 1 + df.get(k, 0)

            # hack for handling training documents
            if training and candidate_df != 1:
                candidate_df -= 1

            # compute the tf*idf of the candidate
            idf = math.log(float(N+1) / float(candidate_df), 2)

            # add the features to the instance container
            self.instances[k] = np.array([len(v.surface_forms) * idf,
                                 v.offsets[0]/maximum_offset])

        # scale features
        self.feature_scaling()


    def feature_scaling(self):
        """ Scale features to [0,1]. """

        candidates = self.instances.keys()
        X = [self.instances[u] for u in candidates]
        X = MinMaxScaler().fit_transform(X)
        for i, candidate in enumerate(candidates):
            self.instances[candidate] = X[i]


    def classify_candidates(self, model):
        """ Classify the candidates as keyphrase or not keyphrase.

            Args:
                model (str): the path to load the model.
        """

        # load the model
        with open(model, 'rb') as f:
            clf = pickle.load(f)

        # get matrix of instances
        candidates = self.instances.keys()
        X = [self.instances[u] for u in candidates]

        # classify candidates
        y = clf.predict_proba(X)

        for i, candidate in enumerate(candidates):
            self.weights[candidate] = y[i][1]


    @staticmethod
    def train(training_instances, training_classes, model_file):
        """ Train a Naive Bayes classifier and store the model in a file.

            Args:
                training_instances (list): list of features.
                training_classes (list): list of binary values.
                model_file (str): the model output file.
        """

        clf = MultinomialNB()
        clf.fit(training_instances, training_classes)
        with open(model_file, 'wb') as f:
            pickle.dump(clf, f)
       

class WINGNUS(LoadFile):
    """ WINGNUS keyphrase extraction model. """

    def __init__(self, input_file=None, language='english'):
        """ Redefining initializer for WINGNUS. """

        super(WINGNUS, self).__init__(input_file=input_file, language=language)

        self.instances = {}
        """ The instances container. """


    def __str__(self):
        """ Defining string representation. """

        return "WINGNUS"


    def candidate_selection(self,
                            NP='^((JJ|NN) ){,2}NN$',
                            NP_IN_NP='^((JJ|NN) )?NN IN ((JJ|NN) )?NN$'):
        """ Select noun phrases (NP) and NP containing a preprositional phrase
            (NP IN NP) as keyphrase candidates.

            Args:
                NP (str): the pattern for noun phrases, defaults to
                    '^((JJ|NN) ){,2}NN$'.
                simplex_NP (str): the pattern for filtering simplex noun
                    phrases, defaults to '^((JJ|NN) )?NN IN ((JJ|NN) )?NN$'.
        """

        # select ngrams from 1 to 4 grams
        self.ngram_selection(n=4)

        # filter candidates containing punctuation marks
        self.candidate_filtering(stoplist=list(string.punctuation) +
                                 ['-lrb-', '-rrb-', '-lcb-', '-rcb-', '-lsb-',
                                  '-rsb-'])

        # filter non-simplex noun phrases
        for k, v in self.candidates.items():

            # valid surface forms container
            valid_surface_forms = []

            # loop through the surface forms
            for i in range(len(v.pos_patterns)):
                pattern = ' '.join([u[:2] for u in v.pos_patterns[i]])
                if re.search(NP, pattern) or re.search(NP_IN_NP, pattern):
                    valid_surface_forms.append(i)

            # delete candidate if not valid
            if not valid_surface_forms:
                del self.candidates[k]

            # otherwise update the candidate data
            else:
                self.candidates[k].surface_forms = [v.surface_forms[i] for i
                                                    in valid_surface_forms]
                self.candidates[k].offsets = [v.offsets[i] for i
                                              in valid_surface_forms]
                self.candidates[k].pos_patterns = [v.pos_patterns[i] for i
                                                   in valid_surface_forms]


    def feature_extraction(self,
                           df=None,
                           N=144,
                           training=False):
        """ Extract features (tf*idf, first occurrence and length) for each 
            candidate.

            Args:
                df (dict): document frequencies.
                N (int): the number of documents for computing IDF, defaults to
                    144 as in the SemEval dataset.
                training (bool): indicates whether features are computed for the
                    training set for computing IDF weights, defaults to false.
        """

        # find the maximum offset
        maximum_offset = float(sum([s.length for s in self.sentences]))

        for k, v in self.candidates.iteritems():

            # get candidate document frequency
            candidate_df = 1 + df.get(k, 0)

            # hack for handling training documents
            if training and candidate_df != 1:
                candidate_df -= 1

            # compute the tf*idf of the candidate
            idf = math.log(float(N+1) / float(candidate_df), 2)

            # # term frequency of substrings
            # tf_substrings = len(v.lexical_form)
            # stoplist = stopwords.words(self.language)
            # size = len(v.lexical_form)
            # full_string = ' '.join(v.lexical_form)
            # for i in range(size):
            #     for j in range(i, min(size, i+3)):

            #         sub_words = v.lexical_form[i:j+1]
            #         sub_string = ' '.join(sub_words)

                    # skip if substring is fullstring
                    # if sub_string == full_string:
                    #     continue

                    # # skip if substring contains a stopword
                    # if set(sub_words).intersection(stoplist):
                    #     continue
                    
                    # check whether the substring occurs
                    # if self.candidates.has_key(sub_string):
                    #     tf_substrings += len(self.candidates[sub_string].surface_forms)

                        # # loop throught substring offsets
                        # for offset_1 in self.candidates[sub_string].offsets:
                        #     is_included = False
                        #     for offset_2 in v.offsets:
                        #         if offset_1 >= offset_2 and \
                        #            offset_1 <= offset_2 + len(v.lexical_form):
                        #            is_included = True
                        #     if not is_included:
                        #         tf_substrings += 1

            # add the features to the instance container
            self.instances[k] = np.array([len(v.surface_forms) * idf,
                                 v.offsets[0]/maximum_offset,
                                 len(v.lexical_form)])

        # scale features
        self.feature_scaling()


    def feature_scaling(self):
        """ Scale features to [0,1]. """

        candidates = self.instances.keys()
        X = [self.instances[u] for u in candidates]
        X = MinMaxScaler().fit_transform(X)
        for i, candidate in enumerate(candidates):
            self.instances[candidate] = X[i]


    def classify_candidates(self, model):
        """ Classify the candidates as keyphrase or not keyphrase.

            Args:
                model (str): the path to load the model.
        """

        # load the model
        with open(model, 'rb') as f:
            clf = pickle.load(f)

        # get matrix of instances
        candidates = self.instances.keys()
        X = [self.instances[u] for u in candidates]

        # classify candidates
        y = clf.predict_proba(X)

        for i, candidate in enumerate(candidates):
            self.weights[candidate] = y[i][1]


    @staticmethod
    def train(training_instances, training_classes, model_file):
        """ Train a Naive Bayes classifier and store the model in a file.

            Args:
                training_instances (list): list of features.
                training_classes (list): list of binary values.
                model_file (str): the model output file.
        """

        clf = MultinomialNB()
        clf.fit(training_instances, training_classes)
        with open(model_file, 'wb') as f:
            pickle.dump(clf, f)


class SEERLAB(LoadFile):
    """ SEERLAB keyphrase extraction model. """

    def __init__(self, input_file=None, language='english'):
        """ Redefining initializer for SEERLAB. """

        super(SEERLAB, self).__init__(input_file=input_file, language=language)

        self.instances = {}
        """ The instances container. """


    def __str__(self):
        """ Defining string representation. """

        return "SEERLAB"


    def candidate_selection(self,
                            dblp_candidates=None,
                            mf_unigrams=30,
                            mf_non_unigrams=30):
        """ Select keyphrase candidates.

            Args:
                dblp_candidates (list): valid candidates according to the list 
                    of candidates extracted from the dblp titles.
                mf_unigrams (int): the number of most frequent unigrams to 
                    include in the candidates, defaults to 30.
                mf_non_unigrams (int): the number of most frequent non-unigrams
                    to include in the candidates, defaults to 30.
        """

        # select ngrams from 1 to 4 grams
        self.ngram_selection(n=4)

        # filter candidates containing stopwords or punctuation marks
        self.candidate_filtering(stoplist=stopwords.words(self.language) +
                                 list(string.punctuation) +
                                 ['-lrb-', '-rrb-', '-lcb-', '-rcb-', '-lsb-',
                                  '-rsb-'])

        # build the sets of unigrams, non-unigrams and acronyms
        unigrams = list()
        non_unigrams = list()
        acronyms = list()

        # loop through the candidates
        for k, v in self.candidates.items():

            # adding unigram
            if len(v.lexical_form) == 1:
                unigrams.append((len(v.surface_forms), k))

            # adding non unigram
            else:
                non_unigrams.append((len(v.surface_forms), k))

            # adding acronym
            form = ' '.join(v.surface_forms[0])
            if form.isupper() and len(form) > 1:
                acronyms.append(k)

        # first populate valid candidates with acronyms
        valid_candidates = set(acronyms)

        # add the most frequent unigrams
        valid_candidates.update(set([v for u, v in
              sorted(unigrams, reverse=True)[:min(len(unigrams), 
                                                  mf_unigrams)]]))
        # add the most frequent non unigrams
        valid_candidates.update(set([v for u, v in
              sorted(non_unigrams, reverse=True)[:min(len(non_unigrams), 
                                                       mf_non_unigrams)]]))

        # filter candidates according the the most frequent sets
        for k, v in self.candidates.items():
            if k not in valid_candidates:
                del self.candidates[k]

        # loop through sentences to extract candidates occuring in dblp
        for i, sentence in enumerate(self.sentences):

            skip = min(4, sentence.length)
            shift = sum([s.length for s in self.sentences[0:i]])
            j = 0

            while j < sentence.length:
                for k in range(min(j+skip, sentence.length+1), j, -1):

                    surface_form = sentence.words[j:k]
                    norm_form = sentence.stems[j:k]
                    pos_pattern = sentence.pos[j:k]
                    key = ' '.join(norm_form)

                    if key in dblp_candidates and key not in self.candidates:

                        self.candidates[key].surface_forms.append(surface_form)
                        self.candidates[key].lexical_form = norm_form
                        self.candidates[key].offsets.append(shift+j)
                        self.candidates[key].pos_patterns.append(pos_pattern)

                        j = k -1
                        break
                j += 1


    def feature_extraction(self, df=None, N=144, training=False):
        """ Extract features (tf*idf, first occurrence and length) for each 
            candidate.

            Args:
                df (dict): document frequencies.
                N (int): the number of documents for computing IDF, defaults to
                    144 as in the SemEval dataset.
                training (bool): indicates whether features are computed for the
                    training set for computing IDF weights, defaults to false.
        """

        # find the maximum offset
        maximum_offset = float(sum([s.length for s in self.sentences]))

        for k, v in self.candidates.iteritems():

            # get candidate document frequency
            candidate_df = 1 + df.get(k, 0)

            # hack for handling training documents
            if training and candidate_df != 1:
                candidate_df -= 1

            # compute the tf*idf of the candidate
            idf = math.log(float(N+1) / float(candidate_df), 2)

            # test if candidate is an acronym
            is_acronym = 0
            for surface_form in v.surface_forms:
                form = ' '.join(surface_form)
                if form.isupper() and len(form) > 1:
                    is_acronym = 1

            # compute frequency in title (defined as first sentence)
            # max_offset = self.sentences[0].length
            # tf_title = len([u for u in v.offsets if u <= max_offset])

            # add the features to the instance container
            self.instances[k] = np.array([len(v.lexical_form),               # N
                                          is_acronym,                     # ACRO
                                          len(v.surface_forms),         # TF_doc
                                          candidate_df,                     # DF
                                          len(v.surface_forms) * idf])   # TFIDF


        # # scale features
        # self.feature_scaling()


    def classify_candidates(self, model):
        """ Classify the candidates as keyphrase or not keyphrase.

            Args:
                model (str): the path to load the model.
        """

        # load the model
        with open(model, 'rb') as f:
            clf = pickle.load(f)

        # get matrix of instances
        candidates = self.instances.keys()
        X = [self.instances[u] for u in candidates]

        # classify candidates
        y = clf.predict_proba(X)

        for i, candidate in enumerate(candidates):
            self.weights[candidate] = y[i][1]


    def feature_scaling(self):
        """ Scale features to [0,1]. """

        candidates = self.instances.keys()
        X = [self.instances[u] for u in candidates]
        X = MinMaxScaler().fit_transform(X)
        for i, candidate in enumerate(candidates):
            self.instances[candidate] = X[i]


    @staticmethod
    def train(training_instances, training_classes, model_file):
        """ Train a Random Forest classifier and store the model in a file.

            Args:
                training_instances (list): list of features.
                training_classes (list): list of binary values.
                model_file (str): the model output file.
        """

        clf = LogisticRegression()
        # clf = MultinomialNB()
        # clf = RandomForestClassifier(n_estimators=200,
        #                              max_features=3,
        #                              class_weight='balanced')
        # clf = RandomForestClassifier()

        # Down sampling the instances to 1:7

        # decompose instances into positives/negatives
        # positives = []
        # negatives = []
        # for i in range(len(training_instances)):
        #     if training_classes[i] == 1:
        #         positives.append(training_instances[i])
        #     else:
        #         negatives.append(training_instances[i])


        # np.random.shuffle(negatives)

        # training_instances = negatives[:min(len(positives)*7, len(negatives))]
        # training_classes = [0]*len(training_instances)
        # training_instances.extend(positives)
        # training_classes.extend([1]*len(positives))        

        # X, y = shuffle(training_instances, training_classes, random_state=0)

        # fit the data
        clf.fit(training_instances, training_classes)
        # clf.fit(X, y)
        with open(model_file, 'wb') as f:
            pickle.dump(clf, f)

        # print clf.feature_importances_

        # estimator = RandomForestClassifier(n_estimators=200, max_features=3)
        # selector = RFE(estimator, None, step=1)
        # selector = selector.fit(training_instances, training_classes)

        # print selector.support_ 
        # print selector.ranking_

        
class SupTfIdf(LoadFile):
    """ SupTfIdf keyphrase extraction model. """

    def __init__(self, input_file=None, language='english'):
        """ Redefining initializer for SupTfIdf. """

        super(SupTfIdf, self).__init__(input_file=input_file, language=language)

        self.instances = {}
        """ The instances container. """


    def __str__(self):
        """ Defining string representation. """

        return "SupTfIdf"


    def candidate_selection(self):
        """ Select 1-3 grams as keyphrase candidates. Candidates that start or 
            end with a stopword are discarded.
        """

        # select ngrams from 1 to 3 grams
        self.ngram_selection(n=3)

        # filter candidates containing punctuation marks
        self.candidate_filtering(list(string.punctuation) +
                                 ['-lrb-', '-rrb-', '-lcb-', '-rcb-', '-lsb-',
                                  '-rsb-'])


    def feature_extraction(self, df=None, N=144, training=False):
        """ Extract features (tf*idf) for each 
            candidate.

            Args:
                df (dict): document frequencies.
                N (int): the number of documents for computing IDF, defaults to
                    144 as in the SemEval dataset.
                training (bool): indicates whether features are computed for the
                    training set for computing IDF weights, defaults to false.
        """

        # find the maximum offset
        maximum_offset = float(sum([s.length for s in self.sentences]))

        for k, v in self.candidates.iteritems():

            # get candidate document frequency
            candidate_df = 1 + df.get(k, 0)

            # hack for handling training documents
            if training and candidate_df != 1:
                candidate_df -= 1

            # compute the tf*idf of the candidate
            idf = math.log(float(N+1) / float(candidate_df), 2)

            # add the features to the instance container
            self.instances[k] = np.array([len(v.surface_forms) * idf])

        # scale features
        self.feature_scaling()


    def feature_scaling(self):
        """ Scale features to [0,1]. """

        candidates = self.instances.keys()
        X = [self.instances[u] for u in candidates]
        X = MinMaxScaler().fit_transform(X)
        for i, candidate in enumerate(candidates):
            self.instances[candidate] = X[i]


    def classify_candidates(self, model):
        """ Classify the candidates as keyphrase or not keyphrase.

            Args:
                model (str): the path to load the model.
        """

        # load the model
        with open(model, 'rb') as f:
            clf = pickle.load(f)

        # get matrix of instances
        candidates = self.instances.keys()
        X = [self.instances[u] for u in candidates]

        # classify candidates
        y = clf.predict_proba(X)

        for i, candidate in enumerate(candidates):
            self.weights[candidate] = y[i][1]


    @staticmethod
    def train(training_instances, training_classes, model_file):
        """ Train a Naive Bayes classifier and store the model in a file.

            Args:
                training_instances (list): list of features.
                training_classes (list): list of binary values.
                model_file (str): the model output file.
        """

        clf = LogisticRegression()
        clf.fit(training_instances, training_classes)
        with open(model_file, 'wb') as f:
            pickle.dump(clf, f)







